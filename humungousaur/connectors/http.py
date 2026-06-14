from __future__ import annotations

import base64
import json
import re
from typing import Any
from urllib.parse import urlparse
from urllib.parse import urlencode
from urllib.request import Request

from .models import ConnectorOperationRequest
from .oauth import ConnectorOAuthService, _open_connector_url


class ConnectorHttpClient:
    def __init__(self, oauth: ConnectorOAuthService) -> None:
        self.oauth = oauth

    def request(self, operation: ConnectorOperationRequest) -> dict[str, Any]:
        provider = self.oauth.registry.provider(operation.provider_id)
        query = dict(operation.query or {})
        body_payload = dict(operation.body) if isinstance(operation.body, dict) else operation.body
        headers = {"Accept": "application/json"}
        headers.update(_auth_headers(self.oauth, provider, query, body_payload))
        url = self._url(_resolved_api_base_url(self.oauth, provider), _resolved_operation_path(self.oauth, provider, operation.path), query)
        body = None
        if body_payload is not None:
            body = json.dumps(body_payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=body, headers=headers, method=operation.method.upper())
        with _open_connector_url(request, timeout=30) as response:
            data = response.read().decode("utf-8")
            status = getattr(response, "status", 200)
        parsed: Any
        try:
            parsed = json.loads(data) if data else {}
        except json.JSONDecodeError:
            parsed = {"text": data}
        return {
            "provider_id": operation.provider_id,
            "operation": operation.operation,
            "status_code": status,
            "response": parsed,
        }

    def _url(self, api_base_url: str, path: str, query: dict[str, Any]) -> str:
        base = str(api_base_url).rstrip("/")
        path_value = str(path or "").strip()
        query_string = urlencode({str(key): str(value) for key, value in query.items()})
        if not path_value:
            return base + (f"?{query_string}" if query_string else "")
        if path_value.startswith("https://"):
            return _absolute_api_url(base, path_value, query_string)
        clean_path = "/" + path_value.lstrip("/")
        return f"{base}{clean_path}" + (f"?{query_string}" if query_string else "")


def _absolute_api_url(api_base_url: str, absolute_url: str, query_string: str) -> str:
    base_host = urlparse(api_base_url).hostname or ""
    target = urlparse(absolute_url)
    target_host = target.hostname or ""
    if target.scheme != "https" or not _same_api_family(base_host, target_host):
        raise ValueError("Connector operation URL must stay inside the provider API family.")
    separator = "&" if target.query and query_string else "?"
    return absolute_url + (f"{separator}{query_string}" if query_string else "")


def _same_api_family(base_host: str, target_host: str) -> bool:
    if not base_host or not target_host:
        return False
    if target_host == base_host or target_host.endswith(f".{base_host}"):
        return True
    if base_host.endswith(".googleapis.com") and target_host.endswith(".googleapis.com"):
        return True
    return False


def _resolved_api_base_url(oauth: ConnectorOAuthService, provider: Any) -> str:
    api_base_url = str(getattr(provider, "api_base_url", "") or "")
    placeholders = set(re.findall(r"\{([a-zA-Z0-9_]+)\}", api_base_url))
    if not placeholders:
        return api_base_url
    resolved = api_base_url
    aliases = {
        "shop": ("shop_domain", "shop"),
        "shop_domain": ("shop_domain", "shop"),
        "account": ("account", "account_identifier"),
        "cloud_id": ("cloud_id", "cloudid", "tenant_id"),
        "homeserver": ("homeserver", "host", "server"),
        "workspace_host": ("workspace_host", "host", "server"),
        "host": ("host", "workspace_host", "server"),
        "server": ("server", "host", "workspace_host"),
        "region": ("region",),
        "service": ("service",),
        "subdomain": ("subdomain", "domain", "site"),
        "site": ("site", "subdomain", "domain"),
        "domain": ("domain", "subdomain", "site"),
    }
    for placeholder in placeholders:
        keys = aliases.get(placeholder, (placeholder,))
        value = ""
        for key in keys:
            value = _credential_value(oauth, provider, key)
            if value:
                break
        if not value:
            raise ValueError(f"{provider.display_name} is missing credential field '{placeholder}'.")
        resolved = resolved.replace("{" + placeholder + "}", _host_template_value(value))
    return resolved


def _host_template_value(value: str) -> str:
    text = str(value or "").strip()
    if "://" in text:
        parsed = urlparse(text)
        text = parsed.netloc or parsed.path
    return text.strip().strip("/")


def _auth_headers(oauth: ConnectorOAuthService, provider: Any, query: dict[str, Any], body: Any = None) -> dict[str, str]:
    scheme = str(getattr(provider, "api_auth_scheme", "bearer") or "bearer")
    provider_id = str(provider.provider_id)
    if scheme == "none":
        return {}
    if scheme == "basic_pat":
        pat = _credential_value(oauth, provider, "api_key")
        if not pat:
            raise ValueError(f"{provider.display_name} is not connected.")
        encoded = base64.b64encode(f":{pat}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}
    if scheme == "basic_account_token":
        account_sid = _credential_value(oauth, provider, "account_sid")
        auth_token = _credential_value(oauth, provider, "auth_token")
        if not account_sid or not auth_token:
            raise ValueError(f"{provider.display_name} is not connected.")
        encoded = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}
    if scheme == "basic_api_key":
        api_key = _credential_value(oauth, provider, "api_key")
        if not api_key:
            raise ValueError(f"{provider.display_name} is not connected.")
        encoded = base64.b64encode(f"{api_key}:X".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}
    if scheme == "basic_username_password":
        username = _credential_value(oauth, provider, "username")
        password = _credential_value(oauth, provider, "password") or _credential_value(oauth, provider, "app_password")
        if not username or not password:
            raise ValueError(f"{provider.display_name} is not connected.")
        encoded = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}
    if scheme == "nextcloud_ocs_basic":
        username = _credential_value(oauth, provider, "username")
        password = _credential_value(oauth, provider, "password") or _credential_value(oauth, provider, "app_password")
        if not username or not password:
            raise ValueError(f"{provider.display_name} is not connected.")
        encoded = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {encoded}", "OCS-APIRequest": "true"}
    if scheme == "zendesk_api_token":
        email = _credential_value(oauth, provider, "email")
        api_token = _credential_value(oauth, provider, "api_token")
        if not email or not api_token:
            raise ValueError(f"{provider.display_name} is not connected.")
        encoded = base64.b64encode(f"{email}/token:{api_token}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}
    if scheme == "query_key_token":
        api_key = _credential_value(oauth, provider, "api_key")
        token = _credential_value(oauth, provider, "token")
        if not api_key or not token:
            raise ValueError(f"{provider.display_name} is not connected.")
        query.setdefault("key", api_key)
        query.setdefault("token", token)
        return {}
    if scheme == "query_api_token":
        api_token = _credential_value(oauth, provider, "api_token") or _credential_value(oauth, provider, "api_key")
        if not api_token:
            raise ValueError(f"{provider.display_name} is not connected.")
        query.setdefault("api_token", api_token)
        return {}
    if scheme == "query_key":
        api_key = _credential_value(oauth, provider, "api_key")
        if not api_key:
            raise ValueError(f"{provider.display_name} is not connected.")
        query.setdefault("key", api_key)
        return {}
    if scheme == "datadog_keys":
        api_key = _credential_value(oauth, provider, "api_key")
        application_key = _credential_value(oauth, provider, "application_key")
        if not api_key or not application_key:
            raise ValueError(f"{provider.display_name} is not connected.")
        return {"DD-API-KEY": api_key, "DD-APPLICATION-KEY": application_key}
    if scheme == "plaid_keys":
        client_id = _credential_value(oauth, provider, "client_id")
        secret = _credential_value(oauth, provider, "secret") or _credential_value(oauth, provider, "client_secret")
        if not client_id or not secret:
            raise ValueError(f"{provider.display_name} is not connected.")
        if isinstance(body, dict):
            body.setdefault("client_id", client_id)
            body.setdefault("secret", secret)
            return {}
        return {"PLAID-CLIENT-ID": client_id, "PLAID-SECRET": secret}
    if scheme == "mailchimp_basic":
        api_key = _credential_value(oauth, provider, "api_key")
        username = _credential_value(oauth, provider, "username") or "humungousaur"
        if not api_key:
            raise ValueError(f"{provider.display_name} is not connected.")
        encoded = base64.b64encode(f"{username}:{api_key}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}
    if scheme == "genie_key":
        api_key = _credential_value(oauth, provider, "api_key")
        if not api_key:
            raise ValueError(f"{provider.display_name} is not connected.")
        return {"Authorization": f"GenieKey {api_key}"}
    if scheme == "pagerduty_token":
        api_key = _credential_value(oauth, provider, "api_key") or _credential_value(oauth, provider, "access_token")
        if not api_key:
            raise ValueError(f"{provider.display_name} is not connected.")
        return {"Authorization": f"Token token={api_key}"}
    if scheme == "discord_bot":
        bot_token = _credential_value(oauth, provider, "bot_token")
        if not bot_token:
            raise ValueError(f"{provider.display_name} is not connected.")
        return {"Authorization": f"Bot {bot_token}"}
    if scheme == "twitch_bearer":
        client_id = _credential_value(oauth, provider, "client_id")
        access_token = _credential_value(oauth, provider, "access_token")
        if not client_id or not access_token:
            raise ValueError(f"{provider.display_name} is not connected.")
        return {"Client-ID": client_id, "Authorization": f"Bearer {access_token}"}
    if scheme == "token_auth":
        token = _credential_value(oauth, provider, "api_key") or _credential_value(oauth, provider, "access_token") or _credential_value(oauth, provider, "token")
        if not token:
            raise ValueError(f"{provider.display_name} is not connected.")
        return {"Authorization": f"Token {token}"}
    if scheme == "anthropic_api_key":
        api_key = _credential_value(oauth, provider, "api_key")
        if not api_key:
            raise ValueError(f"{provider.display_name} is not connected.")
        return {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    if scheme == "x_api_key":
        api_key = _credential_value(oauth, provider, "api_key")
        if not api_key:
            raise ValueError(f"{provider.display_name} is not connected.")
        return {"x-api-key": api_key}
    if scheme == "basic_key_secret":
        api_key = _credential_value(oauth, provider, "api_key")
        api_secret = _credential_value(oauth, provider, "api_secret") or _credential_value(oauth, provider, "secret")
        if not api_key or not api_secret:
            raise ValueError(f"{provider.display_name} is not connected.")
        encoded = base64.b64encode(f"{api_key}:{api_secret}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}
    if scheme == "basic_secret":
        secret = _credential_value(oauth, provider, "api_secret") or _credential_value(oauth, provider, "secret") or _credential_value(oauth, provider, "api_key")
        if not secret:
            raise ValueError(f"{provider.display_name} is not connected.")
        encoded = base64.b64encode(f"{secret}:".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}
    if scheme == "tableau_auth_token":
        access_token = oauth.token_value(provider_id, "access_token") or _credential_value(oauth, provider, "access_token")
        if not access_token:
            raise ValueError(f"{provider.display_name} needs a Tableau REST auth token from PAT sign-in before API calls.")
        return {"X-Tableau-Auth": access_token}
    if scheme == "aws_sigv4":
        raise ValueError(f"{provider.display_name} requests require AWS SigV4 signing.")
    if scheme == "google_api_key_header":
        api_key = _credential_value(oauth, provider, "api_key")
        if not api_key:
            raise ValueError(f"{provider.display_name} is not connected.")
        return {"x-goog-api-key": api_key}
    if scheme == "brave_subscription_token":
        api_key = _credential_value(oauth, provider, "api_key")
        if not api_key:
            raise ValueError(f"{provider.display_name} is not connected.")
        return {"X-Subscription-Token": api_key}
    if scheme == "fal_key":
        api_key = _credential_value(oauth, provider, "api_key")
        if not api_key:
            raise ValueError(f"{provider.display_name} is not connected.")
        return {"Authorization": f"Key {api_key}"}
    if scheme == "pinecone_api_key":
        api_key = _credential_value(oauth, provider, "api_key")
        if not api_key:
            raise ValueError(f"{provider.display_name} is not connected.")
        return {"Api-Key": api_key}
    if scheme == "qdrant_api_key":
        api_key = _credential_value(oauth, provider, "api_key")
        if not api_key:
            raise ValueError(f"{provider.display_name} is not connected.")
        return {"api-key": api_key}
    if scheme == "modal_token":
        token_id = _credential_value(oauth, provider, "token_id")
        token_secret = _credential_value(oauth, provider, "token_secret")
        if not token_id or not token_secret:
            raise ValueError(f"{provider.display_name} is not connected.")
        return {"Modal-Key": token_id, "Modal-Secret": token_secret}
    if scheme == "shopify_admin_token":
        access_token = _credential_value(oauth, provider, "access_token")
        if not access_token:
            raise ValueError(f"{provider.display_name} is not connected.")
        return {"X-Shopify-Access-Token": access_token}
    if scheme == "xero_tenant_bearer":
        access_token = oauth.token_value(provider_id, "access_token") or _credential_value(oauth, provider, "access_token")
        tenant_id = _credential_value(oauth, provider, "tenant_id")
        if not access_token or not tenant_id:
            raise ValueError(f"{provider.display_name} is not connected.")
        return {"Authorization": f"Bearer {access_token}", "xero-tenant-id": tenant_id}
    if scheme == "telegram_bot_token_path":
        if not _credential_value(oauth, provider, "bot_token"):
            raise ValueError(f"{provider.display_name} is not connected.")
        return {}
    token = (
        oauth.token_value(provider_id, "access_token")
        or oauth.token_value(provider_id, "bot_access_token")
        or _credential_value(oauth, provider, "access_token")
        or _credential_value(oauth, provider, "api_key")
        or _credential_value(oauth, provider, "api_token")
        or _credential_value(oauth, provider, "auth_token")
        or _credential_value(oauth, provider, "bearer_token")
        or _credential_value(oauth, provider, "bot_token")
        or _credential_value(oauth, provider, "token")
    )
    if not token:
        raise ValueError(f"{provider.display_name} is not connected.")
    return {"Authorization": f"Bearer {token}"}


def _resolved_operation_path(oauth: ConnectorOAuthService, provider: Any, path: str) -> str:
    scheme = str(getattr(provider, "api_auth_scheme", "bearer") or "bearer")
    path_value = str(path or "")
    if scheme != "telegram_bot_token_path" or path_value.startswith("https://"):
        return path_value
    token = _credential_value(oauth, provider, "bot_token")
    if not token:
        raise ValueError(f"{provider.display_name} is not connected.")
    return f"bot{token}/{path_value.lstrip('/')}"


def _credential_value(oauth: ConnectorOAuthService, provider: Any, key: str) -> str:
    provider_id = str(provider.provider_id)
    token_value = oauth.token_value(provider_id, key)
    if token_value:
        return token_value
    client = oauth.public_client_configs().get(provider_id)
    if client is None:
        return ""
    fields = tuple(str(field) for field in getattr(provider, "credential_fields", ()) or ())
    first_field = fields[0] if fields else "profile_name"
    if key in {first_field, "profile_name", "connection_name", "client_id"}:
        return client.client_id
    if key in {"client_secret", "credential"}:
        return oauth.vault.get_secret(client.client_secret_ref) or ""
    return oauth.vault.get_secret(oauth.secret_ref(provider_id, key)) or ""
