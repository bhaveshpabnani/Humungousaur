from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime

from .common import ICLOUD_PROVIDER_ID, app_result, utc_now


class ICloudDriveCollector:
    provider_id = ICLOUD_PROVIDER_ID
    source_channel = "macos_file_provider_or_cloud_docs_bridge"
    implementation_level = "local_bridge_ingress"
    required_scopes: tuple[str, ...] = ()

    def collect(
        self,
        config: AgentConfig,
        runtime: ConnectorRuntime | None,
        readiness: dict[str, Any],
        provider_state: dict[str, Any],
        *,
        dry_run: bool,
        max_events: int,
    ) -> dict[str, Any]:
        del config, runtime, readiness, dry_run, max_events
        provider_state["source_channel"] = self.source_channel
        provider_state.setdefault("baseline_at", utc_now())
        return app_result(
            self.provider_id,
            "running",
            "iCloud Drive collector is registered; events arrive through the macOS File Provider/CloudDocs bridge.",
            cursor=provider_state.get("baseline_at", ""),
            source_channel=self.source_channel,
            implementation_level=self.implementation_level,
        )


ICLOUD_DRIVE_COLLECTOR = ICloudDriveCollector()
