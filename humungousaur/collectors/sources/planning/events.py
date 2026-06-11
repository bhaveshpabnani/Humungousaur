from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.collectors.event_log import CollectorEventLog

from ...models import CollectorEvent
from ..workspace_connectors import (
    append_connector_source_event,
    connector_source_status,
    record_connector_source_health,
)
from .common import PLANNING_PROVIDER_DISPLAY_NAMES, PLANNING_PROVIDER_IDS
from .registry import planning_app_status_records


_PROVIDER_ALIASES = {
    "linear": "linear",
    "jira": "jira",
    "atlassian_jira": "jira",
    "asana": "asana",
    "trello": "trello",
    "clickup": "clickup",
    "click_up": "clickup",
    "monday": "monday",
    "monday_com": "monday",
    "mondaydotcom": "monday",
    "todoist": "todoist",
}


_EVENT_ALIASES = {
    ("linear", "issue_created"): "linear_issue_created",
    ("linear", "issue_updated"): "linear_issue_status_changed",
    ("linear", "issue_assigned"): "linear_issue_assigned",
    ("linear", "issue_status_changed"): "linear_issue_status_changed",
    ("linear", "issue_moved"): "linear_issue_moved",
    ("linear", "comment_created"): "linear_issue_comment_received",
    ("linear", "issue_comment_received"): "linear_issue_comment_received",
    ("linear", "issue_completed"): "linear_issue_status_changed",
    ("linear", "issue_priority_changed"): "linear_issue_priority_changed",
    ("linear", "issue_due_date_changed"): "linear_issue_due_date_changed",
    ("linear", "cycle_started"): "linear_sprint_started",
    ("linear", "cycle_changed"): "linear_sprint_changed",
    ("linear", "project_opened"): "linear_project_opened",
    ("linear", "project_changed"): "linear_project_changed",
    ("jira", "jira:issue_created"): "jira_issue_created",
    ("jira", "jira:issue_updated"): "jira_issue_status_changed",
    ("jira", "issue_created"): "jira_issue_created",
    ("jira", "issue_updated"): "jira_issue_status_changed",
    ("jira", "issue_assigned"): "jira_issue_assigned",
    ("jira", "issue_status_changed"): "jira_issue_status_changed",
    ("jira", "issue_moved"): "jira_issue_moved",
    ("jira", "comment_created"): "jira_issue_comment_received",
    ("jira", "issue_comment_received"): "jira_issue_comment_received",
    ("jira", "issue_priority_changed"): "jira_issue_priority_changed",
    ("jira", "issue_due_date_changed"): "jira_issue_due_date_changed",
    ("jira", "sprint_started"): "jira_sprint_started",
    ("jira", "sprint_changed"): "jira_sprint_changed",
    ("jira", "project_opened"): "jira_project_opened",
    ("jira", "project_changed"): "jira_project_changed",
    ("asana", "task_created"): "asana_task_created",
    ("asana", "task_updated"): "asana_task_updated",
    ("asana", "task_assigned"): "asana_task_assigned",
    ("asana", "task_completed"): "asana_task_completed",
    ("asana", "task_uncompleted"): "asana_task_reopened",
    ("asana", "task_reopened"): "asana_task_reopened",
    ("asana", "task_moved"): "asana_task_moved",
    ("asana", "story_added"): "asana_task_comment_added",
    ("asana", "comment_added"): "asana_task_comment_added",
    ("asana", "task_comment_added"): "asana_task_comment_added",
    ("asana", "task_priority_changed"): "asana_task_priority_changed",
    ("asana", "task_due_date_changed"): "asana_task_due_date_changed",
    ("asana", "project_opened"): "asana_project_opened",
    ("asana", "project_changed"): "asana_project_changed",
    ("trello", "create_card"): "trello_task_created",
    ("trello", "createcard"): "trello_task_created",
    ("trello", "update_card"): "trello_task_updated",
    ("trello", "updatecard"): "trello_task_updated",
    ("trello", "add_member_to_card"): "trello_task_assigned",
    ("trello", "addmembertocard"): "trello_task_assigned",
    ("trello", "move_card_to_board"): "trello_task_moved",
    ("trello", "movecardtoboard"): "trello_task_moved",
    ("trello", "move_card_from_board"): "trello_task_moved",
    ("trello", "movecardfromboard"): "trello_task_moved",
    ("trello", "comment_card"): "trello_task_comment_added",
    ("trello", "commentcard"): "trello_task_comment_added",
    ("trello", "complete_card"): "trello_task_completed",
    ("trello", "task_created"): "trello_task_created",
    ("trello", "task_updated"): "trello_task_updated",
    ("trello", "task_completed"): "trello_task_completed",
    ("trello", "task_assigned"): "trello_task_assigned",
    ("trello", "task_moved"): "trello_task_moved",
    ("trello", "task_comment_added"): "trello_task_comment_added",
    ("trello", "task_due_date_changed"): "trello_task_due_date_changed",
    ("trello", "task_priority_changed"): "trello_task_priority_changed",
    ("trello", "project_opened"): "trello_project_opened",
    ("trello", "board_opened"): "trello_project_opened",
    ("trello", "project_changed"): "trello_project_changed",
    ("clickup", "taskcreated"): "clickup_task_created",
    ("clickup", "taskupdated"): "clickup_task_updated",
    ("clickup", "taskdeleted"): "clickup_task_updated",
    ("clickup", "taskpriorityupdated"): "clickup_task_priority_changed",
    ("clickup", "taskstatusupdated"): "clickup_task_moved",
    ("clickup", "taskassigneeupdated"): "clickup_task_assigned",
    ("clickup", "taskduedateupdated"): "clickup_task_due_date_changed",
    ("clickup", "taskdue_dateupdated"): "clickup_task_due_date_changed",
    ("clickup", "taskcommentposted"): "clickup_task_comment_added",
    ("clickup", "task_created"): "clickup_task_created",
    ("clickup", "task_updated"): "clickup_task_updated",
    ("clickup", "task_completed"): "clickup_task_completed",
    ("clickup", "task_assigned"): "clickup_task_assigned",
    ("clickup", "task_moved"): "clickup_task_moved",
    ("clickup", "task_comment_added"): "clickup_task_comment_added",
    ("clickup", "task_priority_changed"): "clickup_task_priority_changed",
    ("clickup", "task_due_date_changed"): "clickup_task_due_date_changed",
    ("clickup", "sprint_started"): "clickup_sprint_started",
    ("clickup", "sprint_changed"): "clickup_sprint_changed",
    ("clickup", "project_opened"): "clickup_project_opened",
    ("clickup", "project_changed"): "clickup_project_changed",
    ("monday", "create_item"): "monday_task_created",
    ("monday", "change_status_column_value"): "monday_task_moved",
    ("monday", "change_column_value"): "monday_task_updated",
    ("monday", "change_priority_column_value"): "monday_task_priority_changed",
    ("monday", "change_date_column_value"): "monday_task_due_date_changed",
    ("monday", "create_update"): "monday_task_comment_added",
    ("monday", "task_created"): "monday_task_created",
    ("monday", "task_updated"): "monday_task_updated",
    ("monday", "task_completed"): "monday_task_completed",
    ("monday", "task_assigned"): "monday_task_assigned",
    ("monday", "task_moved"): "monday_task_moved",
    ("monday", "task_comment_added"): "monday_task_comment_added",
    ("monday", "task_priority_changed"): "monday_task_priority_changed",
    ("monday", "task_due_date_changed"): "monday_task_due_date_changed",
    ("monday", "project_opened"): "monday_project_opened",
    ("monday", "board_opened"): "monday_project_opened",
    ("monday", "project_changed"): "monday_project_changed",
    ("todoist", "item:added"): "todoist_task_created",
    ("todoist", "item:updated"): "todoist_task_updated",
    ("todoist", "item:completed"): "todoist_task_completed",
    ("todoist", "item:uncompleted"): "todoist_task_reopened",
    ("todoist", "item:moved"): "todoist_task_moved",
    ("todoist", "note:added"): "todoist_task_comment_added",
    ("todoist", "task_created"): "todoist_task_created",
    ("todoist", "task_updated"): "todoist_task_updated",
    ("todoist", "task_completed"): "todoist_task_completed",
    ("todoist", "task_reopened"): "todoist_task_reopened",
    ("todoist", "task_assigned"): "todoist_task_assigned",
    ("todoist", "task_moved"): "todoist_task_moved",
    ("todoist", "task_comment_added"): "todoist_task_comment_added",
    ("todoist", "task_priority_changed"): "todoist_task_priority_changed",
    ("todoist", "task_due_date_changed"): "todoist_task_due_date_changed",
    ("todoist", "project_opened"): "todoist_project_opened",
    ("todoist", "project_changed"): "todoist_project_changed",
}


def append_planning_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        provider_id = _provider_id(payload)
        source_event = _source_event(provider_id, payload)
        return append_connector_source_event(
            config,
            provider_id=provider_id,
            source_event=source_event,
            object_type=str(payload.get("object_type") or _object_type_for_source_event(source_event)),
            object_id=str(_first(payload, "object_id", "task_id", "issue_id", "item_id", "card_id", "project_id", "sprint_id")),
            metadata=_metadata_from_payload(payload, provider_id, source_event),
            payload=payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
            occurred_at=str(payload.get("occurred_at") or payload.get("timestamp") or payload.get("created_at") or payload.get("updated_at") or ""),
        )
    except (KeyError, ValueError) as exc:
        _append_dead_letter(config, payload, str(exc))
        raise ValueError(str(exc)) from exc


def append_planning_health(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        provider_id = _provider_id(payload)
        collector = str(payload.get("collector") or "").strip()
        if collector:
            status = str(payload.get("status") or "running").strip()
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            CollectorEventLog(config.normalized().collector_events_db_path).record_helper_health(
                helper_id=f"connector-source-{provider_id}-{collector}",
                collector=collector,
                platform=platform.system(),
                status=status,
                version="0.1",
                permission_state=str(payload.get("permission_state") or status),
                message=str(payload.get("message") or ""),
                metadata={
                    "provider_id": provider_id,
                    "display_name": PLANNING_PROVIDER_DISPLAY_NAMES[provider_id],
                    **_safe_legacy_health_metadata(metadata),
                },
            )
            return {"accepted": True, "provider_id": provider_id, "status": status, "collector_count": 1}
        return record_connector_source_health(
            config,
            provider_id=provider_id,
            status=str(payload.get("status") or "running"),
            message=str(payload.get("message") or ""),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
    except (KeyError, ValueError) as exc:
        _append_dead_letter(config, payload, str(exc))
        raise ValueError(str(exc)) from exc


def planning_source_status(config: AgentConfig, provider_id: str | None = None) -> dict[str, Any]:
    provider_ids = [_normalize_provider(provider_id)] if provider_id else list(PLANNING_PROVIDER_IDS)
    sources = [_planning_source_record(config, item) for item in provider_ids if item]
    return {
        "sources": sources,
        "source_count": len(sources),
        "owner": "humungousaur.collectors.sources.planning",
    }


def planning_source_status_map(config: AgentConfig) -> dict[str, dict[str, Any]]:
    return {source["source"]: source for source in planning_source_status(config)["sources"]}


def read_planning_events(
    config: AgentConfig,
    state: dict[str, Any],
    collector: str,
    allowed_stimulus_types: set[str],
    *,
    max_events: int = 20,
) -> list[CollectorEvent]:
    del config, state, collector, allowed_stimulus_types, max_events
    return []


def _planning_source_record(config: AgentConfig, provider_id: str) -> dict[str, Any]:
    status = connector_source_status(config, provider_id=provider_id)
    source = status["sources"][0] if status.get("sources") else {}
    health = source.get("helper_health", []) if isinstance(source, dict) else []
    pending_event_count = sum(
        1
        for event in CollectorEventLog(config.normalized().collector_events_db_path).query(limit=1000)
        if event.get("source") == provider_id
    )
    return {
        **source,
        "source": provider_id,
        "status": _health_status(health),
        "pending_event_count": pending_event_count,
        "dead_letter_count": _line_count(_dead_letters_path(config.normalized(), provider_id)),
        "dead_letters_path": str(_dead_letters_path(config.normalized(), provider_id)),
        "app_collectors": [item for item in planning_app_status_records() if item.get("provider_id") == provider_id],
        "supported_apps": [provider_id],
        "mapping_count": len(source.get("collector_mappings", ())) if isinstance(source, dict) else 0,
        "privacy_contract": {
            "default_privacy_tier": "sensitive_metadata",
            "raw_content_included": False,
            "provider_content_redacted": True,
        },
    }


def _source_event(provider_id: str, payload: dict[str, Any]) -> str:
    explicit = str(payload.get("source_event") or "").strip()
    if explicit:
        return explicit
    event_type = _clean_token(_first(payload, "event_type", "event_name", "event", "action", "native_event_type", "webhook_event", "type"))
    source_event = _EVENT_ALIASES.get((provider_id, event_type))
    if not source_event:
        raise ValueError(f"unsupported planning event mapping: {provider_id}:{event_type or '<event_type>'}")
    return source_event


def _provider_id(payload: dict[str, Any]) -> str:
    provider = _normalize_provider(_first(payload, "provider_id", "provider", "app", "service", "application"))
    if not provider:
        raise ValueError("planning event missing provider_id")
    return provider


def _normalize_provider(value: Any) -> str:
    token = _clean_token(value)
    provider = _PROVIDER_ALIASES.get(token, token)
    if provider not in PLANNING_PROVIDER_IDS:
        raise ValueError(f"unsupported planning provider: {value or '<provider>'}")
    return provider


def _metadata_from_payload(payload: dict[str, Any], provider_id: str, source_event: str) -> dict[str, Any]:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    clean = dict(metadata)
    clean["source_event"] = source_event
    clean["app"] = provider_id
    event_type = _clean_token(_first(payload, "event_type", "event_name", "event", "action", "native_event_type", "webhook_event", "type"))
    if event_type:
        clean["provider_event_type"] = event_type
    for key in (
        "board_id",
        "card_id",
        "cycle_id",
        "due_at",
        "has_due_date",
        "issue_id",
        "item_id",
        "list_id",
        "object_type",
        "priority_bucket",
        "project_id",
        "provider_event_id",
        "space_id",
        "sprint_id",
        "status_bucket",
        "task_id",
        "team_id",
        "workspace_id",
    ):
        if key in payload:
            clean[key] = payload[key]
    for redacted in (
        "title",
        "name",
        "summary",
        "description",
        "body",
        "text",
        "comment",
        "comment_body",
        "url",
        "path",
        "assignee",
        "assignee_name",
        "assignee_email",
        "creator",
        "reporter",
        "participants",
        "labels",
    ):
        if redacted in payload:
            clean[f"{redacted}_redacted"] = True
    return clean


def _object_type_for_source_event(source_event: str) -> str:
    if "project" in source_event:
        return "project"
    if "sprint" in source_event:
        return "sprint"
    if "_issue_" in source_event or source_event.endswith("_issue_created"):
        return "issue"
    return "task"


def _safe_legacy_health_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    from ..workspace_connectors import safe_metadata_values

    return safe_metadata_values(metadata)


def _append_dead_letter(config: AgentConfig, payload: dict[str, Any], reason: str) -> None:
    provider_id = "planning"
    try:
        provider_id = _provider_id(payload)
    except ValueError:
        pass
    path = _dead_letters_path(config.normalized(), provider_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "reason": str(reason)[:500],
        "payload_keys": sorted(str(key) for key in payload.keys()) if isinstance(payload, dict) else [],
        "source": provider_id,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _dead_letters_path(config: AgentConfig, provider_id: str) -> Path:
    return config.normalized().data_dir / "collector_sources" / provider_id / "dead_letters.jsonl"


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except OSError:
        return 0


def _health_status(health: Any) -> str:
    if not isinstance(health, list) or not health:
        return "not_configured"
    return str(health[0].get("status") or "unknown")


def _first(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return ""


def _clean_token(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_").replace(".", "_")
    return "".join(char for char in text if char.isalnum() or char in {"_", ":"})


__all__ = [
    "append_planning_event",
    "append_planning_health",
    "planning_source_status",
    "planning_source_status_map",
    "read_planning_events",
]
