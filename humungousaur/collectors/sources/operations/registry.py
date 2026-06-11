from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.collectors.event_log import CollectorEventLog
from humungousaur.connectors import ConnectorRuntime

from ..workspace_connectors import ConnectorEventMapping, ConnectorSourceManifest
from .common import (
    OPERATIONS_CONSUMER,
    OPERATIONS_MAX_EVENTS_PER_APP,
    OPERATIONS_PROVIDER_IDS,
    OperationsAppCollector,
    aggregate_app_status,
    collector_status_record,
    utc_now,
)


INCIDENT_EVENT_MAPPINGS: tuple[ConnectorEventMapping, ...] = (
    ConnectorEventMapping("incident_declared", "incident_activity", "incident_declared", "Incident was declared"),
    ConnectorEventMapping("incident_acknowledged", "incident_activity", "incident_acknowledged", "Incident was acknowledged"),
    ConnectorEventMapping("incident_escalated", "incident_activity", "incident_escalated", "Incident was escalated"),
    ConnectorEventMapping("incident_resolved", "incident_activity", "incident_resolved", "Incident was resolved"),
    ConnectorEventMapping("on_call_alert_received", "incident_activity", "on_call_alert_received", "On-call alert metadata was received"),
    ConnectorEventMapping("runbook_opened", "incident_activity", "runbook_opened", "Runbook was opened"),
    ConnectorEventMapping("status_page_updated", "incident_activity", "status_page_updated", "Status page was updated"),
)

OBSERVABILITY_EVENT_MAPPINGS: tuple[ConnectorEventMapping, ...] = (
    ConnectorEventMapping("on_call_alert_received", "incident_activity", "on_call_alert_received", "Alert metadata was received"),
    ConnectorEventMapping("incident_declared", "incident_activity", "incident_declared", "Incident was declared"),
    ConnectorEventMapping("incident_resolved", "incident_activity", "incident_resolved", "Incident was resolved"),
    ConnectorEventMapping("metric_threshold_crossed", "analytics_activity", "metric_threshold_crossed", "Metric threshold crossed"),
    ConnectorEventMapping("dashboard_opened", "analytics_activity", "dashboard_opened", "Observability dashboard was opened"),
    ConnectorEventMapping("dashboard_filter_changed", "analytics_activity", "dashboard_filter_changed", "Observability dashboard filter changed"),
)

CLOUD_EVENT_MAPPINGS: tuple[ConnectorEventMapping, ...] = (
    ConnectorEventMapping("cloud_resource_opened", "cloud_console_activity", "cloud_resource_opened", "Cloud resource was opened"),
    ConnectorEventMapping("cloud_resource_changed", "cloud_console_activity", "cloud_resource_changed", "Cloud resource changed"),
    ConnectorEventMapping("deployment_started", "cloud_console_activity", "deployment_started", "Deployment started"),
    ConnectorEventMapping("deployment_failed", "cloud_console_activity", "deployment_failed", "Deployment failed"),
    ConnectorEventMapping("secret_view_attempted", "cloud_console_activity", "secret_view_attempted", "Secret view was attempted"),
    ConnectorEventMapping("billing_alert_seen", "cloud_console_activity", "billing_alert_seen", "Billing alert was seen"),
    ConnectorEventMapping("permission_error_seen", "cloud_console_activity", "permission_error_seen", "Permission error was seen"),
)

RUNTIME_EVENT_MAPPINGS: tuple[ConnectorEventMapping, ...] = (
    ConnectorEventMapping("container_started", "virtual_runtime_activity", "container_started", "Container started"),
    ConnectorEventMapping("container_stopped", "virtual_runtime_activity", "container_stopped", "Container stopped"),
    ConnectorEventMapping("container_failed", "virtual_runtime_activity", "container_failed", "Container failed"),
    ConnectorEventMapping("image_build_started", "virtual_runtime_activity", "image_build_started", "Image build started"),
    ConnectorEventMapping("image_build_failed", "virtual_runtime_activity", "image_build_failed", "Image build failed"),
)


OPERATIONS_APP_COLLECTORS: tuple[OperationsAppCollector, ...] = (
    OperationsAppCollector("sentry", "sentry", "observability", "Sentry issue, alert, release, project, and incident metadata.", "webhook_or_api_poller", "https://docs.sentry.io/organization/integrations/integration-platform/webhooks/"),
    OperationsAppCollector("datadog", "datadog", "observability", "Datadog monitor, event, dashboard, log alert, and incident metadata.", "webhook_or_events_api", "https://docs.datadoghq.com/integrations/webhooks/"),
    OperationsAppCollector("grafana", "grafana", "observability", "Grafana alert, dashboard, annotation, incident, and on-call metadata.", "webhook_or_api_poller", "https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/webhook-notifier/"),
    OperationsAppCollector("pagerduty", "pagerduty", "incident_response", "PagerDuty incident, trigger, acknowledge, escalation, resolve, and runbook metadata.", "webhook_or_api_poller", "https://developer.pagerduty.com/docs/webhooks-overview"),
    OperationsAppCollector("opsgenie", "opsgenie", "incident_response", "Opsgenie alert, acknowledge, escalation, close, and on-call metadata.", "webhook_or_api_poller", "https://support.atlassian.com/opsgenie/docs/webhook-integration/"),
    OperationsAppCollector("aws", "aws", "cloud", "AWS CloudTrail/EventBridge console, deployment, resource, secret, permission, and billing metadata.", "cloudtrail_or_eventbridge", "https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-service-event.html"),
    OperationsAppCollector("azure", "azure", "cloud", "Azure Activity Log/Event Grid resource, deployment, secret, permission, and billing metadata.", "activity_log_or_event_grid", "https://learn.microsoft.com/en-us/azure/event-grid/event-schema"),
    OperationsAppCollector("gcp", "gcp", "cloud", "Google Cloud audit log, resource, deployment, secret, permission, and billing metadata.", "audit_log_or_eventarc", "https://cloud.google.com/eventarc/docs/reference/supported-events"),
    OperationsAppCollector("cloudflare", "cloudflare", "cloud", "Cloudflare zone, DNS, worker, security, deployment, and billing metadata.", "api_poller_or_logpush", "https://developers.cloudflare.com/api/"),
    OperationsAppCollector("vercel", "vercel", "deployment", "Vercel deployment, build, project, domain, and team metadata.", "webhook_or_api_poller", "https://vercel.com/docs/webhooks"),
    OperationsAppCollector("netlify", "netlify", "deployment", "Netlify deploy, build, site, form, function, and domain metadata.", "webhook_or_api_poller", "https://docs.netlify.com/site-deploys/notifications/"),
    OperationsAppCollector("docker_hub", "docker_hub", "runtime", "Docker Hub image build, push, tag, and repository metadata.", "webhook_or_api_poller", "https://docs.docker.com/docker-hub/repos/manage/webhooks/"),
    OperationsAppCollector("kubernetes", "kubernetes", "runtime", "Kubernetes pod, deployment, job, event, and local cluster metadata.", "watch_api_or_local_bridge", "https://kubernetes.io/docs/reference/using-api/api-concepts/", requires_connector=False),
)


def _mappings_for_domain(domain: str) -> tuple[ConnectorEventMapping, ...]:
    if domain == "incident_response":
        return INCIDENT_EVENT_MAPPINGS
    if domain == "observability":
        return OBSERVABILITY_EVENT_MAPPINGS
    if domain == "runtime":
        return RUNTIME_EVENT_MAPPINGS
    return CLOUD_EVENT_MAPPINGS


OPERATIONS_SOURCE_MANIFESTS: tuple[ConnectorSourceManifest, ...] = tuple(
    ConnectorSourceManifest(
        provider_id=collector.provider_id,
        display_name=collector_status_record(collector)["display_name"],
        source_type=collector.source_channel,
        auth_method="api_key_oauth2_or_local_permission",
        collector_mappings=tuple(
            ConnectorEventMapping(
                f"{collector.provider_id}_{mapping.source_event}",
                mapping.collector,
                mapping.stimulus_type,
                f"{collector_status_record(collector)['display_name']} {mapping.text[0].lower()}{mapping.text[1:]}",
            )
            for mapping in _mappings_for_domain(collector.domain)
        ),
        poller_supported=collector.poller_supported,
        webhook_supported=collector.webhook_supported,
        requires_connector=collector.requires_connector,
        notes=collector.description,
    )
    for collector in OPERATIONS_APP_COLLECTORS
)


def operations_app_status_records() -> list[dict[str, Any]]:
    return [collector_status_record(collector) for collector in OPERATIONS_APP_COLLECTORS]


def run_operations_source_tick(config: AgentConfig, provider_id: str | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    from ..workspace_connectors import record_connector_source_health

    normalized = config.normalized()
    collectors = _collectors(provider_id)
    log = CollectorEventLog(normalized.collector_events_db_path)
    state = log.consumer_state(OPERATIONS_CONSUMER)
    source_state = state.setdefault("sources", {}).setdefault("operations", {})
    app_states = source_state.setdefault("apps", {})
    runtime = ConnectorRuntime(normalized)
    results = []
    for collector in collectors:
        readiness = {"connection_ready": True, "connected": True} if not collector.requires_connector else runtime.readiness(collector.provider_id)
        app_state = app_states.setdefault(collector.provider_id, {})
        app_state["last_tick_at"] = utc_now()
        app_state["tick_count"] = int(app_state.get("tick_count") or 0) + 1
        result = collector.collect(readiness, app_state, dry_run=dry_run, max_events=OPERATIONS_MAX_EVENTS_PER_APP)
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
        log.save_consumer_state(OPERATIONS_CONSUMER, state)
    return {
        "status": "succeeded",
        "sources": results,
        "source_count": len(results),
        "aggregate_status": aggregate_app_status(results),
        "dry_run": dry_run,
        "owner": "humungousaur.collectors.sources.operations",
    }


def _collectors(provider_id: str | None = None) -> tuple[OperationsAppCollector, ...]:
    provider = str(provider_id or "").strip()
    if not provider:
        return OPERATIONS_APP_COLLECTORS
    matches = tuple(collector for collector in OPERATIONS_APP_COLLECTORS if collector.provider_id == provider)
    if not matches:
        raise ValueError(f"unsupported operations provider: {provider_id or '<provider>'}")
    return matches


__all__ = [
    "CLOUD_EVENT_MAPPINGS",
    "INCIDENT_EVENT_MAPPINGS",
    "OBSERVABILITY_EVENT_MAPPINGS",
    "OPERATIONS_APP_COLLECTORS",
    "OPERATIONS_PROVIDER_IDS",
    "OPERATIONS_SOURCE_MANIFESTS",
    "RUNTIME_EVENT_MAPPINGS",
    "operations_app_status_records",
    "run_operations_source_tick",
]
