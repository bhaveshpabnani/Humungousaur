from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime

from .common import GOOGLE_WORKSPACE_KEEP_SCOPE, _app_result, _connector_request, _scope_gated_result, _utc_now
from .events import append_google_workspace_event


class KeepCollector:
    app = "keep"
    required_scopes = (GOOGLE_WORKSPACE_KEEP_SCOPE,)
    description = "Polls Google Keep note metadata when scoped, and accepts note/checklist webhook or add-on events."
    source_channel = "keep_api+webhook"
    implementation_level = "scope_gated_poller_and_webhook_ingress"
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
        gated = _scope_gated_result(self.app, readiness, self.required_scopes, self.source_channel)
        if gated is not None:
            return gated
        if dry_run:
            return _app_result("keep", "running", "Dry run skipped Google Keep API calls.", cursor=app_state.get("baseline_at", ""), source_channel=self.source_channel, implementation_level=self.implementation_level)
        if not app_state.get("baseline_at"):
            app_state["baseline_at"] = _utc_now()
            app_state.setdefault("seen_notes", {})
            return _app_result("keep", "running", "Google Keep note baseline recorded.", cursor=app_state["baseline_at"], source_channel=self.source_channel, implementation_level=self.implementation_level)

        response = _connector_request(
            runtime,
            operation="keep_notes_list",
            path="/keep/v1/notes",
            query={"pageSize": max_events, "fields": "notes(name,createTime,updateTime,trashTime),nextPageToken"},
            required_scopes=self.required_scopes,
        )
        body = response.get("response") if isinstance(response.get("response"), dict) else {}
        seen = app_state.setdefault("seen_notes", {})
        if not isinstance(seen, dict):
            seen = {}
            app_state["seen_notes"] = seen
        events_appended = 0
        for item in body.get("notes") if isinstance(body.get("notes"), list) else []:
            if events_appended >= max_events:
                break
            note_id = str(item.get("name") or "")
            updated = str(item.get("updateTime") or item.get("createTime") or "")
            if not note_id or seen.get(note_id) == updated:
                continue
            append_google_workspace_event(config, _keep_note_to_event(item, created=note_id not in seen))
            seen[note_id] = updated
            events_appended += 1
        app_state["last_polled_at"] = _utc_now()
        return _app_result("keep", "running", "Google Keep note metadata polled.", cursor=app_state.get("baseline_at", ""), events_appended=events_appended, source_channel=self.source_channel, implementation_level=self.implementation_level)


def _keep_note_to_event(item: Any, *, created: bool) -> dict[str, Any]:
    payload = item if isinstance(item, dict) else {}
    event_type = "note_deleted" if payload.get("trashTime") else "note_created" if created else "note_edited"
    note_id = str(payload.get("name") or "")
    occurred_at = str(payload.get("trashTime") or payload.get("updateTime") or payload.get("createTime") or "")
    return {
        "app": "keep",
        "event_type": event_type,
        "object_type": "note",
        "object_id": note_id,
        "provider_event_id": f"keep:{note_id}:{occurred_at}",
        "occurred_at": occurred_at,
        "metadata": {
            "source_channel": "keep_api",
            "trashed": bool(payload.get("trashTime")),
        },
    }


GOOGLE_KEEP_COLLECTOR = KeepCollector()
