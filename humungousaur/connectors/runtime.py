from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from .http import ConnectorHttpClient
from .models import ConnectorOperationRequest, DEFAULT_REDIRECT_URI
from .oauth import ConnectorOAuthService
from .policy import ConnectorPolicy
from .registry import ConnectorRegistry, DEFAULT_CONNECTOR_REGISTRY
from .store import ConnectorStore
from .vault import ConnectorVault, LocalFileConnectorVault


class ConnectorRuntime:
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
        self.oauth = ConnectorOAuthService(self.config, registry=self.registry, store=self.store, vault=self.vault)
        self.policy = ConnectorPolicy()
        self.http = ConnectorHttpClient(self.oauth)

    def catalog(self) -> dict[str, Any]:
        clients = self.oauth.public_client_configs()
        tokens = self.oauth.public_token_statuses()
        providers = []
        for provider in self.registry.providers():
            client = clients.get(provider.provider_id)
            token = tokens.get(provider.provider_id)
            configured = bool(client and client.client_id)
            uses_oauth = provider.auth_type == "oauth2_authorization_code"
            managed_oauth_available = self.oauth.managed_oauth_available(provider.provider_id)
            connected = _provider_connected(provider, client, token)
            providers.append(
                {
                    **provider.to_record(),
                    "configured": configured,
                    "managed_oauth_available": managed_oauth_available,
                    "advanced_client_configured": bool(uses_oauth and configured and not managed_oauth_available),
                    "client_id": client.public_record()["client_id"] if client else "",
                    "connected": connected,
                    "connected_at": token.connected_at if token else "",
                    "expires_at": token.expires_at if token else 0,
                    "has_refresh_token": bool(token and token.has_refresh_token),
                    "connection_ready": connected,
                    "collector_ready": connected,
                    "tool_ready": connected,
                }
            )
        return {"providers": providers, "provider_count": len(providers), "redirect_uri": DEFAULT_REDIRECT_URI}

    def status(self, provider_id: str | None = None) -> dict[str, Any]:
        providers = self.catalog()["providers"]
        if provider_id:
            providers = [provider for provider in providers if provider["provider_id"] == provider_id]
            if not providers:
                raise KeyError(f"Unknown connector provider: {provider_id}")
        return {
            "connectors": [
                {
                    "provider_id": provider["provider_id"],
                    "display_name": provider["display_name"],
                    "category": provider["category"],
                    "auth_type": provider["auth_type"],
                    "credential_fields": provider["credential_fields"],
                    "oauth_management": provider["oauth_management"],
                    "managed_oauth_available": provider["managed_oauth_available"],
                    "advanced_client_config": provider["advanced_client_config"],
                    "advanced_client_configured": provider["advanced_client_configured"],
                    "icon": provider["icon"],
                    "brand_color": provider["brand_color"],
                    "logo_asset": provider["logo_asset"],
                    "configured": provider["configured"],
                    "connected": provider["connected"],
                    "connected_at": provider["connected_at"],
                    "expires_at": provider["expires_at"],
                    "has_refresh_token": provider["has_refresh_token"],
                    "workspace_apps": provider["workspace_apps"],
                    "tool_hints": provider["tool_hints"],
                    "connection_ready": provider["connection_ready"],
                    "collector_ready": provider["collector_ready"],
                    "tool_ready": provider["tool_ready"],
                }
                for provider in providers
            ],
            "connector_count": len(providers),
        }

    def configure_client(self, provider_id: str, *, client_id: str, client_secret: str = "", redirect_uri: str = DEFAULT_REDIRECT_URI) -> dict[str, Any]:
        return self.oauth.configure_client(
            provider_id,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )

    def prepare_authorization(self, provider_id: str, *, scopes: list[str] | None = None, redirect_uri: str = "") -> dict[str, Any]:
        return self.oauth.prepare_authorization(provider_id, scopes=scopes, redirect_uri=redirect_uri)

    def complete_authorization(self, *, state: str, code: str) -> dict[str, Any]:
        return self.oauth.complete_authorization(state=state, code=code)

    def refresh_token(self, provider_id: str) -> dict[str, Any]:
        return self.oauth.refresh_token(provider_id)

    def disconnect(self, provider_id: str) -> dict[str, Any]:
        return self.oauth.disconnect(provider_id)

    def readiness(self, provider_id: str) -> dict[str, Any]:
        provider = self.registry.provider(provider_id)
        token = self.oauth.token_status(provider_id)
        client = self.oauth.public_client_configs().get(provider_id)
        connected = _provider_connected(provider, client, token)
        return {
            "provider_id": provider_id,
            "display_name": provider.display_name,
            "auth_type": provider.auth_type,
            "credential_fields": list(provider.credential_fields),
            "oauth_management": provider.oauth_management,
            "managed_oauth_available": self.oauth.managed_oauth_available(provider_id),
            "advanced_client_config": provider.advanced_client_config,
            "configured": bool(client and client.client_id),
            "connected": connected,
            "connection_ready": connected,
            "tool_ready": connected,
            "collector_ready": connected,
            "scopes": list(token.scopes) if token else [],
            "expires_at": token.expires_at if token else 0,
        }

    def secret_value(self, provider_id: str, key: str = "access_token") -> str | None:
        if key in {"client_secret", "credential", "api_key", "bot_token", "access_token_credential"}:
            client = self.oauth.public_client_configs().get(provider_id)
            if client and client.client_secret_ref:
                return self.vault.get_secret(client.client_secret_ref)
        return self.oauth.token_value(provider_id, key)

    def execute_operation(self, request: ConnectorOperationRequest) -> dict[str, Any]:
        token = self.oauth.token_status(request.provider_id)
        self.policy.check_scopes(request, token)
        result = self.http.request(request)
        self.store.audit_operation(
            request.provider_id,
            request.operation,
            status="succeeded",
            created_at=_now_iso(),
            metadata={"method": request.method, "path": request.path, "reason_redacted": bool(request.reason)},
        )
        return result


def _now_iso() -> str:
    import time

    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _provider_connected(provider: Any, client: Any, token: Any) -> bool:
    if str(getattr(provider, "auth_type", "")) == "oauth2_authorization_code":
        return bool(token and token.connected)
    if str(getattr(provider, "auth_type", "")) in {"none", "local_permission", "browser_session", "mcp_oauth"}:
        return bool(client and client.client_id)
    public_record = client.public_record() if client else {}
    return bool(client and client.client_id and public_record.get("has_client_secret"))
