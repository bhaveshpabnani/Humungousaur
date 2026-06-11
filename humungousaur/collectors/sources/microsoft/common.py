from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlparse

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorOperationRequest, ConnectorRuntime


MICROSOFT_365_PROVIDER_ID = "microsoft_365"
MICROSOFT_365_CONSUMER = "connector_sources"
MICROSOFT_365_MAX_EVENTS_PER_APP = 20

MICROSOFT_365_FILES_SCOPE = "Files.Read.All"
MICROSOFT_365_SITES_SCOPE = "Sites.Read.All"
MICROSOFT_365_MAIL_SCOPE = "Mail.Read"
MICROSOFT_365_CALENDAR_SCOPE = "Calendars.Read"
MICROSOFT_365_TASKS_SCOPE = "Tasks.Read"
MICROSOFT_365_ONENOTE_SCOPE = "Notes.Read"
MICROSOFT_365_TEAMS_CHAT_SCOPE = "Chat.Read"
MICROSOFT_365_TEAMS_CHANNEL_SCOPE = "ChannelMessage.Read.All"
MICROSOFT_365_PRESENCE_SCOPE = "Presence.Read"


@dataclass(frozen=True, slots=True)
class Microsoft365BridgeCollector:
    app: str
    required_scopes: tuple[str, ...]
    description: str
    source_channel: str
    implementation_level: str = "webhook_or_addin_ingress"
    poller_supported: bool = False
    webhook_supported: bool = True
    derived_from: tuple[str, ...] = ()

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
            f"Microsoft 365 {self.app.replace('_', ' ').title()} collector is registered; events arrive through {self.source_channel}.",
            cursor=app_state.get("baseline_at", ""),
            events_appended=0,
            source_channel=self.source_channel,
            implementation_level=self.implementation_level,
        )


def _collector_status_record(collector: Any) -> dict[str, Any]:
    return {
        "app": collector.app,
        "required_scopes": list(getattr(collector, "required_scopes", ())),
        "description": collector.description,
        "source_channel": getattr(collector, "source_channel", ""),
        "implementation_level": getattr(collector, "implementation_level", "poller"),
        "poller_supported": bool(getattr(collector, "poller_supported", True)),
        "webhook_supported": bool(getattr(collector, "webhook_supported", True)),
        "derived_from": list(getattr(collector, "derived_from", ())),
    }


def _connector_request(
    runtime: ConnectorRuntime,
    *,
    operation: str,
    path: str,
    query: dict[str, Any] | None = None,
    required_scopes: tuple[str, ...],
) -> dict[str, Any]:
    return runtime.execute_operation(
        ConnectorOperationRequest(
            provider_id=MICROSOFT_365_PROVIDER_ID,
            operation=operation,
            method="GET",
            path=path,
            query=query or {},
            required_scopes=required_scopes,
            reason="Poll Microsoft Graph metadata for local collector events.",
        )
    )


def _connector_request_from_link(
    runtime: ConnectorRuntime,
    *,
    operation: str,
    link: str,
    required_scopes: tuple[str, ...],
) -> dict[str, Any]:
    path, query = _graph_link_to_path_query(link)
    return _connector_request(runtime, operation=operation, path=path, query=query, required_scopes=required_scopes)


def _graph_link_to_path_query(link: str) -> tuple[str, dict[str, Any]]:
    parsed = urlparse(str(link or ""))
    if parsed.scheme and parsed.netloc:
        path = parsed.path or "/"
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        return path, query
    if "?" in str(link):
        path, query_string = str(link).split("?", 1)
        return path, dict(parse_qsl(query_string, keep_blank_values=True))
    return str(link or ""), {}


def _app_result(
    app: str,
    status: str,
    message: str,
    *,
    cursor: str = "",
    events_appended: int = 0,
    source_channel: str = "",
    implementation_level: str = "poller",
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
    hard_failures = {"failed", "permission_denied"}
    if statuses.intersection(hard_failures) and "running" in statuses:
        return "degraded"
    if "permission_denied" in statuses:
        return "permission_denied"
    if "failed" in statuses:
        return "failed"
    if "running" in statuses:
        return "running"
    return "degraded"


def _refresh_if_needed(runtime: ConnectorRuntime, readiness: dict[str, Any]) -> None:
    expires_at = int(readiness.get("expires_at") or 0)
    if expires_at and expires_at < int(time.time()) + 60:
        try:
            runtime.refresh_token(MICROSOFT_365_PROVIDER_ID)
        except ValueError:
            return


def _has_scopes(readiness: dict[str, Any], required_scopes: tuple[str, ...]) -> bool:
    granted = {str(scope) for scope in readiness.get("scopes", []) if str(scope)}
    return all(scope in granted for scope in required_scopes)


def _scope_gated_result(app: str, readiness: dict[str, Any], required_scopes: tuple[str, ...], source_channel: str) -> dict[str, Any] | None:
    if _has_scopes(readiness, required_scopes):
        return None
    return _app_result(
        app,
        "running",
        f"Microsoft 365 {app.replace('_', ' ').title()} API scope is not granted; collector will accept {source_channel} events only.",
        source_channel=source_channel,
        implementation_level="scope_gated_poller",
    )


def _store_delta_cursor(app_state: dict[str, Any], body: dict[str, Any]) -> None:
    next_link = str(body.get("@odata.nextLink") or "")
    delta_link = str(body.get("@odata.deltaLink") or "")
    if next_link:
        app_state["delta_link"] = next_link
    elif delta_link:
        app_state["delta_link"] = delta_link


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
