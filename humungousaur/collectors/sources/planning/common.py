from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime


PLANNING_PROVIDER_IDS = ("linear", "jira", "asana", "trello", "clickup", "monday", "todoist")
PLANNING_CONSUMER = "connector_sources"


PLANNING_PROVIDER_DISPLAY_NAMES = {
    "linear": "Linear",
    "jira": "Jira",
    "asana": "Asana",
    "trello": "Trello",
    "clickup": "ClickUp",
    "monday": "Monday.com",
    "todoist": "Todoist",
}


@dataclass(frozen=True, slots=True)
class PlanningWebhookCollector:
    provider_id: str
    app: str
    description: str
    source_channel: str
    implementation_level: str = "webhook_or_browser_ingress"
    poller_supported: bool = False
    webhook_supported: bool = True
    required_scopes: tuple[str, ...] = ()

    def collect(
        self,
        config: AgentConfig,
        runtime: ConnectorRuntime,
        readiness: dict[str, Any],
        app_state: dict[str, Any],
        *,
        dry_run: bool,
        max_events: int,
    ) -> dict[str, Any]:
        del config, runtime, readiness, dry_run, max_events
        app_state["source_channel"] = self.source_channel
        app_state.setdefault("baseline_at", _utc_now())
        return _app_result(
            self.app,
            "running",
            f"{PLANNING_PROVIDER_DISPLAY_NAMES[self.provider_id]} collector is registered; events arrive through {self.source_channel}.",
            cursor=app_state.get("baseline_at", ""),
            source_channel=self.source_channel,
            implementation_level=self.implementation_level,
        )


def collector_status_record(collector: PlanningWebhookCollector) -> dict[str, Any]:
    return {
        "provider_id": collector.provider_id,
        "app": collector.app,
        "required_scopes": list(collector.required_scopes),
        "description": collector.description,
        "source_channel": collector.source_channel,
        "implementation_level": collector.implementation_level,
        "poller_supported": collector.poller_supported,
        "webhook_supported": collector.webhook_supported,
    }


def app_result(
    app: str,
    status: str,
    message: str,
    *,
    cursor: str = "",
    events_appended: int = 0,
    source_channel: str = "",
    implementation_level: str = "webhook_or_browser_ingress",
) -> dict[str, Any]:
    return _app_result(
        app,
        status,
        message,
        cursor=cursor,
        events_appended=events_appended,
        source_channel=source_channel,
        implementation_level=implementation_level,
    )


def aggregate_app_status(app_results: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status") or "") for item in app_results}
    if "running" in statuses and statuses.intersection({"failed", "permission_denied", "rate_limited"}):
        return "degraded"
    if "permission_denied" in statuses:
        return "permission_denied"
    if "failed" in statuses:
        return "failed"
    if "running" in statuses:
        return "running"
    return "degraded"


def _app_result(
    app: str,
    status: str,
    message: str,
    *,
    cursor: str = "",
    events_appended: int = 0,
    source_channel: str = "",
    implementation_level: str = "webhook_or_browser_ingress",
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


def utc_now() -> str:
    return _utc_now()


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

