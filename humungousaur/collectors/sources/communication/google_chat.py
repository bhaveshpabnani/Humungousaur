from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from .common import CommunicationBridgeCollector, _require_connector_ready
from .events import append_communication_event


GOOGLE_CHAT_COLLECTOR = CommunicationBridgeCollector(
    app="google_chat",
    provider_id="google_workspace",
    display_name="Google Chat",
    required_scopes=("https://www.googleapis.com/auth/chat.messages.readonly",),
    description="Collects Google Chat message, mention, thread, reaction, and space metadata from Workspace Events, Chat app events, Pub/Sub, or local bridge ingress.",
    source_channel="workspace_events+chat_app_events+pubsub+local_bridge",
    docs_url="https://developers.google.com/workspace/chat/events-overview",
)


def append_google_chat_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Google Chat event into communication collector metadata."""

    _require_connector_ready(config, "google_workspace")
    event_type = _google_chat_event_type(payload)
    message = payload.get("message") if isinstance(payload.get("message"), dict) else {}
    space = payload.get("space") if isinstance(payload.get("space"), dict) else {}
    thread = message.get("thread") if isinstance(message.get("thread"), dict) else payload.get("thread") if isinstance(payload.get("thread"), dict) else {}
    metadata = {
        "event_type": payload.get("eventType") or payload.get("type"),
        "space_id": space.get("name") or payload.get("space_id"),
        "message_id": message.get("name") or payload.get("message_id"),
        "thread_id": thread.get("name") if isinstance(thread, dict) else "",
        "sender_id": (message.get("sender") or {}).get("name") if isinstance(message.get("sender"), dict) else "",
        "attachment_count": len(message.get("attachment") or message.get("attachments") or []),
        "reaction_count": len(payload.get("reactions") or []),
        "pubsub_message_id": payload.get("messageId"),
    }
    return append_communication_event(
        config,
        {
            "app": "google_chat",
            "provider_id": "google_workspace",
            "source_event": _google_chat_source_event(event_type),
            "event_type": event_type,
            "message_id": metadata["message_id"] or payload.get("event_id"),
            "thread_id": metadata["thread_id"],
            "conversation_id": metadata["space_id"],
            "metadata": metadata,
            "source_channel": "google_chat_events",
            "occurred_at": str(payload.get("eventTime") or payload.get("createTime") or ""),
        },
    )


def _google_chat_event_type(payload: dict[str, Any]) -> str:
    event = str(payload.get("eventType") or payload.get("type") or payload.get("event_type") or "").lower()
    if "reaction" in event:
        return "reaction_added"
    if "mention" in event:
        return "mention_received"
    if "space" in event and ("opened" in event or "selected" in event):
        return "channel_opened"
    if "presence" in event:
        return "presence_changed"
    message = payload.get("message") if isinstance(payload.get("message"), dict) else {}
    if message.get("thread"):
        return "thread_reply_received"
    return "message_received"


def _google_chat_source_event(event_type: str) -> str:
    return {
        "message_received": "chat_message_received",
        "message_sent": "chat_message_sent",
        "mention_received": "chat_mention_received",
        "thread_reply_received": "chat_thread_reply_received",
        "reaction_added": "chat_reaction_added",
        "channel_opened": "chat_space_opened",
        "presence_changed": "chat_presence_changed",
    }[event_type]
