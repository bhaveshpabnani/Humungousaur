from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile


PACKAGE_MANAGER_ACTIVITY_STIMULUS_TYPES = {
    "dependency_install_started",
    "dependency_install_completed",
    "dependency_install_failed",
    "dependency_update_available",
    "dependency_audit_warning",
    "dependency_conflict_detected",
    "lockfile_changed",
    "environment_setup_failed",
}
BUILD_TOOL_ACTIVITY_STIMULUS_TYPES = {
    "build_task_started",
    "build_task_completed",
    "build_task_failed",
    "compile_warning_detected",
    "compile_error_detected",
    "build_cache_cleared",
    "build_config_changed",
    "artifact_generated",
}
TEST_RUNNER_ACTIVITY_STIMULUS_TYPES = {
    "test_suite_started",
    "test_suite_completed",
    "test_suite_failed",
    "test_case_failed",
    "test_flake_detected",
    "coverage_report_generated",
    "coverage_threshold_failed",
    "snapshot_test_updated",
}
LOCAL_SERVICE_ACTIVITY_STIMULUS_TYPES = {
    "dev_server_started",
    "dev_server_stopped",
    "dev_server_crashed",
    "port_conflict_detected",
    "service_health_changed",
    "local_endpoint_opened",
    "log_error_seen",
    "hot_reload_failed",
}
DEBUGGER_ACTIVITY_STIMULUS_TYPES = {
    "debugger_attached",
    "debugger_detached",
    "debugger_paused",
    "debugger_resumed",
    "breakpoint_added",
    "breakpoint_removed",
    "exception_breakpoint_hit",
    "watch_expression_failed",
}
CODE_HOSTING_ACTIVITY_STIMULUS_TYPES = {
    "pr_opened",
    "pr_updated",
    "review_requested",
    "review_submitted",
    "review_approved",
    "review_changes_requested",
    "pr_merged",
    "merge_ready",
    "branch_created",
    "branch_deleted",
    "commit_pushed",
    "ci_started",
    "ci_passed",
    "ci_failed",
    "ci_canceled",
    "comment_received",
}


def collect_package_manager_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "package_manager_activity", PACKAGE_MANAGER_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_build_tool_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "build_tool_activity", BUILD_TOOL_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_test_runner_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "test_runner_activity", TEST_RUNNER_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_local_service_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "local_service_activity", LOCAL_SERVICE_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_debugger_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "debugger_activity", DEBUGGER_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_code_hosting_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "code_hosting_activity", CODE_HOSTING_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)
