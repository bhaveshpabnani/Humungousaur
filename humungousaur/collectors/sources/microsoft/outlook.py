from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime

from .common import (
    MICROSOFT_365_CALENDAR_SCOPE,
    MICROSOFT_365_MAIL_SCOPE,
    _app_result,
    _connector_request,
    _connector_request_from_link,
    _store_delta_cursor,
    _utc_now,
)
from .events import append_microsoft_365_event


class OutlookMailCollector:
    app = "outlook"
    required_scopes = (MICROSOFT_365_MAIL_SCOPE,)
    description = "Polls Outlook mail message delta cursors for metadata-only message, draft, flag, and delete events."
    source_channel = "graph_mail_delta"
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
            return _app_result("outlook", "running", "Dry run skipped Outlook mail delta calls.", cursor=app_state.get("delta_link", ""), source_channel=self.source_channel)
        delta_link = str(app_state.get("delta_link") or "").strip()
        if not delta_link:
            response = _connector_request(
                runtime,
                operation="outlook_mail_delta_baseline",
                path="/v1.0/me/mailFolders/inbox/messages/delta",
                query={
                    "$select": "id,conversationId,receivedDateTime,sentDateTime,lastModifiedDateTime,importance,isDraft,isRead,hasAttachments,categories,flag,parentFolderId",
                    "$top": max_events,
                },
                required_scopes=self.required_scopes,
            )
            body = response.get("response") if isinstance(response.get("response"), dict) else {}
            _store_delta_cursor(app_state, body)
            app_state["baseline_at"] = _utc_now()
            return _app_result("outlook", "running", "Outlook mail delta cursor baseline recorded.", cursor=app_state.get("delta_link", ""), source_channel=self.source_channel)

        response = _connector_request_from_link(runtime, operation="outlook_mail_delta", link=delta_link, required_scopes=self.required_scopes)
        body = response.get("response") if isinstance(response.get("response"), dict) else {}
        events_appended = 0
        for item in body.get("value") if isinstance(body.get("value"), list) else []:
            if events_appended >= max_events:
                break
            append_microsoft_365_event(config, _message_item_to_event(item))
            events_appended += 1
        _store_delta_cursor(app_state, body)
        app_state["last_polled_at"] = _utc_now()
        return _app_result("outlook", "running", "Outlook mail delta polled.", cursor=app_state.get("delta_link", ""), events_appended=events_appended, source_channel=self.source_channel)


class OutlookCalendarCollector:
    app = "calendar"
    required_scopes = (MICROSOFT_365_CALENDAR_SCOPE,)
    description = "Polls Outlook Calendar delta cursors for metadata-only scheduling and meeting changes."
    source_channel = "graph_calendar_delta"
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
            return _app_result("calendar", "running", "Dry run skipped Outlook Calendar delta calls.", cursor=app_state.get("delta_link", ""), source_channel=self.source_channel)
        delta_link = str(app_state.get("delta_link") or "").strip()
        if not delta_link:
            now = _utc_now()
            response = _connector_request(
                runtime,
                operation="outlook_calendar_delta_baseline",
                path="/v1.0/me/calendarView/delta",
                query={
                    "startDateTime": now,
                    "endDateTime": now[:4] + "-12-31T23:59:59Z",
                    "$select": "id,createdDateTime,lastModifiedDateTime,isCancelled,isOnlineMeeting,showAs,type,seriesMasterId",
                    "$top": max_events,
                },
                required_scopes=self.required_scopes,
            )
            body = response.get("response") if isinstance(response.get("response"), dict) else {}
            _store_delta_cursor(app_state, body)
            app_state["baseline_at"] = now
            return _app_result("calendar", "running", "Outlook Calendar delta cursor baseline recorded.", cursor=app_state.get("delta_link", ""), source_channel=self.source_channel)

        response = _connector_request_from_link(runtime, operation="outlook_calendar_delta", link=delta_link, required_scopes=self.required_scopes)
        body = response.get("response") if isinstance(response.get("response"), dict) else {}
        events_appended = 0
        for item in body.get("value") if isinstance(body.get("value"), list) else []:
            if events_appended >= max_events:
                break
            append_microsoft_365_event(config, _calendar_item_to_event(item))
            events_appended += 1
        _store_delta_cursor(app_state, body)
        app_state["last_polled_at"] = _utc_now()
        return _app_result("calendar", "running", "Outlook Calendar delta polled.", cursor=app_state.get("delta_link", ""), events_appended=events_appended, source_channel=self.source_channel)


def _message_item_to_event(item: Any) -> dict[str, Any]:
    payload = item if isinstance(item, dict) else {}
    message_id = str(payload.get("id") or "")
    removed = isinstance(payload.get("@removed"), dict)
    if removed:
        event_type = "email_deleted"
    elif bool(payload.get("isDraft")):
        event_type = "email_draft_updated"
    else:
        event_type = "important_email_received" if str(payload.get("importance") or "") == "high" else "email_received"
    occurred_at = str(payload.get("lastModifiedDateTime") or payload.get("receivedDateTime") or payload.get("sentDateTime") or "")
    flag = payload.get("flag") if isinstance(payload.get("flag"), dict) else {}
    categories = payload.get("categories") if isinstance(payload.get("categories"), list) else []
    return {
        "app": "outlook",
        "event_type": event_type,
        "object_type": "email_message",
        "object_id": message_id,
        "message_id": message_id,
        "provider_event_id": f"outlook-mail:{message_id}:{occurred_at}:{removed}",
        "occurred_at": occurred_at,
        "metadata": {
            "source_channel": "graph_mail_delta",
            "thread_id": str(payload.get("conversationId") or ""),
            "importance": str(payload.get("importance") or ""),
            "has_attachments": bool(payload.get("hasAttachments")),
            "is_read": bool(payload.get("isRead")),
            "flagged": bool(flag.get("flagStatus") and flag.get("flagStatus") != "notFlagged"),
            "category_count": len(categories),
            "deleted": removed,
        },
    }


def _calendar_item_to_event(item: Any) -> dict[str, Any]:
    payload = item if isinstance(item, dict) else {}
    event_id = str(payload.get("id") or "")
    removed = isinstance(payload.get("@removed"), dict) or bool(payload.get("isCancelled"))
    created = str(payload.get("createdDateTime") or "")
    updated = str(payload.get("lastModifiedDateTime") or "")
    event_type = "calendar_event_deleted" if removed else "calendar_event_created" if created and created == updated else "calendar_event_updated"
    return {
        "app": "calendar",
        "event_type": event_type,
        "object_type": "calendar_event",
        "object_id": event_id,
        "event_id": event_id,
        "provider_event_id": f"outlook-calendar:{event_id}:{updated}:{removed}",
        "occurred_at": updated or created,
        "metadata": {
            "source_channel": "graph_calendar_delta",
            "calendar_event_status": "cancelled" if removed else "confirmed",
            "is_online_meeting": bool(payload.get("isOnlineMeeting")),
            "is_recurring": bool(payload.get("seriesMasterId")),
            "show_as": str(payload.get("showAs") or ""),
            "event_type": str(payload.get("type") or ""),
        },
    }


MICROSOFT_OUTLOOK_COLLECTOR = OutlookMailCollector()
MICROSOFT_OUTLOOK_CALENDAR_COLLECTOR = OutlookCalendarCollector()
