from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.collectors.event_log import CollectorEventLog
from humungousaur.connectors import ConnectorRuntime

from .calendar import GOOGLE_CALENDAR_COLLECTOR
from .chat import GOOGLE_CHAT_COLLECTOR
from .common import (
    GOOGLE_WORKSPACE_CONSUMER,
    GOOGLE_WORKSPACE_MAX_EVENTS_PER_APP,
    GOOGLE_WORKSPACE_PROVIDER_ID,
    _aggregate_app_status,
    _app_result,
    _collector_status_record,
    _refresh_if_needed,
    _scope_gated_result,
    _utc_now,
)
from .contacts import GOOGLE_CONTACTS_COLLECTOR
from .docs import GOOGLE_DOCS_COLLECTOR
from .drive import GOOGLE_DRIVE_COLLECTOR
from .events import append_google_workspace_health, _append_dead_letter
from .gmail import GOOGLE_GMAIL_COLLECTOR
from .keep import GOOGLE_KEEP_COLLECTOR
from .meet import GOOGLE_MEET_COLLECTOR
from .sheets import GOOGLE_SHEETS_COLLECTOR
from .slides import GOOGLE_SLIDES_COLLECTOR
from .tasks import GOOGLE_TASKS_COLLECTOR


GOOGLE_WORKSPACE_APP_COLLECTORS: tuple[Any, ...] = (
    GOOGLE_DRIVE_COLLECTOR,
    GOOGLE_DOCS_COLLECTOR,
    GOOGLE_SHEETS_COLLECTOR,
    GOOGLE_SLIDES_COLLECTOR,
    GOOGLE_GMAIL_COLLECTOR,
    GOOGLE_CALENDAR_COLLECTOR,
    GOOGLE_MEET_COLLECTOR,
    GOOGLE_CHAT_COLLECTOR,
    GOOGLE_CONTACTS_COLLECTOR,
    GOOGLE_TASKS_COLLECTOR,
    GOOGLE_KEEP_COLLECTOR,
)


def google_workspace_app_status_records() -> list[dict[str, Any]]:
    return [_collector_status_record(collector) for collector in GOOGLE_WORKSPACE_APP_COLLECTORS]


def run_google_workspace_source_tick(config: AgentConfig, *, dry_run: bool = False) -> dict[str, Any]:
    normalized = config.normalized()
    event_log = CollectorEventLog(normalized.collector_events_db_path)
    state = event_log.consumer_state(GOOGLE_WORKSPACE_CONSUMER)
    source_state = state.setdefault("sources", {}).setdefault(GOOGLE_WORKSPACE_PROVIDER_ID, {})
    app_states = source_state.setdefault("apps", {})
    runtime = ConnectorRuntime(normalized)
    readiness = runtime.readiness(GOOGLE_WORKSPACE_PROVIDER_ID)
    source_state["last_tick_at"] = _utc_now()
    source_state["tick_count"] = int(source_state.get("tick_count") or 0) + 1
    source_state["collector_owner"] = "humungousaur.collectors.sources.google"
    if not readiness.get("collector_ready"):
        result = {
            "provider_id": GOOGLE_WORKSPACE_PROVIDER_ID,
            "status": "permission_denied",
            "events_appended": 0,
            "last_tick_at": source_state["last_tick_at"],
            "connector_readiness": readiness,
            "apps": [],
        }
        if not dry_run:
            append_google_workspace_health(
                normalized,
                {
                    "status": "permission_denied",
                    "message": "Google Workspace connector is not connected.",
                    "metadata": {"last_tick_at": source_state["last_tick_at"]},
                },
            )
            event_log.save_consumer_state(GOOGLE_WORKSPACE_CONSUMER, state)
        return {"status": "succeeded", "sources": [result], "source_count": 1, "dry_run": dry_run}

    _refresh_if_needed(runtime, readiness)
    readiness = runtime.readiness(GOOGLE_WORKSPACE_PROVIDER_ID)
    app_results: list[dict[str, Any]] = []
    total_events = 0
    for collector in GOOGLE_WORKSPACE_APP_COLLECTORS:
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
                    max_events=GOOGLE_WORKSPACE_MAX_EVENTS_PER_APP,
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
        append_google_workspace_health(
            normalized,
            {
                "status": source_status,
                "message": "Google Workspace app collectors tick completed.",
                "metadata": {
                    "last_tick_at": source_state["last_tick_at"],
                    "events_appended": total_events,
                    "app_count": len(app_results),
                },
            },
        )
        event_log.save_consumer_state(GOOGLE_WORKSPACE_CONSUMER, state)
    return {
        "status": "succeeded",
        "sources": [
            {
                "provider_id": GOOGLE_WORKSPACE_PROVIDER_ID,
                "status": source_status,
                "events_appended": total_events,
                "last_tick_at": source_state["last_tick_at"],
                "poller_supported": True,
                "webhook_supported": True,
                "connector_readiness": runtime.readiness(GOOGLE_WORKSPACE_PROVIDER_ID),
                "apps": app_results,
            }
        ],
        "source_count": 1,
        "dry_run": dry_run,
    }


__all__ = [
    "GOOGLE_WORKSPACE_APP_COLLECTORS",
    "google_workspace_app_status_records",
    "run_google_workspace_source_tick",
]
