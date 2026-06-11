from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile
from ..sources.business_operations import read_business_operations_events


CRM_ACTIVITY_STIMULUS_TYPES = {
    "record_opened",
    "record_updated",
    "lead_created",
    "deal_stage_changed",
    "customer_note_added",
    "followup_scheduled",
}
SUPPORT_DESK_ACTIVITY_STIMULUS_TYPES = {
    "ticket_opened",
    "ticket_assigned",
    "ticket_updated",
    "ticket_replied",
    "ticket_resolved",
    "ticket_escalated",
    "sla_breach_warning",
}
ANALYTICS_ACTIVITY_STIMULUS_TYPES = {
    "dashboard_opened",
    "dashboard_filter_changed",
    "report_exported",
    "metric_threshold_crossed",
    "query_result_viewed",
    "chart_drilled_down",
}
DATABASE_ACTIVITY_STIMULUS_TYPES = {
    "database_connected",
    "database_disconnected",
    "query_started",
    "query_completed",
    "query_failed",
    "schema_changed",
    "migration_started",
    "migration_failed",
}
CLOUD_CONSOLE_ACTIVITY_STIMULUS_TYPES = {
    "cloud_resource_opened",
    "cloud_resource_changed",
    "deployment_started",
    "deployment_failed",
    "secret_view_attempted",
    "billing_alert_seen",
    "permission_error_seen",
}
INCIDENT_ACTIVITY_STIMULUS_TYPES = {
    "incident_declared",
    "incident_acknowledged",
    "incident_escalated",
    "incident_resolved",
    "on_call_alert_received",
    "runbook_opened",
    "status_page_updated",
}


def collect_crm_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_business_operations_events(config, state, "crm_activity", CRM_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "crm_activity", CRM_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_support_desk_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_business_operations_events(config, state, "support_desk_activity", SUPPORT_DESK_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "support_desk_activity", SUPPORT_DESK_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_analytics_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_business_operations_events(config, state, "analytics_activity", ANALYTICS_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "analytics_activity", ANALYTICS_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_database_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "database_activity", DATABASE_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_cloud_console_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "cloud_console_activity", CLOUD_CONSOLE_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_incident_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "incident_activity", INCIDENT_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)
