from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.collectors.event_log import CollectorEventLog
from humungousaur.connectors import ConnectorRuntime

from ..workspace_connectors import ConnectorEventMapping, ConnectorSourceManifest
from .code_hosting import CODE_HOSTING_EVENT_MAPPINGS, CODE_HOSTING_SOURCE_MANIFESTS, poll_code_hosting_provider
from .common import CODE_HOSTING_PROVIDER_IDS, DEVELOPER_CONSUMER, DEVELOPER_PROVIDER_IDS, utc_now
from .git import GIT_EVENT_MAPPINGS, GIT_SOURCE_MANIFESTS
from .ide import IDE_EVENT_MAPPINGS, IDE_SOURCE_MANIFESTS
from .terminal import TERMINAL_EVENT_MAPPINGS, TERMINAL_SOURCE_MANIFESTS


_LOCAL_SOURCE_MANIFESTS = (
    *IDE_SOURCE_MANIFESTS,
    *TERMINAL_SOURCE_MANIFESTS,
    *GIT_SOURCE_MANIFESTS,
)

_SAAS_CODE_HOSTING_MANIFESTS = CODE_HOSTING_SOURCE_MANIFESTS

LOCAL_EVENT_MAPPINGS: tuple[ConnectorEventMapping, ...] = (
    *IDE_EVENT_MAPPINGS,
    *TERMINAL_EVENT_MAPPINGS,
    *GIT_EVENT_MAPPINGS,
)

CODE_HOSTING_EVENT_MAPPING_BY_PROVIDER: dict[str, tuple[ConnectorEventMapping, ...]] = {
    "github": (
        ConnectorEventMapping("pull_request_opened", "github_activity", "pr_opened", "GitHub pull request was opened"),
        ConnectorEventMapping("pull_request_merged", "github_activity", "merge_ready", "GitHub pull request was merged"),
        ConnectorEventMapping("review_requested", "github_activity", "pr_review_requested", "GitHub review was requested"),
        ConnectorEventMapping("ci_failed", "github_activity", "ci_failed", "GitHub CI failed"),
        ConnectorEventMapping("ci_passed", "github_activity", "ci_passed", "GitHub CI passed"),
        ConnectorEventMapping("issue_assigned", "github_activity", "issue_assigned", "GitHub issue was assigned"),
        ConnectorEventMapping("comment_received", "github_activity", "comment_received", "GitHub comment metadata was received"),
        *CODE_HOSTING_EVENT_MAPPINGS,
    ),
    "gitlab": CODE_HOSTING_EVENT_MAPPINGS,
    "bitbucket": CODE_HOSTING_EVENT_MAPPINGS,
    "azure_devops": CODE_HOSTING_EVENT_MAPPINGS,
}


def _local_source_manifest(record: Any) -> ConnectorSourceManifest:
    return ConnectorSourceManifest(
        provider_id=record.provider_id,
        display_name=record.app,
        source_type="local_extension_or_hook",
        auth_method="local_bridge",
        collector_mappings=LOCAL_EVENT_MAPPINGS,
        poller_supported=record.poller_supported,
        webhook_supported=record.webhook_supported,
        requires_connector=False,
        official_docs=record.official_docs,
        notes=record.description,
    )


def _code_hosting_source_manifest(record: Any) -> ConnectorSourceManifest:
    return ConnectorSourceManifest(
        provider_id=record.provider_id,
        display_name=record.app,
        source_type="saas_api_poller_or_webhook",
        auth_method="oauth2_authorization_code_or_app_password",
        collector_mappings=CODE_HOSTING_EVENT_MAPPING_BY_PROVIDER[record.provider_id],
        poller_supported=record.poller_supported,
        webhook_supported=record.webhook_supported,
        requires_connector=True,
        official_docs=record.official_docs,
        notes=record.description,
    )


DEVELOPER_SOURCE_MANIFESTS: tuple[ConnectorSourceManifest, ...] = (
    *(_local_source_manifest(record) for record in _LOCAL_SOURCE_MANIFESTS),
    *(_code_hosting_source_manifest(record) for record in _SAAS_CODE_HOSTING_MANIFESTS if record.provider_id != "github"),
)


def github_source_manifest() -> ConnectorSourceManifest:
    github = next(record for record in _SAAS_CODE_HOSTING_MANIFESTS if record.provider_id == "github")
    return _code_hosting_source_manifest(github)


def developer_source_manifest_records() -> list[dict[str, Any]]:
    return [record.to_record() for record in (*DEVELOPER_SOURCE_MANIFESTS, github_source_manifest())]


def run_developer_source_tick(config: AgentConfig, *, provider_id: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    from ..workspace_connectors import record_connector_source_health

    normalized = config.normalized()
    selected = _selected_provider_ids(provider_id)
    log = CollectorEventLog(normalized.collector_events_db_path)
    state = log.consumer_state(DEVELOPER_CONSUMER)
    source_state = state.setdefault("sources", {})
    results = []
    runtime = ConnectorRuntime(normalized)
    for provider in selected:
        manifest = _manifest_record(provider)
        provider_state = source_state.setdefault(provider, {})
        previous_tick = provider_state.get("last_tick_at", "")
        provider_state["last_tick_at"] = utc_now()
        provider_state["tick_count"] = int(provider_state.get("tick_count") or 0) + 1
        provider_state["collector_owner"] = "humungousaur.collectors.sources.developer"
        provider_state["poller_supported"] = bool(manifest.get("poller_supported"))
        provider_state["webhook_supported"] = bool(manifest.get("webhook_supported"))
        provider_state["requires_connector"] = bool(manifest.get("requires_connector", True))
        if provider in CODE_HOSTING_PROVIDER_IDS:
            readiness = runtime.readiness(provider)
            try:
                app_result = poll_code_hosting_provider(
                    normalized,
                    runtime,
                    provider,
                    readiness,
                    provider_state,
                    dry_run=dry_run,
                )
            except PermissionError as exc:
                app_result = {
                    "provider_id": provider,
                    "status": "permission_denied",
                    "message": str(exc),
                    "events_appended": 0,
                    "source_channel": f"{provider}_api_poller",
                    "implementation_level": "connector_poller",
                }
            except Exception as exc:
                app_result = {
                    "provider_id": provider,
                    "status": "failed",
                    "message": str(exc),
                    "events_appended": 0,
                    "source_channel": f"{provider}_api_poller",
                    "implementation_level": "connector_poller",
                }
        else:
            readiness = {
                "provider_id": provider,
                "configured": True,
                "connected": True,
                "connection_ready": True,
                "collector_ready": True,
                "auth_method": manifest.get("auth_method"),
                "source_type": manifest.get("source_type"),
                "local_bridge": True,
            }
            app_result = {
                "provider_id": provider,
                "status": "running",
                "message": "Local developer source tick completed; extension/hook ingress remains event-driven.",
                "events_appended": 0,
                "source_channel": str(manifest.get("source_type") or "local_extension_or_hook"),
                "implementation_level": "local_event_ingress",
            }
        if not dry_run:
            record_connector_source_health(
                normalized,
                provider_id=provider,
                status=str(app_result.get("status") or "running"),
                message=str(app_result.get("message") or "Developer source tick completed."),
                metadata={
                    "last_tick_at": provider_state["last_tick_at"],
                    "previous_tick_at": previous_tick,
                    "events_appended": int(app_result.get("events_appended") or 0),
                    "source_channel": app_result.get("source_channel") or "",
                },
            )
        results.append(
            {
                "provider_id": provider,
                "status": str(app_result.get("status") or "running"),
                "events_appended": int(app_result.get("events_appended") or 0),
                "last_tick_at": provider_state["last_tick_at"],
                "poller_supported": bool(manifest.get("poller_supported")),
                "webhook_supported": bool(manifest.get("webhook_supported")),
                "connector_readiness": readiness,
                "apps": [app_result],
            }
        )
    if not dry_run:
        log.save_consumer_state(DEVELOPER_CONSUMER, state)
    return {"status": "succeeded", "sources": results, "source_count": len(results), "dry_run": dry_run}


def _selected_provider_ids(provider_id: str | None) -> tuple[str, ...]:
    provider = str(provider_id or "").strip()
    if not provider:
        return tuple(sorted(DEVELOPER_PROVIDER_IDS))
    if provider not in DEVELOPER_PROVIDER_IDS:
        raise KeyError(f"Unknown developer source provider: {provider_id}")
    return (provider,)


def _manifest_record(provider_id: str) -> dict[str, Any]:
    for record in developer_source_manifest_records():
        if record["provider_id"] == provider_id:
            return record
    raise KeyError(f"Unknown developer source provider: {provider_id}")
