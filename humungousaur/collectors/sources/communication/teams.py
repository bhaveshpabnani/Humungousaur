from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from .common import CommunicationBridgeCollector, _require_connector_ready
from .events import append_communication_event


MICROSOFT_TEAMS_COLLECTOR = CommunicationBridgeCollector(
    app="teams",
    provider_id="msteams",
    display_name="Microsoft Teams",
    required_scopes=("ChannelMessage.Read.All", "Chat.Read", "Presence.Read"),
    description="Collects Microsoft Teams message, edit/delete, thread, channel/team navigation, presence/DND, and attachment metadata from Graph change notifications, Teams app events, or browser/native bridge ingress.",
    source_channel="graph_change_notifications+teams_app+browser_extension+native_bridge",
    docs_url="https://learn.microsoft.com/en-us/graph/teams-changenotifications-chatmessage",
)


def append_teams_graph_chat_notification(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize one Microsoft Graph Teams chat/channel change notification."""

    _require_connector_ready(config, "msteams")
    notification = _first_notification(payload)
    resource_data = notification.get("resourceData") if isinstance(notification.get("resourceData"), dict) else {}
    resource = str(notification.get("resource") or resource_data.get("@odata.id") or "")
    change_type = str(notification.get("changeType") or "").lower()
    event_type = {
        "created": "message_received",
        "updated": "message_edited",
        "deleted": "message_deleted",
    }.get(change_type, "message_received")
    metadata = {
        "tenant_id": notification.get("tenantId"),
        "subscription_id": notification.get("subscriptionId"),
        "client_state_present": bool(notification.get("clientState")),
        "resource_type": resource_data.get("@odata.type") or _teams_resource_kind(resource),
        "resource": resource,
        "change_type": change_type,
        "encrypted_content_omitted": bool(notification.get("encryptedContent")),
    }
    return append_communication_event(
        config,
        {
            "app": "teams",
            "provider_id": "msteams",
            "event_type": event_type,
            "message_id": resource_data.get("id") or _last_segment(resource),
            "conversation_id": _teams_conversation_id(resource),
            "metadata": metadata,
            "source_channel": "microsoft_graph_change_notification",
            "occurred_at": str(notification.get("subscriptionExpirationDateTime") or ""),
        },
    )


def _first_notification(payload: dict[str, Any]) -> dict[str, Any]:
    values = payload.get("value")
    if isinstance(values, list) and values and isinstance(values[0], dict):
        return values[0]
    return payload


def _teams_resource_kind(resource: str) -> str:
    if "/channels/" in resource:
        return "channel_message"
    if "/chats/" in resource:
        return "chat_message"
    return "teams_message"


def _teams_conversation_id(resource: str) -> str:
    parts = [part for part in resource.split("/") if part]
    for key in ("chats", "channels", "teams"):
        if key in parts:
            index = parts.index(key)
            if index + 1 < len(parts):
                return parts[index + 1]
    return ""


def _last_segment(resource: str) -> str:
    parts = [part for part in resource.split("/") if part]
    return parts[-1] if parts else ""
