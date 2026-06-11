from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile


KEYBOARD_INPUT_ACTIVITY_STIMULUS_TYPES = {
    "input_source_changed",
    "keyboard_layout_changed",
    "keyboard_shortcut_conflict_detected",
    "modifier_key_remapped",
    "key_repeat_changed",
    "caps_lock_toggled",
    "function_key_mode_changed",
    "hardware_keyboard_connected",
    "hardware_keyboard_disconnected",
}
IME_ACTIVITY_STIMULUS_TYPES = {
    "ime_composition_started",
    "ime_candidate_window_shown",
    "ime_candidate_selected",
    "ime_composition_committed",
    "ime_composition_cancelled",
    "ime_conversion_failed",
    "language_input_switched",
}
TEXT_INPUT_SURFACE_ACTIVITY_STIMULUS_TYPES = {
    "text_field_focused",
    "secure_text_field_focused",
    "multiline_editor_focused",
    "search_field_focused",
    "form_field_autofocused",
    "input_validation_error",
    "input_submit_attempted",
}
PASTEBOARD_WORKFLOW_ACTIVITY_STIMULUS_TYPES = {
    "copy_performed",
    "cut_performed",
    "paste_performed",
    "paste_and_match_style_performed",
    "clipboard_manager_opened",
    "clipboard_history_item_selected",
    "clipboard_cleared",
}


def collect_keyboard_input_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "keyboard_input_activity", KEYBOARD_INPUT_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)


def collect_ime_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "ime_activity", IME_ACTIVITY_STIMULUS_TYPES, source="accessibility", max_events=20)


def collect_text_input_surface_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "text_input_surface_activity", TEXT_INPUT_SURFACE_ACTIVITY_STIMULUS_TYPES, source="accessibility", max_events=20)


def collect_pasteboard_workflow_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "pasteboard_workflow_activity", PASTEBOARD_WORKFLOW_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)
