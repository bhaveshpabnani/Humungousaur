from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile
from ..sources.google_workspace import read_google_workspace_events


MAIL_COMPOSITION_ACTIVITY_STIMULUS_TYPES = {
    "email_draft_started",
    "email_draft_updated",
    "email_reply_started",
    "email_forward_started",
    "email_sent",
    "email_send_scheduled",
    "email_send_cancelled",
    "email_attachment_added",
    "email_attachment_removed",
}
MAIL_ORGANIZATION_ACTIVITY_STIMULUS_TYPES = {
    "email_archived",
    "email_deleted",
    "email_moved",
    "email_labeled",
    "email_flagged",
    "email_unread_marked",
    "email_search_performed",
    "mailbox_filter_changed",
    "mail_rule_applied",
}
CALENDAR_SCHEDULING_ACTIVITY_STIMULUS_TYPES = {
    "calendar_event_created",
    "calendar_event_updated",
    "calendar_event_deleted",
    "calendar_event_rescheduled",
    "calendar_invite_received",
    "calendar_invite_accepted",
    "calendar_invite_declined",
    "calendar_invite_tentative",
    "calendar_availability_checked",
}
REMINDER_TODO_ACTIVITY_STIMULUS_TYPES = {
    "reminder_created",
    "reminder_updated",
    "reminder_completed",
    "reminder_snoozed",
    "reminder_deleted",
    "todo_created",
    "todo_completed",
    "todo_due_date_changed",
    "todo_list_changed",
}


def collect_mail_composition_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "mail_composition_activity", MAIL_COMPOSITION_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "mail_composition_activity", MAIL_COMPOSITION_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_mail_organization_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "mail_organization_activity", MAIL_ORGANIZATION_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "mail_organization_activity", MAIL_ORGANIZATION_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_calendar_scheduling_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "calendar_scheduling_activity", CALENDAR_SCHEDULING_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "calendar_scheduling_activity", CALENDAR_SCHEDULING_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20
    )


def collect_reminder_todo_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "reminder_todo_activity", REMINDER_TODO_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)
