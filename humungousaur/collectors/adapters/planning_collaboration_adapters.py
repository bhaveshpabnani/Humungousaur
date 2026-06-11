from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile
from ..sources.google_workspace import read_google_workspace_events
from ..sources.planning import read_planning_events


TASK_MANAGER_ACTIVITY_STIMULUS_TYPES = {
    "task_created",
    "task_updated",
    "task_completed",
    "task_reopened",
    "task_assigned",
    "task_moved",
    "task_priority_changed",
    "task_due_date_changed",
    "task_comment_added",
    "project_opened",
    "project_changed",
}
ISSUE_TRACKER_ACTIVITY_STIMULUS_TYPES = {
    "issue_created",
    "issue_assigned",
    "issue_status_changed",
    "issue_comment_received",
    "issue_blocker_added",
    "issue_moved",
    "issue_priority_changed",
    "issue_due_date_changed",
    "sprint_started",
    "sprint_changed",
    "project_opened",
    "project_changed",
}
KNOWLEDGE_BASE_ACTIVITY_STIMULUS_TYPES = {
    "page_opened",
    "page_created",
    "page_edited",
    "database_changed",
    "table_changed",
    "page_commented",
    "page_shared",
    "link_created",
    "backlink_created",
    "vault_opened",
    "workspace_opened",
    "wiki_search_performed",
    "doc_link_copied",
}
WHITEBOARD_ACTIVITY_STIMULUS_TYPES = {
    "board_opened",
    "board_edited",
    "sticky_created",
    "diagram_exported",
    "collaborator_joined",
    "whiteboard_comment_added",
}
FORM_SURVEY_ACTIVITY_STIMULUS_TYPES = {
    "form_opened",
    "form_draft_saved",
    "form_submitted",
    "form_validation_error",
    "survey_response_received",
    "approval_form_submitted",
}
LEARNING_ACTIVITY_STIMULUS_TYPES = {
    "lesson_started",
    "lesson_completed",
    "quiz_started",
    "quiz_submitted",
    "course_progress_changed",
    "certificate_earned",
}


def collect_task_manager_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return (
        read_google_workspace_events(config, state, "task_manager_activity", TASK_MANAGER_ACTIVITY_STIMULUS_TYPES)
        + read_planning_events(config, state, "task_manager_activity", TASK_MANAGER_ACTIVITY_STIMULUS_TYPES)
        + read_bridge_events(config, state, "task_manager_activity", TASK_MANAGER_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)
    )


def collect_issue_tracker_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_planning_events(config, state, "issue_tracker_activity", ISSUE_TRACKER_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "issue_tracker_activity", ISSUE_TRACKER_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_knowledge_base_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    from ..sources.knowledge_base import read_knowledge_base_events

    return read_knowledge_base_events(config, state, "knowledge_base_activity", KNOWLEDGE_BASE_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "knowledge_base_activity", KNOWLEDGE_BASE_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_whiteboard_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "whiteboard_activity", WHITEBOARD_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_form_survey_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "form_survey_activity", FORM_SURVEY_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_learning_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "learning_activity", LEARNING_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)
