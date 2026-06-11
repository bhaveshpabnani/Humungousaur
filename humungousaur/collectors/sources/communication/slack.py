from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from .common import CommunicationBridgeCollector, _require_connector_ready
from .events import append_communication_event


SLACK_COLLECTOR = CommunicationBridgeCollector(
    app="slack",
    provider_id="slack",
    display_name="Slack",
    required_scopes=("channels:history", "channels:read", "files:read", "users:read"),
    description="Collects Slack message, draft, edit/delete, thread, workspace/channel navigation, presence/DND, and attachment metadata from Events API, Socket Mode, or browser/native bridge ingress.",
    source_channel="events_api+socket_mode+browser_extension+native_bridge",
    docs_url="https://docs.slack.dev/apis/events-api/",
)


def append_slack_events_api_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Slack Events API callback into a redacted collector event."""

    _require_connector_ready(config, "slack")
    if payload.get("type") == "url_verification":
        return {"accepted": False, "provider_id": "slack", "challenge_supported": True, "reason": "url_verification"}
    event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
    event_type = _slack_event_type(event)
    metadata = {
        "team_id": payload.get("team_id") or event.get("team"),
        "enterprise_id": payload.get("enterprise_id"),
        "channel_id": event.get("channel"),
        "user_id": event.get("user"),
        "bot_id": event.get("bot_id"),
        "slack_event_id": payload.get("event_id"),
        "has_files": bool(event.get("files")),
        "attachment_count": len(event.get("files") or event.get("attachments") or []),
        "thread_present": bool(event.get("thread_ts")),
    }
    return append_communication_event(
        config,
        {
            "app": "slack",
            "provider_id": "slack",
            "event_type": event_type,
            "message_id": event.get("client_msg_id") or event.get("ts") or payload.get("event_id"),
            "thread_id": event.get("thread_ts"),
            "channel_id": event.get("channel"),
            "metadata": metadata,
            "source_channel": "slack_events_api",
            "occurred_at": _slack_timestamp(event.get("event_ts") or event.get("ts")),
        },
    )


def _slack_event_type(event: dict[str, Any]) -> str:
    event_type = str(event.get("type") or "").strip()
    subtype = str(event.get("subtype") or "").strip()
    if event_type == "app_mention":
        return "mention_received"
    if event_type == "reaction_added":
        return "reaction_added"
    if event_type == "message":
        if subtype == "message_changed":
            return "message_edited"
        if subtype == "message_deleted":
            return "message_deleted"
        if subtype == "file_share" or event.get("files"):
            return "attachment_added"
        if event.get("thread_ts") and event.get("thread_ts") != event.get("ts"):
            return "thread_reply"
        return "message_received"
    raise ValueError(f"unsupported Slack Events API event: {event_type or '<type>'}")


def _slack_timestamp(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return str(float(text))
    except ValueError:
        return text
