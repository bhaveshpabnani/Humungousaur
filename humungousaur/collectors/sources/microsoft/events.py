from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.collectors.event_log import CollectorEventLog

from ...models import CollectorEvent
from ..workspace_connectors import (
    append_connector_source_event,
    connector_source_status,
    record_connector_source_health,
)
from .common import MICROSOFT_365_PROVIDER_ID


_APP_ALIASES = {
    "onedrive": "onedrive",
    "one_drive": "onedrive",
    "drive": "onedrive",
    "sharepoint": "sharepoint",
    "share_point": "sharepoint",
    "word": "word",
    "doc": "word",
    "document": "word",
    "excel": "excel",
    "sheet": "excel",
    "spreadsheet": "excel",
    "powerpoint": "powerpoint",
    "power_point": "powerpoint",
    "ppt": "powerpoint",
    "presentation": "powerpoint",
    "outlook": "outlook",
    "mail": "outlook",
    "email": "outlook",
    "calendar": "calendar",
    "outlook_calendar": "calendar",
    "teams": "teams",
    "msteams": "teams",
    "microsoft_teams": "teams",
    "onenote": "onenote",
    "one_note": "onenote",
    "notes": "onenote",
    "todo": "todo",
    "to_do": "todo",
    "microsoft_todo": "todo",
    "planner": "todo",
    "loop": "loop",
}

_EVENT_ALIASES = {
    ("onedrive", "file_created"): "onedrive_file_created",
    ("onedrive", "file_modified"): "onedrive_file_modified",
    ("onedrive", "file_changed"): "onedrive_file_modified",
    ("onedrive", "file_deleted"): "onedrive_file_deleted",
    ("onedrive", "folder_created"): "onedrive_folder_created",
    ("onedrive", "file_renamed"): "onedrive_file_renamed",
    ("onedrive", "folder_renamed"): "onedrive_folder_renamed",
    ("onedrive", "file_moved"): "onedrive_file_moved",
    ("onedrive", "folder_moved"): "onedrive_folder_moved",
    ("onedrive", "folder_deleted"): "onedrive_folder_deleted",
    ("onedrive", "file_shared"): "onedrive_file_shared",
    ("onedrive", "permissions_changed"): "onedrive_permissions_changed",
    ("onedrive", "permission_changed"): "onedrive_permissions_changed",
    ("onedrive", "sync_error"): "onedrive_sync_failed",
    ("onedrive", "sync_failed"): "onedrive_sync_failed",
    ("onedrive", "conflict"): "onedrive_sync_conflict_detected",
    ("onedrive", "sync_conflict_detected"): "onedrive_sync_conflict_detected",
    ("onedrive", "restored"): "onedrive_file_restored",
    ("onedrive", "file_restored"): "onedrive_file_restored",
    ("onedrive", "version_event"): "onedrive_file_version_event",
    ("onedrive", "file_version_event"): "onedrive_file_version_event",
    ("sharepoint", "file_created"): "sharepoint_file_created",
    ("sharepoint", "folder_created"): "sharepoint_folder_created",
    ("sharepoint", "file_modified"): "sharepoint_file_modified",
    ("sharepoint", "file_deleted"): "sharepoint_file_deleted",
    ("sharepoint", "file_renamed"): "sharepoint_file_renamed",
    ("sharepoint", "folder_renamed"): "sharepoint_folder_renamed",
    ("sharepoint", "file_moved"): "sharepoint_file_moved",
    ("sharepoint", "folder_moved"): "sharepoint_folder_moved",
    ("sharepoint", "folder_deleted"): "sharepoint_folder_deleted",
    ("sharepoint", "file_shared"): "sharepoint_file_shared",
    ("sharepoint", "permissions_changed"): "sharepoint_permissions_changed",
    ("sharepoint", "permission_changed"): "sharepoint_permissions_changed",
    ("sharepoint", "sync_error"): "sharepoint_sync_failed",
    ("sharepoint", "sync_failed"): "sharepoint_sync_failed",
    ("sharepoint", "conflict"): "sharepoint_sync_conflict_detected",
    ("sharepoint", "sync_conflict_detected"): "sharepoint_sync_conflict_detected",
    ("sharepoint", "restored"): "sharepoint_file_restored",
    ("sharepoint", "file_restored"): "sharepoint_file_restored",
    ("sharepoint", "version_event"): "sharepoint_file_version_event",
    ("sharepoint", "file_version_event"): "sharepoint_file_version_event",
    ("word", "file_created"): "word_document_draft_started",
    ("word", "file_modified"): "word_document_edited",
    ("word", "file_deleted"): "onedrive_file_deleted",
    ("word", "document_draft_started"): "word_document_draft_started",
    ("word", "document_edited"): "word_document_edited",
    ("word", "document_saved"): "word_document_saved",
    ("word", "comment_added"): "word_comment_added",
    ("word", "suggestion_received"): "word_suggestion_received",
    ("word", "tracked_changes_enabled"): "word_tracked_changes_enabled",
    ("word", "document_exported"): "word_document_exported",
    ("word", "document_shared"): "word_document_shared",
    ("word", "permissions_changed"): "word_permissions_changed",
    ("excel", "file_created"): "excel_workbook_opened",
    ("excel", "file_modified"): "excel_range_edited",
    ("excel", "file_deleted"): "onedrive_file_deleted",
    ("excel", "workbook_opened"): "excel_workbook_opened",
    ("excel", "range_edited"): "excel_range_edited",
    ("excel", "cell_range_edited"): "excel_range_edited",
    ("excel", "sheet_created"): "excel_sheet_created",
    ("excel", "row_inserted"): "excel_row_inserted",
    ("excel", "formula_entered"): "excel_formula_entered",
    ("excel", "formula_error"): "excel_formula_error",
    ("excel", "formula_error_detected"): "excel_formula_error",
    ("excel", "filter_applied"): "excel_filter_applied",
    ("excel", "chart_created"): "excel_chart_created",
    ("excel", "pivot_table_changed"): "excel_pivot_table_changed",
    ("excel", "workbook_exported"): "excel_workbook_exported",
    ("excel", "sheet_shared"): "excel_sheet_shared",
    ("excel", "permissions_changed"): "excel_permissions_changed",
    ("powerpoint", "file_created"): "powerpoint_deck_opened",
    ("powerpoint", "file_modified"): "powerpoint_slide_edited",
    ("powerpoint", "file_deleted"): "onedrive_file_deleted",
    ("powerpoint", "deck_opened"): "powerpoint_deck_opened",
    ("powerpoint", "slide_created"): "powerpoint_slide_created",
    ("powerpoint", "slide_edited"): "powerpoint_slide_edited",
    ("powerpoint", "slideshow_started"): "powerpoint_slideshow_started",
    ("powerpoint", "slideshow_ended"): "powerpoint_slideshow_ended",
    ("powerpoint", "deck_exported"): "powerpoint_deck_exported",
    ("powerpoint", "deck_shared"): "powerpoint_deck_shared",
    ("powerpoint", "permissions_changed"): "powerpoint_permissions_changed",
    ("outlook", "email_received"): "outlook_message_received",
    ("outlook", "message_received"): "outlook_message_received",
    ("outlook", "important_email_received"): "outlook_important_message_received",
    ("outlook", "draft_started"): "outlook_draft_started",
    ("outlook", "email_draft_started"): "outlook_draft_started",
    ("outlook", "email_draft_updated"): "outlook_draft_updated",
    ("outlook", "email_sent"): "outlook_message_sent",
    ("outlook", "message_sent"): "outlook_message_sent",
    ("outlook", "email_labeled"): "outlook_message_labeled",
    ("outlook", "email_archived"): "outlook_message_archived",
    ("outlook", "email_deleted"): "outlook_message_deleted",
    ("outlook", "email_flagged"): "outlook_message_flagged",
    ("calendar", "meeting_starting"): "outlook_calendar_meeting_starting",
    ("calendar", "meeting_started"): "outlook_calendar_meeting_started",
    ("calendar", "meeting_ended"): "outlook_calendar_meeting_ended",
    ("calendar", "calendar_event_created"): "outlook_calendar_event_created",
    ("calendar", "calendar_event_updated"): "outlook_calendar_event_updated",
    ("calendar", "calendar_event_deleted"): "outlook_calendar_event_deleted",
    ("calendar", "calendar_event_rescheduled"): "outlook_calendar_event_rescheduled",
    ("calendar", "calendar_invite_received"): "outlook_calendar_invite_received",
    ("calendar", "calendar_invite_accepted"): "outlook_calendar_invite_accepted",
    ("calendar", "calendar_invite_declined"): "outlook_calendar_invite_declined",
    ("calendar", "calendar_availability_checked"): "outlook_calendar_availability_checked",
    ("teams", "message_received"): "teams_message_received",
    ("teams", "message_sent"): "teams_message_sent",
    ("teams", "mention_received"): "teams_mention_received",
    ("teams", "thread_reply_received"): "teams_thread_reply_received",
    ("teams", "reaction_added"): "teams_reaction_added",
    ("teams", "channel_opened"): "teams_channel_opened",
    ("teams", "workspace_switched"): "teams_workspace_switched",
    ("teams", "presence_changed"): "teams_presence_changed",
    ("teams", "meeting_joined"): "teams_meeting_joined",
    ("teams", "meeting_left"): "teams_meeting_left",
    ("teams", "microphone_muted"): "teams_microphone_muted",
    ("teams", "microphone_unmuted"): "teams_microphone_unmuted",
    ("teams", "screen_share_started"): "teams_screen_share_started",
    ("teams", "screen_share_stopped"): "teams_screen_share_stopped",
    ("teams", "meeting_transcript_available"): "teams_transcript_available",
    ("teams", "meeting_recording_available"): "teams_recording_available",
    ("onenote", "note_created"): "onenote_note_created",
    ("onenote", "page_created"): "onenote_note_created",
    ("onenote", "note_edited"): "onenote_note_edited",
    ("onenote", "page_edited"): "onenote_note_edited",
    ("onenote", "note_deleted"): "onenote_note_deleted",
    ("onenote", "page_deleted"): "onenote_note_deleted",
    ("onenote", "note_shared"): "onenote_note_shared",
    ("onenote", "checklist_item_completed"): "onenote_checklist_item_completed",
    ("todo", "task_created"): "todo_task_created",
    ("todo", "task_updated"): "todo_task_updated",
    ("todo", "task_completed"): "todo_task_completed",
    ("todo", "task_due_date_changed"): "todo_task_due_date_changed",
    ("todo", "todo_created"): "todo_task_created",
    ("todo", "todo_completed"): "todo_task_completed",
    ("loop", "component_created"): "loop_component_created",
    ("loop", "component_edited"): "loop_component_edited",
    ("loop", "component_shared"): "loop_component_shared",
    ("loop", "task_completed"): "loop_task_completed",
    ("loop", "page_created"): "loop_page_created",
    ("loop", "page_edited"): "loop_page_edited",
}


def append_microsoft_365_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        source_event = _source_event(payload)
        return append_connector_source_event(
            config,
            provider_id=MICROSOFT_365_PROVIDER_ID,
            source_event=source_event,
            object_type=str(payload.get("object_type") or ""),
            object_id=str(
                payload.get("object_id")
                or payload.get("file_id")
                or payload.get("document_id")
                or payload.get("workbook_id")
                or payload.get("message_id")
                or payload.get("event_id")
                or payload.get("task_id")
                or payload.get("page_id")
                or ""
            ),
            metadata=_metadata_from_payload(payload, source_event),
            payload=payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
            occurred_at=str(payload.get("occurred_at") or payload.get("timestamp") or ""),
        )
    except (KeyError, ValueError) as exc:
        _append_dead_letter(config, payload, str(exc))
        raise ValueError(str(exc)) from exc


def append_microsoft_365_health(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        collector = str(payload.get("collector") or "").strip()
        if collector:
            status = str(payload.get("status") or "running").strip()
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            CollectorEventLog(config.normalized().collector_events_db_path).record_helper_health(
                helper_id=f"connector-source-{MICROSOFT_365_PROVIDER_ID}-{collector}",
                collector=collector,
                platform=platform.system(),
                status=status,
                version="0.1",
                permission_state=str(payload.get("permission_state") or status),
                message=str(payload.get("message") or ""),
                metadata={
                    "provider_id": MICROSOFT_365_PROVIDER_ID,
                    "display_name": "Microsoft 365",
                    **_safe_legacy_health_metadata(metadata),
                },
            )
            return {"accepted": True, "provider_id": MICROSOFT_365_PROVIDER_ID, "status": status, "collector_count": 1}
        return record_connector_source_health(
            config,
            provider_id=MICROSOFT_365_PROVIDER_ID,
            status=str(payload.get("status") or "running"),
            message=str(payload.get("message") or ""),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
    except (KeyError, ValueError) as exc:
        _append_dead_letter(config, payload, str(exc))
        raise ValueError(str(exc)) from exc


def microsoft_365_source_status(config: AgentConfig) -> dict[str, Any]:
    from .registry import microsoft_365_app_status_records

    status = connector_source_status(config, provider_id=MICROSOFT_365_PROVIDER_ID)
    source = status["sources"][0] if status.get("sources") else {}
    health = source.get("helper_health", []) if isinstance(source, dict) else []
    pending_event_count = sum(
        1
        for event in CollectorEventLog(config.normalized().collector_events_db_path).query(limit=1000)
        if event.get("source") == MICROSOFT_365_PROVIDER_ID
    )
    return {
        **source,
        "source": MICROSOFT_365_PROVIDER_ID,
        "status": _health_status(health),
        "pending_event_count": pending_event_count,
        "dead_letter_count": _line_count(_dead_letters_path(config.normalized())),
        "dead_letters_path": str(_dead_letters_path(config.normalized())),
        "app_collectors": microsoft_365_app_status_records(),
        "supported_apps": sorted(set(_APP_ALIASES.values())),
        "mapping_count": len(source.get("collector_mappings", ())) if isinstance(source, dict) else 0,
        "privacy_contract": {
            "default_privacy_tier": "sensitive_metadata",
            "raw_content_included": False,
            "provider_content_redacted": True,
        },
    }


def read_microsoft_365_events(
    config: AgentConfig,
    state: dict[str, Any],
    collector: str,
    allowed_stimulus_types: set[str],
    *,
    max_events: int = 20,
) -> list[CollectorEvent]:
    del config, state, collector, allowed_stimulus_types, max_events
    return []


def _source_event(payload: dict[str, Any]) -> str:
    explicit = str(payload.get("source_event") or "").strip()
    if explicit:
        return explicit
    app = _normalize_app(payload.get("app") or payload.get("service") or payload.get("application"))
    event_type = _clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type"))
    source_event = _EVENT_ALIASES.get((app, event_type))
    if not source_event:
        raise ValueError(f"unsupported Microsoft 365 event mapping: {app or '<app>'}:{event_type or '<event_type>'}")
    return source_event


def _metadata_from_payload(payload: dict[str, Any], source_event: str) -> dict[str, Any]:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    clean = dict(metadata)
    clean["source_event"] = source_event
    app = _normalize_app(payload.get("app") or payload.get("service") or payload.get("application"))
    if app:
        clean["app"] = f"microsoft_365_{app}"
    event_type = _clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type"))
    if event_type:
        clean["provider_event_type"] = event_type
    for key in (
        "attachment_count",
        "availability",
        "calendar_event_status",
        "channel_id",
        "duration_minutes",
        "event_id",
        "file_id",
        "folder_id",
        "has_attachments",
        "has_due_date",
        "importance",
        "is_online_meeting",
        "message_id",
        "mime_type",
        "object_type",
        "page_id",
        "permission_role",
        "permission_scope",
        "provider_event_id",
        "range_cell_count",
        "rev",
        "row_count",
        "site_id",
        "source_channel",
        "task_id",
        "team_id",
        "thread_id",
        "workbook_id",
    ):
        if key in payload:
            clean[key] = payload[key]
    for redacted in (
        "title",
        "subject",
        "body",
        "text",
        "content",
        "cell_value",
        "formula",
        "url",
        "path",
        "name",
        "participants",
        "attendees",
        "location",
        "display_name",
        "email",
        "phone_number",
        "address",
        "channel_name",
        "team_name",
    ):
        if redacted in payload:
            clean[f"{redacted}_redacted"] = True
    return clean


def _append_dead_letter(config: AgentConfig, payload: dict[str, Any], reason: str) -> None:
    path = _dead_letters_path(config.normalized())
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "reason": str(reason)[:500],
        "payload_keys": sorted(str(key) for key in payload.keys()) if isinstance(payload, dict) else [],
        "source": MICROSOFT_365_PROVIDER_ID,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _dead_letters_path(config: AgentConfig) -> Path:
    return config.normalized().data_dir / "collector_sources" / MICROSOFT_365_PROVIDER_ID / "dead_letters.jsonl"


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except OSError:
        return 0


def _health_status(health: Any) -> str:
    if not isinstance(health, list) or not health:
        return "not_configured"
    return str(health[0].get("status") or "unknown")


def _normalize_app(value: Any) -> str:
    token = _clean_token(value)
    return _APP_ALIASES.get(token, token)


def _clean_token(value: Any) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", "_").replace(".", "_").split())


def _safe_legacy_health_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in metadata.items():
        token = _clean_token(key)
        if not token:
            continue
        if token == "id" or token.endswith("_id"):
            value_text = str(value or "").strip()
            if value_text:
                import hashlib

                clean[f"{token}_hash"] = f"sha256:{hashlib.sha256(value_text.encode('utf-8')).hexdigest()}"
                clean[f"{token}_redacted"] = True
            continue
        if token in {"title", "subject", "body", "text", "content", "message", "email", "url", "path", "token", "secret"}:
            clean[f"{token}_redacted"] = True
            continue
        if isinstance(value, bool):
            clean[token] = value
        elif isinstance(value, (int, float)):
            clean[token] = value
        elif isinstance(value, list):
            clean[f"{token}_count"] = len(value)
        elif isinstance(value, dict):
            clean[f"{token}_keys"] = sorted(_clean_token(item) for item in value)[:20]
        elif isinstance(value, str):
            clean[f"{token}_redacted"] = True
    return clean


__all__ = [
    "append_microsoft_365_event",
    "append_microsoft_365_health",
    "microsoft_365_source_status",
    "read_microsoft_365_events",
]
