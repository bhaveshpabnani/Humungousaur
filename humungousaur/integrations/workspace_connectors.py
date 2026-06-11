from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime, DEFAULT_REDIRECT_URI
from humungousaur.connectors.models import ConnectorProviderManifest as WorkspaceConnectorProvider
from humungousaur.connectors.providers import PROVIDER_MANIFESTS as PROVIDERS


def connector_catalog(config: AgentConfig) -> dict[str, Any]:
    return ConnectorRuntime(config).catalog()


def connector_status(config: AgentConfig, provider_id: str | None = None) -> dict[str, Any]:
    return ConnectorRuntime(config).status(provider_id=provider_id)


def configure_connector_client(
    config: AgentConfig,
    provider_id: str,
    *,
    client_id: str,
    client_secret: str = "",
    redirect_uri: str = DEFAULT_REDIRECT_URI,
) -> dict[str, Any]:
    return ConnectorRuntime(config).configure_client(
        provider_id,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )


def prepare_connector_authorization(
    config: AgentConfig,
    provider_id: str,
    *,
    scopes: list[str] | None = None,
    redirect_uri: str = "",
) -> dict[str, Any]:
    return ConnectorRuntime(config).prepare_authorization(provider_id, scopes=scopes, redirect_uri=redirect_uri)


def complete_connector_authorization(config: AgentConfig, *, state: str, code: str) -> dict[str, Any]:
    return ConnectorRuntime(config).complete_authorization(state=state, code=code)


def refresh_connector_token(config: AgentConfig, provider_id: str) -> dict[str, Any]:
    return ConnectorRuntime(config).refresh_token(provider_id)


def disconnect_connector(config: AgentConfig, provider_id: str) -> dict[str, Any]:
    return ConnectorRuntime(config).disconnect(provider_id)


def connector_secret_value(config: AgentConfig, provider_id: str, key: str = "access_token") -> str | None:
    return ConnectorRuntime(config).secret_value(provider_id, key)
