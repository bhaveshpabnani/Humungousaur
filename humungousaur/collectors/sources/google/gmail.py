from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime

from .common import GOOGLE_WORKSPACE_GMAIL_SCOPE, _app_result, _connector_request, _utc_now
from .events import append_google_workspace_event


class GmailCollector:
    app = "gmail"
    required_scopes = (GOOGLE_WORKSPACE_GMAIL_SCOPE,)
    description = "Polls Gmail history cursors for metadata-only message, send, label, and delete events."
    source_channel = "gmail_history"
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
            return _app_result("gmail", "running", "Dry run skipped Gmail API calls.", cursor=app_state.get("history_id", ""), source_channel=self.source_channel)
        history_id = str(app_state.get("history_id") or "").strip()
        if not history_id:
            response = _connector_request(
                runtime,
                operation="gmail_profile",
                path="/gmail/v1/users/me/profile",
                query={"fields": "historyId"},
                required_scopes=self.required_scopes,
            )
            baseline = str((response.get("response") or {}).get("historyId") or "")
            if baseline:
                app_state["history_id"] = baseline
                app_state["baseline_at"] = _utc_now()
            return _app_result("gmail", "running", "Gmail history baseline recorded.", cursor=baseline, source_channel=self.source_channel)

        response = _connector_request(
            runtime,
            operation="gmail_history_list",
            path="/gmail/v1/users/me/history",
            query={
                "startHistoryId": history_id,
                "maxResults": max_events,
                "fields": "history(id,messagesAdded(message(id,threadId,labelIds)),messagesDeleted(message(id,threadId,labelIds)),labelsAdded(message(id,threadId,labelIds),labelIds),labelsRemoved(message(id,threadId,labelIds),labelIds)),historyId,nextPageToken",
            },
            required_scopes=self.required_scopes,
        )
        body = response.get("response") if isinstance(response.get("response"), dict) else {}
        events_appended = 0
        for item in body.get("history") if isinstance(body.get("history"), list) else []:
            for event_payload in _gmail_history_item_to_events(item):
                if events_appended >= max_events:
                    break
                append_google_workspace_event(config, event_payload)
                events_appended += 1
        latest = str(body.get("historyId") or "")
        if latest:
            app_state["history_id"] = latest
        app_state["last_polled_at"] = _utc_now()
        return _app_result("gmail", "running", "Gmail history polled.", cursor=app_state.get("history_id", ""), events_appended=events_appended, source_channel=self.source_channel)


def _gmail_history_item_to_events(history_item: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for added in history_item.get("messagesAdded") if isinstance(history_item.get("messagesAdded"), list) else []:
        message = added.get("message") if isinstance(added, dict) and isinstance(added.get("message"), dict) else {}
        events.append(_gmail_message_to_event(message, history_item, "email_sent" if _has_label(message, "SENT") else "email_received"))
    for deleted in history_item.get("messagesDeleted") if isinstance(history_item.get("messagesDeleted"), list) else []:
        message = deleted.get("message") if isinstance(deleted, dict) and isinstance(deleted.get("message"), dict) else {}
        events.append(_gmail_message_to_event(message, history_item, "email_deleted"))
    for labels_added in history_item.get("labelsAdded") if isinstance(history_item.get("labelsAdded"), list) else []:
        message = labels_added.get("message") if isinstance(labels_added, dict) and isinstance(labels_added.get("message"), dict) else {}
        label_ids = {str(label) for label in labels_added.get("labelIds", []) if str(label)} if isinstance(labels_added, dict) else set()
        event_type = "email_deleted" if "TRASH" in label_ids else "email_labeled"
        events.append(_gmail_message_to_event(message, history_item, event_type, label_count=len(label_ids)))
    for labels_removed in history_item.get("labelsRemoved") if isinstance(history_item.get("labelsRemoved"), list) else []:
        message = labels_removed.get("message") if isinstance(labels_removed, dict) and isinstance(labels_removed.get("message"), dict) else {}
        label_ids = {str(label) for label in labels_removed.get("labelIds", []) if str(label)} if isinstance(labels_removed, dict) else set()
        event_type = "email_archived" if "INBOX" in label_ids else "email_labeled"
        events.append(_gmail_message_to_event(message, history_item, event_type, label_count=len(label_ids)))
    return events


def _gmail_message_to_event(
    message: dict[str, Any],
    history_item: dict[str, Any],
    event_type: str,
    *,
    label_count: int | None = None,
) -> dict[str, Any]:
    labels = {str(label) for label in message.get("labelIds", []) if str(label)}
    return {
        "app": "gmail",
        "event_type": event_type,
        "object_type": "email_message",
        "object_id": str(message.get("id") or ""),
        "event_id": str(message.get("id") or ""),
        "provider_event_id": f"gmail-history:{history_item.get('id') or ''}:{message.get('id') or ''}",
        "metadata": {
            "source_channel": "gmail_history",
            "thread_id": str(message.get("threadId") or ""),
            "label_count": len(labels) if label_count is None else label_count,
        },
    }


def _has_label(message: dict[str, Any], label_id: str) -> bool:
    return label_id in {str(label) for label in message.get("labelIds", []) if str(label)}


GOOGLE_GMAIL_COLLECTOR = GmailCollector()
