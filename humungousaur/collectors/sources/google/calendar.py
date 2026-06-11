from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime

from .common import GOOGLE_WORKSPACE_CALENDAR_SCOPE, _app_result, _connector_request, _utc_now
from .events import append_google_workspace_event


class CalendarCollector:
    app = "calendar"
    required_scopes = (GOOGLE_WORKSPACE_CALENDAR_SCOPE,)
    description = "Polls Google Calendar updated events for metadata-only scheduling changes."
    source_channel = "calendar_events"
    implementation_level = "poller"
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
        del readiness
        if dry_run:
            return _app_result("calendar", "running", "Dry run skipped Calendar API calls.", cursor=app_state.get("sync_token", ""), source_channel=self.source_channel)
        sync_token = str(app_state.get("sync_token") or "").strip()
        if not sync_token:
            page_token = str(app_state.get("page_token") or "").strip()
            query = {
                "timeMin": _utc_now(),
                "showDeleted": "true",
                "singleEvents": "true",
                "maxResults": max_events,
                "fields": "nextPageToken,nextSyncToken",
            }
            if page_token:
                query = {"pageToken": page_token, "fields": "nextPageToken,nextSyncToken"}
            response = _connector_request(
                runtime,
                operation="calendar_events_sync_baseline",
                path="/calendar/v3/calendars/primary/events",
                query=query,
                required_scopes=self.required_scopes,
            )
            body = response.get("response") if isinstance(response.get("response"), dict) else {}
            if body.get("nextSyncToken"):
                app_state["sync_token"] = str(body.get("nextSyncToken") or "")
                app_state.pop("page_token", None)
            elif body.get("nextPageToken"):
                app_state["page_token"] = str(body.get("nextPageToken") or "")
            app_state["baseline_at"] = _utc_now()
            return _app_result("calendar", "running", "Google Calendar sync cursor baseline recorded.", cursor=app_state.get("sync_token", app_state.get("page_token", "")), source_channel=self.source_channel)

        query = {
            "syncToken": sync_token,
            "showDeleted": "true",
            "maxResults": max_events,
            "fields": "items(id,status,updated,created,eventType,recurringEventId,hangoutLink,conferenceData(conferenceId,conferenceSolution(key(type)))),nextPageToken,nextSyncToken",
        }
        page_token = str(app_state.get("page_token") or "").strip()
        if page_token:
            query.pop("syncToken", None)
            query["pageToken"] = page_token
        response = _connector_request(
            runtime,
            operation="calendar_events_sync",
            path="/calendar/v3/calendars/primary/events",
            query=query,
            required_scopes=self.required_scopes,
        )
        body = response.get("response") if isinstance(response.get("response"), dict) else {}
        events_appended = 0
        for item in body.get("items") if isinstance(body.get("items"), list) else []:
            if events_appended >= max_events:
                break
            event_payload = _calendar_item_to_event(item)
            append_google_workspace_event(config, event_payload)
            events_appended += 1
        next_page = str(body.get("nextPageToken") or "")
        next_sync = str(body.get("nextSyncToken") or "")
        if next_page:
            app_state["page_token"] = next_page
        else:
            app_state.pop("page_token", None)
        if next_sync:
            app_state["sync_token"] = next_sync
        app_state["last_polled_at"] = _utc_now()
        return _app_result("calendar", "running", "Google Calendar sync events polled.", cursor=app_state.get("sync_token", ""), events_appended=events_appended, source_channel=self.source_channel)


def _calendar_item_to_event(item: Any) -> dict[str, Any]:
    payload = item if isinstance(item, dict) else {}
    status = str(payload.get("status") or "")
    created = str(payload.get("created") or "")
    updated = str(payload.get("updated") or "")
    event_type = "calendar_event_deleted" if status == "cancelled" else "calendar_event_created" if created and created == updated else "calendar_event_updated"
    conference_data = payload.get("conferenceData") if isinstance(payload.get("conferenceData"), dict) else {}
    return {
        "app": "calendar",
        "event_type": event_type,
        "object_type": "calendar_event",
        "object_id": str(payload.get("id") or ""),
        "event_id": str(payload.get("id") or ""),
        "provider_event_id": f"calendar-event:{payload.get('id') or ''}:{updated}",
        "occurred_at": updated,
        "metadata": {
            "source_channel": "calendar_events",
            "calendar_event_status": status,
            "is_recurring": bool(payload.get("recurringEventId")),
            "has_meet_link": bool(payload.get("hangoutLink") or conference_data),
        },
    }


GOOGLE_CALENDAR_COLLECTOR = CalendarCollector()
