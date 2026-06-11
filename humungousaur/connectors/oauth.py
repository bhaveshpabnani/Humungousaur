from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import ssl
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import HTTPSHandler, Request, build_opener, urlopen

try:
    import certifi
except ImportError:  # pragma: no cover - optional runtime hardening dependency.
    certifi = None

from humungousaur.config import AgentConfig

from .models import (
    ConnectorClientConfig,
    ConnectorOAuthState,
    ConnectorProviderManifest,
    ConnectorTokenStatus,
    DEFAULT_REDIRECT_URI,
    redact_secret,
)
from .registry import ConnectorRegistry, DEFAULT_CONNECTOR_REGISTRY
from .store import ConnectorStore
from .vault import ConnectorVault, LocalFileConnectorVault


class ConnectorOAuthService:
    def __init__(
        self,
        config: AgentConfig,
        *,
        registry: ConnectorRegistry = DEFAULT_CONNECTOR_REGISTRY,
        store: ConnectorStore | None = None,
        vault: ConnectorVault | None = None,
    ) -> None:
        self.config = config.normalized()
        self.registry = registry
        self.store = store or ConnectorStore.for_config(self.config)
        self.vault = vault or LocalFileConnectorVault.for_config(self.config)
        self.migrate_legacy_json()

    def configure_client(
        self,
        provider_id: str,
        *,
        client_id: str,
        client_secret: str = "",
        redirect_uri: str = DEFAULT_REDIRECT_URI,
    ) -> dict[str, Any]:
        self.registry.provider(provider_id)
        clean_client_id = " ".join(str(client_id or "").split())
        if not clean_client_id:
            raise ValueError("client_id is required.")
        secret_ref = ""
        if str(client_secret or "").strip():
            secret_ref = self._secret_ref(provider_id, "client_secret")
            self.vault.set_secret(secret_ref, str(client_secret or "").strip())
        else:
            existing = self.store.get_client(provider_id)
            secret_ref = existing.client_secret_ref if existing else ""
        client = ConnectorClientConfig(
            provider_id=provider_id,
            client_id=clean_client_id,
            client_secret_ref=secret_ref,
            redirect_uri=str(redirect_uri or DEFAULT_REDIRECT_URI).strip() or DEFAULT_REDIRECT_URI,
            updated_at=_now_iso(),
        )
        self.store.save_client(client)
        return {"provider_id": provider_id, "configured": True, **client.public_record()}

    def prepare_authorization(
        self,
        provider_id: str,
        *,
        scopes: list[str] | None = None,
        redirect_uri: str = "",
    ) -> dict[str, Any]:
        provider = self.registry.provider(provider_id)
        if provider.auth_type != "oauth2_authorization_code":
            raise ValueError(f"{provider.display_name} uses {provider.auth_type} setup, not an OAuth authorization-code connect flow.")
        state = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(48)
        requested_scopes = tuple(str(item).strip() for item in (scopes or list(provider.default_scopes)) if str(item).strip())
        broker_url = _managed_oauth_broker_url()
        stored_client = self.store.get_client(provider_id)
        if broker_url and stored_client is None:
            callback_uri = str(redirect_uri or DEFAULT_REDIRECT_URI).strip() or DEFAULT_REDIRECT_URI
            oauth_state = ConnectorOAuthState(
                state=state,
                provider_id=provider_id,
                code_verifier=_BROKER_STATE_MARKER,
                redirect_uri=callback_uri,
                scopes=requested_scopes,
                created_at=_now_iso(),
                created_at_epoch=time.time(),
            )
            self.store.save_state(oauth_state)
            params = {
                "provider_id": provider_id,
                "redirect_uri": callback_uri,
                "state": state,
                "scope": " ".join(requested_scopes),
            }
            return {
                "provider_id": provider_id,
                "display_name": provider.display_name,
                "authorization_url": f"{broker_url}{_managed_oauth_start_path()}?{urlencode(params)}",
                "state": state,
                "redirect_uri": callback_uri,
                "scopes": list(requested_scopes),
                "uses_pkce": False,
                "uses_broker": True,
            }

        client = self.client_config(provider_id)
        client_secret = self.vault.get_secret(client.client_secret_ref) or ""
        use_pkce = provider.supports_pkce and not client_secret
        callback_uri = str(redirect_uri or client.redirect_uri or DEFAULT_REDIRECT_URI).strip() or DEFAULT_REDIRECT_URI
        oauth_state = ConnectorOAuthState(
            state=state,
            provider_id=provider_id,
            code_verifier=code_verifier if use_pkce else "",
            redirect_uri=callback_uri,
            scopes=requested_scopes,
            created_at=_now_iso(),
            created_at_epoch=time.time(),
        )
        self.store.save_state(oauth_state)
        params: dict[str, str] = {
            "client_id": client.client_id,
            "redirect_uri": callback_uri,
            "response_type": "code",
            "scope": " ".join(requested_scopes),
            "state": state,
        }
        params.update(_authorization_extras(provider.provider_id))
        if use_pkce:
            params["code_challenge"] = _pkce_challenge(code_verifier)
            params["code_challenge_method"] = "S256"
        return {
            "provider_id": provider_id,
            "display_name": provider.display_name,
            "authorization_url": f"{provider.auth_url}?{urlencode(params)}",
            "state": state,
            "redirect_uri": callback_uri,
            "scopes": list(requested_scopes),
            "uses_pkce": use_pkce,
            "uses_broker": False,
        }

    def complete_authorization(self, *, state: str, code: str) -> dict[str, Any]:
        record = self.store.pop_state(str(state or ""))
        if record is None:
            raise ValueError("OAuth state is unknown or expired.")
        provider = self.registry.provider(record.provider_id)
        if provider.auth_type != "oauth2_authorization_code":
            raise ValueError(f"{provider.display_name} does not use OAuth authorization-code token exchange.")
        if record.code_verifier == _BROKER_STATE_MARKER:
            broker_url = _managed_oauth_broker_url()
            if not broker_url:
                raise ValueError(f"{provider.display_name} OAuth broker is not configured.")
            response = _post_json(
                f"{broker_url}{_managed_oauth_token_path()}",
                {
                    "provider_id": record.provider_id,
                    "code": str(code or "").strip(),
                    "state": record.state,
                    "redirect_uri": record.redirect_uri,
                },
            )
            if response.get("ok") is False or response.get("success") is False:
                raise ValueError(str(response.get("error") or "OAuth broker token exchange failed."))
            token = self._save_token_from_response(provider, response, scopes=record.scopes)
            return {"display_name": provider.display_name, **token.public_record(), "uses_broker": True}
        client = self.client_config(record.provider_id)
        payload: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": str(code or "").strip(),
            "redirect_uri": record.redirect_uri,
            "client_id": client.client_id,
        }
        client_secret = self.vault.get_secret(client.client_secret_ref) or ""
        if client_secret:
            payload["client_secret"] = client_secret
        if record.code_verifier:
            payload["code_verifier"] = record.code_verifier
        response = _post_form(provider.token_url, payload)
        if response.get("ok") is False:
            raise ValueError(str(response.get("error") or "OAuth token exchange failed."))
        token = self._save_token_from_response(provider, response, scopes=record.scopes)
        return {"display_name": provider.display_name, **token.public_record()}

    def refresh_token(self, provider_id: str) -> dict[str, Any]:
        provider = self.registry.provider(provider_id)
        if provider.auth_type != "oauth2_authorization_code":
            raise ValueError(f"{provider.display_name} uses {provider.auth_type} setup, not OAuth refresh tokens.")
        client = self.client_config(provider_id)
        existing = self.store.get_token(provider_id)
        refresh_token = self.vault.get_secret(existing.refresh_token_ref) if existing else None
        if not refresh_token:
            raise ValueError(f"{provider.display_name} does not have a stored refresh token.")
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client.client_id,
        }
        client_secret = self.vault.get_secret(client.client_secret_ref) or ""
        if client_secret:
            payload["client_secret"] = client_secret
        response = _post_form(provider.token_url, payload)
        if response.get("ok") is False:
            raise ValueError(str(response.get("error") or "OAuth refresh failed."))
        token = self._save_token_from_response(provider, response, scopes=existing.scopes if existing else ())
        if existing and not response.get("refresh_token"):
            token = ConnectorTokenStatus(
                provider_id=token.provider_id,
                connected=token.connected,
                access_token_ref=token.access_token_ref,
                refresh_token_ref=existing.refresh_token_ref,
                bot_access_token_ref=token.bot_access_token_ref,
                token_type=token.token_type,
                scopes=token.scopes,
                connected_at=token.connected_at,
                expires_at=token.expires_at,
            )
            self.store.save_token(token)
        return {"display_name": provider.display_name, **token.public_record()}

    def disconnect(self, provider_id: str) -> dict[str, Any]:
        provider = self.registry.provider(provider_id)
        existing = self.store.delete_token(provider_id)
        if existing:
            for secret_ref in (existing.access_token_ref, existing.refresh_token_ref, existing.bot_access_token_ref):
                self.vault.delete_secret(secret_ref)
        removed_client = None
        if provider.auth_type != "oauth2_authorization_code":
            removed_client = self.store.delete_client(provider_id)
            if removed_client and removed_client.client_secret_ref:
                self.vault.delete_secret(removed_client.client_secret_ref)
        return {
            "provider_id": provider_id,
            "display_name": provider.display_name,
            "connected": False,
            "removed": bool(existing or removed_client),
        }

    def client_config(self, provider_id: str) -> ConnectorClientConfig:
        client = self.store.get_client(provider_id)
        if client is None:
            client = self._client_config_from_env(provider_id)
        if client is None or not client.client_id:
            display_name = self.registry.provider(provider_id).display_name
            env_prefix = provider_id.upper().replace("-", "_")
            raise ValueError(
                f"{display_name} managed OAuth is not configured for this build. "
                "Production builds should provide a product-owned OAuth client or broker so users can connect with one click. "
                f"For self-hosted development only, set HUMUNGOUSAUR_{env_prefix}_CLIENT_ID or save an advanced OAuth client before starting sign-in."
            )
        return client

    def token_status(self, provider_id: str) -> ConnectorTokenStatus | None:
        return self.store.get_token(provider_id)

    def token_value(self, provider_id: str, key: str = "access_token") -> str | None:
        token = self.store.get_token(provider_id)
        if token is None:
            return None
        ref_by_key = {
            "access_token": token.access_token_ref,
            "refresh_token": token.refresh_token_ref,
            "bot_access_token": token.bot_access_token_ref,
        }
        return self.vault.get_secret(ref_by_key.get(key, ""))

    def public_token_statuses(self) -> dict[str, ConnectorTokenStatus]:
        return self.store.list_tokens()

    def public_client_configs(self) -> dict[str, ConnectorClientConfig]:
        self.sync_env_client_configs()
        return self.store.list_clients()

    def managed_oauth_available(self, provider_id: str) -> bool:
        provider = self.registry.provider(provider_id)
        if provider.auth_type != "oauth2_authorization_code":
            return False
        return bool(_managed_oauth_broker_url() or _env_client_id(provider_id))

    def sync_env_client_configs(self) -> None:
        for provider in self.registry.providers():
            if provider.auth_type == "oauth2_authorization_code" and self.store.get_client(provider.provider_id) is None:
                self._client_config_from_env(provider.provider_id)

    def migrate_legacy_json(self) -> None:
        clients_path = self.config.data_dir / "connectors" / "oauth_clients.json"
        tokens_path = self.config.data_dir / "connectors" / "oauth_tokens.json"
        for provider_id, payload in _load_legacy_json(clients_path).items():
            if self.store.get_client(provider_id) or not isinstance(payload, dict):
                continue
            client_id = str(payload.get("client_id") or "").strip()
            if not client_id:
                continue
            secret = str(payload.get("client_secret") or "").strip()
            secret_ref = ""
            if secret:
                secret_ref = self._secret_ref(provider_id, "client_secret")
                self.vault.set_secret(secret_ref, secret)
            self.store.save_client(
                ConnectorClientConfig(
                    provider_id=provider_id,
                    client_id=client_id,
                    client_secret_ref=secret_ref,
                    redirect_uri=str(payload.get("redirect_uri") or DEFAULT_REDIRECT_URI),
                    updated_at=str(payload.get("updated_at") or _now_iso()),
                )
            )
        for provider_id, payload in _load_legacy_json(tokens_path).items():
            if self.store.get_token(provider_id) or not isinstance(payload, dict):
                continue
            self._save_token_from_response(
                self.registry.provider(provider_id),
                payload,
                scopes=payload.get("scopes") or payload.get("scope") or [],
                connected_at=str(payload.get("connected_at") or _now_iso()),
                expires_at=int(payload.get("expires_at") or 0),
            )

    def _save_token_from_response(
        self,
        provider: ConnectorProviderManifest,
        token: dict[str, Any],
        *,
        scopes: Any = None,
        connected_at: str | None = None,
        expires_at: int | None = None,
    ) -> ConnectorTokenStatus:
        provider_id = provider.provider_id
        access_token = str(token.get("access_token") or token.get("authed_user", {}).get("access_token") or "")
        refresh_token = str(token.get("refresh_token") or "")
        bot_access_token = str(token.get("bot_access_token") or "")
        if token.get("bot_user_id") and access_token and provider_id == "slack":
            bot_access_token = access_token
        access_ref = self._secret_ref(provider_id, "access_token") if access_token else ""
        refresh_ref = self._secret_ref(provider_id, "refresh_token") if refresh_token else ""
        bot_ref = self._secret_ref(provider_id, "bot_access_token") if bot_access_token else ""
        if access_token:
            self.vault.set_secret(access_ref, access_token)
        if refresh_token:
            self.vault.set_secret(refresh_ref, refresh_token)
        if bot_access_token:
            self.vault.set_secret(bot_ref, bot_access_token)
        expires_in = int(token.get("expires_in") or 0)
        scope_list = _scope_list(token.get("scope") or scopes or [])
        status = ConnectorTokenStatus(
            provider_id=provider_id,
            connected=bool(access_ref or bot_ref),
            access_token_ref=access_ref,
            refresh_token_ref=refresh_ref,
            bot_access_token_ref=bot_ref,
            token_type=str(token.get("token_type") or ""),
            scopes=tuple(scope_list),
            connected_at=connected_at or _now_iso(),
            expires_at=int(expires_at if expires_at is not None else (int(time.time()) + expires_in if expires_in else 0)),
        )
        self.store.save_token(status, metadata={"token_keys": sorted(str(key) for key in token.keys())})
        return status

    def _secret_ref(self, provider_id: str, key: str) -> str:
        return f"connector:{provider_id}:{key}"

    def _client_config_from_env(self, provider_id: str) -> ConnectorClientConfig | None:
        env_prefix = provider_id.upper().replace("-", "_")
        env_client_id = _env_client_id(provider_id)
        if not env_client_id:
            return None
        env_client_secret = str(os.environ.get(f"HUMUNGOUSAUR_{env_prefix}_CLIENT_SECRET") or "").strip()
        secret_ref = ""
        if env_client_secret:
            secret_ref = self._secret_ref(provider_id, "client_secret")
            self.vault.set_secret(secret_ref, env_client_secret)
        client = ConnectorClientConfig(
            provider_id=provider_id,
            client_id=env_client_id,
            client_secret_ref=secret_ref,
            redirect_uri=DEFAULT_REDIRECT_URI,
            updated_at=_now_iso(),
        )
        self.store.save_client(client)
        return client


def _env_client_id(provider_id: str) -> str:
    env_prefix = provider_id.upper().replace("-", "_")
    return str(os.environ.get(f"HUMUNGOUSAUR_{env_prefix}_CLIENT_ID") or "").strip()


def _managed_oauth_broker_url() -> str:
    return str(os.environ.get("HUMUNGOUSAUR_CONNECTOR_OAUTH_BROKER_URL") or "").strip().rstrip("/")


def _managed_oauth_start_path() -> str:
    path = str(os.environ.get("HUMUNGOUSAUR_CONNECTOR_OAUTH_START_PATH") or "/connectors/oauth/start").strip()
    return path if path.startswith("/") else f"/{path}"


def _managed_oauth_token_path() -> str:
    path = str(os.environ.get("HUMUNGOUSAUR_CONNECTOR_OAUTH_TOKEN_PATH") or "/connectors/oauth/token").strip()
    return path if path.startswith("/") else f"/{path}"


_BROKER_STATE_MARKER = "__humungousaur_oauth_broker__"


def _post_form(url: str, payload: dict[str, str]) -> dict[str, Any]:
    body = urlencode(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with _open_connector_url(request, timeout=30) as response:
        data = response.read().decode("utf-8")
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ValueError("OAuth provider returned a non-JSON token response.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("OAuth provider returned an invalid token response.")
    return parsed


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    with _open_connector_url(request, timeout=30) as response:
        data = response.read().decode("utf-8")
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ValueError("OAuth broker returned a non-JSON token response.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("OAuth broker returned an invalid token response.")
    return parsed


def _connector_ssl_context() -> ssl.SSLContext:
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def _open_connector_url(request: Request, *, timeout: float):
    if str(request.full_url).startswith("https://"):
        opener = build_opener(HTTPSHandler(context=_connector_ssl_context()))
        return opener.open(request, timeout=timeout)
    return urlopen(request, timeout=timeout)


def _authorization_extras(provider_id: str) -> dict[str, str]:
    if provider_id == "google_workspace":
        return {"access_type": "offline", "prompt": "consent"}
    return {}


def _scope_list(scope_value: Any) -> list[str]:
    if isinstance(scope_value, str):
        return [item for item in scope_value.split() if item]
    if isinstance(scope_value, list) or isinstance(scope_value, tuple):
        return [str(item) for item in scope_value if str(item).strip()]
    return []


def _load_legacy_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


__all__ = ["ConnectorOAuthService", "redact_secret"]
