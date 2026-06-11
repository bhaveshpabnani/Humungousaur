from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile


SOFTWARE_ACTIVITY_STIMULUS_TYPES = {
    "installer_started",
    "installer_failed",
    "app_installed",
    "app_uninstalled",
    "app_updated",
    "package_installed",
    "extension_installed",
}
PRINT_SCAN_ACTIVITY_STIMULUS_TYPES = {
    "print_job_started",
    "print_job_completed",
    "print_job_failed",
    "scan_started",
    "scan_completed",
    "printer_selected",
}
SEARCH_ACTIVITY_STIMULUS_TYPES = {
    "spotlight_opened",
    "launcher_query_submitted",
    "system_search_performed",
    "app_launched_from_search",
    "file_opened_from_search",
}
PERIPHERAL_ACTIVITY_STIMULUS_TYPES = {
    "external_display_connected",
    "external_display_disconnected",
    "usb_device_connected",
    "usb_device_disconnected",
    "bluetooth_device_connected",
    "bluetooth_device_disconnected",
    "storage_device_mounted",
    "storage_device_ejected",
}
MEDIA_ACTIVITY_STIMULUS_TYPES = {
    "media_playback_started",
    "media_playback_paused",
    "media_playback_stopped",
    "media_track_changed",
    "screen_recording_started",
    "screen_recording_stopped",
}
FOCUS_TASK_ACTIVITY_STIMULUS_TYPES = {
    "focus_mode_enabled",
    "focus_mode_disabled",
    "task_started",
    "task_completed",
    "workspace_switched",
    "desktop_space_changed",
    "mode_changed",
}


def collect_software_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "software_activity", SOFTWARE_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)


def collect_print_scan_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "print_scan_activity", PRINT_SCAN_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)


def collect_search_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "search_activity", SEARCH_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_peripheral_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "peripheral_activity", PERIPHERAL_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)


def collect_media_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "media_activity", MEDIA_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_focus_task_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "focus_task_activity", FOCUS_TASK_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)
