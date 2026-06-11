from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any

from humungousaur.collectors.event_log import CollectorEventLog
from humungousaur.collectors.models import CollectorEvent
from humungousaur.config import AgentConfig

from ..workspace_connectors import (
    append_connector_source_event,
    connector_source_status,
    record_connector_source_health,
    safe_metadata_values,
)
from .common import COMMUNICATION_SOURCE_ID


_APP_ALIASES = {
    "slack": "slack",
    "microsoft_teams": "teams",
    "ms_teams": "teams",
    "msteams": "teams",
    "teams": "teams",
    "discord": "discord",
    "google_chat": "google_chat",
    "googlechat": "google_chat",
    "gmail": "gmail",
    "google_mail": "gmail",
    "outlook": "outlook",
    "outlook_mail": "outlook",
    "telegram": "telegram",
    "whatsapp": "whatsapp",
    "signal": "signal",
}

_APP_PROVIDER_IDS = {
    "slack": "slack",
    "teams": "msteams",
    "discord": "discord",
    "google_chat": "google_workspace",
    "gmail": "google_workspace",
    "outlook": "microsoft_365",
    "telegram": "telegram",
    "whatsapp": "whatsapp",
    "signal": "signal",
}

_APP_DISPLAY_NAMES = {
    "slack": "Slack",
    "teams": "Microsoft Teams",
    "discord": "Discord",
    "google_chat": "Google Chat",
    "gmail": "Gmail",
    "outlook": "Outlook",
    "telegram": "Telegram",
    "whatsapp": "WhatsApp",
    "signal": "Signal",
}

_MAIL_PREFIXES = {"gmail": "gmail", "outlook": "outlook"}

_CHAT_EVENT_ALIASES = {
    "message": "message_received",
    "message_received": "message_received",
    "message_created": "message_received",
    "message_create": "message_received",
    "mention": "mention_received",
    "mention_received": "mention_received",
    "dm": "dm_received",
    "direct_message": "dm_received",
    "dm_received": "dm_received",
    "thread_reply": "thread_reply_received",
    "thread_reply_received": "thread_reply_received",
    "reaction": "reaction_added",
    "reaction_added": "reaction_added",
    "message_sent": "message_sent",
    "sent": "message_sent",
    "send": "message_sent",
    "message_edited": "message_edited",
    "edited_message": "message_edited",
    "message_changed": "message_edited",
    "message_deleted": "message_deleted",
    "deleted_message": "message_deleted",
    "draft_started": "draft_started",
    "draft_created": "draft_started",
    "draft_updated": "draft_updated",
    "attachment_added": "attachment_added",
    "file_shared": "attachment_added",
    "media_received": "attachment_added",
    "attachment_removed": "attachment_removed",
    "thread_opened": "thread_opened",
    "thread_reply_started": "thread_reply_started",
    "thread_reply_sent": "thread_reply_sent",
    "thread_replied": "thread_reply_sent",
    "thread_resolved": "thread_resolved",
    "thread_closed": "thread_resolved",
    "thread_unread_changed": "thread_unread_changed",
    "workspace_switched": "workspace_switched",
    "workspace_opened": "workspace_switched",
    "team_switched": "workspace_switched",
    "server_switched": "workspace_switched",
    "channel_opened": "channel_opened",
    "channel_navigation": "channel_opened",
    "chat_opened": "channel_opened",
    "channel_joined": "channel_joined",
    "channel_left": "channel_left",
    "channel_muted": "channel_muted",
    "channel_pinned": "channel_pinned",
    "channel_search_performed": "channel_search_performed",
    "search_performed": "channel_search_performed",
    "saved_item_opened": "saved_item_opened",
    "presence_changed": "presence_changed",
    "presence": "presence_changed",
    "status_changed": "status_changed",
    "status_cleared": "status_cleared",
    "dnd_scheduled": "dnd_scheduled",
    "dnd_enabled": "dnd_enabled",
    "do_not_disturb_enabled": "dnd_enabled",
    "dnd_disabled": "dnd_disabled",
    "do_not_disturb_disabled": "dnd_disabled",
    "notification_preference_changed": "notification_preference_changed",
}

_MAIL_EVENT_ALIASES = {
    "message_received": "message_received",
    "email_received": "message_received",
    "important_message_received": "important_message_received",
    "important_email_received": "important_message_received",
    "message_opened": "message_opened",
    "email_opened": "message_opened",
    "thread_opened": "message_opened",
    "draft_started": "draft_started",
    "draft_created": "draft_started",
    "email_draft_started": "draft_started",
    "draft_updated": "draft_updated",
    "message_edited": "draft_updated",
    "email_draft_updated": "draft_updated",
    "reply_started": "reply_started",
    "thread_reply_started": "reply_started",
    "thread_replied": "reply_started",
    "forward_started": "forward_started",
    "message_sent": "message_sent",
    "email_sent": "message_sent",
    "sent": "message_sent",
    "send_scheduled": "send_scheduled",
    "send_cancelled": "send_cancelled",
    "attachment_added": "attachment_added",
    "file_attached": "attachment_added",
    "attachment_removed": "attachment_removed",
    "message_archived": "message_archived",
    "thread_resolved": "message_archived",
    "message_deleted": "message_deleted",
    "message_moved": "message_moved",
    "message_labeled": "message_labeled",
    "label_added": "message_labeled",
    "label_changed": "message_labeled",
    "message_flagged": "message_flagged",
    "unread_marked": "unread_marked",
    "search_performed": "search_performed",
    "filter_changed": "filter_changed",
}


def append_communication_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        app = _app(payload)
        provider_id = _provider_id(payload, app)
        source_event = _source_event(payload, app, provider_id)
        return append_connector_source_event(
            config,
            provider_id=provider_id,
            source_event=source_event,
            object_type=str(payload.get("object_type") or _default_object_type(app, source_event)),
            object_id=str(
                payload.get("object_id")
                or payload.get("message_id")
                or payload.get("thread_id")
                or payload.get("conversation_id")
                or payload.get("channel_id")
                or payload.get("mail_id")
                or ""
            ),
            metadata=_metadata_from_payload(payload, app, provider_id, source_event),
            payload=payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
            occurred_at=str(payload.get("occurred_at") or payload.get("timestamp") or ""),
        )
    except (KeyError, ValueError) as exc:
        _append_dead_letter(config, payload, str(exc))
        raise ValueError(str(exc)) from exc


def append_communication_health(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        app = _app(payload) if (payload.get("app") or payload.get("service") or payload.get("application")) else ""
        provider_id = str(payload.get("provider_id") or "").strip() or ( _APP_PROVIDER_IDS[app] if app else "" )
        if not provider_id:
            raise ValueError("provider_id or app is required")
        collector = str(payload.get("collector") or "").strip()
        if collector:
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            CollectorEventLog(config.normalized().collector_events_db_path).record_helper_health(
                helper_id=f"communication-source-{provider_id}-{collector}",
                collector=collector,
                platform=platform.system(),
                status=str(payload.get("status") or "running"),
                version="0.1",
                permission_state=str(payload.get("permission_state") or payload.get("status") or "running"),
                message=str(payload.get("message") or ""),
                metadata={
                    "provider_id": provider_id,
                    "app": app or provider_id,
                    "display_name": _APP_DISPLAY_NAMES.get(app, provider_id),
                    "source": COMMUNICATION_SOURCE_ID,
                    **safe_metadata_values(metadata),
                },
            )
            return {"accepted": True, "provider_id": provider_id, "status": str(payload.get("status") or "running"), "collector_count": 1}
        return record_connector_source_health(
            config,
            provider_id=provider_id,
            status=str(payload.get("status") or "running"),
            message=str(payload.get("message") or ""),
            metadata={
                "source": COMMUNICATION_SOURCE_ID,
                "app": app or provider_id,
                **(payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}),
            },
        )
    except (KeyError, ValueError) as exc:
        _append_dead_letter(config, payload, str(exc))
        raise ValueError(str(exc)) from exc


def communication_source_status(config: AgentConfig) -> dict[str, Any]:
    from .registry import COMMUNICATION_APP_COLLECTORS, communication_app_status_records

    normalized = config.normalized()
    provider_ids = sorted({collector.provider_id for collector in COMMUNICATION_APP_COLLECTORS})
    source_records = []
    for provider_id in provider_ids:
        try:
            source_records.extend(connector_source_status(normalized, provider_id=provider_id).get("sources", []))
        except KeyError:
            continue
    pending_event_count = sum(
        1
        for event in CollectorEventLog(normalized.collector_events_db_path).query(limit=2000)
        if event.get("source") in provider_ids
    )
    health_items = [item for source in source_records for item in source.get("helper_health", []) if isinstance(source, dict)]
    return {
        "source": COMMUNICATION_SOURCE_ID,
        "status": _health_status(health_items),
        "provider_ids": provider_ids,
        "pending_event_count": pending_event_count,
        "dead_letter_count": _line_count(_dead_letters_path(normalized)),
        "dead_letters_path": str(_dead_letters_path(normalized)),
        "app_collectors": communication_app_status_records(),
        "supported_apps": sorted({collector.app for collector in COMMUNICATION_APP_COLLECTORS}),
        "source_manifests": source_records,
        "privacy_contract": {
            "default_privacy_tier": "sensitive_metadata",
            "raw_content_included": False,
            "message_bodies_redacted": True,
            "participants_redacted": True,
            "channel_names_redacted": True,
            "attachment_filenames_redacted": True,
            "labels_redacted": True,
        },
    }


def read_communication_events(
    config: AgentConfig,
    state: dict[str, Any],
    collector: str,
    allowed_stimulus_types: set[str],
    *,
    max_events: int = 20,
) -> list[CollectorEvent]:
    del config, state, collector, allowed_stimulus_types, max_events
    return []


def _app(payload: dict[str, Any]) -> str:
    app = _normalize_app(payload.get("app") or payload.get("service") or payload.get("application"))
    if not app:
        raise ValueError("app is required")
    return app


def _provider_id(payload: dict[str, Any], app: str) -> str:
    explicit = str(payload.get("provider_id") or "").strip()
    if explicit:
        return explicit
    return _APP_PROVIDER_IDS[app]


def _source_event(payload: dict[str, Any], app: str, provider_id: str) -> str:
    explicit = str(payload.get("source_event") or "").strip()
    if explicit:
        return explicit
    event_type = _clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type"))
    if not event_type:
        raise ValueError("event_type or source_event is required")
    if app in _MAIL_PREFIXES:
        suffix = _MAIL_EVENT_ALIASES.get(event_type)
        if not suffix:
            raise ValueError(f"unsupported communication mail event mapping: {app}:{event_type}")
        return f"{_MAIL_PREFIXES[app]}_{suffix}"
    suffix = _CHAT_EVENT_ALIASES.get(event_type)
    if not suffix:
        raise ValueError(f"unsupported communication chat event mapping: {app}:{event_type}")
    if provider_id == "microsoft_365" and app == "teams":
        return f"teams_{suffix}"
    if provider_id == "google_workspace" and app == "google_chat":
        return f"chat_{suffix}"
    return suffix


def _metadata_from_payload(payload: dict[str, Any], app: str, provider_id: str, source_event: str) -> dict[str, Any]:
    metadata = dict(payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {})
    metadata.update(
        {
            "app": app,
            "provider_id": provider_id,
            "provider_event_type": _clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type") or source_event),
            "source_channel": _clean_token(payload.get("source_channel") or payload.get("ingress") or "communication_ingress"),
            "message_body_redacted": True,
            "participants_redacted": True,
            "channel_name_redacted": True,
            "workspace_name_redacted": True,
            "attachment_filename_redacted": True,
            "label_name_redacted": True,
            "raw_content_included": False,
        }
    )
    for count_key in ("attachment_count", "label_count", "recipient_count", "participant_count", "reaction_count"):
        if count_key in payload:
            metadata[count_key] = payload[count_key]
    if "has_attachments" in payload:
        metadata["has_attachments"] = bool(payload.get("has_attachments"))
    return metadata


def _default_object_type(app: str, source_event: str) -> str:
    if app in _MAIL_PREFIXES:
        return "email_thread" if "thread" in source_event else "email_message"
    if "thread" in source_event:
        return "chat_thread"
    if "channel" in source_event or "workspace" in source_event:
        return "chat_channel"
    return "chat_message"


def _append_dead_letter(config: AgentConfig, payload: dict[str, Any], reason: str) -> None:
    path = _dead_letters_path(config.normalized())
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_payload = {
        "app": _clean_token(payload.get("app") or payload.get("service") or payload.get("application")),
        "provider_id": str(payload.get("provider_id") or "").strip(),
        "event_type": _clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type")),
        "source_event": str(payload.get("source_event") or "").strip(),
        "metadata_keys": sorted(str(key) for key in (payload.get("metadata") or {}).keys()) if isinstance(payload.get("metadata"), dict) else [],
        "reason": reason,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(safe_payload, ensure_ascii=False, sort_keys=True) + "\n")


def _dead_letters_path(config: AgentConfig) -> Path:
    return config.data_dir / "collector_dead_letters" / "communication.jsonl"


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.open("r", encoding="utf-8"))


def _health_status(health: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status") or "") for item in health}
    if not statuses:
        return "running"
    if "failed" in statuses:
        return "failed"
    if "permission_denied" in statuses and "running" in statuses:
        return "degraded"
    if "permission_denied" in statuses:
        return "permission_denied"
    if "degraded" in statuses:
        return "degraded"
    if "running" in statuses:
        return "running"
    return sorted(statuses)[0]


def _normalize_app(value: Any) -> str:
    app = _clean_token(value)
    if app not in _APP_ALIASES:
        raise ValueError(f"unsupported communication app: {app or '<app>'}")
    return _APP_ALIASES[app]


def _clean_token(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_").replace(".", "_")
    return "".join(char for char in text if char.isalnum() or char == "_")


__all__ = [
    "append_communication_event",
    "append_communication_health",
    "communication_source_status",
    "read_communication_events",
]
