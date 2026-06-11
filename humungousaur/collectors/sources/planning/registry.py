from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.collectors.event_log import CollectorEventLog
from humungousaur.connectors import ConnectorRuntime

from ..workspace_connectors import record_connector_source_health
from .asana import ASANA_COLLECTOR
from .clickup import CLICKUP_COLLECTOR
from .common import (
    PLANNING_CONSUMER,
    PLANNING_PROVIDER_IDS,
    aggregate_app_status,
    app_result,
    collector_status_record,
    utc_now,
)
from .jira import JIRA_COLLECTOR
from .linear import LINEAR_COLLECTOR
from .monday import MONDAY_COLLECTOR
from .todoist import TODOIST_COLLECTOR
from .trello import TRELLO_COLLECTOR


PLANNING_APP_COLLECTORS: tuple[Any, ...] = (
    LINEAR_COLLECTOR,
    JIRA_COLLECTOR,
    ASANA_COLLECTOR,
    TRELLO_COLLECTOR,
    CLICKUP_COLLECTOR,
    MONDAY_COLLECTOR,
    TODOIST_COLLECTOR,
)


def planning_app_status_records() -> list[dict[str, Any]]:
    return [collector_status_record(collector) for collector in PLANNING_APP_COLLECTORS]


def run_planning_source_tick(config: AgentConfig, *, provider_id: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    normalized = config.normalized()
    selected = _selected_collectors(provider_id)
    event_log = CollectorEventLog(normalized.collector_events_db_path)
    state = event_log.consumer_state(PLANNING_CONSUMER)
    source_states = state.setdefault("sources", {})
    runtime = ConnectorRuntime(normalized)
    results = []
    for collector in selected:
        provider_state = source_states.setdefault(collector.provider_id, {})
        app_states = provider_state.setdefault("apps", {})
        app_state = app_states.setdefault(collector.app, {})
        previous_tick = provider_state.get("last_tick_at", "")
        provider_state["last_tick_at"] = utc_now()
        provider_state["tick_count"] = int(provider_state.get("tick_count") or 0) + 1
        provider_state["collector_owner"] = "humungousaur.collectors.sources.planning"
        provider_state["poller_supported"] = bool(collector.poller_supported)
        provider_state["webhook_supported"] = bool(collector.webhook_supported)
        readiness = runtime.readiness(collector.provider_id)
        if not readiness.get("collector_ready"):
            result = {
                "provider_id": collector.provider_id,
                "status": "permission_denied",
                "events_appended": 0,
                "last_tick_at": provider_state["last_tick_at"],
                "poller_supported": collector.poller_supported,
                "webhook_supported": collector.webhook_supported,
                "connector_readiness": readiness,
                "apps": [],
            }
            if not dry_run:
                record_connector_source_health(
                    normalized,
                    provider_id=collector.provider_id,
                    status="permission_denied",
                    message=f"{collector.app} connector is not connected; webhook/browser events can still be accepted when relayed locally.",
                    metadata={"last_tick_at": provider_state["last_tick_at"], "previous_tick_at": previous_tick},
                )
            results.append(result)
            continue
        try:
            app_result_record = collector.collect(
                normalized,
                runtime,
                readiness,
                app_state,
                dry_run=dry_run,
                max_events=0,
            )
        except Exception as exc:
            app_result_record = app_result(
                collector.app,
                "failed",
                str(exc),
                source_channel=collector.source_channel,
                implementation_level=collector.implementation_level,
            )
        source_status = aggregate_app_status([app_result_record])
        if not dry_run:
            record_connector_source_health(
                normalized,
                provider_id=collector.provider_id,
                status=source_status,
                message=f"{collector.app} planning collector tick completed.",
                metadata={
                    "last_tick_at": provider_state["last_tick_at"],
                    "previous_tick_at": previous_tick,
                    "source_channel": collector.source_channel,
                },
            )
        results.append(
            {
                "provider_id": collector.provider_id,
                "status": source_status,
                "events_appended": int(app_result_record.get("events_appended") or 0),
                "last_tick_at": provider_state["last_tick_at"],
                "poller_supported": collector.poller_supported,
                "webhook_supported": collector.webhook_supported,
                "connector_readiness": runtime.readiness(collector.provider_id),
                "apps": [app_result_record],
            }
        )
    if not dry_run:
        event_log.save_consumer_state(PLANNING_CONSUMER, state)
    return {"status": "succeeded", "sources": results, "source_count": len(results), "dry_run": dry_run}


def _selected_collectors(provider_id: str | None) -> tuple[Any, ...]:
    provider = str(provider_id or "").strip()
    if not provider:
        return PLANNING_APP_COLLECTORS
    if provider not in PLANNING_PROVIDER_IDS:
        raise KeyError(f"Unknown planning source provider: {provider_id}")
    return tuple(collector for collector in PLANNING_APP_COLLECTORS if collector.provider_id == provider)


__all__ = [
    "PLANNING_APP_COLLECTORS",
    "planning_app_status_records",
    "run_planning_source_tick",
]

