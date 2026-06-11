from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime


COMMUNICATION_CONSUMER = "connector_sources"
COMMUNICATION_SOURCE_ID = "communication"
COMMUNICATION_MAX_EVENTS_PER_APP = 20


@dataclass(frozen=True, slots=True)
class CommunicationBridgeCollector:
    app: str
    provider_id: str
    display_name: str
    description: str
    source_channel: str
    docs_url: str
    required_scopes: tuple[str, ...] = ()
    implementation_level: str = "webhook_or_extension_ingress"
    poller_supported: bool = False
    webhook_supported: bool = True

    def collect(
        self,
        readiness: dict[str, Any],
        app_state: dict[str, Any],
        *,
        dry_run: bool,
        max_events: int,
    ) -> dict[str, Any]:
        del dry_run, max_events
        app_state["source_channel"] = self.source_channel
        app_state["provider_id"] = self.provider_id
        app_state.setdefault("baseline_at", _utc_now())
        connected = bool(readiness.get("connected") or readiness.get("connection_ready"))
        status = "running" if connected else "permission_denied"
        if self.implementation_level.endswith("_bridge"):
            status = "running"
        message = (
            f"{self.display_name} communication collector is registered; events arrive through {self.source_channel}."
            if connected
            else f"{self.display_name} connector is not connected; local bridge or webhook ingress can still submit metadata-only events."
        )
        return _app_result(
            self.app,
            status,
            message,
            cursor=app_state.get("baseline_at", ""),
            provider_id=self.provider_id,
            events_appended=0,
            source_channel=self.source_channel,
            implementation_level=self.implementation_level,
        )


def _collector_status_record(collector: CommunicationBridgeCollector) -> dict[str, Any]:
    return {
        "app": collector.app,
        "provider_id": collector.provider_id,
        "display_name": collector.display_name,
        "required_scopes": list(collector.required_scopes),
        "description": collector.description,
        "source_channel": collector.source_channel,
        "docs_url": collector.docs_url,
        "implementation_level": collector.implementation_level,
        "poller_supported": collector.poller_supported,
        "webhook_supported": collector.webhook_supported,
    }


def _require_connector_ready(config: AgentConfig, provider_id: str) -> dict[str, Any]:
    readiness = ConnectorRuntime(config.normalized()).readiness(provider_id)
    connected = bool(readiness.get("connection_ready") or readiness.get("connected") or readiness.get("collector_ready"))
    if not connected:
        raise PermissionError(f"{provider_id} connector is not ready for webhook ingestion")
    return readiness


def _app_result(
    app: str,
    status: str,
    message: str,
    *,
    provider_id: str,
    cursor: str = "",
    events_appended: int = 0,
    source_channel: str = "",
    implementation_level: str = "webhook_or_extension_ingress",
) -> dict[str, Any]:
    return {
        "app": app,
        "provider_id": provider_id,
        "status": status,
        "message": message[:500],
        "cursor_present": bool(cursor),
        "events_appended": int(events_appended),
        "source_channel": source_channel,
        "implementation_level": implementation_level,
    }


def _aggregate_app_status(app_results: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status") or "") for item in app_results}
    if "running" in statuses and statuses.intersection({"permission_denied", "failed"}):
        return "degraded"
    if "permission_denied" in statuses:
        return "permission_denied"
    if "failed" in statuses:
        return "failed"
    if "running" in statuses:
        return "running"
    return "degraded"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
