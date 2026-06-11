from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile
from ..sources.google_workspace import read_google_workspace_events


ACCESSIBILITY_STIMULUS_TYPES = {
    "focused_control_changed",
    "selected_text_changed",
    "button_available",
    "form_field_focused",
    "menu_opened",
    "table_row_selected",
    "checkbox_toggled",
}
NOTIFICATION_STIMULUS_TYPES = {
    "notification_received",
    "notification_clicked",
    "notification_dismissed",
    "critical_alert_received",
    "reminder_fired",
}
CALENDAR_STIMULUS_TYPES = {
    "meeting_starting",
    "meeting_started",
    "meeting_ended",
    "deadline_near",
    "scheduled_wakeup_due",
    "followup_due",
}
COMMUNICATION_STIMULUS_TYPES = {
    "message_received",
    "mention_received",
    "dm_received",
    "thread_reply_received",
    "reaction_added",
    "message_sent",
    "draft_created",
    "call_invite_received",
    "channel_unread_changed",
}
MAIL_STIMULUS_TYPES = {
    "email_received",
    "important_email_received",
    "email_opened",
    "draft_started",
    "attachment_downloaded",
    "send_failed",
}
DOCUMENT_STIMULUS_TYPES = {
    "doc_opened",
    "doc_edited",
    "comment_added",
    "suggestion_received",
    "export_pdf_created",
    "spreadsheet_formula_error",
    "slide_deck_presented",
}
CREATIVE_STIMULUS_TYPES = {
    "canvas_selection_changed",
    "frame_exported",
    "asset_imported",
    "render_started",
    "render_finished",
    "timeline_marker_changed",
}
SECURITY_STIMULUS_TYPES = {
    "password_field_focused",
    "secret_manager_opened",
    "private_browsing_detected",
    "sensitive_app_focused",
    "camera_enabled",
    "microphone_enabled",
}
AGENT_RUNTIME_STIMULUS_TYPES = {
    "agent_run_started",
    "tool_started",
    "tool_failed",
    "approval_requested",
    "run_cancelled",
    "run_stuck",
    "memory_updated",
    "autonomous_cycle_started",
}


def collect_accessibility_context(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "accessibility_context", ACCESSIBILITY_STIMULUS_TYPES, source="accessibility")


def collect_notification_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "notification_activity", NOTIFICATION_STIMULUS_TYPES, source="activity")


def collect_calendar_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "calendar_activity", CALENDAR_STIMULUS_TYPES) + read_bridge_events(
        config, state, "calendar_activity", CALENDAR_STIMULUS_TYPES, source="system"
    )


def collect_communication_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "communication_activity", COMMUNICATION_STIMULUS_TYPES, source="channel_message")


def collect_mail_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "mail_activity", MAIL_STIMULUS_TYPES) + read_bridge_events(
        config, state, "mail_activity", MAIL_STIMULUS_TYPES, source="activity"
    )


def collect_document_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "document_activity", DOCUMENT_STIMULUS_TYPES) + read_bridge_events(
        config, state, "document_activity", DOCUMENT_STIMULUS_TYPES, source="activity"
    )


def collect_creative_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "creative_activity", CREATIVE_STIMULUS_TYPES, source="activity")


def collect_security_context(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "security_context", SECURITY_STIMULUS_TYPES, source="system")


def collect_agent_runtime(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "agent_runtime", AGENT_RUNTIME_STIMULUS_TYPES, source="system")
