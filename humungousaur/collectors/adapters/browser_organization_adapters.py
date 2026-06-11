from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile


BROWSER_WINDOW_ACTIVITY_STIMULUS_TYPES = {
    "browser_window_opened",
    "browser_window_closed",
    "browser_window_focused",
    "browser_window_minimized",
    "browser_window_fullscreen_entered",
    "browser_window_fullscreen_exited",
    "browser_session_restored",
    "recently_closed_window_reopened",
}
BROWSER_TAB_GROUP_ACTIVITY_STIMULUS_TYPES = {
    "tab_group_created",
    "tab_group_renamed",
    "tab_group_color_changed",
    "tab_group_collapsed",
    "tab_group_expanded",
    "tab_group_saved",
    "tab_group_restored",
    "tab_moved_to_group",
    "tab_removed_from_group",
}
BROWSER_PROFILE_ACTIVITY_STIMULUS_TYPES = {
    "browser_profile_switched",
    "browser_profile_created",
    "browser_profile_signed_in",
    "browser_profile_signed_out",
    "browser_sync_enabled",
    "browser_sync_disabled",
    "guest_profile_opened",
    "private_window_opened",
}
BROWSER_EXTENSION_ACTIVITY_STIMULUS_TYPES = {
    "extension_action_clicked",
    "extension_popup_opened",
    "extension_installed",
    "extension_removed",
    "extension_enabled",
    "extension_disabled",
    "extension_permission_requested",
    "extension_error_reported",
}
BROWSER_WEB_APP_ACTIVITY_STIMULUS_TYPES = {
    "web_app_installed",
    "web_app_uninstalled",
    "web_app_opened",
    "web_app_closed",
    "web_app_windowed",
    "web_app_offline_ready",
    "web_app_notification_permission_requested",
    "web_app_badge_changed",
}
BROWSER_VIEW_MODE_ACTIVITY_STIMULUS_TYPES = {
    "reader_mode_enabled",
    "reader_mode_disabled",
    "find_in_page_performed",
    "page_zoom_changed",
    "page_muted",
    "page_unmuted",
    "picture_in_picture_started",
    "picture_in_picture_stopped",
    "page_translation_offered",
    "page_translation_accepted",
}


def collect_browser_window_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "browser_window_activity", BROWSER_WINDOW_ACTIVITY_STIMULUS_TYPES, source="browser", max_events=20)


def collect_browser_tab_group_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "browser_tab_group_activity", BROWSER_TAB_GROUP_ACTIVITY_STIMULUS_TYPES, source="browser", max_events=20)


def collect_browser_profile_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "browser_profile_activity", BROWSER_PROFILE_ACTIVITY_STIMULUS_TYPES, source="browser", max_events=20)


def collect_browser_extension_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "browser_extension_activity", BROWSER_EXTENSION_ACTIVITY_STIMULUS_TYPES, source="browser", max_events=20)


def collect_browser_web_app_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "browser_web_app_activity", BROWSER_WEB_APP_ACTIVITY_STIMULUS_TYPES, source="browser", max_events=20)


def collect_browser_view_mode_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "browser_view_mode_activity", BROWSER_VIEW_MODE_ACTIVITY_STIMULUS_TYPES, source="browser", max_events=20)
