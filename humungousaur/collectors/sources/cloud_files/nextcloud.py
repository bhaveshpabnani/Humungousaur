from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime

from .common import NEXTCLOUD_METADATA_SCOPES, NEXTCLOUD_PROVIDER_ID, app_result


class NextcloudCloudFileCollector:
    provider_id = NEXTCLOUD_PROVIDER_ID
    source_channel = "nextcloud_webdav_ocs_activity_or_bridge"
    implementation_level = "webdav_or_ocs_ingress"
    required_scopes = NEXTCLOUD_METADATA_SCOPES

    def collect(
        self,
        config: AgentConfig,
        runtime: ConnectorRuntime,
        readiness: dict[str, Any],
        provider_state: dict[str, Any],
        *,
        dry_run: bool,
        max_events: int,
    ) -> dict[str, Any]:
        del config, runtime, readiness, dry_run, max_events
        provider_state.setdefault("baseline_at", "")
        return app_result(
            self.provider_id,
            "running",
            "Nextcloud cloud-file source is registered; file metadata events arrive through WebDAV/OCS relays or local sync bridges.",
            cursor=str(provider_state.get("baseline_at") or ""),
            source_channel=self.source_channel,
            implementation_level=self.implementation_level,
        )


NEXTCLOUD_CLOUD_FILE_COLLECTOR = NextcloudCloudFileCollector()
