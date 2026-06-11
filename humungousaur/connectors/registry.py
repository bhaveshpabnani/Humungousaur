from __future__ import annotations

from typing import Any

from .models import ConnectorProviderManifest
from .providers import PROVIDER_MANIFESTS


class ConnectorRegistry:
    def __init__(
        self,
        *,
        providers: tuple[ConnectorProviderManifest, ...] = PROVIDER_MANIFESTS,
    ) -> None:
        self._providers = {provider.provider_id: provider for provider in providers}

    def providers(self) -> list[ConnectorProviderManifest]:
        return list(self._providers.values())

    def provider(self, provider_id: str) -> ConnectorProviderManifest:
        provider = self._providers.get(str(provider_id or "").strip())
        if provider is None:
            raise KeyError(f"Unknown connector provider: {provider_id}")
        return provider


DEFAULT_CONNECTOR_REGISTRY = ConnectorRegistry()
