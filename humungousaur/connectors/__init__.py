from .models import (
    ConnectorOperationRequest,
    ConnectorProviderManifest,
    DEFAULT_REDIRECT_URI,
)
from .registry import ConnectorRegistry, DEFAULT_CONNECTOR_REGISTRY

__all__ = [
    "ConnectorOperationRequest",
    "ConnectorProviderManifest",
    "ConnectorRegistry",
    "ConnectorRuntime",
    "DEFAULT_CONNECTOR_REGISTRY",
    "DEFAULT_REDIRECT_URI",
]


def __getattr__(name: str):
    if name == "ConnectorRuntime":
        from .runtime import ConnectorRuntime

        return ConnectorRuntime
    raise AttributeError(name)
