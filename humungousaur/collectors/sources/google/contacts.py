from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime

from .common import GOOGLE_WORKSPACE_CONTACTS_SCOPE, _app_result, _connector_request, _scope_gated_result, _utc_now
from .events import append_google_workspace_event


class ContactsCollector:
    app = "contacts"
    required_scopes = (GOOGLE_WORKSPACE_CONTACTS_SCOPE,)
    description = "Polls Google Contacts/People metadata when scoped, and accepts contact webhook or extension events."
    source_channel = "people_api+webhook"
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
            return _app_result("contacts", "running", "Dry run skipped Google Contacts API calls.", cursor=app_state.get("baseline_at", ""), source_channel=self.source_channel, implementation_level=self.implementation_level)
        if not app_state.get("baseline_at"):
            app_state["baseline_at"] = _utc_now()
            app_state.setdefault("seen_people", {})
            return _app_result("contacts", "running", "Google Contacts baseline recorded.", cursor=app_state["baseline_at"], source_channel=self.source_channel, implementation_level=self.implementation_level)

        response = _connector_request(
            runtime,
            operation="contacts_connections_list",
            path="https://people.googleapis.com/v1/people/me/connections",
            query={
                "pageSize": max_events,
                "personFields": "metadata",
                "fields": "connections(resourceName,metadata(sources(updateTime,type))),nextPageToken",
            },
            required_scopes=self.required_scopes,
        )
        body = response.get("response") if isinstance(response.get("response"), dict) else {}
        seen = app_state.setdefault("seen_people", {})
        if not isinstance(seen, dict):
            seen = {}
            app_state["seen_people"] = seen
        events_appended = 0
        for item in body.get("connections") if isinstance(body.get("connections"), list) else []:
            if events_appended >= max_events:
                break
            contact_id, updated = _contact_identity(item)
            if not contact_id or seen.get(contact_id) == updated:
                continue
            append_google_workspace_event(config, _contact_to_event(contact_id, updated, created=contact_id not in seen))
            seen[contact_id] = updated
            events_appended += 1
        app_state["last_polled_at"] = _utc_now()
        return _app_result("contacts", "running", "Google Contacts metadata polled.", cursor=app_state.get("baseline_at", ""), events_appended=events_appended, source_channel=self.source_channel, implementation_level=self.implementation_level)


def _contact_identity(item: Any) -> tuple[str, str]:
    payload = item if isinstance(item, dict) else {}
    contact_id = str(payload.get("resourceName") or "")
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    sources = metadata.get("sources") if isinstance(metadata.get("sources"), list) else []
    updated = ""
    for source in sources:
        if isinstance(source, dict):
            updated = max(updated, str(source.get("updateTime") or ""))
    return contact_id, updated


def _contact_to_event(contact_id: str, updated: str, *, created: bool) -> dict[str, Any]:
    return {
        "app": "contacts",
        "event_type": "contact_created" if created else "contact_updated",
        "object_type": "contact",
        "object_id": contact_id,
        "contact_id": contact_id,
        "provider_event_id": f"contacts:{contact_id}:{updated}",
        "occurred_at": updated,
        "metadata": {"source_channel": "people_api"},
    }


GOOGLE_CONTACTS_COLLECTOR = ContactsCollector()
