from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.collectors.event_log import CollectorEventLog
from humungousaur.connectors import ConnectorRuntime

from .common import (
    MICROSOFT_365_CONSUMER,
    MICROSOFT_365_MAX_EVENTS_PER_APP,
    MICROSOFT_365_PROVIDER_ID,
    _aggregate_app_status,
    _app_result,
    _collector_status_record,
    _refresh_if_needed,
    _scope_gated_result,
    _utc_now,
)
from .events import append_microsoft_365_health, _append_dead_letter
from .excel import MICROSOFT_EXCEL_COLLECTOR
from .loop import MICROSOFT_LOOP_COLLECTOR
from .onedrive import MICROSOFT_ONEDRIVE_COLLECTOR
from .onenote import MICROSOFT_ONENOTE_COLLECTOR
from .outlook import MICROSOFT_OUTLOOK_CALENDAR_COLLECTOR, MICROSOFT_OUTLOOK_COLLECTOR
from .powerpoint import MICROSOFT_POWERPOINT_COLLECTOR
from .sharepoint import MICROSOFT_SHAREPOINT_COLLECTOR
from .teams import MICROSOFT_TEAMS_COLLECTOR
from .todo import MICROSOFT_TODO_COLLECTOR
from .word import MICROSOFT_WORD_COLLECTOR


MICROSOFT_365_APP_COLLECTORS: tuple[Any, ...] = (
    MICROSOFT_ONEDRIVE_COLLECTOR,
    MICROSOFT_SHAREPOINT_COLLECTOR,
    MICROSOFT_WORD_COLLECTOR,
    MICROSOFT_EXCEL_COLLECTOR,
    MICROSOFT_POWERPOINT_COLLECTOR,
    MICROSOFT_OUTLOOK_COLLECTOR,
    MICROSOFT_OUTLOOK_CALENDAR_COLLECTOR,
    MICROSOFT_TEAMS_COLLECTOR,
    MICROSOFT_ONENOTE_COLLECTOR,
    MICROSOFT_TODO_COLLECTOR,
    MICROSOFT_LOOP_COLLECTOR,
)


def microsoft_365_app_status_records() -> list[dict[str, Any]]:
    return [_collector_status_record(collector) for collector in MICROSOFT_365_APP_COLLECTORS]


def run_microsoft_365_source_tick(config: AgentConfig, *, dry_run: bool = False) -> dict[str, Any]:
    normalized = config.normalized()
    event_log = CollectorEventLog(normalized.collector_events_db_path)
    state = event_log.consumer_state(MICROSOFT_365_CONSUMER)
    source_state = state.setdefault("sources", {}).setdefault(MICROSOFT_365_PROVIDER_ID, {})
    app_states = source_state.setdefault("apps", {})
    runtime = ConnectorRuntime(normalized)
    readiness = runtime.readiness(MICROSOFT_365_PROVIDER_ID)
    source_state["last_tick_at"] = _utc_now()
    source_state["tick_count"] = int(source_state.get("tick_count") or 0) + 1
    source_state["collector_owner"] = "humungousaur.collectors.sources.microsoft"
    if not readiness.get("collector_ready"):
        result = {
            "provider_id": MICROSOFT_365_PROVIDER_ID,
            "status": "permission_denied",
            "events_appended": 0,
            "last_tick_at": source_state["last_tick_at"],
            "connector_readiness": readiness,
            "apps": [],
        }
        if not dry_run:
            append_microsoft_365_health(
                normalized,
                {
                    "status": "permission_denied",
                    "message": "Microsoft 365 connector is not connected.",
                    "metadata": {"last_tick_at": source_state["last_tick_at"]},
                },
            )
            event_log.save_consumer_state(MICROSOFT_365_CONSUMER, state)
        return {"status": "succeeded", "sources": [result], "source_count": 1, "dry_run": dry_run}

    _refresh_if_needed(runtime, readiness)
    readiness = runtime.readiness(MICROSOFT_365_PROVIDER_ID)
    app_results: list[dict[str, Any]] = []
    total_events = 0
    for collector in MICROSOFT_365_APP_COLLECTORS:
        app_state = app_states.setdefault(collector.app, {})
        try:
            scope_result = _scope_gated_result(
                collector.app,
                readiness,
                tuple(getattr(collector, "required_scopes", ())),
                getattr(collector, "source_channel", ""),
            )
            if scope_result is not None:
                app_state.setdefault("baseline_at", _utc_now())
                app_result = scope_result
            else:
                app_result = collector.collect(
                    normalized,
                    runtime,
                    readiness,
                    app_state,
                    dry_run=dry_run,
                    max_events=MICROSOFT_365_MAX_EVENTS_PER_APP,
                )
        except PermissionError as exc:
            app_result = _app_result(collector.app, "permission_denied", str(exc), events_appended=0, source_channel=getattr(collector, "source_channel", ""))
        except Exception as exc:
            _append_dead_letter(
                normalized,
                {"app": collector.app, "state_keys": sorted(app_state.keys())},
                f"{type(exc).__name__}: {exc}",
            )
            app_result = _app_result(collector.app, "failed", str(exc), events_appended=0, source_channel=getattr(collector, "source_channel", ""))
        app_results.append(app_result)
        total_events += int(app_result.get("events_appended") or 0)
    source_status = _aggregate_app_status(app_results)
    if not dry_run:
        append_microsoft_365_health(
            normalized,
            {
                "status": source_status,
                "message": "Microsoft 365 app collectors tick completed.",
                "metadata": {
                    "last_tick_at": source_state["last_tick_at"],
                    "events_appended": total_events,
                    "app_count": len(app_results),
                },
            },
        )
        event_log.save_consumer_state(MICROSOFT_365_CONSUMER, state)
    return {
        "status": "succeeded",
        "sources": [
            {
                "provider_id": MICROSOFT_365_PROVIDER_ID,
                "status": source_status,
                "events_appended": total_events,
                "last_tick_at": source_state["last_tick_at"],
                "poller_supported": True,
                "webhook_supported": True,
                "connector_readiness": runtime.readiness(MICROSOFT_365_PROVIDER_ID),
                "apps": app_results,
            }
        ],
        "source_count": 1,
        "dry_run": dry_run,
    }


__all__ = [
    "MICROSOFT_365_APP_COLLECTORS",
    "microsoft_365_app_status_records",
    "run_microsoft_365_source_tick",
]
