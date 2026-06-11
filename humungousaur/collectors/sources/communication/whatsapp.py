from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from .common import CommunicationBridgeCollector, _require_connector_ready
from .events import append_communication_event


WHATSAPP_COLLECTOR = CommunicationBridgeCollector(
    app="whatsapp",
    provider_id="whatsapp",
    display_name="WhatsApp",
    required_scopes=("whatsapp_business_messaging",),
    description="Collects WhatsApp message, status, edit/delete where available, conversation, presence-like delivery/read, and attachment metadata from Cloud API webhooks or a paired local bridge.",
    source_channel="cloud_api_webhook+paired_local_bridge",
    docs_url="https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/overview/",
)


def append_whatsapp_cloud_webhook(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a WhatsApp Cloud API webhook change into chat metadata."""

    _require_connector_ready(config, "whatsapp")
    change = _first_whatsapp_change(payload)
    value = change.get("value") if isinstance(change.get("value"), dict) else change
    message = _first(value.get("messages"))
    status = _first(value.get("statuses"))
    if message:
        message_type = str(message.get("type") or "text")
        event_type = "attachment_added" if message_type not in {"text", "button", "interactive"} else "message_received"
        object_id = message.get("id")
        occurred_at = str(message.get("timestamp") or "")
    elif status:
        event_type = "status_changed"
        object_id = status.get("id")
        occurred_at = str(status.get("timestamp") or "")
    else:
        raise ValueError("unsupported WhatsApp webhook without message or status metadata")
    metadata = {
        "phone_number_id": (value.get("metadata") or {}).get("phone_number_id") if isinstance(value.get("metadata"), dict) else "",
        "business_account_id": payload.get("entry", [{}])[0].get("id") if isinstance(payload.get("entry"), list) and payload.get("entry") else "",
        "message_type": message.get("type") if message else "",
        "status": status.get("status") if status else "",
        "conversation_id": (status.get("conversation") or {}).get("id") if isinstance(status, dict) and isinstance(status.get("conversation"), dict) else "",
        "contact_count": len(value.get("contacts") or []),
        "has_media": bool(message and message.get(str(message.get("type") or ""))),
    }
    return append_communication_event(
        config,
        {
            "app": "whatsapp",
            "provider_id": "whatsapp",
            "event_type": event_type,
            "message_id": object_id,
            "conversation_id": metadata.get("conversation_id"),
            "metadata": metadata,
            "source_channel": "whatsapp_cloud_api_webhook",
            "occurred_at": occurred_at,
        },
    )


def _first_whatsapp_change(payload: dict[str, Any]) -> dict[str, Any]:
    entries = payload.get("entry")
    if isinstance(entries, list) and entries:
        changes = entries[0].get("changes") if isinstance(entries[0], dict) else None
        if isinstance(changes, list) and changes and isinstance(changes[0], dict):
            return changes[0]
    return payload


def _first(value: Any) -> dict[str, Any]:
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    return {}
