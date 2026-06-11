from __future__ import annotations

import json
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
        token = self.oauth.token_value(operation.provider_id, "access_token") or self.oauth.token_value(operation.provider_id, "bot_access_token")
        if not token:
            raise ValueError(f"{provider.display_name} is not connected.")
        url = self._url(provider.api_base_url, operation.path, operation.query or {})
        body = None
        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
        if operation.body is not None:
            body = json.dumps(operation.body).encode("utf-8")
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
