from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from .common import CommunicationBridgeCollector, _require_connector_ready
from .events import append_communication_event


DISCORD_COLLECTOR = CommunicationBridgeCollector(
    app="discord",
    provider_id="discord",
    display_name="Discord",
    required_scopes=("bot", "messages.read"),
    description="Collects Discord message, edit/delete, thread, channel/server navigation, presence, and attachment metadata from Gateway dispatch events or browser/native bridge ingress.",
    source_channel="gateway_events+browser_extension+native_bridge",
    docs_url="https://docs.discord.com/developers/events/gateway-events",
)


def append_discord_gateway_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Discord Gateway dispatch event into communication metadata."""

    _require_connector_ready(config, "discord")
    dispatch_type = str(payload.get("t") or payload.get("event_type") or "").upper()
    data = payload.get("d") if isinstance(payload.get("d"), dict) else payload
    event_type = _discord_event_type(dispatch_type, data)
    metadata = {
        "guild_id": data.get("guild_id"),
        "channel_id": data.get("channel_id") or data.get("id"),
        "thread_id": data.get("thread_id"),
        "author_id": (data.get("author") or {}).get("id") if isinstance(data.get("author"), dict) else data.get("user_id"),
        "webhook_id": data.get("webhook_id"),
        "gateway_sequence": payload.get("s"),
        "attachment_count": len(data.get("attachments") or []),
        "mention_count": len(data.get("mentions") or []),
    }
    return append_communication_event(
        config,
        {
            "app": "discord",
            "provider_id": "discord",
            "event_type": event_type,
            "message_id": data.get("id") or payload.get("s"),
            "thread_id": data.get("thread_id"),
            "channel_id": data.get("channel_id"),
            "metadata": metadata,
            "source_channel": "discord_gateway",
            "occurred_at": str(data.get("timestamp") or data.get("edited_timestamp") or ""),
        },
    )


def _discord_event_type(dispatch_type: str, data: dict[str, Any]) -> str:
    if dispatch_type == "MESSAGE_CREATE":
        if data.get("thread_id"):
            return "thread_reply"
        if data.get("attachments"):
            return "attachment_added"
        return "message_received"
    if dispatch_type == "MESSAGE_UPDATE":
        return "message_edited"
    if dispatch_type == "MESSAGE_DELETE":
        return "message_deleted"
    if dispatch_type in {"THREAD_CREATE", "THREAD_UPDATE"}:
        return "thread_opened"
    if dispatch_type == "THREAD_DELETE":
        return "thread_resolved"
    if dispatch_type == "PRESENCE_UPDATE":
        return "presence_changed"
    raise ValueError(f"unsupported Discord Gateway communication event: {dispatch_type or '<event>'}")
