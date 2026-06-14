from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from humungousaur.config import AgentConfig


KNOWLEDGE_BASE_CONSUMER = "connector_sources"
KNOWLEDGE_BASE_PROVIDER_IDS = (
    "notion",
    "confluence",
    "coda",
    "obsidian",
    "evernote",
    "readwise",
    "apple_local",
    "microsoft_365",
)


@dataclass(frozen=True, slots=True)
class KnowledgeBaseAppCollector:
    provider_id: str
    app: str
    display_name: str
    description: str
    source_channel: str
    implementation_level: str
    required_scopes: tuple[str, ...] = ()
    poller_supported: bool = False
    webhook_supported: bool = True
    local_bridge_supported: bool = False
    derived_from: tuple[str, ...] = ()
    official_docs: tuple[str, ...] = ()

    def collect(
        self,
        config: AgentConfig,
        readiness: dict[str, Any],
        app_state: dict[str, Any],
        *,
        dry_run: bool,
        max_events: int,
    ) -> dict[str, Any]:
        del config, dry_run, max_events
        app_state["source_channel"] = self.source_channel
        app_state.setdefault("baseline_at", _utc_now())
        if self.local_bridge_supported:
            return _app_result(
                self.app,
                "running",
                f"{self.display_name} collector is registered; events arrive through {self.source_channel}.",
                cursor=app_state.get("baseline_at", ""),
                source_channel=self.source_channel,
                implementation_level=self.implementation_level,
            )
        if not readiness.get("collector_ready") and not readiness.get("connection_ready") and not readiness.get("connected"):
            return _app_result(
                self.app,
                "permission_denied",
                f"{self.display_name} connector is not connected; webhook or API events are not available.",
                source_channel=self.source_channel,
                implementation_level=self.implementation_level,
            )
        missing = _missing_scopes(readiness, self.required_scopes)
        if missing:
            return _app_result(
                self.app,
                "running",
                f"{self.display_name} API scope is not granted; collector will accept webhook/add-on events only.",
                source_channel=self.source_channel,
                implementation_level="scope_gated_webhook_ingress",
            )
        return _app_result(
            self.app,
            "running",
            f"{self.display_name} collector is registered; events arrive through {self.source_channel}.",
            cursor=app_state.get("baseline_at", ""),
            source_channel=self.source_channel,
            implementation_level=self.implementation_level,
        )


def _collector_status_record(collector: KnowledgeBaseAppCollector) -> dict[str, Any]:
    return {
        "provider_id": collector.provider_id,
        "app": collector.app,
        "display_name": collector.display_name,
        "required_scopes": list(collector.required_scopes),
        "description": collector.description,
        "source_channel": collector.source_channel,
        "implementation_level": collector.implementation_level,
        "poller_supported": collector.poller_supported,
        "webhook_supported": collector.webhook_supported,
        "local_bridge_supported": collector.local_bridge_supported,
        "derived_from": list(collector.derived_from),
        "official_docs": list(collector.official_docs),
    }


def _app_result(
    app: str,
    status: str,
    message: str,
    *,
    cursor: str = "",
    events_appended: int = 0,
    source_channel: str = "",
    implementation_level: str = "webhook_or_bridge_ingress",
) -> dict[str, Any]:
    return {
        "app": app,
        "status": status,
        "message": message[:500],
        "cursor_present": bool(cursor),
        "events_appended": int(events_appended),
        "source_channel": source_channel,
        "implementation_level": implementation_level,
    }


def _aggregate_app_status(app_results: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status") or "") for item in app_results}
    if "running" in statuses and statuses.intersection({"permission_denied", "failed", "rate_limited"}):
        return "degraded"
    if "failed" in statuses:
        return "failed"
    if "permission_denied" in statuses:
        return "permission_denied"
    if "rate_limited" in statuses:
        return "rate_limited"
    if "running" in statuses:
        return "running"
    return "degraded"


def _readiness(config: AgentConfig, provider_id: str) -> dict[str, Any]:
    if provider_id in {"obsidian", "apple_local"}:
        return {
            "provider_id": provider_id,
            "configured": True,
            "connected": True,
            "collector_ready": True,
            "connection_ready": True,
            "local_bridge_ready": True,
        }
    try:
        from humungousaur.connectors import ConnectorRuntime

        readiness = ConnectorRuntime(config).readiness(provider_id)
        readiness["connection_ready"] = bool(readiness.get("connected"))
        return readiness
    except Exception as exc:
        return {
            "provider_id": provider_id,
            "configured": False,
            "connected": False,
            "collector_ready": False,
            "connection_ready": False,
            "error": str(exc),
        }


def _missing_scopes(readiness: dict[str, Any], required_scopes: tuple[str, ...]) -> list[str]:
    granted = {str(scope) for scope in readiness.get("scopes", []) if str(scope)}
    return [scope for scope in required_scopes if scope not in granted]


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
