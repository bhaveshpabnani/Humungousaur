from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime

from .common import (
    MICROSOFT_365_PRESENCE_SCOPE,
    MICROSOFT_365_TEAMS_CHAT_SCOPE,
    _app_result,
    _connector_request,
    _has_scopes,
    _utc_now,
)
from .events import append_microsoft_365_event


class TeamsCollector:
    app = "teams"
    required_scopes = (MICROSOFT_365_TEAMS_CHAT_SCOPE,)
    description = "Collects Teams chat, channel, thread, presence, meeting, and call-control metadata from Graph webhooks, app/browser ingress, and optional presence polling."
    source_channel = "teams_change_notifications+browser_extension+presence_api"
    implementation_level = "webhook_extension_and_scope_gated_presence_poller"
    poller_supported = True
    webhook_supported = True
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
        del max_events
        if not _has_scopes(readiness, (MICROSOFT_365_PRESENCE_SCOPE,)):
            app_state.setdefault("baseline_at", _utc_now())
            return _app_result("teams", "running", "Teams collector is ready for webhooks/app ingress; Presence.Read is not granted for presence polling.", cursor=app_state.get("baseline_at", ""), source_channel=self.source_channel, implementation_level=self.implementation_level)
        if dry_run:
            return _app_result("teams", "running", "Dry run skipped Teams presence call.", cursor=app_state.get("presence_sequence", ""), source_channel=self.source_channel, implementation_level=self.implementation_level)

        response = _connector_request(
            runtime,
            operation="teams_presence_get",
            path="/v1.0/me/presence",
            query={},
            required_scopes=(MICROSOFT_365_PRESENCE_SCOPE,),
        )
        body = response.get("response") if isinstance(response.get("response"), dict) else {}
        sequence = str(body.get("sequenceNumber") or body.get("availability") or body.get("activity") or "")
        previous = str(app_state.get("presence_sequence") or "")
        events_appended = 0
        if previous and sequence and sequence != previous:
            append_microsoft_365_event(config, _presence_to_event(body, sequence))
            events_appended = 1
        if sequence:
            app_state["presence_sequence"] = sequence
        app_state["last_polled_at"] = _utc_now()
        return _app_result("teams", "running", "Teams presence metadata polled.", cursor=app_state.get("presence_sequence", ""), events_appended=events_appended, source_channel=self.source_channel, implementation_level=self.implementation_level)


def _presence_to_event(payload: dict[str, Any], sequence: str) -> dict[str, Any]:
    return {
        "app": "teams",
        "event_type": "presence_changed",
        "object_type": "presence",
        "object_id": "me",
        "provider_event_id": f"teams-presence:{sequence}",
        "metadata": {
            "source_channel": "presence_api",
            "availability": str(payload.get("availability") or ""),
            "activity": str(payload.get("activity") or ""),
        },
    }


MICROSOFT_TEAMS_COLLECTOR = TeamsCollector()
