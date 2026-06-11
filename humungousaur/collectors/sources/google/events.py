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
from .common import GOOGLE_WORKSPACE_PROVIDER_ID


_APP_ALIASES = {
    "drive": "drive",
    "google_drive": "drive",
    "docs": "docs",
    "google_docs": "docs",
    "document": "docs",
    "sheets": "sheets",
    "google_sheets": "sheets",
    "spreadsheet": "sheets",
    "slides": "slides",
    "google_slides": "slides",
    "presentation": "slides",
    "gmail": "gmail",
    "mail": "gmail",
    "calendar": "calendar",
    "google_calendar": "calendar",
    "meet": "meet",
    "google_meet": "meet",
    "tasks": "tasks",
    "google_tasks": "tasks",
    "keep": "keep",
    "google_keep": "keep",
    "chat": "chat",
    "google_chat": "chat",
    "contacts": "contacts",
    "google_contacts": "contacts",
    "people": "contacts",
}

_EVENT_ALIASES = {
    ("drive", "file_created"): "drive_file_created",
    ("drive", "file_modified"): "drive_file_modified",
    ("drive", "file_changed"): "drive_file_modified",
    ("drive", "file_deleted"): "drive_file_deleted",
    ("drive", "file_shared"): "drive_file_shared",
    ("drive", "permissions_changed"): "drive_file_shared",
    ("drive", "cloud_file_created"): "drive_cloud_file_created",
    ("drive", "folder_created"): "drive_cloud_folder_created",
    ("drive", "file_renamed"): "drive_cloud_file_renamed",
    ("drive", "folder_renamed"): "drive_cloud_folder_renamed",
    ("drive", "file_moved"): "drive_cloud_file_moved",
    ("drive", "folder_moved"): "drive_cloud_folder_moved",
    ("drive", "cloud_file_deleted"): "drive_cloud_file_deleted",
    ("drive", "folder_deleted"): "drive_cloud_folder_deleted",
    ("drive", "cloud_file_shared"): "drive_cloud_file_shared",
    ("drive", "permission_changed"): "drive_cloud_permission_changed",
    ("drive", "sync_error"): "drive_cloud_sync_failed",
    ("drive", "sync_failed"): "drive_cloud_sync_failed",
    ("drive", "conflict"): "drive_cloud_sync_conflict_detected",
    ("drive", "sync_conflict_detected"): "drive_cloud_sync_conflict_detected",
    ("drive", "restored"): "drive_cloud_file_restored",
    ("drive", "file_restored"): "drive_cloud_file_restored",
    ("drive", "version_event"): "drive_cloud_file_version_event",
    ("drive", "file_version_event"): "drive_cloud_file_version_event",
    ("docs", "file_created"): "docs_document_draft_started",
    ("docs", "file_modified"): "docs_document_edited",
    ("docs", "file_deleted"): "drive_file_deleted",
    ("docs", "document_draft_started"): "docs_document_draft_started",
    ("docs", "document_edited"): "docs_document_edited",
    ("docs", "document_saved"): "docs_document_saved",
    ("docs", "comment_added"): "docs_comment_added",
    ("docs", "suggestion_received"): "docs_suggestion_received",
    ("docs", "document_exported"): "docs_document_exported",
    ("docs", "document_shared"): "docs_document_shared",
    ("docs", "permissions_changed"): "docs_permissions_changed",
    ("sheets", "file_created"): "sheets_spreadsheet_opened",
    ("sheets", "file_modified"): "sheets_range_edited",
    ("sheets", "file_deleted"): "drive_file_deleted",
    ("sheets", "spreadsheet_opened"): "sheets_spreadsheet_opened",
    ("sheets", "sheet_created"): "sheets_sheet_created",
    ("sheets", "range_edited"): "sheets_range_edited",
    ("sheets", "cell_range_edited"): "sheets_range_edited",
    ("sheets", "row_inserted"): "sheets_row_inserted",
    ("sheets", "formula_entered"): "sheets_formula_entered",
    ("sheets", "formula_error"): "sheets_formula_error",
    ("sheets", "formula_error_detected"): "sheets_formula_error",
    ("sheets", "filter_applied"): "sheets_filter_applied",
    ("sheets", "chart_created"): "sheets_chart_created",
    ("sheets", "csv_imported"): "sheets_csv_imported",
    ("sheets", "workbook_exported"): "sheets_workbook_exported",
    ("sheets", "sheet_shared"): "sheets_sheet_shared",
    ("sheets", "permissions_changed"): "sheets_permissions_changed",
    ("slides", "file_created"): "slides_deck_opened",
    ("slides", "file_modified"): "slides_slide_edited",
    ("slides", "file_deleted"): "drive_file_deleted",
    ("slides", "deck_opened"): "slides_deck_opened",
    ("slides", "slide_created"): "slides_slide_created",
    ("slides", "slide_edited"): "slides_slide_edited",
    ("slides", "slideshow_started"): "slides_slideshow_started",
    ("slides", "slideshow_ended"): "slides_slideshow_ended",
    ("slides", "deck_exported"): "slides_deck_exported",
    ("slides", "deck_shared"): "slides_deck_shared",
    ("slides", "permissions_changed"): "slides_permissions_changed",
    ("gmail", "email_received"): "gmail_message_received",
    ("gmail", "message_received"): "gmail_message_received",
    ("gmail", "important_email_received"): "gmail_important_message_received",
    ("gmail", "draft_started"): "gmail_draft_started",
    ("gmail", "email_draft_started"): "gmail_draft_started",
    ("gmail", "email_draft_updated"): "gmail_draft_updated",
    ("gmail", "email_sent"): "gmail_message_sent",
    ("gmail", "message_sent"): "gmail_message_sent",
    ("gmail", "email_labeled"): "gmail_message_labeled",
    ("gmail", "email_archived"): "gmail_message_archived",
    ("gmail", "email_deleted"): "gmail_message_deleted",
    ("calendar", "meeting_starting"): "calendar_meeting_starting",
    ("calendar", "meeting_started"): "calendar_meeting_started",
    ("calendar", "meeting_ended"): "calendar_meeting_ended",
    ("calendar", "calendar_event_created"): "calendar_event_created",
    ("calendar", "calendar_event_updated"): "calendar_event_updated",
    ("calendar", "calendar_event_deleted"): "calendar_event_deleted",
    ("calendar", "calendar_event_rescheduled"): "calendar_event_rescheduled",
    ("calendar", "calendar_invite_received"): "calendar_invite_received",
    ("calendar", "calendar_invite_accepted"): "calendar_invite_accepted",
    ("calendar", "calendar_invite_declined"): "calendar_invite_declined",
    ("calendar", "calendar_availability_checked"): "calendar_availability_checked",
    ("meet", "meeting_joined"): "meet_joined",
    ("meet", "joined"): "meet_joined",
    ("meet", "meeting_left"): "meet_left",
    ("meet", "left"): "meet_left",
    ("meet", "waiting_room_joined"): "meet_waiting_room_joined",
    ("meet", "waiting_room_admitted"): "meet_waiting_room_admitted",
    ("meet", "participant_joined"): "meet_participant_joined",
    ("meet", "participant_left"): "meet_participant_left",
    ("meet", "breakout_room_joined"): "meet_breakout_room_joined",
    ("meet", "breakout_room_left"): "meet_breakout_room_left",
    ("meet", "meeting_recording_started"): "meet_recording_started",
    ("meet", "recording_started"): "meet_recording_started",
    ("meet", "meeting_recording_stopped"): "meet_recording_stopped",
    ("meet", "recording_stopped"): "meet_recording_stopped",
    ("meet", "microphone_muted"): "meet_microphone_muted",
    ("meet", "mic_muted"): "meet_microphone_muted",
    ("meet", "microphone_unmuted"): "meet_microphone_unmuted",
    ("meet", "mic_unmuted"): "meet_microphone_unmuted",
    ("meet", "camera_enabled"): "meet_camera_enabled",
    ("meet", "camera_disabled"): "meet_camera_disabled",
    ("meet", "hand_raised"): "meet_hand_raised",
    ("meet", "hand_lowered"): "meet_hand_lowered",
    ("meet", "reaction_sent"): "meet_reaction_sent",
    ("meet", "captions_enabled"): "meet_captions_enabled",
    ("meet", "captions_disabled"): "meet_captions_disabled",
    ("meet", "meeting_chat_opened"): "meet_meeting_chat_opened",
    ("meet", "screen_share_started"): "meet_screen_share_started",
    ("meet", "screen_share_stopped"): "meet_screen_share_stopped",
    ("meet", "window_share_started"): "meet_window_share_started",
    ("meet", "window_share_stopped"): "meet_window_share_stopped",
    ("meet", "presentation_started"): "meet_presentation_started",
    ("meet", "presentation_stopped"): "meet_presentation_stopped",
    ("meet", "presenter_changed"): "meet_presenter_changed",
    ("meet", "remote_control_requested"): "meet_remote_control_requested",
    ("meet", "remote_control_granted"): "meet_remote_control_granted",
    ("meet", "remote_control_revoked"): "meet_remote_control_revoked",
    ("meet", "meeting_transcript_available"): "meet_transcript_available",
    ("meet", "transcript_available"): "meet_transcript_available",
    ("meet", "meeting_recording_available"): "meet_recording_available",
    ("meet", "recording_available"): "meet_recording_available",
    ("meet", "meeting_summary_generated"): "meet_summary_generated",
    ("meet", "summary_generated"): "meet_summary_generated",
    ("meet", "meeting_action_items_detected"): "meet_action_items_detected",
    ("meet", "action_items_detected"): "meet_action_items_detected",
    ("meet", "meeting_notes_shared"): "meet_notes_shared",
    ("meet", "notes_shared"): "meet_notes_shared",
    ("meet", "meeting_whiteboard_exported"): "meet_whiteboard_exported",
    ("meet", "whiteboard_exported"): "meet_whiteboard_exported",
    ("meet", "meeting_followup_created"): "meet_followup_created",
    ("meet", "followup_created"): "meet_followup_created",
    ("tasks", "task_created"): "tasks_task_created",
    ("tasks", "task_updated"): "tasks_task_updated",
    ("tasks", "task_completed"): "tasks_task_completed",
    ("tasks", "task_due_date_changed"): "tasks_task_due_date_changed",
    ("keep", "note_created"): "keep_note_created",
    ("keep", "note_edited"): "keep_note_edited",
    ("keep", "note_deleted"): "keep_note_deleted",
    ("keep", "note_shared"): "keep_note_shared",
    ("keep", "checklist_item_completed"): "keep_checklist_item_completed",
    ("chat", "message_received"): "chat_message_received",
    ("chat", "message_sent"): "chat_message_sent",
    ("chat", "mention_received"): "chat_mention_received",
    ("chat", "thread_reply_received"): "chat_thread_reply_received",
    ("chat", "reaction_added"): "chat_reaction_added",
    ("chat", "space_opened"): "chat_space_opened",
    ("chat", "presence_changed"): "chat_presence_changed",
    ("contacts", "contact_opened"): "contacts_contact_opened",
    ("contacts", "contact_created"): "contacts_contact_created",
    ("contacts", "contact_updated"): "contacts_contact_updated",
    ("contacts", "contact_shared"): "contacts_contact_shared",
    ("contacts", "address_copied"): "contacts_address_copied",
    ("contacts", "phone_number_clicked"): "contacts_phone_number_clicked",
}


def append_google_workspace_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        source_event = _source_event(payload)
        return append_connector_source_event(
            config,
            provider_id=GOOGLE_WORKSPACE_PROVIDER_ID,
            source_event=source_event,
            object_type=str(payload.get("object_type") or ""),
            object_id=str(payload.get("object_id") or payload.get("file_id") or payload.get("document_id") or payload.get("spreadsheet_id") or payload.get("event_id") or ""),
            metadata=_metadata_from_payload(payload, source_event),
            payload=payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
            occurred_at=str(payload.get("occurred_at") or payload.get("timestamp") or ""),
        )
    except (KeyError, ValueError) as exc:
        _append_dead_letter(config, payload, str(exc))
        raise ValueError(str(exc)) from exc


def append_google_workspace_health(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        collector = str(payload.get("collector") or "").strip()
        if collector:
            status = str(payload.get("status") or "running").strip()
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            CollectorEventLog(config.normalized().collector_events_db_path).record_helper_health(
                helper_id=f"connector-source-{GOOGLE_WORKSPACE_PROVIDER_ID}-{collector}",
                collector=collector,
                platform=platform.system(),
                status=status,
                version="0.1",
                permission_state=str(payload.get("permission_state") or status),
                message=str(payload.get("message") or ""),
                metadata={
                    "provider_id": GOOGLE_WORKSPACE_PROVIDER_ID,
                    "display_name": "Google Workspace",
                    **_safe_legacy_health_metadata(metadata),
                },
            )
            return {"accepted": True, "provider_id": GOOGLE_WORKSPACE_PROVIDER_ID, "status": status, "collector_count": 1}
        return record_connector_source_health(
            config,
            provider_id=GOOGLE_WORKSPACE_PROVIDER_ID,
            status=str(payload.get("status") or "running"),
            message=str(payload.get("message") or ""),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
    except (KeyError, ValueError) as exc:
        _append_dead_letter(config, payload, str(exc))
        raise ValueError(str(exc)) from exc


def google_workspace_source_status(config: AgentConfig) -> dict[str, Any]:
    from .registry import google_workspace_app_status_records

    status = connector_source_status(config, provider_id=GOOGLE_WORKSPACE_PROVIDER_ID)
    source = status["sources"][0] if status.get("sources") else {}
    health = source.get("helper_health", []) if isinstance(source, dict) else []
    pending_event_count = sum(
        1
        for event in CollectorEventLog(config.normalized().collector_events_db_path).query(limit=1000)
        if event.get("source") == GOOGLE_WORKSPACE_PROVIDER_ID
    )
    return {
        **source,
        "source": GOOGLE_WORKSPACE_PROVIDER_ID,
        "status": _health_status(health),
        "pending_event_count": pending_event_count,
        "dead_letter_count": _line_count(_dead_letters_path(config.normalized())),
        "dead_letters_path": str(_dead_letters_path(config.normalized())),
        "app_collectors": google_workspace_app_status_records(),
        "supported_apps": sorted(set(_APP_ALIASES.values())),
        "mapping_count": len(source.get("collector_mappings", ())) if isinstance(source, dict) else 0,
        "privacy_contract": {
            "default_privacy_tier": "sensitive_metadata",
            "raw_content_included": False,
            "provider_content_redacted": True,
        },
    }


def read_google_workspace_events(
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
        raise ValueError(f"unsupported Google Workspace event mapping: {app or '<app>'}:{event_type or '<event_type>'}")
    return source_event


def _metadata_from_payload(payload: dict[str, Any], source_event: str) -> dict[str, Any]:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    clean = dict(metadata)
    clean["source_event"] = source_event
    app = _normalize_app(payload.get("app") or payload.get("service") or payload.get("application"))
    if app:
        clean["app"] = f"google_{app}"
    event_type = _clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type"))
    if event_type:
        clean["provider_event_type"] = event_type
    for key in (
        "attachment_count",
        "calendar_id",
        "contact_id",
        "duration_minutes",
        "document_id",
        "event_id",
        "file_id",
        "folder_id",
        "meeting_id",
        "conference_id",
        "conference_record_id",
        "has_attachments",
        "has_action_items",
        "has_recording",
        "has_summary",
        "has_transcript",
        "mime_type",
        "object_type",
        "participant_count",
        "permission_role",
        "permission_scope",
        "provider_event_id",
        "range_cell_count",
        "rev",
        "recording_id",
        "row_count",
        "space_id",
        "spreadsheet_id",
        "task_id",
        "transcript_id",
    ):
        if key in payload:
            clean[key] = payload[key]
    for redacted in (
        "title",
        "subject",
        "body",
        "text",
        "cell_value",
        "formula",
        "url",
        "path",
        "file_name",
        "name",
        "participants",
        "attendees",
        "location",
        "display_name",
        "email",
        "phone_number",
        "address",
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
        "source": GOOGLE_WORKSPACE_PROVIDER_ID,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _dead_letters_path(config: AgentConfig) -> Path:
    return config.normalized().data_dir / "collector_sources" / GOOGLE_WORKSPACE_PROVIDER_ID / "dead_letters.jsonl"


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
    "append_google_workspace_event",
    "append_google_workspace_health",
    "google_workspace_source_status",
    "read_google_workspace_events",
]
