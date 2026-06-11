from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..workspace_connectors import append_connector_source_event


_APP_ALIASES = {
    "visual_studio_code": "vscode",
    "vs_code": "vscode",
    "vscode": "vscode",
    "cursor": "vscode",
    "jetbrains": "jetbrains",
    "intellij": "jetbrains",
    "idea": "jetbrains",
    "pycharm": "jetbrains",
    "webstorm": "jetbrains",
    "xcode": "xcode",
    "terminal": "terminal",
    "shell": "terminal",
    "iterm": "terminal",
    "iterm2": "terminal",
    "git": "git",
    "github": "github",
    "gitlab": "gitlab",
    "bitbucket": "bitbucket",
    "azure_devops": "azure_devops",
    "azuredevops": "azure_devops",
    "ado": "azure_devops",
}

_EVENT_ALIASES = {
    "active_file": "active_file_changed",
    "active_file_changed": "active_file_changed",
    "save": "file_saved",
    "saved": "file_saved",
    "file_saved": "file_saved",
    "diagnostic": "diagnostic_added",
    "diagnostic_added": "diagnostic_added",
    "diagnostic_resolved": "diagnostic_resolved",
    "test_started": "test_suite_started",
    "test_finished": "test_suite_completed",
    "test_failed": "test_suite_failed",
    "debug_started": "debug_session_started",
    "debug_session_started": "debug_session_started",
    "debugger_attached": "debugger_attached",
    "debugger_detached": "debugger_detached",
    "command_started": "terminal_command_started",
    "command_finished": "terminal_command_finished",
    "command_failed": "terminal_command_failed",
    "branch_changed": "git_branch_changed",
    "commit": "commit_created",
    "commit_created": "commit_created",
    "push": "commit_pushed",
    "commit_pushed": "commit_pushed",
    "pipeline_failed": "pipeline_failed",
    "pipeline_succeeded": "pipeline_succeeded",
    "pipeline_canceled": "pipeline_canceled",
    "ci_failed": "ci_failed",
    "ci_passed": "ci_passed",
    "ci_canceled": "ci_canceled",
    "pull_request_opened": "pull_request_opened",
    "pull_request_updated": "pull_request_updated",
    "pull_request_merged": "pull_request_merged",
    "merge_request_opened": "merge_request_opened",
    "merge_request_updated": "merge_request_updated",
    "merge_request_merged": "merge_request_merged",
    "review_requested": "review_requested",
    "review_approved": "review_approved",
    "review_changes_requested": "review_changes_requested",
    "comment_received": "comment_received",
    "issue_created": "issue_created",
    "issue_assigned": "issue_assigned",
    "issue_status_changed": "issue_status_changed",
    "issue_comment_received": "issue_comment_received",
}


def append_developer_source_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    provider_id, source_event = normalize_developer_source_event(payload)
    return append_connector_source_event(
        config,
        provider_id=provider_id,
        source_event=source_event,
        object_type=str(payload.get("object_type") or payload.get("resource_type") or ""),
        object_id=str(payload.get("object_id") or payload.get("resource_id") or payload.get("id") or ""),
        metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else payload,
        payload=payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
        occurred_at=str(payload.get("occurred_at") or payload.get("timestamp") or ""),
    )


def normalize_developer_source_event(payload: dict[str, Any]) -> tuple[str, str]:
    explicit_provider = str(payload.get("provider_id") or payload.get("provider") or "").strip()
    provider_id = _APP_ALIASES.get(_clean_token(explicit_provider), _clean_token(explicit_provider))
    if not provider_id:
        provider_id = _APP_ALIASES.get(_clean_token(payload.get("app") or payload.get("service") or payload.get("application")), "")
    if not provider_id:
        raise ValueError("developer source event is missing provider_id/app")

    explicit_event = str(payload.get("source_event") or "").strip()
    if explicit_event:
        source_event = explicit_event
    else:
        source_event = _EVENT_ALIASES.get(_clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type")), "")
    if not source_event:
        raise ValueError(f"unsupported developer source event for {provider_id}")
    return provider_id, source_event


def _clean_token(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return "".join(char for char in text if char.isalnum() or char == "_")
