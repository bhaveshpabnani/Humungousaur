from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.collectors.event_log import CollectorEventLog
from humungousaur.connectors import ConnectorRuntime

from ..workspace_connectors import ConnectorEventMapping, ConnectorSourceManifest
from .common import (
    DATA_ANALYTICS_CONSUMER,
    DATA_ANALYTICS_MAX_EVENTS_PER_APP,
    DATA_ANALYTICS_PROVIDER_IDS,
    DataAnalyticsAppCollector,
    aggregate_app_status,
    collector_status_record,
    utc_now,
)


ANALYTICS_EVENT_MAPPINGS: tuple[ConnectorEventMapping, ...] = (
    ConnectorEventMapping("dashboard_opened", "analytics_activity", "dashboard_opened", "Analytics dashboard was opened"),
    ConnectorEventMapping("dashboard_filter_changed", "analytics_activity", "dashboard_filter_changed", "Analytics dashboard filter changed"),
    ConnectorEventMapping("report_exported", "analytics_activity", "report_exported", "Analytics report export completed"),
    ConnectorEventMapping("metric_threshold_crossed", "analytics_activity", "metric_threshold_crossed", "Analytics metric threshold crossed"),
    ConnectorEventMapping("query_result_viewed", "analytics_activity", "query_result_viewed", "Query result metadata was viewed"),
    ConnectorEventMapping("chart_drilled_down", "analytics_activity", "chart_drilled_down", "Analytics chart was drilled down"),
)

DATABASE_EVENT_MAPPINGS: tuple[ConnectorEventMapping, ...] = (
    ConnectorEventMapping("database_connected", "database_activity", "database_connected", "Database connection opened"),
    ConnectorEventMapping("database_disconnected", "database_activity", "database_disconnected", "Database connection closed"),
    ConnectorEventMapping("query_started", "database_activity", "query_started", "Database query started"),
    ConnectorEventMapping("query_completed", "database_activity", "query_completed", "Database query completed"),
    ConnectorEventMapping("query_failed", "database_activity", "query_failed", "Database query failed"),
    ConnectorEventMapping("schema_changed", "database_activity", "schema_changed", "Database schema changed"),
    ConnectorEventMapping("migration_started", "database_activity", "migration_started", "Database migration started"),
    ConnectorEventMapping("migration_failed", "database_activity", "migration_failed", "Database migration failed"),
)


DATA_ANALYTICS_APP_COLLECTORS: tuple[DataAnalyticsAppCollector, ...] = (
    DataAnalyticsAppCollector("bigquery", "bigquery", "database", "BigQuery job, audit-log, table, schema, and query metadata.", "api_poller_or_audit_log", "https://cloud.google.com/bigquery/docs/reference/auditlogs", required_scopes=("https://www.googleapis.com/auth/bigquery.readonly",)),
    DataAnalyticsAppCollector("snowflake", "snowflake", "database", "Snowflake query history, task, alert, schema, and warehouse metadata.", "api_poller_or_event_table", "https://docs.snowflake.com/en/user-guide/event-table", required_scopes=("MONITOR",)),
    DataAnalyticsAppCollector("databricks", "databricks", "database", "Databricks job, query, notebook, warehouse, and Unity Catalog metadata.", "api_poller_or_audit_log", "https://docs.databricks.com/en/admin/account-settings/audit-logs.html"),
    DataAnalyticsAppCollector("postgres", "postgres", "database", "Postgres client/local bridge metadata for connections, queries, migrations, and schema changes.", "local_client_or_log_bridge", "https://www.postgresql.org/docs/current/monitoring-stats.html", implementation_level="local_client_or_log_bridge", webhook_supported=False, requires_connector=False),
    DataAnalyticsAppCollector("supabase", "supabase", "database", "Supabase database, edge function, auth, storage, and SQL editor metadata.", "api_poller_or_webhook", "https://supabase.com/docs/reference/api", required_scopes=("project:read",)),
    DataAnalyticsAppCollector("mysql", "mysql", "database", "MySQL client/local bridge metadata for connections, queries, migrations, and schema changes.", "local_client_or_log_bridge", "https://dev.mysql.com/doc/", implementation_level="local_client_or_log_bridge", webhook_supported=False, requires_connector=False),
    DataAnalyticsAppCollector("mongodb_atlas", "mongodb_atlas", "database", "MongoDB Atlas alert, query, cluster, backup, and schema metadata.", "api_poller_or_alert_webhook", "https://www.mongodb.com/docs/atlas/api/", required_scopes=("Project Read Only",)),
    DataAnalyticsAppCollector("tableau", "tableau", "analytics", "Tableau workbook, datasource, view, refresh, and webhook metadata.", "rest_api_or_webhook", "https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_concepts_webhooks.htm"),
    DataAnalyticsAppCollector("looker", "looker", "analytics", "Looker dashboard, explore, query task, schedule, and alert metadata.", "api_poller_or_webhook", "https://cloud.google.com/looker/docs/api-intro"),
    DataAnalyticsAppCollector("metabase", "metabase", "analytics", "Metabase dashboard, question, subscription, alert, and query metadata.", "api_poller_or_webhook", "https://www.metabase.com/docs/latest/api-documentation"),
    DataAnalyticsAppCollector("power_bi", "power_bi", "analytics", "Power BI activity event, dashboard, report, dataset, and refresh metadata.", "activity_events_api_or_webhook", "https://learn.microsoft.com/en-us/rest/api/power-bi/admin/get-activity-events"),
    DataAnalyticsAppCollector("google_analytics", "google_analytics", "analytics", "Google Analytics property, report, alert, and exploration metadata.", "api_poller", "https://developers.google.com/analytics/devguides/reporting/data/v1"),
    DataAnalyticsAppCollector("mixpanel", "mixpanel", "analytics", "Mixpanel dashboard, report, cohort, funnel, and alert metadata.", "api_poller", "https://developer.mixpanel.com/reference/overview"),
    DataAnalyticsAppCollector("amplitude", "amplitude", "analytics", "Amplitude chart, dashboard, cohort, experiment, and alert metadata.", "api_poller", "https://amplitude.com/docs/apis"),
)


DATA_ANALYTICS_SOURCE_MANIFESTS: tuple[ConnectorSourceManifest, ...] = tuple(
    ConnectorSourceManifest(
        provider_id=collector.provider_id,
        display_name=collector_status_record(collector)["display_name"],
        source_type=collector.source_channel,
        auth_method="oauth2_api_key_or_local_permission",
        collector_mappings=tuple(
            ConnectorEventMapping(
                f"{collector.provider_id}_{mapping.source_event}",
                mapping.collector,
                mapping.stimulus_type,
                f"{collector_status_record(collector)['display_name']} {mapping.text[0].lower()}{mapping.text[1:]}",
            )
            for mapping in (DATABASE_EVENT_MAPPINGS if collector.domain == "database" else ANALYTICS_EVENT_MAPPINGS)
        ),
        poller_supported=collector.poller_supported,
        webhook_supported=collector.webhook_supported,
        requires_connector=collector.requires_connector,
        notes=collector.description,
    )
    for collector in DATA_ANALYTICS_APP_COLLECTORS
)


def data_analytics_app_status_records() -> list[dict[str, Any]]:
    return [collector_status_record(collector) for collector in DATA_ANALYTICS_APP_COLLECTORS]


def run_data_analytics_source_tick(config: AgentConfig, provider_id: str | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    from ..workspace_connectors import record_connector_source_health

    normalized = config.normalized()
    collectors = _collectors(provider_id)
    log = CollectorEventLog(normalized.collector_events_db_path)
    state = log.consumer_state(DATA_ANALYTICS_CONSUMER)
    source_state = state.setdefault("sources", {}).setdefault("data_analytics", {})
    app_states = source_state.setdefault("apps", {})
    runtime = ConnectorRuntime(normalized)
    results = []
    for collector in collectors:
        readiness = {"connection_ready": True, "connected": True} if not collector.requires_connector else runtime.readiness(collector.provider_id)
        app_state = app_states.setdefault(collector.provider_id, {})
        app_state["last_tick_at"] = utc_now()
        app_state["tick_count"] = int(app_state.get("tick_count") or 0) + 1
        result = collector.collect(readiness, app_state, dry_run=dry_run, max_events=DATA_ANALYTICS_MAX_EVENTS_PER_APP)
        if not dry_run:
            record_connector_source_health(
                normalized,
                provider_id=collector.provider_id,
                status=str(result.get("status") or "running"),
                message=str(result.get("message") or ""),
                metadata={"last_tick_at": app_state["last_tick_at"], "source_channel": collector.source_channel},
            )
        results.append(result)
    if not dry_run:
        log.save_consumer_state(DATA_ANALYTICS_CONSUMER, state)
    return {
        "status": "succeeded",
        "sources": results,
        "source_count": len(results),
        "aggregate_status": aggregate_app_status(results),
        "dry_run": dry_run,
        "owner": "humungousaur.collectors.sources.data_analytics",
    }


def _collectors(provider_id: str | None = None) -> tuple[DataAnalyticsAppCollector, ...]:
    provider = str(provider_id or "").strip()
    if not provider:
        return DATA_ANALYTICS_APP_COLLECTORS
    matches = tuple(collector for collector in DATA_ANALYTICS_APP_COLLECTORS if collector.provider_id == provider)
    if not matches:
        raise ValueError(f"unsupported data/analytics provider: {provider_id or '<provider>'}")
    return matches


__all__ = [
    "ANALYTICS_EVENT_MAPPINGS",
    "DATABASE_EVENT_MAPPINGS",
    "DATA_ANALYTICS_APP_COLLECTORS",
    "DATA_ANALYTICS_PROVIDER_IDS",
    "DATA_ANALYTICS_SOURCE_MANIFESTS",
    "data_analytics_app_status_records",
    "run_data_analytics_source_tick",
]
