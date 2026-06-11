from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile


WORKSPACE_LAYOUT_ACTIVITY_STIMULUS_TYPES = {
    "mission_control_opened",
    "workspace_overview_opened",
    "desktop_space_created",
    "desktop_space_deleted",
    "desktop_space_switched",
    "stage_manager_enabled",
    "stage_manager_disabled",
}
WINDOW_ARRANGEMENT_ACTIVITY_STIMULUS_TYPES = {
    "window_tiled",
    "window_snapped",
    "split_view_started",
    "split_view_ended",
    "window_fullscreen_entered",
    "window_fullscreen_exited",
    "window_moved_to_display",
    "window_moved_to_space",
}
DISPLAY_ARRANGEMENT_ACTIVITY_STIMULUS_TYPES = {
    "display_arrangement_changed",
    "display_resolution_changed",
    "display_scaling_changed",
    "display_rotation_changed",
    "primary_display_changed",
    "display_profile_changed",
}
APP_WORKSPACE_ACTIVITY_STIMULUS_TYPES = {
    "app_workspace_opened",
    "app_workspace_switched",
    "app_workspace_restored",
    "app_workspace_saved",
    "layout_preset_applied",
    "profile_switched",
}


def collect_workspace_layout_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "workspace_layout_activity", WORKSPACE_LAYOUT_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)


def collect_window_arrangement_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "window_arrangement_activity", WINDOW_ARRANGEMENT_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)


def collect_display_arrangement_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "display_arrangement_activity", DISPLAY_ARRANGEMENT_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)


def collect_app_workspace_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "app_workspace_activity", APP_WORKSPACE_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)
