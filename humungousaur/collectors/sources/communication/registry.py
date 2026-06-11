from __future__ import annotations

from typing import Any

from humungousaur.collectors.event_log import CollectorEventLog
from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime

from .common import (
    COMMUNICATION_CONSUMER,
    COMMUNICATION_MAX_EVENTS_PER_APP,
    COMMUNICATION_SOURCE_ID,
    _aggregate_app_status,
    _collector_status_record,
    _utc_now,
)
from .discord import DISCORD_COLLECTOR
from .events import append_communication_health, _append_dead_letter
from .gmail import GMAIL_COMMUNICATION_COLLECTOR
from .google_chat import GOOGLE_CHAT_COLLECTOR
from .outlook import OUTLOOK_COMMUNICATION_COLLECTOR
from .signal import SIGNAL_COLLECTOR
from .slack import SLACK_COLLECTOR
from .teams import MICROSOFT_TEAMS_COLLECTOR
from .telegram import TELEGRAM_COLLECTOR
from .whatsapp import WHATSAPP_COLLECTOR


COMMUNICATION_APP_COLLECTORS: tuple[Any, ...] = (
    SLACK_COLLECTOR,
    MICROSOFT_TEAMS_COLLECTOR,
    DISCORD_COLLECTOR,
    GOOGLE_CHAT_COLLECTOR,
    GMAIL_COMMUNICATION_COLLECTOR,
    OUTLOOK_COMMUNICATION_COLLECTOR,
    TELEGRAM_COLLECTOR,
    WHATSAPP_COLLECTOR,
    SIGNAL_COLLECTOR,
)


def communication_app_status_records() -> list[dict[str, Any]]:
    return [_collector_status_record(collector) for collector in COMMUNICATION_APP_COLLECTORS]


def run_communication_source_tick(config: AgentConfig, *, dry_run: bool = False) -> dict[str, Any]:
    normalized = config.normalized()
    event_log = CollectorEventLog(normalized.collector_events_db_path)
    state = event_log.consumer_state(COMMUNICATION_CONSUMER)
    source_state = state.setdefault("sources", {}).setdefault(COMMUNICATION_SOURCE_ID, {})
    app_states = source_state.setdefault("apps", {})
    source_state["last_tick_at"] = _utc_now()
    source_state["tick_count"] = int(source_state.get("tick_count") or 0) + 1
    source_state["collector_owner"] = "humungousaur.collectors.sources.communication"
    runtime = ConnectorRuntime(normalized)
    app_results: list[dict[str, Any]] = []
    total_events = 0
    for collector in COMMUNICATION_APP_COLLECTORS:
        app_state = app_states.setdefault(collector.app, {})
        try:
            readiness = runtime.readiness(collector.provider_id)
            readiness["connection_ready"] = bool(readiness.get("connected"))
            app_result = collector.collect(
                readiness,
                app_state,
                dry_run=dry_run,
                max_events=COMMUNICATION_MAX_EVENTS_PER_APP,
            )
        except Exception as exc:
            _append_dead_letter(
                normalized,
                {"app": collector.app, "provider_id": collector.provider_id, "state_keys": sorted(app_state.keys())},
                f"{type(exc).__name__}: {exc}",
            )
            app_result = {
                "app": collector.app,
                "provider_id": collector.provider_id,
                "status": "failed",
                "message": str(exc),
                "events_appended": 0,
                "source_channel": collector.source_channel,
                "implementation_level": collector.implementation_level,
            }
        app_results.append(app_result)
        total_events += int(app_result.get("events_appended") or 0)
    source_status = _aggregate_app_status(app_results)
    if not dry_run:
        for result in app_results:
            append_communication_health(
                normalized,
                {
                    "app": result["app"],
                    "provider_id": result["provider_id"],
                    "status": result["status"],
                    "message": result["message"],
                    "metadata": {
                        "last_tick_at": source_state["last_tick_at"],
                        "source_channel": result.get("source_channel", ""),
                        "events_appended": result.get("events_appended", 0),
                    },
                },
            )
        event_log.save_consumer_state(COMMUNICATION_CONSUMER, state)
    return {
        "status": "succeeded",
        "sources": [
            {
                "provider_id": COMMUNICATION_SOURCE_ID,
                "status": source_status,
                "events_appended": total_events,
                "last_tick_at": source_state["last_tick_at"],
                "poller_supported": any(bool(collector.poller_supported) for collector in COMMUNICATION_APP_COLLECTORS),
                "webhook_supported": any(bool(collector.webhook_supported) for collector in COMMUNICATION_APP_COLLECTORS),
                "apps": app_results,
            }
        ],
        "source_count": 1,
        "dry_run": dry_run,
    }


__all__ = [
    "COMMUNICATION_APP_COLLECTORS",
    "communication_app_status_records",
    "run_communication_source_tick",
]
