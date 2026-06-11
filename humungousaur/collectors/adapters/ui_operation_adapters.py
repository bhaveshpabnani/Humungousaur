from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile


COMMAND_ACTIVITY_STIMULUS_TYPES = {
    "command_palette_opened",
    "command_executed",
    "menu_item_selected",
    "context_menu_opened",
    "context_menu_item_selected",
    "toolbar_button_pressed",
    "shortcut_action_triggered",
}
SELECTION_ACTIVITY_STIMULUS_TYPES = {
    "item_selected",
    "multi_selection_changed",
    "text_selection_changed",
    "list_row_selected",
    "table_cell_selected",
    "canvas_object_selected",
    "inspector_selection_changed",
}
NAVIGATION_ACTIVITY_STIMULUS_TYPES = {
    "sidebar_item_selected",
    "breadcrumb_clicked",
    "in_app_tab_switched",
    "pane_switched",
    "in_app_back",
    "in_app_forward",
    "search_result_opened",
}
EDIT_HISTORY_ACTIVITY_STIMULUS_TYPES = {
    "undo_performed",
    "redo_performed",
    "autosave_completed",
    "manual_save_completed",
    "revert_performed",
    "version_restored",
    "history_checkpoint_created",
}


def collect_command_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "command_activity", COMMAND_ACTIVITY_STIMULUS_TYPES, source="accessibility", max_events=20)


def collect_selection_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "selection_activity", SELECTION_ACTIVITY_STIMULUS_TYPES, source="accessibility", max_events=20)


def collect_navigation_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "navigation_activity", NAVIGATION_ACTIVITY_STIMULUS_TYPES, source="accessibility", max_events=20)


def collect_edit_history_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "edit_history_activity", EDIT_HISTORY_ACTIVITY_STIMULUS_TYPES, source="accessibility", max_events=20)
