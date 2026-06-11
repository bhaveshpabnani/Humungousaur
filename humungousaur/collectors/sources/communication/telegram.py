from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from .common import CommunicationBridgeCollector, _require_connector_ready
from .events import append_communication_event


TELEGRAM_COLLECTOR = CommunicationBridgeCollector(
    app="telegram",
    provider_id="telegram",
    display_name="Telegram",
    required_scopes=("bot_token",),
    description="Collects Telegram message, edit, channel post, topic/thread, chat navigation, and attachment metadata from Bot API webhooks, long polling, or local bridge ingress.",
    source_channel="bot_api_webhook+long_polling+local_bridge",
    docs_url="https://core.telegram.org/bots/api",
    implementation_level="poller_or_webhook_ingress",
    poller_supported=True,
    webhook_supported=True,
)


def append_telegram_bot_update(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Telegram Bot API Update from webhook or getUpdates."""

    _require_connector_ready(config, "telegram")
    message_key, message = _telegram_message(payload)
    event_type = "message_edited" if message_key.startswith("edited_") else "message_received"
    if _telegram_has_attachment(message):
        event_type = "attachment_added"
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    metadata = {
        "update_id": payload.get("update_id"),
        "message_id": message.get("message_id"),
        "chat_id": chat.get("id"),
        "chat_type": chat.get("type"),
        "from_id": (message.get("from") or {}).get("id") if isinstance(message.get("from"), dict) else "",
        "message_thread_id": message.get("message_thread_id"),
        "has_media": _telegram_has_attachment(message),
        "attachment_count": 1 if _telegram_has_attachment(message) else 0,
    }
    return append_communication_event(
        config,
        {
            "app": "telegram",
            "provider_id": "telegram",
            "event_type": event_type,
            "message_id": message.get("message_id") or payload.get("update_id"),
            "thread_id": message.get("message_thread_id"),
            "conversation_id": chat.get("id"),
            "metadata": metadata,
            "source_channel": "telegram_bot_api",
            "occurred_at": str(message.get("date") or ""),
        },
    )


def _telegram_message(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    for key in ("message", "edited_message", "channel_post", "edited_channel_post"):
        value = payload.get(key)
        if isinstance(value, dict):
            return key, value
    raise ValueError("unsupported Telegram update without message metadata")


def _telegram_has_attachment(message: dict[str, Any]) -> bool:
    return any(key in message for key in ("audio", "document", "photo", "sticker", "video", "voice", "video_note", "animation"))
