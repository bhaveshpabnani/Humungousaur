from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile
from ..sources.google_workspace import read_google_workspace_events


CLOUD_SYNC_ACTIVITY_STIMULUS_TYPES = {
    "sync_started",
    "sync_completed",
    "sync_failed",
    "sync_conflict_detected",
    "remote_file_changed",
    "cloud_file_created",
    "cloud_folder_created",
    "cloud_file_renamed",
    "cloud_folder_renamed",
    "cloud_file_moved",
    "cloud_folder_moved",
    "cloud_file_deleted",
    "cloud_folder_deleted",
    "cloud_file_shared",
    "cloud_permission_changed",
    "cloud_file_restored",
    "cloud_file_version_event",
    "cloud_quota_warning",
}
AUTH_ACTIVITY_STIMULUS_TYPES = {
    "login_prompt_shown",
    "oauth_flow_started",
    "oauth_flow_completed",
    "oauth_flow_failed",
    "mfa_prompt_shown",
    "sign_in_failed",
    "account_switched",
}
NETWORK_ACTIVITY_STIMULUS_TYPES = {
    "offline_mode_detected",
    "captive_portal_detected",
    "dns_error",
    "api_request_failed",
    "api_rate_limited",
    "bandwidth_spike",
    "proxy_changed",
}
AUTOMATION_ACTIVITY_STIMULUS_TYPES = {
    "shortcut_triggered",
    "workflow_started",
    "workflow_completed",
    "workflow_failed",
    "automation_prompt_shown",
    "scheduled_job_started",
    "scheduled_job_failed",
}
VIRTUAL_RUNTIME_ACTIVITY_STIMULUS_TYPES = {
    "container_started",
    "container_stopped",
    "container_failed",
    "image_build_started",
    "image_build_failed",
    "vm_started",
    "vm_stopped",
    "emulator_started",
    "emulator_failed",
}
REMOTE_SESSION_ACTIVITY_STIMULUS_TYPES = {
    "remote_session_started",
    "remote_session_ended",
    "screen_share_started",
    "screen_share_stopped",
    "remote_control_requested",
    "remote_control_granted",
    "remote_control_revoked",
}


def collect_cloud_sync_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "cloud_sync_activity", CLOUD_SYNC_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "cloud_sync_activity", CLOUD_SYNC_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_auth_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "auth_activity", AUTH_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)


def collect_network_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "network_activity", NETWORK_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)


def collect_automation_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "automation_activity", AUTOMATION_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_virtual_runtime_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "virtual_runtime_activity", VIRTUAL_RUNTIME_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_remote_session_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "remote_session_activity", REMOTE_SESSION_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)
