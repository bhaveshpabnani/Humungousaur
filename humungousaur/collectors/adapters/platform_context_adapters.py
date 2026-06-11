from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile


PERMISSION_ACTIVITY_STIMULUS_TYPES = {
    "permission_requested",
    "permission_granted",
    "permission_denied",
    "permission_revoked",
    "privacy_indicator_enabled",
    "privacy_indicator_disabled",
}
LOCATION_ACTIVITY_STIMULUS_TYPES = {
    "location_requested",
    "location_access_started",
    "location_access_stopped",
    "region_changed",
    "timezone_changed",
}
RESOURCE_ACTIVITY_STIMULUS_TYPES = {
    "cpu_pressure_high",
    "memory_pressure_high",
    "thermal_pressure_high",
    "process_hung",
    "process_high_cpu",
    "disk_io_pressure_high",
}
STORAGE_ACTIVITY_STIMULUS_TYPES = {
    "disk_space_low",
    "volume_space_low",
    "trash_emptied",
    "cache_cleanup_started",
    "cache_cleanup_completed",
    "backup_started",
    "backup_completed",
    "backup_failed",
}
WELLBEING_ACTIVITY_STIMULUS_TYPES = {
    "break_reminder_fired",
    "screen_time_limit_reached",
    "app_limit_reached",
    "wellbeing_nudge_shown",
    "wellbeing_nudge_dismissed",
}
POLICY_ACTIVITY_STIMULUS_TYPES = {
    "device_compliance_warning",
    "managed_profile_changed",
    "policy_blocked_action",
    "dlp_warning_shown",
    "certificate_warning_shown",
    "update_required",
}


def collect_permission_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "permission_activity", PERMISSION_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)


def collect_location_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "location_activity", LOCATION_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)


def collect_resource_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "resource_activity", RESOURCE_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)


def collect_storage_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "storage_activity", STORAGE_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)


def collect_wellbeing_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "wellbeing_activity", WELLBEING_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)


def collect_policy_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "policy_activity", POLICY_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)
