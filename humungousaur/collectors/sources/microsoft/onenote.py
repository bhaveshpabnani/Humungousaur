from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime

from .common import MICROSOFT_365_ONENOTE_SCOPE, _app_result, _connector_request, _scope_gated_result, _utc_now
from .events import append_microsoft_365_event


class OneNoteCollector:
    app = "onenote"
    required_scopes = (MICROSOFT_365_ONENOTE_SCOPE,)
    description = "Polls OneNote page metadata when scoped, and accepts note/page events from add-ins or webhook relays."
    source_channel = "graph_onenote_pages+addin+webhook"
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
            return _app_result("onenote", "running", "Dry run skipped OneNote pages call.", cursor=app_state.get("modified_min", ""), source_channel=self.source_channel, implementation_level=self.implementation_level)
        modified_min = str(app_state.get("modified_min") or "").strip()
        if not modified_min:
            app_state["modified_min"] = _utc_now()
            app_state["baseline_at"] = app_state["modified_min"]
            return _app_result("onenote", "running", "OneNote modified baseline recorded.", cursor=app_state["modified_min"], source_channel=self.source_channel, implementation_level=self.implementation_level)

        response = _connector_request(
            runtime,
            operation="onenote_pages_list",
            path="/v1.0/me/onenote/pages",
            query={
                "$select": "id,createdDateTime,lastModifiedDateTime,level,order,parentSection",
                "$top": max_events,
                "$orderby": "lastModifiedDateTime desc",
            },
            required_scopes=self.required_scopes,
        )
        body = response.get("response") if isinstance(response.get("response"), dict) else {}
        events_appended = 0
        max_modified = modified_min
        for item in body.get("value") if isinstance(body.get("value"), list) else []:
            if events_appended >= max_events:
                break
            modified = str(item.get("lastModifiedDateTime") or "")
            if modified and modified <= modified_min:
                continue
            append_microsoft_365_event(config, _page_to_event(item))
            events_appended += 1
            max_modified = max(max_modified, modified)
        app_state["modified_min"] = max_modified or _utc_now()
        app_state["last_polled_at"] = _utc_now()
        return _app_result("onenote", "running", "OneNote page metadata polled.", cursor=app_state.get("modified_min", ""), events_appended=events_appended, source_channel=self.source_channel, implementation_level=self.implementation_level)


def _page_to_event(item: Any) -> dict[str, Any]:
    payload = item if isinstance(item, dict) else {}
    page_id = str(payload.get("id") or "")
    created = str(payload.get("createdDateTime") or "")
    modified = str(payload.get("lastModifiedDateTime") or "")
    return {
        "app": "onenote",
        "event_type": "note_created" if created and created == modified else "note_edited",
        "object_type": "note_page",
        "object_id": page_id,
        "page_id": page_id,
        "provider_event_id": f"onenote-page:{page_id}:{modified}",
        "occurred_at": modified or created,
        "metadata": {
            "source_channel": "graph_onenote_pages",
            "page_level": payload.get("level", 0),
            "page_order": payload.get("order", 0),
            "has_parent_section": bool(payload.get("parentSection")),
        },
    }


MICROSOFT_ONENOTE_COLLECTOR = OneNoteCollector()
