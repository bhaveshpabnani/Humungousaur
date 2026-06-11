from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.cognition.models import CognitivePriority, new_id, utc_now
from humungousaur.cognition.queue import RuntimeEventQueue
from humungousaur.memory.event_store import EventStore


SEMANTIC_EVENT_TYPES = {
    "system_session_started",
    "system_idle_started",
    "system_idle_ended",
    "app_focus_changed",
    "app_lifecycle_changed",
    "browser_context_changed",
    "browser_lifecycle_changed",
    "browser_window_activity",
    "browser_tab_group_activity",
    "browser_profile_activity",
    "browser_extension_activity",
    "browser_web_app_activity",
    "browser_view_mode_activity",
    "browser_page_activity",
    "research_session_started",
    "research_session_updated",
    "research_session_ended",
    "project_files_changed",
    "voice_wake_detected",
    "voice_command_received",
    "wakeup_activity",
    "screen_context_changed",
    "clipboard_changed",
    "device_state_changed",
    "meeting_app_activity",
    "call_control_activity",
    "meeting_presentation_activity",
    "meeting_artifact_activity",
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
    "keyboard_input_activity",
    "ime_activity",
    "text_input_surface_activity",
    "pasteboard_workflow_activity",
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
    "spreadsheet_editing_activity",
    "spreadsheet_formula_activity",
    "spreadsheet_data_analysis_activity",
    "spreadsheet_import_export_activity",
    "presentation_authoring_activity",
    "presentation_design_activity",
    "presentation_delivery_activity",
    "presentation_export_activity",
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
    "download_activity",
    "input_device_activity",
    "accessibility_context_changed",
    "agent_runtime_activity",
    "calendar_activity",
    "calendar_scheduling_activity",
    "reminder_todo_activity",
    "channel_activity",
    "communication_activity",
    "chat_composition_activity",
    "chat_thread_activity",
    "chat_channel_navigation_activity",
    "chat_presence_activity",
    "creative_activity",
    "document_activity",
    "document_composition_activity",
    "document_review_activity",
    "document_structure_activity",
    "document_export_publish_activity",
    "ide_activity",
    "package_manager_activity",
    "build_tool_activity",
    "test_runner_activity",
    "local_service_activity",
    "debugger_activity",
    "git_activity",
    "github_activity",
    "mail_activity",
    "mail_composition_activity",
    "mail_organization_activity",
    "meeting_audio_activity",
    "notification_activity",
    "share_activity",
    "security_context_changed",
    "terminal_activity",
    "visual_state_changed",
    "window_lifecycle_changed",
    "user_returned_to_work",
    "task_context_resumed",
    "possible_blocker_detected",
    "explicit_user_request",
    "external_message_received",
    "calendar_event_started",
    "ci_failure_detected",
}

PASSIVE_CONTEXT_TYPES = {
    "app_focus_changed",
    "browser_context_changed",
    "browser_window_activity",
    "browser_tab_group_activity",
    "browser_profile_activity",
    "browser_extension_activity",
    "browser_web_app_activity",
    "browser_view_mode_activity",
    "research_session_updated",
    "project_files_changed",
    "screen_context_changed",
    "clipboard_changed",
    "device_state_changed",
    "meeting_app_activity",
    "call_control_activity",
    "meeting_presentation_activity",
    "meeting_artifact_activity",
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
    "keyboard_input_activity",
    "ime_activity",
    "text_input_surface_activity",
    "pasteboard_workflow_activity",
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
    "spreadsheet_editing_activity",
    "spreadsheet_formula_activity",
    "spreadsheet_data_analysis_activity",
    "spreadsheet_import_export_activity",
    "presentation_authoring_activity",
    "presentation_design_activity",
    "presentation_delivery_activity",
    "presentation_export_activity",
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
    "download_activity",
    "accessibility_context_changed",
    "notification_activity",
    "calendar_activity",
    "calendar_scheduling_activity",
    "reminder_todo_activity",
    "channel_activity",
    "communication_activity",
    "chat_composition_activity",
    "chat_thread_activity",
    "chat_channel_navigation_activity",
    "chat_presence_activity",
    "share_activity",
    "mail_activity",
    "mail_composition_activity",
    "mail_organization_activity",
    "document_composition_activity",
    "document_review_activity",
    "document_structure_activity",
    "document_export_publish_activity",
    "meeting_audio_activity",
    "document_activity",
    "creative_activity",
    "visual_state_changed",
    "security_context_changed",
    "agent_runtime_activity",
    "package_manager_activity",
    "build_tool_activity",
    "test_runner_activity",
    "local_service_activity",
    "debugger_activity",
    "git_activity",
    "github_activity",
    "wakeup_activity",
}


@dataclass(slots=True)
class SemanticEvent:
    event_id: str
    event_type: str
    source: str
    summary: str
    occurred_at: str
    metadata: dict[str, Any] = field(default_factory=dict)
    related_goal_id: str = ""
    related_task_id: str = ""
    confidence: float = 1.0
    privacy_level: str = "compact"
    raw_ref: str = ""
    sent_to_llm: bool = False


@dataclass(slots=True)
class AutonomousActionCandidate:
    action_id: str
    trigger_event_id: str
    action_type: str
    reason: str
    risk: str = "low"
    requires_user_approval: bool = False
    status: str = "queued"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)


def current_context_path(config: AgentConfig) -> Path:
    return config.normalized().data_dir / "current_context.md"


def events_markdown_path(config: AgentConfig) -> Path:
    return config.normalized().data_dir / "events.md"


def semantic_events_status(config: AgentConfig, *, limit: int = 20) -> dict[str, Any]:
    normalized = config.normalized()
    limit = max(1, min(limit, 100))
    memory = EventStore(normalized.memory_db_path)
    recent = memory.tail(limit=max(limit * 6, 50))
    semantic_events = [event for event in recent if event.get("event_type") == "semantic_event"][:limit]
    action_candidates = [event for event in recent if event.get("event_type") == "autonomous_action_candidate"][:limit]
    context_path = current_context_path(normalized)
    timeline_path = events_markdown_path(normalized)
    return {
        "semantic_events": semantic_events,
        "action_candidates": action_candidates,
        "queued_action_events": [
            asdict(event)
            for event in RuntimeEventQueue(normalized.cognition_db_path).queued(limit=limit)
            if event.source == "semantic_trigger" or event.event_type == "AUTONOMOUS_ACTION_CANDIDATE"
        ],
        "current_context_path": str(context_path),
        "events_path": str(timeline_path),
        "current_context_exists": context_path.exists(),
        "events_exists": timeline_path.exists(),
        "current_context_preview": _preview_file(context_path),
        "events_preview": _preview_file(timeline_path),
    }


def rebuild_current_context(config: AgentConfig, *, limit: int = 40, record_event: bool = True) -> dict[str, Any]:
    normalized = config.normalized()
    memory = EventStore(normalized.memory_db_path)
    recent = [event for event in memory.tail(limit=max(limit * 8, 100)) if event.get("event_type") == "semantic_event"][:limit]
    actions = [event for event in memory.tail(limit=max(limit * 8, 100)) if event.get("event_type") == "autonomous_action_candidate"][:limit]
    context_markdown = _render_current_context(recent, actions)
    events_markdown = _render_events_markdown(recent)
    context_path = current_context_path(normalized)
    timeline_path = events_markdown_path(normalized)
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(context_markdown, encoding="utf-8")
    timeline_path.write_text(events_markdown, encoding="utf-8")
    if record_event:
        memory.append(
            "current_context_brief",
            {
                "current_context_path": str(context_path),
                "events_path": str(timeline_path),
                "semantic_event_count": len(recent),
                "action_candidate_count": len(actions),
                "privacy_note": "Generated from compact semantic events, not raw screenshots, audio, video, or clipboard contents.",
            },
        )
    return {
        "current_context_path": str(context_path),
        "events_path": str(timeline_path),
        "semantic_event_count": len(recent),
        "action_candidate_count": len(actions),
    }


def record_attention_batch_semantics(config: AgentConfig, attention_batch: dict[str, Any]) -> dict[str, Any]:
    normalized = config.normalized()
    events = semantic_events_from_attention_batch(attention_batch)
    return record_semantic_events(normalized, events)


def record_stimulus_semantics(config: AgentConfig, stimulus: dict[str, Any], *, decision: str = "") -> dict[str, Any]:
    normalized = config.normalized()
    events = semantic_events_from_stimulus(stimulus, decision=decision)
    if not events:
        return {"semantic_events": [], "action_candidates": [], "context": {}}
    return record_semantic_events(normalized, events)


def record_semantic_events(config: AgentConfig, events: list[SemanticEvent]) -> dict[str, Any]:
    normalized = config.normalized()
    if not events:
        return {"semantic_events": [], "action_candidates": [], "context": rebuild_current_context(normalized, limit=40, record_event=False)}
    memory = EventStore(normalized.memory_db_path)
    recorded_events: list[dict[str, Any]] = []
    queued_candidates: list[dict[str, Any]] = []
    for event in events:
        payload = asdict(event)
        memory.append("semantic_event", payload)
        recorded_events.append(payload)
        for candidate in deterministic_action_candidates(normalized, event):
            candidate_payload = asdict(candidate)
            memory.append("autonomous_action_candidate", candidate_payload)
            RuntimeEventQueue(normalized.cognition_db_path).push(
                "AUTONOMOUS_ACTION_CANDIDATE",
                payload=candidate_payload,
                priority=_candidate_priority(candidate),
                source="semantic_trigger",
            )
            queued_candidates.append(candidate_payload)
    context = rebuild_current_context(normalized, limit=40, record_event=False)
    return {"semantic_events": recorded_events, "action_candidates": queued_candidates, "context": context}


def semantic_events_from_attention_batch(batch: dict[str, Any]) -> list[SemanticEvent]:
    compact_events = batch.get("events", [])
    if not isinstance(compact_events, list):
        compact_events = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in compact_events:
        if isinstance(item, dict):
            grouped.setdefault(str(item.get("collector") or "unknown"), []).append(item)
    occurred_at = str(batch.get("occurred_at") or utc_now())
    batch_id = str(batch.get("batch_id") or "")
    semantic: list[SemanticEvent] = []
    if grouped.get("active_window"):
        latest = grouped["active_window"][-1]
        semantic.append(
            _event(
                "app_focus_changed",
                "activity",
                _active_window_summary(latest),
                occurred_at=occurred_at,
                metadata=_safe_subset(latest, ("app_name", "window_title", "collector", "stimulus_type")),
                raw_ref=batch_id,
                sent_to_llm=True,
            )
        )
    if grouped.get("browser"):
        latest = grouped["browser"][-1]
        semantic.append(
            _event(
                "browser_context_changed",
                "browser",
                _browser_summary(latest),
                occurred_at=occurred_at,
                metadata=_safe_subset(latest, ("app_name", "window_title", "url", "collector", "stimulus_type")),
                raw_ref=batch_id,
                sent_to_llm=True,
            )
        )
    if grouped.get("app_lifecycle"):
        latest = grouped["app_lifecycle"][-1]
        semantic.append(
            _event(
                "app_lifecycle_changed",
                "activity",
                str(latest.get("summary") or "Application lifecycle changed."),
                occurred_at=occurred_at,
                metadata=_safe_subset(latest, ("app_name", "collector", "stimulus_type")),
                raw_ref=batch_id,
                sent_to_llm=True,
            )
        )
    if grouped.get("window_lifecycle"):
        latest = grouped["window_lifecycle"][-1]
        semantic.append(
            _event(
                "window_lifecycle_changed",
                "activity",
                str(latest.get("summary") or "Window lifecycle changed."),
                occurred_at=occurred_at,
                metadata=_safe_subset(latest, ("app_name", "window_title", "collector", "stimulus_type")),
                raw_ref=batch_id,
                sent_to_llm=True,
            )
        )
    if grouped.get("browser_lifecycle"):
        latest = grouped["browser_lifecycle"][-1]
        semantic.append(
            _event(
                "browser_lifecycle_changed",
                "browser",
                str(latest.get("summary") or "Browser lifecycle changed."),
                occurred_at=occurred_at,
                metadata=_safe_subset(latest, ("app_name", "window_title", "url", "collector", "stimulus_type")),
                raw_ref=batch_id,
                sent_to_llm=True,
            )
        )
    if grouped.get("input_device"):
        latest = grouped["input_device"][-1]
        semantic.append(
            _event(
                "input_device_activity",
                "activity",
                str(latest.get("summary") or "Input device activity changed."),
                occurred_at=occurred_at,
                metadata=_safe_subset(latest, ("input_event", "idle_bucket", "collector", "stimulus_type")),
                raw_ref=batch_id,
                sent_to_llm=True,
                privacy_level="metadata",
            )
        )
    if grouped.get("voice_wakeup"):
        latest = grouped["voice_wakeup"][-1]
        stimulus_type = str(latest.get("stimulus_type") or "")
        semantic.append(
            _event(
                "voice_wake_detected" if stimulus_type == "wake_word_detected" else "voice_command_received",
                "voice_transcript",
                str(latest.get("summary") or "Voice wakeup event."),
                occurred_at=occurred_at,
                metadata=_safe_subset(latest, ("collector", "stimulus_type", "privacy_level", "bridge_event")),
                raw_ref=batch_id,
                sent_to_llm=stimulus_type != "wake_word_detected",
                privacy_level="redacted",
            )
        )
    for collector, event_type, source, privacy_level in (
        ("direct_user", "explicit_user_request", "user_text", "metadata"),
        ("meeting_audio", "meeting_audio_activity", "audio_transcript", "redacted"),
        ("browser_window_activity", "browser_window_activity", "browser", "redacted"),
        ("browser_tab_group_activity", "browser_tab_group_activity", "browser", "redacted"),
        ("browser_profile_activity", "browser_profile_activity", "browser", "redacted"),
        ("browser_extension_activity", "browser_extension_activity", "browser", "redacted"),
        ("browser_web_app_activity", "browser_web_app_activity", "browser", "redacted"),
        ("browser_view_mode_activity", "browser_view_mode_activity", "browser", "redacted"),
        ("browser_page_activity", "browser_page_activity", "browser", "metadata"),
        ("meeting_app_activity", "meeting_app_activity", "activity", "redacted"),
        ("call_control_activity", "call_control_activity", "activity", "redacted"),
        ("meeting_presentation_activity", "meeting_presentation_activity", "activity", "redacted"),
        ("meeting_artifact_activity", "meeting_artifact_activity", "activity", "redacted"),
        ("terminal_activity", "terminal_activity", "activity", "metadata"),
        ("ide_activity", "ide_activity", "activity", "metadata"),
        ("package_manager_activity", "package_manager_activity", "activity", "redacted"),
        ("build_tool_activity", "build_tool_activity", "activity", "redacted"),
        ("test_runner_activity", "test_runner_activity", "activity", "redacted"),
        ("local_service_activity", "local_service_activity", "activity", "redacted"),
        ("debugger_activity", "debugger_activity", "activity", "redacted"),
        ("git_activity", "git_activity", "activity", "metadata"),
        ("github_activity", "github_activity", "activity", "metadata"),
        ("accessibility_context", "accessibility_context_changed", "accessibility", "redacted"),
        ("device_state", "device_state_changed", "system", "metadata"),
        ("software_activity", "software_activity", "system", "metadata"),
        ("print_scan_activity", "print_scan_activity", "system", "metadata"),
        ("search_activity", "search_activity", "activity", "redacted"),
        ("peripheral_activity", "peripheral_activity", "system", "metadata"),
        ("media_activity", "media_activity", "activity", "metadata"),
        ("focus_task_activity", "focus_task_activity", "activity", "metadata"),
        ("workspace_layout_activity", "workspace_layout_activity", "system", "redacted"),
        ("window_arrangement_activity", "window_arrangement_activity", "system", "redacted"),
        ("display_arrangement_activity", "display_arrangement_activity", "system", "metadata"),
        ("app_workspace_activity", "app_workspace_activity", "activity", "redacted"),
        ("keyboard_input_activity", "keyboard_input_activity", "system", "metadata"),
        ("ime_activity", "ime_activity", "accessibility", "redacted"),
        ("text_input_surface_activity", "text_input_surface_activity", "accessibility", "redacted"),
        ("pasteboard_workflow_activity", "pasteboard_workflow_activity", "activity", "redacted"),
        ("cloud_sync_activity", "cloud_sync_activity", "activity", "metadata"),
        ("auth_activity", "auth_activity", "system", "redacted"),
        ("credential_activity", "credential_activity", "system", "redacted"),
        ("passkey_activity", "passkey_activity", "system", "redacted"),
        ("autofill_activity", "autofill_activity", "browser", "redacted"),
        ("verification_code_activity", "verification_code_activity", "system", "redacted"),
        ("network_activity", "network_activity", "system", "metadata"),
        ("automation_activity", "automation_activity", "activity", "metadata"),
        ("virtual_runtime_activity", "virtual_runtime_activity", "activity", "metadata"),
        ("remote_session_activity", "remote_session_activity", "activity", "redacted"),
        ("permission_activity", "permission_activity", "system", "redacted"),
        ("location_activity", "location_activity", "system", "redacted"),
        ("resource_activity", "resource_activity", "system", "metadata"),
        ("storage_activity", "storage_activity", "system", "metadata"),
        ("wellbeing_activity", "wellbeing_activity", "system", "metadata"),
        ("policy_activity", "policy_activity", "system", "metadata"),
        ("notes_activity", "notes_activity", "activity", "redacted"),
        ("bookmark_history_activity", "bookmark_history_activity", "browser", "redacted"),
        ("contact_activity", "contact_activity", "activity", "redacted"),
        ("commerce_activity", "commerce_activity", "activity", "redacted"),
        ("finance_activity", "finance_activity", "activity", "redacted"),
        ("social_feed_activity", "social_feed_activity", "channel_message", "redacted"),
        ("task_manager_activity", "task_manager_activity", "activity", "redacted"),
        ("issue_tracker_activity", "issue_tracker_activity", "activity", "redacted"),
        ("knowledge_base_activity", "knowledge_base_activity", "activity", "redacted"),
        ("whiteboard_activity", "whiteboard_activity", "activity", "redacted"),
        ("form_survey_activity", "form_survey_activity", "activity", "redacted"),
        ("learning_activity", "learning_activity", "activity", "metadata"),
        ("crm_activity", "crm_activity", "activity", "redacted"),
        ("support_desk_activity", "support_desk_activity", "activity", "redacted"),
        ("analytics_activity", "analytics_activity", "activity", "redacted"),
        ("database_activity", "database_activity", "activity", "redacted"),
        ("cloud_console_activity", "cloud_console_activity", "activity", "redacted"),
        ("incident_activity", "incident_activity", "activity", "redacted"),
        ("file_operation_activity", "file_operation_activity", "activity", "redacted"),
        ("folder_navigation_activity", "folder_navigation_activity", "activity", "redacted"),
        ("file_preview_activity", "file_preview_activity", "activity", "redacted"),
        ("trash_activity", "trash_activity", "activity", "redacted"),
        ("ai_assistant_activity", "ai_assistant_activity", "activity", "redacted"),
        ("pdf_activity", "pdf_activity", "activity", "redacted"),
        ("spreadsheet_activity", "spreadsheet_activity", "activity", "redacted"),
        ("presentation_activity", "presentation_activity", "activity", "redacted"),
        ("spreadsheet_editing_activity", "spreadsheet_editing_activity", "activity", "redacted"),
        ("spreadsheet_formula_activity", "spreadsheet_formula_activity", "activity", "redacted"),
        ("spreadsheet_data_analysis_activity", "spreadsheet_data_analysis_activity", "activity", "redacted"),
        ("spreadsheet_import_export_activity", "spreadsheet_import_export_activity", "activity", "redacted"),
        ("presentation_authoring_activity", "presentation_authoring_activity", "activity", "redacted"),
        ("presentation_design_activity", "presentation_design_activity", "activity", "redacted"),
        ("presentation_delivery_activity", "presentation_delivery_activity", "activity", "redacted"),
        ("presentation_export_activity", "presentation_export_activity", "activity", "redacted"),
        ("file_dialog_activity", "file_dialog_activity", "activity", "redacted"),
        ("system_settings_activity", "system_settings_activity", "system", "metadata"),
        ("text_composition_activity", "text_composition_activity", "activity", "redacted"),
        ("dictation_activity", "dictation_activity", "audio_transcript", "redacted"),
        ("writing_assist_activity", "writing_assist_activity", "activity", "redacted"),
        ("translation_activity", "translation_activity", "activity", "redacted"),
        ("file_transfer_activity", "file_transfer_activity", "activity", "redacted"),
        ("archive_activity", "archive_activity", "activity", "redacted"),
        ("camera_capture_activity", "camera_capture_activity", "screen_ocr", "redacted"),
        ("continuity_activity", "continuity_activity", "system", "redacted"),
        ("command_activity", "command_activity", "accessibility", "redacted"),
        ("selection_activity", "selection_activity", "accessibility", "redacted"),
        ("navigation_activity", "navigation_activity", "accessibility", "redacted"),
        ("edit_history_activity", "edit_history_activity", "accessibility", "redacted"),
        ("dock_taskbar_activity", "dock_taskbar_activity", "system", "redacted"),
        ("menu_bar_tray_activity", "menu_bar_tray_activity", "system", "redacted"),
        ("quick_settings_activity", "quick_settings_activity", "system", "metadata"),
        ("widget_activity", "widget_activity", "system", "redacted"),
        ("downloads", "download_activity", "activity", "metadata"),
        ("visual_state", "visual_state_changed", "screen_ocr", "redacted"),
        ("notification_activity", "notification_activity", "activity", "metadata"),
        ("share_activity", "share_activity", "activity", "redacted"),
        ("calendar_activity", "calendar_activity", "system", "metadata"),
        ("calendar_scheduling_activity", "calendar_scheduling_activity", "system", "redacted"),
        ("reminder_todo_activity", "reminder_todo_activity", "system", "redacted"),
        ("wakeups", "wakeup_activity", "system", "metadata"),
        ("channel_activity", "channel_activity", "channel_message", "metadata"),
        ("communication_activity", "communication_activity", "channel_message", "metadata"),
        ("chat_composition_activity", "chat_composition_activity", "channel_message", "redacted"),
        ("chat_thread_activity", "chat_thread_activity", "channel_message", "redacted"),
        ("chat_channel_navigation_activity", "chat_channel_navigation_activity", "channel_message", "redacted"),
        ("chat_presence_activity", "chat_presence_activity", "channel_message", "redacted"),
        ("mail_activity", "mail_activity", "activity", "metadata"),
        ("mail_composition_activity", "mail_composition_activity", "activity", "redacted"),
        ("mail_organization_activity", "mail_organization_activity", "activity", "redacted"),
        ("document_composition_activity", "document_composition_activity", "activity", "redacted"),
        ("document_review_activity", "document_review_activity", "activity", "redacted"),
        ("document_structure_activity", "document_structure_activity", "activity", "redacted"),
        ("document_export_publish_activity", "document_export_publish_activity", "activity", "redacted"),
        ("document_activity", "document_activity", "activity", "metadata"),
        ("creative_activity", "creative_activity", "activity", "metadata"),
        ("security_context", "security_context_changed", "system", "metadata"),
        ("agent_runtime", "agent_runtime_activity", "system", "metadata"),
    ):
        if grouped.get(collector):
            latest = grouped[collector][-1]
            semantic.append(
                _event(
                    event_type,
                    source,
                    str(latest.get("summary") or f"{collector} event."),
                    occurred_at=occurred_at,
                    metadata=_safe_subset(
                        latest,
                        (
                            "app_name",
                            "window_title",
                            "url",
                            "channel_id",
                            "conversation_id",
                            "privacy_level",
                            "collector",
                            "stimulus_type",
                            "bridge_event",
                            "device_name",
                            "printer_name",
                            "package_name",
                            "task_id",
                            "service_name",
                            "account_id",
                            "credential_provider",
                            "passkey_provider",
                            "autofill_kind",
                            "verification_channel",
                            "provider",
                            "runtime_name",
                            "session_id",
                            "permission",
                            "region",
                            "timezone",
                            "process_name",
                            "volume_name",
                            "policy_id",
                            "note_id",
                            "contact_id",
                            "merchant",
                            "provider_name",
                            "social_network",
                            "task_id",
                            "issue_id",
                            "page_id",
                            "board_id",
                            "form_id",
                            "course_id",
                            "customer_id",
                            "ticket_id",
                            "dashboard_id",
                            "database_name",
                            "resource_type",
                            "incident_id",
                            "layout_mode",
                            "arrangement_kind",
                            "display_kind",
                            "workspace_kind",
                            "input_source_kind",
                            "keyboard_layout_kind",
                            "ime_kind",
                            "input_surface_kind",
                            "pasteboard_action",
                            "browser_window_kind",
                            "tab_group_kind",
                            "browser_profile_kind",
                            "extension_kind",
                            "web_app_kind",
                            "view_mode_kind",
                            "meeting_surface",
                            "meeting_control",
                            "share_kind",
                            "artifact_kind",
                            "mail_action",
                            "mailbox_action",
                            "calendar_action",
                            "reminder_action",
                            "chat_action",
                            "thread_action",
                            "channel_action",
                            "presence_action",
                            "document_action",
                            "review_action",
                            "structure_action",
                            "publish_action",
                            "sheet_action",
                            "formula_action",
                            "data_action",
                            "spreadsheet_transfer_action",
                            "slide_action",
                            "design_action",
                            "delivery_action",
                            "deck_publish_action",
                            "package_manager",
                            "build_tool",
                            "test_runner",
                            "service_kind",
                            "debugger_kind",
                            "file_action",
                            "folder_action",
                            "preview_kind",
                            "trash_action",
                            "model",
                            "assistant_id",
                            "document_id",
                            "workbook_id",
                            "deck_id",
                            "dialog_kind",
                            "settings_pane",
                            "composition_surface",
                            "dictation_provider",
                            "assist_kind",
                            "translation_provider",
                            "transfer_kind",
                            "archive_format",
                            "capture_device",
                            "continuity_kind",
                            "command_kind",
                            "control_role",
                            "selection_kind",
                            "navigation_target_type",
                            "history_action",
                            "surface_kind",
                            "status_item_kind",
                            "setting_kind",
                            "widget_kind",
                        ),
                    ),
                    raw_ref=batch_id,
                    sent_to_llm=True,
                    privacy_level=privacy_level,
                )
            )
    if grouped.get("filesystem"):
        paths = [str(item.get("path") or "") for item in grouped["filesystem"] if str(item.get("path") or "")]
        semantic.append(
            _event(
                "project_files_changed",
                "activity",
                f"{len(grouped['filesystem'])} project file change(s): {', '.join(paths[:8]) or 'paths omitted'}.",
                occurred_at=occurred_at,
                metadata={"file_count": len(grouped["filesystem"]), "paths": paths[:20]},
                raw_ref=batch_id,
                sent_to_llm=True,
            )
        )
    if grouped.get("clipboard"):
        latest = grouped["clipboard"][-1]
        semantic.append(
            _event(
                "clipboard_changed",
                "activity",
                f"Clipboard changed; content omitted ({int(latest.get('text_length') or 0)} chars).",
                occurred_at=occurred_at,
                metadata=_safe_subset(latest, ("text_length", "truncated", "collector", "stimulus_type")),
                raw_ref=batch_id,
                sent_to_llm=True,
                privacy_level="redacted",
            )
        )
    screen_count = len(grouped.get("screen_ocr", [])) + len(grouped.get("screenshot", [])) + len(grouped.get("video_frame", []))
    if screen_count:
        semantic.append(
            _event(
                "screen_context_changed",
                "screen_ocr",
                f"{screen_count} opt-in screen context change(s); raw pixels and OCR text omitted.",
                occurred_at=occurred_at,
                metadata={"screen_event_count": screen_count, "collectors": [name for name in ("screen_ocr", "screenshot", "video_frame") if grouped.get(name)]},
                raw_ref=batch_id,
                sent_to_llm=True,
                privacy_level="redacted",
            )
        )
    return semantic


def semantic_events_from_stimulus(stimulus: dict[str, Any], *, decision: str = "") -> list[SemanticEvent]:
    source = str(stimulus.get("source") or "user_text")
    if source not in {"user_text", "voice_transcript", "channel_message"}:
        return []
    metadata = stimulus.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    text = str(stimulus.get("text") or "").strip()
    occurred_at = str(stimulus.get("occurred_at") or utc_now())
    stimulus_id = str(stimulus.get("stimulus_id") or "")
    if not text:
        return []
    if source == "voice_transcript":
        events = []
        if metadata.get("wake_word_detected") or metadata.get("activation_id"):
            events.append(
                _event(
                    "voice_wake_detected",
                    source,
                    "Wake-word activation detected locally.",
                    occurred_at=occurred_at,
                    metadata=_safe_subset(metadata, ("activation_id", "wake_word", "provider")),
                    raw_ref=stimulus_id,
                    sent_to_llm=False,
                )
            )
        events.append(
            _event(
                "voice_command_received",
                source,
                _truncate(f"Voice command received: {text}", 500),
                occurred_at=occurred_at,
                metadata={"decision": decision, **_safe_subset(metadata, ("activation_id", "provider", "stt_provider"))},
                raw_ref=stimulus_id,
                sent_to_llm=True,
            )
        )
        return events
    if source == "channel_message":
        return [
            _event(
                "external_message_received",
                source,
                _truncate(f"External channel message received: {text}", 500),
                occurred_at=occurred_at,
                metadata={"decision": decision, **_safe_subset(metadata, ("channel_id", "conversation_id", "sender"))},
                raw_ref=stimulus_id,
                sent_to_llm=True,
            )
        ]
    return [
        _event(
            "explicit_user_request",
            source,
            _truncate(f"User request: {text}", 500),
            occurred_at=occurred_at,
            metadata={"decision": decision},
            raw_ref=stimulus_id,
            sent_to_llm=True,
        )
    ]


def deterministic_action_candidates(config: AgentConfig, event: SemanticEvent) -> list[AutonomousActionCandidate]:
    recent = _recent_semantic_payloads(config, limit=20)
    candidates: list[AutonomousActionCandidate] = []
    if event.event_type == "project_files_changed":
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Project files changed; refresh compact work context and keep the agent ready without interrupting the user.",
                metadata={"file_count": int(event.metadata.get("file_count") or 0), "paths": event.metadata.get("paths", [])},
            )
        )
    elif event.event_type == "browser_context_changed":
        candidates.append(
            _candidate(
                event,
                "monitor_research",
                "Browser context changed after dwell; observe research context silently unless it connects to an active request.",
                metadata=_safe_subset(event.metadata, ("app_name", "window_title", "url")),
            )
        )
    elif event.event_type == "browser_window_activity" and str(event.metadata.get("stimulus_type") or "") in {"browser_window_opened", "browser_window_focused", "browser_session_restored", "recently_closed_window_reopened"}:
        candidates.append(
            _candidate(
                event,
                "prepare_resume_context",
                "Browser window or session context changed; prepare compact research/session context without tab titles or page contents.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "browser_tab_group_activity" and str(event.metadata.get("stimulus_type") or "") in {"tab_group_created", "tab_group_restored", "tab_group_saved", "tab_moved_to_group", "tab_removed_from_group"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Browser tab organization changed; refresh compact browsing context while group names, tab titles, and URLs remain redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "browser_profile_activity" and str(event.metadata.get("stimulus_type") or "") in {"browser_profile_switched", "guest_profile_opened", "private_window_opened", "browser_profile_signed_in", "browser_profile_signed_out"}:
        candidates.append(
            _candidate(
                event,
                "suppress_collection" if str(event.metadata.get("stimulus_type") or "") in {"guest_profile_opened", "private_window_opened"} else "update_context",
                "Browser profile or private context changed; keep collection conservative and avoid exposing account or private-window details.",
                risk="medium" if str(event.metadata.get("stimulus_type") or "") in {"guest_profile_opened", "private_window_opened"} else "low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "browser_extension_activity" and str(event.metadata.get("stimulus_type") or "") in {"extension_permission_requested", "extension_error_reported", "extension_installed", "extension_action_clicked"}:
        candidates.append(
            _candidate(
                event,
                "review_attention" if str(event.metadata.get("stimulus_type") or "") in {"extension_permission_requested", "extension_error_reported"} else "update_context",
                "Browser extension surface changed; review permission/error events while keeping extension names and page contents redacted.",
                risk="medium" if str(event.metadata.get("stimulus_type") or "") in {"extension_permission_requested", "extension_error_reported"} else "low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "browser_web_app_activity" and str(event.metadata.get("stimulus_type") or "") in {"web_app_installed", "web_app_opened", "web_app_notification_permission_requested", "web_app_badge_changed"}:
        candidates.append(
            _candidate(
                event,
                "review_attention" if str(event.metadata.get("stimulus_type") or "") == "web_app_notification_permission_requested" else "update_context",
                "Installed web app context changed; refresh app context without exposing app names, origins, or notification content.",
                risk="medium" if str(event.metadata.get("stimulus_type") or "") == "web_app_notification_permission_requested" else "low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "browser_view_mode_activity" and str(event.metadata.get("stimulus_type") or "") in {"reader_mode_enabled", "find_in_page_performed", "page_zoom_changed", "picture_in_picture_started", "page_translation_accepted"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Browser reading/view mode changed; refresh compact browsing context while queries, media titles, and page contents stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "app_focus_changed" and _looks_like_work_return(event, recent):
        candidates.append(
            _candidate(
                event,
                "prepare_resume_context",
                "User returned to a work surface after browser/research activity; prepare a concise resume context before speaking.",
                risk="low",
                metadata={"transition": "research_to_work"},
            )
        )
    elif event.event_type == "screen_context_changed":
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Opt-in screen context changed; refresh compact context while omitting raw pixels and OCR.",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "ci_failure_detected":
        candidates.append(
            _candidate(
                event,
                "analyze",
                "CI failure is actionable and should be analyzed for the active workspace.",
                risk="medium",
                requires_user_approval=False,
                metadata=event.metadata,
            )
        )
    elif event.event_type == "calendar_event_started":
        candidates.append(
            _candidate(
                event,
                "prepare_briefing",
                "Calendar event started; prepare relevant context silently before deciding whether to interrupt.",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "terminal_activity" and str(event.metadata.get("stimulus_type") or "").endswith(("failed", "crashed")):
        candidates.append(
            _candidate(
                event,
                "analyze",
                "Terminal, build, test, or server failure bridge event is actionable for the active workspace.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "package_manager_activity" and str(event.metadata.get("stimulus_type") or "") in {"dependency_install_failed", "dependency_audit_warning", "dependency_conflict_detected", "environment_setup_failed"}:
        candidates.append(
            _candidate(
                event,
                "analyze" if str(event.metadata.get("stimulus_type") or "").endswith("failed") or str(event.metadata.get("stimulus_type") or "") == "dependency_conflict_detected" else "review_attention",
                "Package manager or dependency state may block local development while package names and logs stay redacted.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "build_tool_activity" and str(event.metadata.get("stimulus_type") or "") in {"build_task_failed", "compile_error_detected", "compile_warning_detected", "build_config_changed"}:
        candidates.append(
            _candidate(
                event,
                "analyze" if str(event.metadata.get("stimulus_type") or "") in {"build_task_failed", "compile_error_detected"} else "update_context",
                "Build tooling changed or failed; inspect the compact build context without exposing target names, paths, or logs.",
                risk="medium" if str(event.metadata.get("stimulus_type") or "") in {"build_task_failed", "compile_error_detected"} else "low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "test_runner_activity" and str(event.metadata.get("stimulus_type") or "") in {"test_suite_failed", "test_case_failed", "test_flake_detected", "coverage_threshold_failed", "snapshot_test_updated"}:
        candidates.append(
            _candidate(
                event,
                "analyze" if str(event.metadata.get("stimulus_type") or "") in {"test_suite_failed", "test_case_failed", "coverage_threshold_failed"} else "review_attention",
                "Test runner event may require repair or review while test names, assertions, snapshots, and logs stay redacted.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "local_service_activity" and str(event.metadata.get("stimulus_type") or "") in {"dev_server_crashed", "port_conflict_detected", "log_error_seen", "hot_reload_failed"}:
        candidates.append(
            _candidate(
                event,
                "analyze",
                "Local development service event may block iteration; inspect compact service context without endpoint paths or logs.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "debugger_activity" and str(event.metadata.get("stimulus_type") or "") in {"debugger_paused", "exception_breakpoint_hit", "watch_expression_failed"}:
        candidates.append(
            _candidate(
                event,
                "analyze",
                "Debugger paused or failed while stack frames, watch expressions, and variable values remain redacted.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "visual_state_changed" and str(event.metadata.get("stimulus_type") or "") in {"error_banner_visible", "loading_spinner_stuck"}:
        candidates.append(
            _candidate(
                event,
                "analyze",
                "A bridge-observed visual error or stuck loading state may indicate the user is blocked.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "git_activity" and str(event.metadata.get("stimulus_type") or "") in {"merge_conflict_detected", "rebase_conflict_detected", "working_tree_dirty"}:
        candidates.append(
            _candidate(
                event,
                "analyze",
                "A local Git state change may need workspace-aware help or recovery context.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "github_activity" and str(event.metadata.get("stimulus_type") or "") in {"ci_failed", "pr_review_requested", "issue_assigned", "comment_received"}:
        candidates.append(
            _candidate(
                event,
                "analyze",
                "A GitHub PR, issue, comment, or CI event may require workspace follow-up.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "software_activity" and str(event.metadata.get("stimulus_type") or "") in {"installer_failed", "app_installed", "app_updated", "package_installed", "extension_installed"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Software install or update activity changed the local environment; refresh compact system context.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "print_scan_activity" and str(event.metadata.get("stimulus_type") or "") in {"print_job_failed", "scan_completed"}:
        candidates.append(
            _candidate(
                event,
                "review_attention",
                "Print or scan activity may need user-visible follow-up.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "search_activity" and str(event.metadata.get("stimulus_type") or "") in {"app_launched_from_search", "file_opened_from_search"}:
        candidates.append(
            _candidate(
                event,
                "prepare_resume_context",
                "A search or launcher result opened a work surface; prepare context silently.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "peripheral_activity" and str(event.metadata.get("stimulus_type") or "") in {"external_display_connected", "storage_device_mounted"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Peripheral or storage state changed; refresh compact environment context.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "media_activity" and str(event.metadata.get("stimulus_type") or "") == "screen_recording_started":
        candidates.append(
            _candidate(
                event,
                "suppress_collection",
                "Screen recording started; keep rich collection conservative unless explicitly requested.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "focus_task_activity" and str(event.metadata.get("stimulus_type") or "") in {"task_started", "workspace_switched", "focus_mode_enabled"}:
        candidates.append(
            _candidate(
                event,
                "prepare_resume_context",
                "Focus mode, workspace, or task context changed; prepare a compact resume context silently.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "workspace_layout_activity" and str(event.metadata.get("stimulus_type") or "") in {"mission_control_opened", "workspace_overview_opened", "desktop_space_switched", "stage_manager_enabled", "stage_manager_disabled"}:
        candidates.append(
            _candidate(
                event,
                "prepare_resume_context",
                "Desktop workspace layout changed; prepare compact resume context while visible windows and workspace names remain redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "window_arrangement_activity" and str(event.metadata.get("stimulus_type") or "") in {"window_tiled", "window_snapped", "split_view_started", "window_fullscreen_entered", "window_moved_to_display", "window_moved_to_space"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Window arrangement changed; refresh compact context while window titles and app contents remain redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "display_arrangement_activity" and str(event.metadata.get("stimulus_type") or "") in {"display_arrangement_changed", "display_resolution_changed", "display_scaling_changed", "primary_display_changed"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Display arrangement changed; refresh compact environment context without exposing visible contents.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "app_workspace_activity" and str(event.metadata.get("stimulus_type") or "") in {"app_workspace_opened", "app_workspace_switched", "app_workspace_restored", "layout_preset_applied", "profile_switched"}:
        candidates.append(
            _candidate(
                event,
                "prepare_resume_context",
                "App workspace or layout profile changed; prepare compact resume context while workspace names and contents stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "keyboard_input_activity" and str(event.metadata.get("stimulus_type") or "") in {"input_source_changed", "keyboard_layout_changed", "keyboard_shortcut_conflict_detected", "modifier_key_remapped", "hardware_keyboard_connected"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Keyboard input configuration changed; refresh compact input context without recording typed text.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "ime_activity" and str(event.metadata.get("stimulus_type") or "") in {"ime_composition_started", "ime_candidate_window_shown", "ime_candidate_selected", "ime_conversion_failed", "language_input_switched"}:
        candidates.append(
            _candidate(
                event,
                "suppress_collection" if str(event.metadata.get("stimulus_type") or "") in {"ime_composition_started", "ime_candidate_window_shown", "ime_candidate_selected"} else "update_context",
                "IME composition is active; keep rich collection conservative and omit candidate or committed text.",
                risk="medium" if str(event.metadata.get("stimulus_type") or "") in {"ime_composition_started", "ime_candidate_window_shown", "ime_candidate_selected"} else "low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "text_input_surface_activity" and str(event.metadata.get("stimulus_type") or "") in {"secure_text_field_focused", "multiline_editor_focused", "search_field_focused", "input_validation_error", "input_submit_attempted"}:
        candidates.append(
            _candidate(
                event,
                "suppress_collection" if str(event.metadata.get("stimulus_type") or "") == "secure_text_field_focused" else "update_context",
                "Text input surface changed; avoid field values and keep secure entry especially conservative.",
                risk="medium" if str(event.metadata.get("stimulus_type") or "") == "secure_text_field_focused" else "low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "pasteboard_workflow_activity" and str(event.metadata.get("stimulus_type") or "") in {"copy_performed", "cut_performed", "paste_performed", "clipboard_manager_opened", "clipboard_history_item_selected"}:
        candidates.append(
            _candidate(
                event,
                "suppress_collection" if str(event.metadata.get("stimulus_type") or "") in {"clipboard_manager_opened", "clipboard_history_item_selected"} else "update_context",
                "Pasteboard workflow changed; update local context while clipboard contents and history values remain redacted.",
                risk="medium" if str(event.metadata.get("stimulus_type") or "") in {"clipboard_manager_opened", "clipboard_history_item_selected"} else "low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "cloud_sync_activity" and str(event.metadata.get("stimulus_type") or "") in {"sync_failed", "sync_conflict_detected", "cloud_quota_warning"}:
        candidates.append(
            _candidate(
                event,
                "review_attention",
                "Cloud sync failed, conflicted, or hit quota; determine whether it affects active work.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "auth_activity" and str(event.metadata.get("stimulus_type") or "") in {"login_prompt_shown", "mfa_prompt_shown", "sign_in_failed", "oauth_flow_failed"}:
        candidates.append(
            _candidate(
                event,
                "suppress_collection",
                "Authentication-sensitive context is active; suppress rich collection and avoid exposing credentials or codes.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "credential_activity":
        candidates.append(
            _candidate(
                event,
                "review_attention" if str(event.metadata.get("stimulus_type") or "") == "credential_fill_failed" else "suppress_collection",
                "Credential manager activity is active; suppress rich collection and block usernames, passwords, vault items, and credential values.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "passkey_activity":
        candidates.append(
            _candidate(
                event,
                "review_attention" if str(event.metadata.get("stimulus_type") or "") == "passkey_failed" else "suppress_collection",
                "Passkey, biometric, or security-key context is active; suppress rich collection and block key material.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "autofill_activity":
        candidates.append(
            _candidate(
                event,
                "review_attention" if str(event.metadata.get("stimulus_type") or "") == "form_autofill_failed" else "suppress_collection",
                "Autofill context is active; suppress rich collection and block field values, payment details, addresses, and identity data.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "verification_code_activity":
        candidates.append(
            _candidate(
                event,
                "review_attention" if str(event.metadata.get("stimulus_type") or "") == "verification_code_failed" else "suppress_collection",
                "Verification-code context is active; suppress rich collection and block OTPs, backup codes, and message contents.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "network_activity" and str(event.metadata.get("stimulus_type") or "") in {"offline_mode_detected", "captive_portal_detected", "dns_error", "api_request_failed", "api_rate_limited"}:
        candidates.append(
            _candidate(
                event,
                "analyze",
                "Network or API issue may explain a user-visible failure and should be correlated with current work context.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "automation_activity" and str(event.metadata.get("stimulus_type") or "").endswith("failed"):
        candidates.append(
            _candidate(
                event,
                "analyze",
                "Automation or scheduled job failed; inspect context and prepare recovery steps.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "virtual_runtime_activity" and str(event.metadata.get("stimulus_type") or "") in {"container_failed", "image_build_failed", "emulator_failed"}:
        candidates.append(
            _candidate(
                event,
                "analyze",
                "Container, image build, VM, or emulator failure may block local development.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "remote_session_activity" and str(event.metadata.get("stimulus_type") or "") in {"remote_session_started", "screen_share_started", "remote_control_requested"}:
        candidates.append(
            _candidate(
                event,
                "suppress_collection",
                "Remote or screen-share context is active; keep rich collection conservative and avoid interruption.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "permission_activity" and str(event.metadata.get("stimulus_type") or "") in {"permission_requested", "privacy_indicator_enabled"}:
        candidates.append(
            _candidate(
                event,
                "suppress_collection",
                "A platform permission or privacy indicator is active; keep collection conservative and avoid sensitive prompts.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "location_activity" and str(event.metadata.get("stimulus_type") or "") in {"location_requested", "location_access_started", "region_changed", "timezone_changed"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Location, region, or timezone context changed; refresh compact environment context without precise coordinates.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "resource_activity" and str(event.metadata.get("stimulus_type") or "") in {"cpu_pressure_high", "memory_pressure_high", "thermal_pressure_high", "process_hung", "process_high_cpu", "disk_io_pressure_high"}:
        candidates.append(
            _candidate(
                event,
                "analyze",
                "Resource pressure may explain slowness, hangs, or local failures.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "storage_activity" and str(event.metadata.get("stimulus_type") or "") in {"disk_space_low", "volume_space_low", "backup_failed"}:
        candidates.append(
            _candidate(
                event,
                "review_attention",
                "Storage, volume, or backup state may need user-visible follow-up.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "wellbeing_activity" and str(event.metadata.get("stimulus_type") or "") in {"break_reminder_fired", "screen_time_limit_reached", "app_limit_reached"}:
        candidates.append(
            _candidate(
                event,
                "review_attention",
                "A wellbeing or app-limit signal fired; decide whether to remain silent or defer work.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "policy_activity" and str(event.metadata.get("stimulus_type") or "") in {"device_compliance_warning", "policy_blocked_action", "dlp_warning_shown", "certificate_warning_shown", "update_required"}:
        candidates.append(
            _candidate(
                event,
                "review_attention",
                "Policy, compliance, certificate, or update state may block the current workflow.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "notes_activity" and str(event.metadata.get("stimulus_type") or "") in {"note_created", "note_edited", "note_shared", "checklist_item_completed"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Notes or checklist activity changed; refresh compact context without note contents.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "bookmark_history_activity" and str(event.metadata.get("stimulus_type") or "") in {"bookmark_added", "reading_list_added", "saved_tab_group_changed"}:
        candidates.append(
            _candidate(
                event,
                "monitor_research",
                "Bookmark, reading-list, or tab-group activity may indicate research context worth tracking silently.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "contact_activity" and str(event.metadata.get("stimulus_type") or "") in {"contact_shared", "address_copied", "phone_number_clicked"}:
        candidates.append(
            _candidate(
                event,
                "suppress_collection",
                "Contact-sensitive activity is active; keep rich collection suppressed and avoid exposing contact details.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "commerce_activity" and str(event.metadata.get("stimulus_type") or "") in {"checkout_started", "checkout_completed", "subscription_changed", "return_started", "refund_status_changed"}:
        candidates.append(
            _candidate(
                event,
                "review_attention",
                "Commerce, checkout, subscription, return, or refund activity may need user-visible follow-up.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "finance_activity":
        candidates.append(
            _candidate(
                event,
                "suppress_collection",
                "Finance or wallet activity is active; suppress rich collection and avoid exposing amounts, accounts, or payment tokens.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "social_feed_activity" and str(event.metadata.get("stimulus_type") or "") in {"comment_received", "follow_request_received", "social_notification_received"}:
        candidates.append(
            _candidate(
                event,
                "review_message",
                "Social feed activity may require attention or response, while post/comment bodies stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "task_manager_activity" and str(event.metadata.get("stimulus_type") or "") in {
        "task_created",
        "task_updated",
        "task_assigned",
        "task_moved",
        "task_priority_changed",
        "task_due_date_changed",
        "task_comment_added",
        "project_opened",
        "project_changed",
    }:
        candidates.append(
            _candidate(
                event,
                "prepare_resume_context",
                "Task manager activity changed; prepare compact task context without exposing task bodies.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "issue_tracker_activity" and str(event.metadata.get("stimulus_type") or "") in {
        "issue_assigned",
        "issue_status_changed",
        "issue_comment_received",
        "issue_blocker_added",
        "issue_moved",
        "issue_priority_changed",
        "issue_due_date_changed",
        "project_opened",
        "project_changed",
    }:
        candidates.append(
            _candidate(
                event,
                "analyze",
                "Issue tracker assignment, status, comment, or blocker may require workspace follow-up.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "knowledge_base_activity" and str(event.metadata.get("stimulus_type") or "") in {"page_created", "page_edited", "page_commented", "page_shared", "doc_link_copied"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Knowledge-base activity changed; refresh compact context without page contents.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "whiteboard_activity" and str(event.metadata.get("stimulus_type") or "") in {"board_edited", "sticky_created", "diagram_exported", "whiteboard_comment_added"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Whiteboard or diagram collaboration changed; update compact context without board contents.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "form_survey_activity" and str(event.metadata.get("stimulus_type") or "") in {"form_submitted", "form_validation_error", "survey_response_received", "approval_form_submitted"}:
        candidates.append(
            _candidate(
                event,
                "review_attention",
                "Form, survey, validation, or approval activity may need follow-up while answers remain redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "learning_activity" and str(event.metadata.get("stimulus_type") or "") in {"lesson_completed", "quiz_submitted", "course_progress_changed", "certificate_earned"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Learning progress changed; refresh compact context without lesson or quiz contents.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "crm_activity" and str(event.metadata.get("stimulus_type") or "") in {"deal_stage_changed", "customer_note_added", "followup_scheduled"}:
        candidates.append(
            _candidate(
                event,
                "prepare_resume_context",
                "CRM activity changed; prepare compact customer-work context without customer fields or notes.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "support_desk_activity" and str(event.metadata.get("stimulus_type") or "") in {"ticket_assigned", "ticket_replied", "ticket_escalated", "sla_breach_warning"}:
        candidates.append(
            _candidate(
                event,
                "review_attention",
                "Support ticket activity may require timely follow-up while customer content stays redacted.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "analytics_activity" and str(event.metadata.get("stimulus_type") or "") in {"metric_threshold_crossed", "report_exported", "query_result_viewed"}:
        candidates.append(
            _candidate(
                event,
                "analyze",
                "Analytics threshold, export, or query-result activity may explain a business signal.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "database_activity" and str(event.metadata.get("stimulus_type") or "") in {"query_failed", "schema_changed", "migration_failed"}:
        candidates.append(
            _candidate(
                event,
                "analyze",
                "Database query, schema, or migration event may affect the current workflow.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "cloud_console_activity" and str(event.metadata.get("stimulus_type") or "") in {"deployment_failed", "secret_view_attempted", "billing_alert_seen", "permission_error_seen"}:
        candidates.append(
            _candidate(
                event,
                "suppress_collection" if str(event.metadata.get("stimulus_type") or "") == "secret_view_attempted" else "analyze",
                "Cloud console activity may expose secrets or affect deployed infrastructure.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "incident_activity" and str(event.metadata.get("stimulus_type") or "") in {"incident_declared", "incident_escalated", "on_call_alert_received"}:
        candidates.append(
            _candidate(
                event,
                "review_attention",
                "Incident or on-call activity may require immediate attention while logs and details remain redacted.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "file_operation_activity" and str(event.metadata.get("stimulus_type") or "") in {"file_opened", "file_closed", "file_saved", "file_renamed", "file_moved", "file_duplicated", "file_tagged", "file_shared_from_manager"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "File manager operation changed the work surface while paths, filenames, tags, and contents remain redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "folder_navigation_activity" and str(event.metadata.get("stimulus_type") or "") in {"folder_opened", "folder_changed", "folder_created", "folder_renamed", "folder_moved", "path_bar_used"}:
        candidates.append(
            _candidate(
                event,
                "prepare_resume_context",
                "Folder navigation changed the active file context while folder names and paths remain redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "file_preview_activity" and str(event.metadata.get("stimulus_type") or "") in {"quick_look_opened", "preview_pane_opened", "file_metadata_inspected", "file_info_panel_opened"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "File preview or metadata inspection changed the local context while preview contents and paths remain redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "trash_activity" and str(event.metadata.get("stimulus_type") or "") in {"file_moved_to_trash", "folder_moved_to_trash", "trash_item_restored", "trash_item_deleted", "trash_emptied"}:
        candidates.append(
            _candidate(
                event,
                "review_attention" if str(event.metadata.get("stimulus_type") or "") in {"trash_item_deleted", "trash_emptied"} else "update_context",
                "Trash or recycle-bin activity changed file state while item paths and contents remain redacted.",
                risk="medium" if str(event.metadata.get("stimulus_type") or "") in {"trash_item_deleted", "trash_emptied"} else "low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "ai_assistant_activity" and str(event.metadata.get("stimulus_type") or "") in {"ai_tool_call_failed", "ai_suggestion_accepted", "ai_conversation_exported"}:
        candidates.append(
            _candidate(
                event,
                "review_agent_runtime",
                "AI assistant activity may change the user's work context or need recovery while prompts and responses remain redacted.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "pdf_activity" and str(event.metadata.get("stimulus_type") or "") in {"pdf_form_filled", "pdf_signature_requested", "pdf_signed", "pdf_exported"}:
        candidates.append(
            _candidate(
                event,
                "review_attention",
                "PDF form, signature, or export activity may need follow-up while document content remains redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "spreadsheet_activity" and str(event.metadata.get("stimulus_type") or "") in {"formula_error_detected", "pivot_table_changed", "workbook_exported"}:
        candidates.append(
            _candidate(
                event,
                "analyze" if str(event.metadata.get("stimulus_type") or "") == "formula_error_detected" else "update_context",
                "Spreadsheet formula, pivot, or export activity changed the work surface while sheet contents remain redacted.",
                risk="medium" if str(event.metadata.get("stimulus_type") or "") == "formula_error_detected" else "low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "presentation_activity" and str(event.metadata.get("stimulus_type") or "") in {"slideshow_started", "slideshow_ended", "deck_exported"}:
        candidates.append(
            _candidate(
                event,
                "prepare_briefing" if str(event.metadata.get("stimulus_type") or "") == "slideshow_started" else "update_context",
                "Presentation activity changed the work mode while slide contents and speaker notes remain redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "spreadsheet_editing_activity" and str(event.metadata.get("stimulus_type") or "") in {"cell_range_edited", "cell_range_filled", "row_inserted", "row_deleted", "column_inserted", "column_deleted", "sheet_created", "sheet_renamed", "sheet_deleted"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Spreadsheet editing changed workbook state while workbook names, sheet names, ranges, and values stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "spreadsheet_formula_activity" and str(event.metadata.get("stimulus_type") or "") in {"formula_entered", "formula_edited", "formula_error_detected", "formula_error_resolved", "calculation_failed"}:
        candidates.append(
            _candidate(
                event,
                "analyze" if str(event.metadata.get("stimulus_type") or "") in {"formula_error_detected", "calculation_failed"} else "update_context",
                "Spreadsheet formula activity changed calculation state while formulas, cell values, named ranges, and sheet contents stay redacted.",
                risk="medium" if str(event.metadata.get("stimulus_type") or "") in {"formula_error_detected", "calculation_failed"} else "low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "spreadsheet_data_analysis_activity" and str(event.metadata.get("stimulus_type") or "") in {"sort_applied", "filter_applied", "pivot_table_created", "pivot_table_changed", "chart_created", "chart_updated", "data_validation_changed", "conditional_format_changed"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Spreadsheet analysis changed filters, pivots, charts, validation, or formatting while source data and labels stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "spreadsheet_import_export_activity" and str(event.metadata.get("stimulus_type") or "") in {"csv_imported", "data_connection_failed", "workbook_exported", "workbook_export_failed", "sheet_shared", "permissions_changed", "workbook_submitted"}:
        candidates.append(
            _candidate(
                event,
                "review_attention" if str(event.metadata.get("stimulus_type") or "") in {"data_connection_failed", "workbook_export_failed"} else "update_context",
                "Spreadsheet import, export, sharing, or connection state changed while filenames, links, recipients, destinations, and connection details stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "presentation_authoring_activity" and str(event.metadata.get("stimulus_type") or "") in {"slide_created", "slide_edited", "slide_deleted", "slide_duplicated", "slide_reordered", "speaker_notes_edited", "outline_edited", "object_inserted", "object_edited"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Presentation authoring changed deck state while slide text, speaker notes, outlines, object text, and asset names stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "presentation_design_activity" and str(event.metadata.get("stimulus_type") or "") in {"theme_applied", "layout_changed", "master_slide_edited", "transition_changed", "animation_added", "animation_removed", "media_inserted", "chart_inserted", "accessibility_check_run"}:
        candidates.append(
            _candidate(
                event,
                "review_attention" if str(event.metadata.get("stimulus_type") or "") == "accessibility_check_run" else "update_context",
                "Presentation design changed visual structure while theme names, slide content, media names, animations, and chart data stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "presentation_delivery_activity" and str(event.metadata.get("stimulus_type") or "") in {"slideshow_started", "slideshow_ended", "presenter_view_opened", "slide_advanced", "slide_rewound", "rehearsal_started", "rehearsal_completed"}:
        candidates.append(
            _candidate(
                event,
                "prepare_briefing" if str(event.metadata.get("stimulus_type") or "") in {"slideshow_started", "presenter_view_opened", "rehearsal_started"} else "update_context",
                "Presentation delivery state changed while deck titles, slide text, speaker notes, and audience details stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "presentation_export_activity" and str(event.metadata.get("stimulus_type") or "") in {"deck_exported", "deck_export_failed", "deck_shared", "deck_permissions_changed", "deck_publish_completed", "handout_created", "recording_exported"}:
        candidates.append(
            _candidate(
                event,
                "review_attention" if str(event.metadata.get("stimulus_type") or "") == "deck_export_failed" else "update_context",
                "Presentation export, sharing, publishing, handout, or recording state changed while filenames, links, recipients, destinations, and recording details stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "file_dialog_activity" and str(event.metadata.get("stimulus_type") or "") in {"save_panel_shown", "save_confirmed", "import_started", "export_started"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "File open/save/import/export activity changed the work surface while selected paths remain redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "system_settings_activity" and str(event.metadata.get("stimulus_type") or "") in {"setting_changed", "display_setting_changed", "keyboard_shortcut_changed", "default_app_changed", "accessibility_setting_changed"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "System settings changed; refresh compact environment context.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "text_composition_activity" and str(event.metadata.get("stimulus_type") or "") in {"composition_submitted", "draft_autosaved", "snippet_inserted", "template_inserted", "text_expansion_used"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Text composition changed; refresh compact context while draft bodies, snippets, templates, and typed text remain redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "dictation_activity" and str(event.metadata.get("stimulus_type") or "") in {"dictation_transcript_ready", "dictation_error", "voice_typing_started"}:
        candidates.append(
            _candidate(
                event,
                "review_attention" if str(event.metadata.get("stimulus_type") or "") == "dictation_error" else "suppress_collection",
                "Dictation or voice typing is active; keep rich collection conservative and omit transcript bodies.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "writing_assist_activity" and str(event.metadata.get("stimulus_type") or "") in {"spellcheck_suggestion_accepted", "grammar_suggestion_accepted", "autocorrect_applied", "predictive_text_accepted", "rewrite_suggestion_accepted"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Writing assist changed composed text while original text, suggestions, and replacements remain redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "translation_activity" and str(event.metadata.get("stimulus_type") or "") in {"translation_completed", "translation_failed", "translated_text_inserted"}:
        candidates.append(
            _candidate(
                event,
                "review_attention" if str(event.metadata.get("stimulus_type") or "") == "translation_failed" else "update_context",
                "Translation activity changed text context while source and translated text remain redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "file_transfer_activity" and str(event.metadata.get("stimulus_type") or "") in {"upload_failed", "file_transfer_failed", "network_share_connected", "airdrop_received", "nearby_share_received"}:
        candidates.append(
            _candidate(
                event,
                "review_attention" if str(event.metadata.get("stimulus_type") or "") in {"airdrop_received", "nearby_share_received"} else "analyze",
                "File transfer, upload, AirDrop, nearby-share, or network-share activity may require follow-up while transfer details remain redacted.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "archive_activity" and str(event.metadata.get("stimulus_type") or "") in {"compression_failed", "extraction_failed", "archive_encrypted", "archive_password_requested"}:
        candidates.append(
            _candidate(
                event,
                "suppress_collection" if str(event.metadata.get("stimulus_type") or "") == "archive_password_requested" else "review_attention",
                "Archive or extraction activity may need follow-up while paths, passwords, and contents stay redacted.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "camera_capture_activity" and str(event.metadata.get("stimulus_type") or "") in {"camera_capture_started", "video_recording_started", "qr_code_scanned"}:
        candidates.append(
            _candidate(
                event,
                "suppress_collection",
                "Camera, recording, or QR-scan context is active; keep rich collection conservative and omit captured media.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "continuity_activity" and str(event.metadata.get("stimulus_type") or "") in {"universal_clipboard_received", "sms_relay_received", "phone_call_relay_started", "mobile_hotspot_connected"}:
        candidates.append(
            _candidate(
                event,
                "suppress_collection" if str(event.metadata.get("stimulus_type") or "") in {"universal_clipboard_received", "sms_relay_received", "phone_call_relay_started"} else "update_context",
                "Cross-device continuity changed local context while device names, clipboard contents, and messages remain redacted.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "command_activity" and str(event.metadata.get("stimulus_type") or "") in {"command_executed", "menu_item_selected", "context_menu_item_selected", "toolbar_button_pressed", "shortcut_action_triggered"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "A generic in-app command was executed; refresh compact context while command labels and payloads remain redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "selection_activity" and str(event.metadata.get("stimulus_type") or "") in {"item_selected", "multi_selection_changed", "text_selection_changed", "table_cell_selected", "canvas_object_selected", "inspector_selection_changed"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "In-app selection changed; refresh compact context while selected values and labels remain redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "navigation_activity" and str(event.metadata.get("stimulus_type") or "") in {"sidebar_item_selected", "breadcrumb_clicked", "in_app_tab_switched", "pane_switched", "search_result_opened"}:
        candidates.append(
            _candidate(
                event,
                "prepare_resume_context",
                "In-app navigation changed the active work surface; prepare compact resume context without route labels or search text.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "edit_history_activity" and str(event.metadata.get("stimulus_type") or "") in {"undo_performed", "redo_performed", "revert_performed", "version_restored"}:
        candidates.append(
            _candidate(
                event,
                "review_attention" if str(event.metadata.get("stimulus_type") or "") in {"revert_performed", "version_restored"} else "update_context",
                "Edit history changed; refresh context or review possible destructive revert/version activity while document contents remain redacted.",
                risk="medium" if str(event.metadata.get("stimulus_type") or "") in {"revert_performed", "version_restored"} else "low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "dock_taskbar_activity" and str(event.metadata.get("stimulus_type") or "") in {"dock_badge_changed", "taskbar_badge_changed", "jump_list_opened", "dock_item_clicked", "taskbar_item_clicked"}:
        candidates.append(
            _candidate(
                event,
                "prepare_resume_context" if str(event.metadata.get("stimulus_type") or "").endswith("_clicked") else "review_attention",
                "Dock/taskbar activity may signal an app switch or attention badge while labels and item contents remain redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "menu_bar_tray_activity" and str(event.metadata.get("stimulus_type") or "") in {"tray_notification_clicked", "status_indicator_changed", "background_app_menu_opened", "status_item_opened"}:
        candidates.append(
            _candidate(
                event,
                "review_attention",
                "Menu bar, tray, or background-app status activity may need attention while item payloads remain redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "quick_settings_activity" and str(event.metadata.get("stimulus_type") or "") in {"wifi_toggle_changed", "bluetooth_toggle_changed", "do_not_disturb_changed", "screen_mirroring_changed"}:
        candidates.append(
            _candidate(
                event,
                "suppress_collection" if str(event.metadata.get("stimulus_type") or "") == "screen_mirroring_changed" else "update_context",
                "Quick settings changed local environment; refresh compact context or suppress rich capture during mirroring.",
                risk="medium" if str(event.metadata.get("stimulus_type") or "") == "screen_mirroring_changed" else "low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "widget_activity" and str(event.metadata.get("stimulus_type") or "") in {"widget_clicked", "widget_alert_seen", "widget_added", "widget_removed"}:
        candidates.append(
            _candidate(
                event,
                "review_attention" if str(event.metadata.get("stimulus_type") or "") == "widget_alert_seen" else "update_context",
                "Widget activity changed the desktop context while widget names, alerts, and payloads remain redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "notification_activity" and str(event.metadata.get("stimulus_type") or "") in {"critical_alert_received", "reminder_fired"}:
        candidates.append(
            _candidate(
                event,
                "review_attention",
                "A critical alert or reminder fired; decide whether it needs user-visible attention.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "communication_activity" and str(event.metadata.get("stimulus_type") or "") in {"mention_received", "dm_received", "thread_reply_received", "call_invite_received"}:
        candidates.append(
            _candidate(
                event,
                "review_message",
                "A direct or mention-like communication event arrived; determine whether a reply or task is needed.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "channel_activity" and str(event.metadata.get("stimulus_type") or "") in {"mention_received", "dm_received", "thread_reply_received", "call_invite_received"}:
        candidates.append(
            _candidate(
                event,
                "review_message",
                "A channel-native direct or mention-like event arrived; determine whether a reply or task is needed.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "chat_composition_activity" and str(event.metadata.get("stimulus_type") or "") in {"chat_draft_started", "chat_message_sent", "slash_command_used", "chat_attachment_added"}:
        candidates.append(
            _candidate(
                event,
                "prepare_reply" if str(event.metadata.get("stimulus_type") or "") == "chat_draft_started" else "update_context",
                "Chat composition changed; prepare or refresh context while message bodies, recipients, attachments, and command payloads stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "chat_thread_activity" and str(event.metadata.get("stimulus_type") or "") in {"thread_opened", "thread_reply_started", "thread_reply_sent", "thread_unread_changed"}:
        candidates.append(
            _candidate(
                event,
                "prepare_reply" if str(event.metadata.get("stimulus_type") or "") == "thread_reply_started" else "review_message",
                "Chat thread activity changed; review or prepare reply context while thread titles, participants, replies, and bodies stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "chat_channel_navigation_activity" and str(event.metadata.get("stimulus_type") or "") in {"chat_workspace_switched", "chat_channel_opened", "chat_channel_search_performed", "chat_saved_item_opened"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Chat workspace or channel navigation changed; refresh compact collaboration context while names, search terms, and saved item contents stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "chat_presence_activity" and str(event.metadata.get("stimulus_type") or "") in {"chat_status_changed", "presence_changed", "do_not_disturb_scheduled", "do_not_disturb_enabled", "do_not_disturb_disabled", "availability_set", "notification_preference_changed"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Chat presence or notification state changed; refresh collaboration context while custom status text and availability notes stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "calendar_activity" and str(event.metadata.get("stimulus_type") or "") in {"meeting_starting", "meeting_started", "deadline_near", "followup_due"}:
        candidates.append(
            _candidate(
                event,
                "prepare_briefing",
                "A calendar, deadline, or follow-up event is active; prepare context silently.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "calendar_scheduling_activity" and str(event.metadata.get("stimulus_type") or "") in {"calendar_event_created", "calendar_event_rescheduled", "calendar_invite_received", "calendar_invite_accepted", "calendar_invite_declined", "calendar_availability_checked"}:
        candidates.append(
            _candidate(
                event,
                "prepare_briefing" if str(event.metadata.get("stimulus_type") or "") in {"calendar_event_created", "calendar_event_rescheduled", "calendar_invite_received"} else "update_context",
                "Calendar scheduling changed; prepare or refresh context while titles, attendees, locations, and notes stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "reminder_todo_activity" and str(event.metadata.get("stimulus_type") or "") in {"reminder_created", "reminder_completed", "reminder_snoozed", "todo_created", "todo_completed", "todo_due_date_changed"}:
        candidates.append(
            _candidate(
                event,
                "review_attention" if str(event.metadata.get("stimulus_type") or "") in {"reminder_snoozed", "todo_due_date_changed"} else "update_context",
                "Reminder or lightweight to-do state changed while titles, notes, and lists remain redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "wakeup_activity":
        candidates.append(
            _candidate(
                event,
                "prepare_briefing",
                "A scheduled wakeup or follow-up is due; prepare relevant context silently.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "mail_composition_activity" and str(event.metadata.get("stimulus_type") or "") in {"email_reply_started", "email_forward_started", "email_sent", "email_send_scheduled", "email_attachment_added", "email_send_cancelled"}:
        candidates.append(
            _candidate(
                event,
                "prepare_reply" if str(event.metadata.get("stimulus_type") or "") in {"email_reply_started", "email_forward_started"} else "update_context",
                "Mail composition changed; prepare or refresh context while subjects, recipients, bodies, and attachments stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "mail_organization_activity" and str(event.metadata.get("stimulus_type") or "") in {"email_archived", "email_deleted", "email_moved", "email_labeled", "email_search_performed", "mail_rule_applied"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Mailbox organization changed; refresh compact mail context while senders, subjects, queries, labels, and rule details stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "document_composition_activity" and str(event.metadata.get("stimulus_type") or "") in {"document_draft_started", "document_edited", "document_section_edited", "document_outline_updated", "document_style_applied", "document_template_applied", "document_citation_inserted", "document_media_inserted", "document_saved"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Document composition changed; refresh compact document context while text, titles, selected content, paths, and inserted content stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "document_review_activity" and str(event.metadata.get("stimulus_type") or "") in {"document_comment_added", "document_comment_replied", "document_suggestion_received", "document_review_requested", "document_mention_added"}:
        candidates.append(
            _candidate(
                event,
                "review_attention",
                "Document review activity may need attention while comments, suggestions, reviewer names, mentions, and selected text stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "document_structure_activity" and str(event.metadata.get("stimulus_type") or "") in {"document_heading_changed", "document_section_added", "document_section_moved", "document_toc_updated", "document_outline_opened", "document_navigation_pane_used"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Document structure changed; refresh compact outline context while headings, section names, and document contents stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "document_export_publish_activity" and str(event.metadata.get("stimulus_type") or "") in {"document_export_completed", "document_export_failed", "document_publish_completed", "document_share_link_created", "document_permissions_changed", "document_submitted"}:
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Document export, publish, or sharing state changed while filenames, links, recipients, destinations, and permission details stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "meeting_audio_activity" and str(event.metadata.get("stimulus_type") or "") in {"call_started", "meeting_transcript_chunk", "speaker_changed"}:
        candidates.append(
            _candidate(
                event,
                "prepare_briefing",
                "Meeting or call activity is active; prepare compact context without exposing raw audio.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "meeting_app_activity" and str(event.metadata.get("stimulus_type") or "") in {"meeting_joined", "waiting_room_admitted", "breakout_room_joined", "meeting_recording_started"}:
        candidates.append(
            _candidate(
                event,
                "prepare_briefing",
                "Meeting app state changed; prepare compact meeting context while titles and participant names stay redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "call_control_activity" and str(event.metadata.get("stimulus_type") or "") in {"microphone_unmuted", "camera_enabled", "captions_enabled", "meeting_chat_opened"}:
        candidates.append(
            _candidate(
                event,
                "suppress_collection",
                "Meeting call controls indicate live audio, camera, captions, or chat context; keep rich collection conservative.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "meeting_presentation_activity" and str(event.metadata.get("stimulus_type") or "") in {"screen_share_started", "window_share_started", "presentation_started", "remote_control_requested"}:
        candidates.append(
            _candidate(
                event,
                "suppress_collection" if str(event.metadata.get("stimulus_type") or "") in {"screen_share_started", "window_share_started", "remote_control_requested"} else "prepare_briefing",
                "Meeting presentation or share state changed; avoid exposing shared screen contents while preparing relevant context.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "meeting_artifact_activity" and str(event.metadata.get("stimulus_type") or "") in {"meeting_transcript_available", "meeting_summary_generated", "meeting_action_items_detected", "meeting_notes_shared", "meeting_followup_created"}:
        candidates.append(
            _candidate(
                event,
                "review_attention",
                "Meeting artifact or follow-up became available; review whether it creates tasks while artifact contents remain redacted.",
                risk="low",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "security_context_changed":
        candidates.append(
            _candidate(
                event,
                "suppress_collection",
                "Security-sensitive context is active; keep rich collection suppressed and avoid interruption unless explicitly requested.",
                risk="medium",
                requires_user_approval=False,
                metadata=event.metadata,
            )
        )
    elif event.event_type == "agent_runtime_activity" and str(event.metadata.get("stimulus_type") or "") in {"tool_failed", "run_stuck", "approval_requested"}:
        candidates.append(
            _candidate(
                event,
                "review_agent_runtime",
                "Agent runtime event may need recovery, approval handling, or user-visible status.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    return candidates


def _event(
    event_type: str,
    source: str,
    summary: str,
    *,
    occurred_at: str,
    metadata: dict[str, Any] | None = None,
    raw_ref: str = "",
    sent_to_llm: bool = False,
    privacy_level: str = "compact",
) -> SemanticEvent:
    return SemanticEvent(
        event_id=new_id("semantic"),
        event_type=event_type if event_type in SEMANTIC_EVENT_TYPES else "system_session_started",
        source=source,
        summary=_truncate(summary, 1000),
        occurred_at=occurred_at,
        metadata=_json_safe(metadata or {}),
        raw_ref=raw_ref,
        sent_to_llm=sent_to_llm,
        privacy_level=privacy_level,
    )


def _candidate(
    event: SemanticEvent,
    action_type: str,
    reason: str,
    *,
    risk: str = "low",
    requires_user_approval: bool = False,
    metadata: dict[str, Any] | None = None,
) -> AutonomousActionCandidate:
    return AutonomousActionCandidate(
        action_id=new_id("action"),
        trigger_event_id=event.event_id,
        action_type=action_type,
        reason=_truncate(reason, 1000),
        risk=risk,
        requires_user_approval=requires_user_approval,
        metadata=_json_safe(metadata or {}),
    )


def _candidate_priority(candidate: AutonomousActionCandidate) -> CognitivePriority:
    if candidate.risk == "medium" or candidate.action_type in {"analyze", "prepare_resume_context"}:
        return CognitivePriority.NORMAL
    return CognitivePriority.LOW


def _recent_semantic_payloads(config: AgentConfig, *, limit: int) -> list[dict[str, Any]]:
    memory = EventStore(config.normalized().memory_db_path)
    return [event.get("payload", {}) for event in memory.tail(limit=max(limit * 4, 50)) if event.get("event_type") == "semantic_event"][:limit]


def _looks_like_work_return(event: SemanticEvent, recent: list[dict[str, Any]]) -> bool:
    app = str(event.metadata.get("app_name") or "").lower()
    title = str(event.metadata.get("window_title") or "").lower()
    work_surface = any(token in f"{app} {title}" for token in ("codex", "xcode", "terminal", "visual studio code", "vscode", "cursor"))
    recent_browser = any(item.get("event_type") in {"browser_context_changed", "research_session_updated"} for item in recent)
    return work_surface and recent_browser


def _render_current_context(semantic_events: list[dict[str, Any]], action_candidates: list[dict[str, Any]]) -> str:
    events = [event.get("payload", {}) for event in semantic_events]
    actions = [event.get("payload", {}) for event in action_candidates]
    latest_focus = next((event for event in events if event.get("event_type") == "app_focus_changed"), {})
    latest_browser = next((event for event in events if event.get("event_type") == "browser_context_changed"), {})
    latest_files = next((event for event in events if event.get("event_type") == "project_files_changed"), {})
    lines = [
        "# Current Context",
        "",
        "Privacy note: this brief is generated from compact semantic events. Raw continuous audio, video, screenshots, OCR text, and clipboard content are not included by default.",
        "",
        "## Focus",
        f"- Active work surface: {latest_focus.get('summary', 'No stable app focus recorded.')}",
        f"- Browser/research context: {latest_browser.get('summary', 'No stable browser context recorded.')}",
        f"- Project file activity: {latest_files.get('summary', 'No recent project file changes recorded.')}",
        "",
        "## Recent Semantic Events",
    ]
    for event in events[:12]:
        lines.append(f"- {event.get('occurred_at', '')}: {event.get('event_type', 'event')} - {event.get('summary', '')}")
    if not events:
        lines.append("- No semantic events recorded yet.")
    lines.extend(["", "## Queued Autonomous Candidates"])
    for candidate in actions[:12]:
        lines.append(f"- {candidate.get('action_type', 'action')}: {candidate.get('reason', '')}")
    if not actions:
        lines.append("- No autonomous candidates queued.")
    lines.append("")
    return "\n".join(lines)


def _render_events_markdown(semantic_events: list[dict[str, Any]]) -> str:
    lines = [
        "# Semantic Event Timeline",
        "",
        "Source of truth remains the local event store; this file is a compact generated view for LLM context and UI inspection.",
        "",
    ]
    for event in semantic_events:
        payload = event.get("payload", {})
        lines.append(f"- `{payload.get('event_type', 'event')}` {payload.get('occurred_at', '')}: {payload.get('summary', '')}")
    if not semantic_events:
        lines.append("- No semantic events recorded yet.")
    lines.append("")
    return "\n".join(lines)


def _active_window_summary(event: dict[str, Any]) -> str:
    app = str(event.get("app_name") or "unknown app")
    title = str(event.get("window_title") or "unknown window")
    return f"Active app became {app} - {title}."


def _browser_summary(event: dict[str, Any]) -> str:
    app = str(event.get("app_name") or "browser")
    title = str(event.get("window_title") or event.get("url") or "unknown page")
    return f"Browser context became {app} - {title}."


def _safe_subset(source: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return _json_safe({key: source.get(key) for key in keys if key in source})


def _json_safe(value: dict[str, Any]) -> dict[str, Any]:
    try:
        json.dumps(value, ensure_ascii=False, sort_keys=True)
        return value
    except (TypeError, ValueError):
        return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))


def _truncate(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _preview_file(path: Path, *, limit: int = 2000) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")[:limit]
    except OSError:
        return ""
