from __future__ import annotations

from .models import ConnectorOperationRequest, ConnectorTokenStatus


class ConnectorPolicy:
    def check_scopes(self, request: ConnectorOperationRequest, token: ConnectorTokenStatus | None) -> None:
        if token is None or not token.connected:
            raise ValueError(f"{request.provider_id} is not connected.")
        granted = set(token.scopes)
        missing = [scope for scope in request.required_scopes if scope not in granted]
        if missing:
            raise PermissionError(f"{request.provider_id} connector is missing scopes: {', '.join(missing)}")
