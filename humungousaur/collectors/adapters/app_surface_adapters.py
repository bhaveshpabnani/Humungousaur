from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile
from ..sources.google_workspace import read_google_workspace_events


AI_ASSISTANT_ACTIVITY_STIMULUS_TYPES = {
    "ai_chat_opened",
    "ai_prompt_submitted",
    "ai_response_received",
    "ai_file_context_attached",
    "ai_tool_call_started",
    "ai_tool_call_failed",
    "ai_code_suggestion_accepted",
    "ai_code_suggestion_rejected",
    "ai_suggestion_accepted",
    "ai_model_error",
    "ai_tool_error",
    "ai_conversation_exported",
}
PDF_ACTIVITY_STIMULUS_TYPES = {
    "pdf_opened",
    "pdf_annotated",
    "pdf_search_performed",
    "pdf_form_filled",
    "pdf_signature_requested",
    "pdf_signed",
    "pdf_exported",
}
SPREADSHEET_ACTIVITY_STIMULUS_TYPES = {
    "workbook_opened",
    "cell_range_edited",
    "formula_error_detected",
    "pivot_table_changed",
    "chart_updated",
    "csv_imported",
    "workbook_exported",
}
PRESENTATION_ACTIVITY_STIMULUS_TYPES = {
    "deck_opened",
    "slide_edited",
    "slideshow_started",
    "slideshow_ended",
    "speaker_notes_edited",
    "deck_exported",
}
FILE_DIALOG_ACTIVITY_STIMULUS_TYPES = {
    "open_panel_shown",
    "save_panel_shown",
    "file_selected",
    "folder_selected",
    "save_confirmed",
    "import_started",
    "export_started",
}
SYSTEM_SETTINGS_ACTIVITY_STIMULUS_TYPES = {
    "settings_pane_opened",
    "setting_changed",
    "display_setting_changed",
    "sound_setting_changed",
    "keyboard_shortcut_changed",
    "default_app_changed",
    "accessibility_setting_changed",
}


def collect_ai_assistant_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "ai_assistant_activity", AI_ASSISTANT_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_pdf_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "pdf_activity", PDF_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_spreadsheet_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "spreadsheet_activity", SPREADSHEET_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "spreadsheet_activity", SPREADSHEET_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_presentation_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "presentation_activity", PRESENTATION_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "presentation_activity", PRESENTATION_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_file_dialog_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "file_dialog_activity", FILE_DIALOG_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_system_settings_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "system_settings_activity", SYSTEM_SETTINGS_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)
