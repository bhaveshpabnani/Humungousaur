from __future__ import annotations

import hashlib
import json
from typing import Any

from .models import CollectorEvent, CollectorProfile, utc_now as _utc_now


def compact_attention_event(event: CollectorEvent) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "collector": event.collector,
        "source": event.source,
        "stimulus_type": event.stimulus_type,
        "occurred_at": event.occurred_at,
        "signature": event.stable_signature(),
    }
    if event.collector == "filesystem":
        compact["path"] = str(event.payload.get("relative_path") or event.metadata.get("path") or "")
        compact["size_bytes"] = int(event.metadata.get("size_bytes") or 0)
    elif event.collector == "browser":
        compact["app_name"] = str(event.metadata.get("app_name", ""))
        compact["window_title"] = str(event.metadata.get("window_title", ""))
        compact["url"] = str(event.metadata.get("url", ""))
    elif event.collector == "active_window":
        compact["app_name"] = str(event.metadata.get("app_name", ""))
        compact["window_title"] = str(event.metadata.get("window_title", ""))
    elif event.collector == "clipboard":
        compact["text_length"] = int(event.metadata.get("text_length") or 0)
        compact["truncated"] = bool(event.metadata.get("truncated", False))
    elif event.collector == "screen_ocr":
        compact["text_length"] = int(event.metadata.get("text_length") or 0)
        compact["truncated"] = bool(event.metadata.get("truncated", False))
    elif event.collector in {"screenshot", "video_frame"}:
        compact["filename"] = str(event.metadata.get("filename", ""))
        compact["width"] = event.metadata.get("width")
        compact["height"] = event.metadata.get("height")
    elif event.collector in {"app_lifecycle", "window_lifecycle"}:
        compact["app_name"] = str(event.metadata.get("app_name", ""))
        compact["window_title"] = str(event.metadata.get("window_title", ""))
        compact["summary"] = event.text[:240]
    elif event.collector == "browser_lifecycle":
        compact["app_name"] = str(event.metadata.get("app_name", ""))
        compact["window_title"] = str(event.metadata.get("window_title", ""))
        compact["url"] = str(event.metadata.get("url", ""))
        compact["summary"] = event.text[:240]
    elif event.collector in {
        "browser_window_activity",
        "browser_tab_group_activity",
        "browser_profile_activity",
        "browser_extension_activity",
        "browser_web_app_activity",
        "browser_view_mode_activity",
    }:
        compact["summary"] = _safe_bridge_summary(event)
        compact["app_name"] = str(event.metadata.get("app_name", ""))
        compact["privacy_level"] = str(event.metadata.get("privacy_level", "redacted"))
        compact["bridge_event"] = bool(event.metadata.get("bridge_event", False))
        for key in (
            "browser_window_kind",
            "tab_group_kind",
            "browser_profile_kind",
            "extension_kind",
            "web_app_kind",
            "view_mode_kind",
        ):
            if key in event.metadata:
                compact[key] = str(event.metadata.get(key, ""))
    elif event.collector == "input_device":
        compact["input_event"] = event.stimulus_type
        compact["idle_bucket"] = str(event.metadata.get("idle_bucket", ""))
        compact["summary"] = event.text[:240]
    elif event.collector in {
        "keyboard_input_activity",
        "ime_activity",
        "text_input_surface_activity",
        "pasteboard_workflow_activity",
    }:
        compact["summary"] = _safe_bridge_summary(event)
        compact["app_name"] = str(event.metadata.get("app_name", ""))
        compact["privacy_level"] = str(event.metadata.get("privacy_level", "redacted" if event.collector != "keyboard_input_activity" else "metadata"))
        compact["bridge_event"] = bool(event.metadata.get("bridge_event", False))
        for key in (
            "input_source_kind",
            "keyboard_layout_kind",
            "ime_kind",
            "input_surface_kind",
            "pasteboard_action",
        ):
            if key in event.metadata:
                compact[key] = str(event.metadata.get(key, ""))
    elif event.collector in {
        "package_manager_activity",
        "build_tool_activity",
        "test_runner_activity",
        "local_service_activity",
        "debugger_activity",
        "code_hosting_activity",
    }:
        compact["summary"] = _safe_bridge_summary(event)
        compact["app_name"] = str(event.metadata.get("app_name", ""))
        compact["privacy_level"] = str(event.metadata.get("privacy_level", "redacted"))
        compact["bridge_event"] = bool(event.metadata.get("bridge_event", False))
        for key in (
            "package_manager",
            "build_tool",
            "test_runner",
            "service_kind",
            "debugger_kind",
            "code_hosting_provider",
        ):
            if key in event.metadata:
                compact[key] = str(event.metadata.get(key, ""))
    elif event.collector in {
        "mail_composition_activity",
        "mail_organization_activity",
        "calendar_scheduling_activity",
        "reminder_todo_activity",
    }:
        compact["summary"] = _safe_bridge_summary(event)
        compact["app_name"] = str(event.metadata.get("app_name", ""))
        compact["privacy_level"] = str(event.metadata.get("privacy_level", "redacted"))
        compact["bridge_event"] = bool(event.metadata.get("bridge_event", False))
        for key in (
            "mail_action",
            "mailbox_action",
            "calendar_action",
            "reminder_action",
        ):
            if key in event.metadata:
                compact[key] = str(event.metadata.get(key, ""))
    elif event.collector in {
        "chat_composition_activity",
        "chat_thread_activity",
        "chat_channel_navigation_activity",
        "chat_presence_activity",
    }:
        compact["summary"] = _safe_bridge_summary(event)
        compact["app_name"] = str(event.metadata.get("app_name", ""))
        compact["privacy_level"] = str(event.metadata.get("privacy_level", "redacted"))
        compact["bridge_event"] = bool(event.metadata.get("bridge_event", False))
        for key in (
            "chat_action",
            "thread_action",
            "channel_action",
            "presence_action",
        ):
            if key in event.metadata:
                compact[key] = str(event.metadata.get(key, ""))
    elif event.collector in {
        "document_composition_activity",
        "document_review_activity",
        "document_structure_activity",
        "document_export_publish_activity",
    }:
        compact["summary"] = _safe_bridge_summary(event)
        compact["app_name"] = str(event.metadata.get("app_name", ""))
        compact["privacy_level"] = str(event.metadata.get("privacy_level", "redacted"))
        compact["bridge_event"] = bool(event.metadata.get("bridge_event", False))
        for key in (
            "document_action",
            "review_action",
            "structure_action",
            "publish_action",
        ):
            if key in event.metadata:
                compact[key] = str(event.metadata.get(key, ""))
    elif event.collector in {
        "spreadsheet_editing_activity",
        "spreadsheet_formula_activity",
        "spreadsheet_data_analysis_activity",
        "spreadsheet_import_export_activity",
        "presentation_authoring_activity",
        "presentation_design_activity",
        "presentation_delivery_activity",
        "presentation_export_activity",
    }:
        compact["summary"] = _safe_bridge_summary(event)
        compact["app_name"] = str(event.metadata.get("app_name", ""))
        compact["privacy_level"] = str(event.metadata.get("privacy_level", "redacted"))
        compact["bridge_event"] = bool(event.metadata.get("bridge_event", False))
        for key in (
            "sheet_action",
            "formula_action",
            "data_action",
            "spreadsheet_transfer_action",
            "slide_action",
            "design_action",
            "delivery_action",
            "deck_publish_action",
        ):
            if key in event.metadata:
                compact[key] = str(event.metadata.get(key, ""))
    elif event.collector in {
        "direct_user",
        "voice_wakeup",
        "meeting_audio",
        "meeting_app_activity",
        "call_control_activity",
        "meeting_presentation_activity",
        "meeting_artifact_activity",
        "browser_page_activity",
        "terminal_activity",
        "ide_activity",
        "git_activity",
        "github_activity",
        "code_hosting_activity",
        "accessibility_context",
        "device_state",
        "software_activity",
        "print_scan_activity",
        "search_activity",
        "peripheral_activity",
        "media_activity",
        "focus_task_activity",
        "workspace_layout_activity",
        "window_arrangement_activity",
        "display_arrangement_activity",
        "app_workspace_activity",
        "cloud_sync_activity",
        "auth_activity",
        "credential_activity",
        "passkey_activity",
        "autofill_activity",
        "verification_code_activity",
        "network_activity",
        "automation_activity",
        "virtual_runtime_activity",
        "remote_session_activity",
        "permission_activity",
        "location_activity",
        "resource_activity",
        "storage_activity",
        "wellbeing_activity",
        "policy_activity",
        "notes_activity",
        "bookmark_history_activity",
        "contact_activity",
        "commerce_activity",
        "finance_activity",
        "social_feed_activity",
        "task_manager_activity",
        "issue_tracker_activity",
        "knowledge_base_activity",
        "whiteboard_activity",
        "form_survey_activity",
        "learning_activity",
        "crm_activity",
        "support_desk_activity",
        "analytics_activity",
        "database_activity",
        "cloud_console_activity",
        "incident_activity",
        "file_operation_activity",
        "folder_navigation_activity",
        "file_preview_activity",
        "trash_activity",
        "ai_assistant_activity",
        "pdf_activity",
        "spreadsheet_activity",
        "presentation_activity",
        "file_dialog_activity",
        "system_settings_activity",
        "text_composition_activity",
        "dictation_activity",
        "writing_assist_activity",
        "translation_activity",
        "file_transfer_activity",
        "archive_activity",
        "camera_capture_activity",
        "continuity_activity",
        "command_activity",
        "selection_activity",
        "navigation_activity",
        "edit_history_activity",
        "dock_taskbar_activity",
        "menu_bar_tray_activity",
        "quick_settings_activity",
        "widget_activity",
        "downloads",
        "visual_state",
        "notification_activity",
        "share_activity",
        "calendar_activity",
        "wakeups",
        "channel_activity",
        "communication_activity",
        "mail_activity",
        "document_activity",
        "creative_activity",
        "security_context",
        "agent_runtime",
    }:
        compact["summary"] = _safe_bridge_summary(event)
        compact["app_name"] = str(event.metadata.get("app_name", ""))
        compact["window_title"] = str(event.metadata.get("window_title", ""))
        compact["url"] = str(event.metadata.get("url", ""))
        compact["channel_id"] = str(event.metadata.get("channel_id", ""))
        compact["conversation_id"] = str(event.metadata.get("conversation_id", ""))
        compact["privacy_level"] = str(event.metadata.get("privacy_level", "metadata"))
        compact["bridge_event"] = bool(event.metadata.get("bridge_event", False))
    else:
        compact["summary"] = event.text[:240]
    return compact


def attention_batch_payload(events: list[dict[str, Any]], profile: CollectorProfile) -> dict[str, Any]:
    batch_id = f"attention-{hashlib.sha256(json.dumps(events, sort_keys=True, default=str).encode('utf-8')).hexdigest()[:12]}"
    counts: dict[str, int] = {}
    for event in events:
        collector = str(event.get("collector", "unknown"))
        counts[collector] = counts.get(collector, 0) + 1
    text = _attention_batch_text(events, counts)
    return {
        "batch_id": batch_id,
        "event_type": "attention_batch",
        "source": "activity",
        "stimulus_type": "attention_batch",
        "text": text,
        "event_count": len(events),
        "collector_counts": counts,
        "events": events[-50:],
        "privacy_mode": profile.privacy_mode,
        "occurred_at": _utc_now(),
        "safety_note": "Compact local attention summary; raw screenshots, audio, video, and clipboard contents are not included.",
    }


def _safe_bridge_summary(event: CollectorEvent) -> str:
    if event.collector == "permission_activity":
        return f"Permission/privacy activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "location_activity":
        return f"Location/region activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "cloud_sync_activity":
        return f"Cloud sync activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "workspace_layout_activity":
        return f"Workspace layout activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "window_arrangement_activity":
        return f"Window arrangement activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "display_arrangement_activity":
        return f"Display arrangement activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "app_workspace_activity":
        return f"App workspace activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "browser_window_activity":
        return f"Browser window/session activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "browser_tab_group_activity":
        return f"Browser tab-group activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "browser_profile_activity":
        return f"Browser profile activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "browser_extension_activity":
        return f"Browser extension activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "browser_web_app_activity":
        return f"Browser web-app activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "browser_view_mode_activity":
        return f"Browser view-mode activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "meeting_app_activity":
        return f"Meeting app activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "call_control_activity":
        return f"Meeting call-control activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "meeting_presentation_activity":
        return f"Meeting presentation/share activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "meeting_artifact_activity":
        return f"Meeting artifact activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "keyboard_input_activity":
        return f"Keyboard/input-source activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "ime_activity":
        return f"IME/input composition activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "text_input_surface_activity":
        return f"Text input surface activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "pasteboard_workflow_activity":
        return f"Pasteboard workflow activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "package_manager_activity":
        return f"Package manager activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "build_tool_activity":
        return f"Build tool activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "test_runner_activity":
        return f"Test runner activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "local_service_activity":
        return f"Local service activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "debugger_activity":
        return f"Debugger activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "code_hosting_activity":
        return f"Code hosting activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "mail_composition_activity":
        return f"Mail composition activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "mail_organization_activity":
        return f"Mail organization activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "calendar_scheduling_activity":
        return f"Calendar scheduling activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "reminder_todo_activity":
        return f"Reminder/to-do activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "chat_composition_activity":
        return f"Chat composition activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "chat_thread_activity":
        return f"Chat thread activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "chat_channel_navigation_activity":
        return f"Chat channel navigation activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "chat_presence_activity":
        return f"Chat presence activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "document_composition_activity":
        return f"Document composition activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "document_review_activity":
        return f"Document review activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "document_structure_activity":
        return f"Document structure activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "document_export_publish_activity":
        return f"Document export/publish activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "auth_activity":
        return f"Authentication activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "credential_activity":
        return f"Credential manager activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "passkey_activity":
        return f"Passkey/security-key activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "autofill_activity":
        return f"Autofill activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "verification_code_activity":
        return f"Verification-code activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "network_activity":
        return f"Network/API activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "search_activity":
        return f"Search/launcher activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "print_scan_activity":
        return f"Print/scan activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "media_activity":
        return f"Media activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "automation_activity":
        return f"Automation activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "virtual_runtime_activity":
        return f"Container/VM runtime activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "remote_session_activity":
        return f"Remote/screen-share activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "policy_activity":
        return f"Policy/compliance activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "notes_activity":
        return f"Notes/checklist activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "bookmark_history_activity":
        return f"Bookmark/history activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "contact_activity":
        return f"Contact activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "commerce_activity":
        return f"Commerce activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "finance_activity":
        return f"Finance/wallet activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "social_feed_activity":
        return f"Social/feed activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "task_manager_activity":
        return f"Task manager activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "issue_tracker_activity":
        return f"Issue tracker activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "knowledge_base_activity":
        return f"Knowledge-base activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "whiteboard_activity":
        return f"Whiteboard activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "form_survey_activity":
        return f"Form/survey activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "learning_activity":
        return f"Learning/course activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "crm_activity":
        return f"CRM activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "support_desk_activity":
        return f"Support desk activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "analytics_activity":
        return f"Analytics activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "database_activity":
        return f"Database activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "cloud_console_activity":
        return f"Cloud console activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "incident_activity":
        return f"Incident/on-call activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "file_operation_activity":
        return f"File operation activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "folder_navigation_activity":
        return f"Folder navigation activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "file_preview_activity":
        return f"File preview activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "trash_activity":
        return f"Trash/recycle-bin activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "ai_assistant_activity":
        return f"AI assistant activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "pdf_activity":
        return f"PDF activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "spreadsheet_activity":
        return f"Spreadsheet activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "presentation_activity":
        return f"Presentation activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "spreadsheet_editing_activity":
        return f"Spreadsheet editing activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "spreadsheet_formula_activity":
        return f"Spreadsheet formula activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "spreadsheet_data_analysis_activity":
        return f"Spreadsheet data-analysis activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "spreadsheet_import_export_activity":
        return f"Spreadsheet import/export activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "presentation_authoring_activity":
        return f"Presentation authoring activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "presentation_design_activity":
        return f"Presentation design activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "presentation_delivery_activity":
        return f"Presentation delivery activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "presentation_export_activity":
        return f"Presentation export activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "file_dialog_activity":
        return f"File dialog activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "system_settings_activity":
        return f"System settings activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "text_composition_activity":
        return f"Text composition activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "dictation_activity":
        return f"Dictation/voice typing activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "writing_assist_activity":
        return f"Writing assist activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "translation_activity":
        return f"Translation activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "file_transfer_activity":
        return f"File transfer activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "archive_activity":
        return f"Archive/compression activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "camera_capture_activity":
        return f"Camera/photo capture activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "continuity_activity":
        return f"Cross-device continuity activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "command_activity":
        return f"In-app command activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "selection_activity":
        return f"In-app selection activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "navigation_activity":
        return f"In-app navigation activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "edit_history_activity":
        return f"Edit history activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "dock_taskbar_activity":
        return f"Dock/taskbar activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "menu_bar_tray_activity":
        return f"Menu bar/tray activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "quick_settings_activity":
        return f"Quick settings activity observed: {event.stimulus_type.replace('_', ' ')}."
    if event.collector == "widget_activity":
        return f"Widget activity observed: {event.stimulus_type.replace('_', ' ')}."
    return event.text[:240]


def _attention_batch_text(events: list[dict[str, Any]], counts: dict[str, int]) -> str:
    lines = [f"Attention batch: {len(events)} filtered local event(s)."]
    filesystem_paths = [str(event.get("path", "")) for event in events if event.get("collector") == "filesystem" and event.get("path")]
    if filesystem_paths:
        lines.append(f"Filesystem changes: {len(filesystem_paths)} file(s): {', '.join(filesystem_paths[:5])}.")
    for collector in ("active_window", "browser"):
        latest = next((event for event in reversed(events) if event.get("collector") == collector), None)
        if latest:
            label = "Active window" if collector == "active_window" else "Browser context"
            title = str(latest.get("window_title") or latest.get("url") or "unknown")
            app = str(latest.get("app_name") or collector)
            lines.append(f"{label}: {app} - {title}.")
    if counts.get("browser_window_activity"):
        lines.append(f"Browser window/session event(s): {counts['browser_window_activity']}; tab lists, titles, and page contents are omitted.")
    if counts.get("browser_tab_group_activity"):
        lines.append(f"Browser tab-group event(s): {counts['browser_tab_group_activity']}; group names, tab titles, and URLs are omitted.")
    if counts.get("browser_profile_activity"):
        lines.append(f"Browser profile event(s): {counts['browser_profile_activity']}; profile names, account details, and private-window contents are omitted.")
    if counts.get("browser_extension_activity"):
        lines.append(f"Browser extension event(s): {counts['browser_extension_activity']}; extension names, permission details, and page contents are omitted.")
    if counts.get("browser_web_app_activity"):
        lines.append(f"Browser web-app event(s): {counts['browser_web_app_activity']}; app names, origins, and notification contents are omitted.")
    if counts.get("browser_view_mode_activity"):
        lines.append(f"Browser view-mode event(s): {counts['browser_view_mode_activity']}; page contents, find queries, and media titles are omitted.")
    if counts.get("clipboard"):
        latest_clipboard = next((event for event in reversed(events) if event.get("collector") == "clipboard"), {})
        lines.append(f"Clipboard changed ({latest_clipboard.get('text_length', 0)} chars); content omitted.")
    if counts.get("screen_ocr"):
        latest_ocr = next((event for event in reversed(events) if event.get("collector") == "screen_ocr"), {})
        lines.append(f"Screen OCR changed ({latest_ocr.get('text_length', 0)} chars); raw text omitted.")
    if counts.get("screenshot"):
        lines.append(f"Screenshot capture event(s): {counts['screenshot']}; image omitted.")
    if counts.get("video_frame"):
        lines.append(f"Video keyframe event(s): {counts['video_frame']}; frame omitted.")
    if counts.get("voice_wakeup"):
        lines.append(f"Voice wakeup event(s): {counts['voice_wakeup']}; transcript text is compacted by the voice helper.")
    if counts.get("meeting_audio"):
        lines.append(f"Meeting audio event(s): {counts['meeting_audio']}; raw audio and transcript bodies are omitted.")
    if counts.get("meeting_app_activity"):
        lines.append(f"Meeting app event(s): {counts['meeting_app_activity']}; titles, participant names, and room details are omitted.")
    if counts.get("call_control_activity"):
        lines.append(f"Meeting call-control event(s): {counts['call_control_activity']}; chat, captions, reactions, and transcript contents are omitted.")
    if counts.get("meeting_presentation_activity"):
        lines.append(f"Meeting presentation/share event(s): {counts['meeting_presentation_activity']}; shared window names and screen contents are omitted.")
    if counts.get("meeting_artifact_activity"):
        lines.append(f"Meeting artifact event(s): {counts['meeting_artifact_activity']}; recording, transcript, notes, whiteboard, and action-item contents are omitted.")
    if counts.get("visual_state"):
        lines.append(f"Visual-state event(s): {counts['visual_state']}; visual contents are summarized by the bridge.")
    if counts.get("device_state"):
        lines.append(f"Device/session state event(s): {counts['device_state']}.")
    if counts.get("software_activity"):
        lines.append(f"Software/install event(s): {counts['software_activity']}; package logs and installer payloads are omitted.")
    if counts.get("print_scan_activity"):
        lines.append(f"Print/scan event(s): {counts['print_scan_activity']}; document contents are omitted.")
    if counts.get("search_activity"):
        lines.append(f"Search/launcher event(s): {counts['search_activity']}; raw query text is redacted by bridge policy.")
    if counts.get("peripheral_activity"):
        lines.append(f"Peripheral event(s): {counts['peripheral_activity']}.")
    if counts.get("media_activity"):
        lines.append(f"Media event(s): {counts['media_activity']}; media contents are omitted.")
    if counts.get("focus_task_activity"):
        lines.append(f"Focus/task event(s): {counts['focus_task_activity']}.")
    if counts.get("workspace_layout_activity"):
        lines.append(f"Workspace layout event(s): {counts['workspace_layout_activity']}; workspace names, visible windows, and contents are omitted.")
    if counts.get("window_arrangement_activity"):
        lines.append(f"Window arrangement event(s): {counts['window_arrangement_activity']}; window titles, app contents, and layout details are omitted.")
    if counts.get("display_arrangement_activity"):
        lines.append(f"Display arrangement event(s): {counts['display_arrangement_activity']}; precise display names and visible contents are omitted.")
    if counts.get("app_workspace_activity"):
        lines.append(f"App workspace event(s): {counts['app_workspace_activity']}; workspace/project names and restored contents are omitted.")
    if counts.get("keyboard_input_activity"):
        lines.append(f"Keyboard/input-source event(s): {counts['keyboard_input_activity']}; typed text and shortcut payloads are omitted.")
    if counts.get("ime_activity"):
        lines.append(f"IME/input composition event(s): {counts['ime_activity']}; candidate text, committed text, and conversion contents are omitted.")
    if counts.get("text_input_surface_activity"):
        lines.append(f"Text input surface event(s): {counts['text_input_surface_activity']}; field values, labels, validation bodies, and typed text are omitted.")
    if counts.get("pasteboard_workflow_activity"):
        lines.append(f"Pasteboard workflow event(s): {counts['pasteboard_workflow_activity']}; clipboard contents and history item values are omitted.")
    if counts.get("cloud_sync_activity"):
        lines.append(f"Cloud sync event(s): {counts['cloud_sync_activity']}; file contents and private paths are omitted.")
    if counts.get("auth_activity"):
        lines.append(f"Authentication event(s): {counts['auth_activity']}; credentials, tokens, and codes are blocked.")
    if counts.get("credential_activity"):
        lines.append(f"Credential manager event(s): {counts['credential_activity']}; usernames, passwords, vault items, and credential values are blocked.")
    if counts.get("passkey_activity"):
        lines.append(f"Passkey/security-key event(s): {counts['passkey_activity']}; relying-party details, key handles, and biometric data are blocked.")
    if counts.get("autofill_activity"):
        lines.append(f"Autofill event(s): {counts['autofill_activity']}; field values, addresses, cards, and identity details are blocked.")
    if counts.get("verification_code_activity"):
        lines.append(f"Verification-code event(s): {counts['verification_code_activity']}; OTPs, backup codes, and message contents are blocked.")
    if counts.get("network_activity"):
        lines.append(f"Network/API event(s): {counts['network_activity']}; request bodies and secrets are omitted.")
    if counts.get("automation_activity"):
        lines.append(f"Automation event(s): {counts['automation_activity']}; workflow payloads are omitted.")
    if counts.get("virtual_runtime_activity"):
        lines.append(f"Container/VM runtime event(s): {counts['virtual_runtime_activity']}; logs are summarized by the bridge.")
    if counts.get("remote_session_activity"):
        lines.append(f"Remote/screen-share event(s): {counts['remote_session_activity']}; screen contents are omitted.")
    if counts.get("permission_activity"):
        lines.append(f"Permission/privacy event(s): {counts['permission_activity']}; protected data and prompts are redacted.")
    if counts.get("location_activity"):
        lines.append(f"Location/region event(s): {counts['location_activity']}; precise coordinates are omitted.")
    if counts.get("resource_activity"):
        lines.append(f"Resource pressure event(s): {counts['resource_activity']}.")
    if counts.get("storage_activity"):
        lines.append(f"Storage/backup event(s): {counts['storage_activity']}; file contents are omitted.")
    if counts.get("wellbeing_activity"):
        lines.append(f"Wellbeing/app-limit event(s): {counts['wellbeing_activity']}.")
    if counts.get("policy_activity"):
        lines.append(f"Policy/compliance event(s): {counts['policy_activity']}; restricted contents are omitted.")
    if counts.get("notes_activity"):
        lines.append(f"Notes/checklist event(s): {counts['notes_activity']}; note contents are omitted.")
    if counts.get("bookmark_history_activity"):
        lines.append(f"Bookmark/history event(s): {counts['bookmark_history_activity']}; query text and private URLs are omitted.")
    if counts.get("contact_activity"):
        lines.append(f"Contact event(s): {counts['contact_activity']}; contact details are omitted.")
    if counts.get("commerce_activity"):
        lines.append(f"Commerce event(s): {counts['commerce_activity']}; item, address, and payment details are omitted.")
    if counts.get("finance_activity"):
        lines.append(f"Finance/wallet event(s): {counts['finance_activity']}; amounts, account details, and tokens are omitted.")
    if counts.get("social_feed_activity"):
        lines.append(f"Social/feed event(s): {counts['social_feed_activity']}; post and comment bodies are omitted.")
    if counts.get("task_manager_activity"):
        lines.append(f"Task manager event(s): {counts['task_manager_activity']}; task titles, comments, and bodies are omitted.")
    if counts.get("issue_tracker_activity"):
        lines.append(f"Issue tracker event(s): {counts['issue_tracker_activity']}; issue titles, comments, and bodies are omitted.")
    if counts.get("knowledge_base_activity"):
        lines.append(f"Knowledge-base event(s): {counts['knowledge_base_activity']}; page contents and search text are omitted.")
    if counts.get("whiteboard_activity"):
        lines.append(f"Whiteboard event(s): {counts['whiteboard_activity']}; board contents are omitted.")
    if counts.get("form_survey_activity"):
        lines.append(f"Form/survey event(s): {counts['form_survey_activity']}; answers and response bodies are omitted.")
    if counts.get("learning_activity"):
        lines.append(f"Learning/course event(s): {counts['learning_activity']}; lesson and quiz contents are omitted.")
    if counts.get("crm_activity"):
        lines.append(f"CRM event(s): {counts['crm_activity']}; customer fields and notes are omitted.")
    if counts.get("support_desk_activity"):
        lines.append(f"Support desk event(s): {counts['support_desk_activity']}; customer ticket contents are omitted.")
    if counts.get("analytics_activity"):
        lines.append(f"Analytics event(s): {counts['analytics_activity']}; dashboard data and query results are omitted.")
    if counts.get("database_activity"):
        lines.append(f"Database event(s): {counts['database_activity']}; SQL, rows, and credentials are omitted.")
    if counts.get("cloud_console_activity"):
        lines.append(f"Cloud console event(s): {counts['cloud_console_activity']}; resource IDs, secrets, and account details are omitted.")
    if counts.get("incident_activity"):
        lines.append(f"Incident/on-call event(s): {counts['incident_activity']}; incident details and logs are omitted.")
    if counts.get("file_operation_activity"):
        lines.append(f"File operation event(s): {counts['file_operation_activity']}; paths, filenames, tags, and file contents are omitted.")
    if counts.get("folder_navigation_activity"):
        lines.append(f"Folder navigation event(s): {counts['folder_navigation_activity']}; folder paths, names, and view contents are omitted.")
    if counts.get("file_preview_activity"):
        lines.append(f"File preview event(s): {counts['file_preview_activity']}; preview contents, metadata details, paths, and filenames are omitted.")
    if counts.get("trash_activity"):
        lines.append(f"Trash/recycle-bin event(s): {counts['trash_activity']}; trashed item paths, filenames, and contents are omitted.")
    if counts.get("ai_assistant_activity"):
        lines.append(f"AI assistant event(s): {counts['ai_assistant_activity']}; prompts, responses, and tool payloads are omitted.")
    if counts.get("pdf_activity"):
        lines.append(f"PDF event(s): {counts['pdf_activity']}; document text, annotations, form values, and signatures are omitted.")
    if counts.get("spreadsheet_activity"):
        lines.append(f"Spreadsheet event(s): {counts['spreadsheet_activity']}; cell values, formulas, and sheet contents are omitted.")
    if counts.get("presentation_activity"):
        lines.append(f"Presentation event(s): {counts['presentation_activity']}; slide contents and speaker notes are omitted.")
    if counts.get("spreadsheet_editing_activity"):
        lines.append(f"Spreadsheet editing event(s): {counts['spreadsheet_editing_activity']}; workbook names, sheet names, ranges, and cell values are omitted.")
    if counts.get("spreadsheet_formula_activity"):
        lines.append(f"Spreadsheet formula event(s): {counts['spreadsheet_formula_activity']}; formulas, cell values, named ranges, and sheet contents are omitted.")
    if counts.get("spreadsheet_data_analysis_activity"):
        lines.append(f"Spreadsheet data-analysis event(s): {counts['spreadsheet_data_analysis_activity']}; source data, pivot labels, chart labels, filters, and validation values are omitted.")
    if counts.get("spreadsheet_import_export_activity"):
        lines.append(f"Spreadsheet import/export event(s): {counts['spreadsheet_import_export_activity']}; filenames, links, recipients, destinations, and connection details are omitted.")
    if counts.get("presentation_authoring_activity"):
        lines.append(f"Presentation authoring event(s): {counts['presentation_authoring_activity']}; slide text, speaker notes, outlines, object text, and asset names are omitted.")
    if counts.get("presentation_design_activity"):
        lines.append(f"Presentation design event(s): {counts['presentation_design_activity']}; theme names, slide content, media names, animation details, and chart data are omitted.")
    if counts.get("presentation_delivery_activity"):
        lines.append(f"Presentation delivery event(s): {counts['presentation_delivery_activity']}; deck titles, slide text, speaker notes, and audience details are omitted.")
    if counts.get("presentation_export_activity"):
        lines.append(f"Presentation export event(s): {counts['presentation_export_activity']}; filenames, links, recipients, destinations, handouts, and recording details are omitted.")
    if counts.get("file_dialog_activity"):
        lines.append(f"File dialog event(s): {counts['file_dialog_activity']}; selected paths and filenames are omitted.")
    if counts.get("system_settings_activity"):
        lines.append(f"System settings event(s): {counts['system_settings_activity']}; sensitive preference values are omitted.")
    if counts.get("text_composition_activity"):
        lines.append(f"Text composition event(s): {counts['text_composition_activity']}; draft bodies, snippets, templates, and typed text are omitted.")
    if counts.get("dictation_activity"):
        lines.append(f"Dictation event(s): {counts['dictation_activity']}; raw audio and transcript bodies are omitted.")
    if counts.get("writing_assist_activity"):
        lines.append(f"Writing assist event(s): {counts['writing_assist_activity']}; original text, suggestions, and replacements are omitted.")
    if counts.get("translation_activity"):
        lines.append(f"Translation event(s): {counts['translation_activity']}; source text, translated text, and detected language contents are omitted.")
    if counts.get("file_transfer_activity"):
        lines.append(f"File transfer event(s): {counts['file_transfer_activity']}; filenames, URLs, recipients, and transfer payloads are omitted.")
    if counts.get("archive_activity"):
        lines.append(f"Archive/compression event(s): {counts['archive_activity']}; archive paths, passwords, and contents are omitted.")
    if counts.get("camera_capture_activity"):
        lines.append(f"Camera/photo capture event(s): {counts['camera_capture_activity']}; captured media and decoded QR contents are omitted.")
    if counts.get("continuity_activity"):
        lines.append(f"Continuity event(s): {counts['continuity_activity']}; device names, clipboard contents, and message bodies are omitted.")
    if counts.get("command_activity"):
        lines.append(f"In-app command event(s): {counts['command_activity']}; command labels, menu paths, and command payloads are omitted.")
    if counts.get("selection_activity"):
        lines.append(f"In-app selection event(s): {counts['selection_activity']}; selected text, object names, and values are omitted.")
    if counts.get("navigation_activity"):
        lines.append(f"In-app navigation event(s): {counts['navigation_activity']}; item labels, routes, and search text are omitted.")
    if counts.get("edit_history_activity"):
        lines.append(f"Edit history event(s): {counts['edit_history_activity']}; document contents and version details are omitted.")
    if counts.get("dock_taskbar_activity"):
        lines.append(f"Dock/taskbar event(s): {counts['dock_taskbar_activity']}; app labels, item names, badges, and jump-list contents are omitted.")
    if counts.get("menu_bar_tray_activity"):
        lines.append(f"Menu bar/tray event(s): {counts['menu_bar_tray_activity']}; item labels, tray payloads, and background app contents are omitted.")
    if counts.get("quick_settings_activity"):
        lines.append(f"Quick settings event(s): {counts['quick_settings_activity']}; precise device and network details are omitted.")
    if counts.get("widget_activity"):
        lines.append(f"Widget event(s): {counts['widget_activity']}; widget names, alerts, and payload contents are omitted.")
    if counts.get("app_lifecycle"):
        lines.append(f"App lifecycle event(s): {counts['app_lifecycle']}.")
    if counts.get("window_lifecycle"):
        latest_window = next((event for event in reversed(events) if event.get("collector") == "window_lifecycle"), {})
        lines.append(
            f"Window lifecycle: {latest_window.get('app_name', 'app')} - {latest_window.get('window_title', 'window')}."
        )
    if counts.get("browser_lifecycle"):
        latest_browser = next((event for event in reversed(events) if event.get("collector") == "browser_lifecycle"), {})
        lines.append(f"Browser lifecycle: {latest_browser.get('window_title') or latest_browser.get('url') or 'browser event'}.")
    if counts.get("input_device"):
        lines.append(f"Input-device event(s): {counts['input_device']}; raw typed text is never collected.")
    if counts.get("browser_page_activity"):
        lines.append(f"Browser page activity event(s): {counts['browser_page_activity']}; selected text and form values are redacted by bridge policy.")
    if counts.get("terminal_activity"):
        lines.append(f"Terminal activity event(s): {counts['terminal_activity']}; command output is summarized by the bridge.")
    if counts.get("ide_activity"):
        lines.append(f"IDE activity event(s): {counts['ide_activity']}; file paths and diagnostics are compacted.")
    if counts.get("package_manager_activity"):
        lines.append(f"Package manager event(s): {counts['package_manager_activity']}; package names, registry URLs, scripts, and logs are omitted.")
    if counts.get("build_tool_activity"):
        lines.append(f"Build tool event(s): {counts['build_tool_activity']}; target names, paths, artifacts, and logs are omitted.")
    if counts.get("test_runner_activity"):
        lines.append(f"Test runner event(s): {counts['test_runner_activity']}; test names, assertions, snapshots, coverage details, and logs are omitted.")
    if counts.get("local_service_activity"):
        lines.append(f"Local service event(s): {counts['local_service_activity']}; endpoint paths, ports when sensitive, and logs are omitted.")
    if counts.get("debugger_activity"):
        lines.append(f"Debugger event(s): {counts['debugger_activity']}; stack frames, watch expressions, and variable values are omitted.")
    if counts.get("git_activity"):
        lines.append(f"Git activity event(s): {counts['git_activity']}; diffs and patches are omitted.")
    if counts.get("github_activity"):
        lines.append(f"GitHub activity event(s): {counts['github_activity']}; remote content is summarized.")
    if counts.get("code_hosting_activity"):
        lines.append(f"Code-hosting event(s): {counts['code_hosting_activity']}; PR, issue, CI, and review content is redacted.")
    if counts.get("accessibility_context"):
        lines.append(f"Accessibility context event(s): {counts['accessibility_context']}; UI values and selected text are redacted unless explicitly summarized by the bridge.")
    if counts.get("notification_activity"):
        lines.append(f"Notification event(s): {counts['notification_activity']}.")
    if counts.get("share_activity"):
        lines.append(f"Share/drag-drop event(s): {counts['share_activity']}; shared contents are omitted.")
    if counts.get("downloads"):
        lines.append(f"Download/export event(s): {counts['downloads']}; file contents are omitted.")
    if counts.get("calendar_activity"):
        lines.append(f"Calendar event(s): {counts['calendar_activity']}.")
    if counts.get("wakeups"):
        lines.append(f"Wakeup event(s): {counts['wakeups']}.")
    if counts.get("calendar_scheduling_activity"):
        lines.append(f"Calendar scheduling event(s): {counts['calendar_scheduling_activity']}; titles, attendees, locations, notes, and availability details are omitted.")
    if counts.get("reminder_todo_activity"):
        lines.append(f"Reminder/to-do event(s): {counts['reminder_todo_activity']}; titles, notes, lists, and due-date details are omitted.")
    if counts.get("direct_user"):
        lines.append(f"Direct user intent event(s): {counts['direct_user']}.")
    if counts.get("channel_activity"):
        lines.append(f"Channel activity event(s): {counts['channel_activity']}; message body is compacted by channel policy.")
    if counts.get("communication_activity"):
        lines.append(f"Communication event(s): {counts['communication_activity']}; message body is compacted by channel policy.")
    if counts.get("chat_composition_activity"):
        lines.append(f"Chat composition event(s): {counts['chat_composition_activity']}; message bodies, recipients, attachment names, slash command payloads, and draft contents are omitted.")
    if counts.get("chat_thread_activity"):
        lines.append(f"Chat thread event(s): {counts['chat_thread_activity']}; thread titles, participants, replies, and message bodies are omitted.")
    if counts.get("chat_channel_navigation_activity"):
        lines.append(f"Chat channel navigation event(s): {counts['chat_channel_navigation_activity']}; workspace names, channel names, search terms, and saved item contents are omitted.")
    if counts.get("chat_presence_activity"):
        lines.append(f"Chat presence event(s): {counts['chat_presence_activity']}; custom status text, availability notes, and notification preferences are omitted.")
    if counts.get("mail_activity"):
        lines.append(f"Mail event(s): {counts['mail_activity']}; email body is omitted.")
    if counts.get("mail_composition_activity"):
        lines.append(f"Mail composition event(s): {counts['mail_composition_activity']}; subjects, recipients, bodies, attachments, and filenames are omitted.")
    if counts.get("mail_organization_activity"):
        lines.append(f"Mail organization event(s): {counts['mail_organization_activity']}; senders, subjects, queries, mailbox labels, and rule details are omitted.")
    if counts.get("document_composition_activity"):
        lines.append(f"Document composition event(s): {counts['document_composition_activity']}; document text, titles, selected content, paths, and inserted content are omitted.")
    if counts.get("document_review_activity"):
        lines.append(f"Document review event(s): {counts['document_review_activity']}; comments, suggestions, reviewer names, mentions, and selected text are omitted.")
    if counts.get("document_structure_activity"):
        lines.append(f"Document structure event(s): {counts['document_structure_activity']}; section names, headings, outline text, and document contents are omitted.")
    if counts.get("document_export_publish_activity"):
        lines.append(f"Document export/publish event(s): {counts['document_export_publish_activity']}; filenames, links, recipients, destinations, and permission details are omitted.")
    if counts.get("document_activity"):
        lines.append(f"Document event(s): {counts['document_activity']}; document contents are not included.")
    if counts.get("creative_activity"):
        lines.append(f"Creative app event(s): {counts['creative_activity']}; asset contents are not included.")
    if counts.get("security_context"):
        lines.append(f"Security context event(s): {counts['security_context']}; sensitive contents are blocked.")
    if counts.get("agent_runtime"):
        lines.append(f"Agent runtime event(s): {counts['agent_runtime']}.")
    return " ".join(lines)
