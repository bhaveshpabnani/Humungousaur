from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile


DOCK_TASKBAR_ACTIVITY_STIMULUS_TYPES = {
    "dock_item_clicked",
    "taskbar_item_clicked",
    "dock_item_pinned",
    "dock_item_unpinned",
    "taskbar_item_pinned",
    "taskbar_item_unpinned",
    "dock_badge_changed",
    "taskbar_badge_changed",
    "jump_list_opened",
}
MENU_BAR_TRAY_ACTIVITY_STIMULUS_TYPES = {
    "menu_bar_item_clicked",
    "system_tray_item_clicked",
    "status_item_opened",
    "tray_menu_opened",
    "tray_notification_clicked",
    "background_app_menu_opened",
    "status_indicator_changed",
}
QUICK_SETTINGS_ACTIVITY_STIMULUS_TYPES = {
    "control_center_opened",
    "quick_settings_opened",
    "wifi_toggle_changed",
    "bluetooth_toggle_changed",
    "do_not_disturb_changed",
    "brightness_changed",
    "volume_changed",
    "screen_mirroring_changed",
}
WIDGET_ACTIVITY_STIMULUS_TYPES = {
    "widget_panel_opened",
    "widget_clicked",
    "widget_added",
    "widget_removed",
    "widget_refreshed",
    "widget_alert_seen",
}


def collect_dock_taskbar_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "dock_taskbar_activity", DOCK_TASKBAR_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)


def collect_menu_bar_tray_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "menu_bar_tray_activity", MENU_BAR_TRAY_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)


def collect_quick_settings_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "quick_settings_activity", QUICK_SETTINGS_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)


def collect_widget_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "widget_activity", WIDGET_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)
