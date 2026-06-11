from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


DESIGN_PROVIDER_IDS = ("figma", "figjam", "miro", "canva", "sketch", "adobe_xd")
DESIGN_CONSUMER = "connector_sources"
DESIGN_MAX_EVENTS_PER_APP = 20

DESIGN_PROVIDER_DISPLAY_NAMES = {
    "figma": "Figma",
    "figjam": "FigJam",
    "miro": "Miro",
    "canva": "Canva",
    "sketch": "Sketch",
    "adobe_xd": "Adobe XD",
}


@dataclass(frozen=True, slots=True)
class DesignAppCollector:
    provider_id: str
    app: str
    domain: str
    description: str
    source_channel: str
    docs_url: str
    required_scopes: tuple[str, ...] = ()
    implementation_level: str = "webhook_or_app_plugin_ingress"
    poller_supported: bool = False
    webhook_supported: bool = True
    requires_connector: bool = True

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
        app_state.setdefault("baseline_at", utc_now())
        connected = bool(readiness.get("connected") or readiness.get("connection_ready") or not self.requires_connector)
        status = "running" if connected else "permission_denied"
        message = (
            f"{DESIGN_PROVIDER_DISPLAY_NAMES[self.provider_id]} collector is registered; design metadata arrives through {self.source_channel}."
            if connected
            else f"{DESIGN_PROVIDER_DISPLAY_NAMES[self.provider_id]} connector is not connected; local plugin/webhook ingress can still submit metadata-only events."
        )
        return app_result(
            self.app,
            status,
            message,
            provider_id=self.provider_id,
            domain=self.domain,
            cursor=app_state.get("baseline_at", ""),
            source_channel=self.source_channel,
            implementation_level=self.implementation_level,
        )


def collector_status_record(collector: DesignAppCollector) -> dict[str, Any]:
    return {
        "app": collector.app,
        "provider_id": collector.provider_id,
        "display_name": DESIGN_PROVIDER_DISPLAY_NAMES[collector.provider_id],
        "domain": collector.domain,
        "required_scopes": list(collector.required_scopes),
        "description": collector.description,
        "source_channel": collector.source_channel,
        "docs_url": collector.docs_url,
        "implementation_level": collector.implementation_level,
        "poller_supported": collector.poller_supported,
        "webhook_supported": collector.webhook_supported,
        "requires_connector": collector.requires_connector,
    }


def app_result(
    app: str,
    status: str,
    message: str,
    *,
    provider_id: str,
    domain: str,
    cursor: str = "",
    events_appended: int = 0,
    source_channel: str = "",
    implementation_level: str = "webhook_or_app_plugin_ingress",
) -> dict[str, Any]:
    return {
        "app": app,
        "provider_id": provider_id,
        "domain": domain,
        "status": status,
        "message": message[:500],
        "cursor_present": bool(cursor),
        "events_appended": int(events_appended),
        "source_channel": source_channel,
        "implementation_level": implementation_level,
    }


def aggregate_app_status(app_results: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status") or "") for item in app_results}
    if "running" in statuses and statuses.intersection({"permission_denied", "rate_limited", "failed"}):
        return "degraded"
    if "permission_denied" in statuses:
        return "permission_denied"
    if "failed" in statuses:
        return "failed"
    if "running" in statuses:
        return "running"
    return "degraded"


def clean_token(value: Any) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", "_").replace(".", "_").split())


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
