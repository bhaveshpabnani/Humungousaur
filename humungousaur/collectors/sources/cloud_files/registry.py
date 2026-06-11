from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.collectors.event_log import CollectorEventLog
from humungousaur.connectors import ConnectorRuntime

from ..workspace_connectors import ConnectorEventMapping, ConnectorSourceManifest
from .box import BOX_CLOUD_FILE_COLLECTOR
from .common import BOX_PROVIDER_ID, CLOUD_FILE_CONSUMER, CLOUD_FILE_MAX_EVENTS_PER_PROVIDER, CLOUD_FILE_PROVIDER_IDS, DROPBOX_PROVIDER_ID, GOOGLE_WORKSPACE_PROVIDER_ID, ICLOUD_PROVIDER_ID, MICROSOFT_365_PROVIDER_ID, app_result, utc_now
from .dropbox import DROPBOX_CLOUD_FILE_COLLECTOR
from .icloud import ICLOUD_DRIVE_COLLECTOR


def _cloud_file_mappings(prefix: str, display_name: str) -> tuple[ConnectorEventMapping, ...]:
    return (
        ConnectorEventMapping(f"{prefix}_file_created", "cloud_sync_activity", "cloud_file_created", f"{display_name} file was created"),
        ConnectorEventMapping(f"{prefix}_folder_created", "cloud_sync_activity", "cloud_folder_created", f"{display_name} folder was created"),
        ConnectorEventMapping(f"{prefix}_file_renamed", "cloud_sync_activity", "cloud_file_renamed", f"{display_name} file was renamed"),
        ConnectorEventMapping(f"{prefix}_folder_renamed", "cloud_sync_activity", "cloud_folder_renamed", f"{display_name} folder was renamed"),
        ConnectorEventMapping(f"{prefix}_file_moved", "cloud_sync_activity", "cloud_file_moved", f"{display_name} file was moved"),
        ConnectorEventMapping(f"{prefix}_folder_moved", "cloud_sync_activity", "cloud_folder_moved", f"{display_name} folder was moved"),
        ConnectorEventMapping(f"{prefix}_file_deleted", "cloud_sync_activity", "cloud_file_deleted", f"{display_name} file was deleted"),
        ConnectorEventMapping(f"{prefix}_folder_deleted", "cloud_sync_activity", "cloud_folder_deleted", f"{display_name} folder was deleted"),
        ConnectorEventMapping(f"{prefix}_file_shared", "cloud_sync_activity", "cloud_file_shared", f"{display_name} sharing changed"),
        ConnectorEventMapping(f"{prefix}_permission_changed", "cloud_sync_activity", "cloud_permission_changed", f"{display_name} permissions changed"),
        ConnectorEventMapping(f"{prefix}_sync_failed", "cloud_sync_activity", "sync_failed", f"{display_name} sync error was detected"),
        ConnectorEventMapping(f"{prefix}_sync_conflict_detected", "cloud_sync_activity", "sync_conflict_detected", f"{display_name} sync conflict was detected"),
        ConnectorEventMapping(f"{prefix}_file_restored", "cloud_sync_activity", "cloud_file_restored", f"{display_name} item was restored"),
        ConnectorEventMapping(f"{prefix}_file_version_event", "cloud_sync_activity", "cloud_file_version_event", f"{display_name} version event occurred"),
        ConnectorEventMapping(f"{prefix}_remote_file_changed", "cloud_sync_activity", "remote_file_changed", f"{display_name} remote file changed"),
    )


CLOUD_FILE_SOURCE_MANIFESTS: tuple[ConnectorSourceManifest, ...] = (
    ConnectorSourceManifest(
        provider_id=DROPBOX_PROVIDER_ID,
        display_name="Dropbox",
        source_type="saas_api_poller_or_webhook",
        auth_method="oauth2_authorization_code",
        collector_mappings=_cloud_file_mappings("dropbox", "Dropbox"),
        poller_supported=True,
        webhook_supported=True,
        notes="Use files/list_folder cursors for metadata deltas; webhooks wake the local poller.",
    ),
    ConnectorSourceManifest(
        provider_id=BOX_PROVIDER_ID,
        display_name="Box",
        source_type="saas_api_poller_or_webhook",
        auth_method="oauth2_authorization_code",
        collector_mappings=_cloud_file_mappings("box", "Box"),
        poller_supported=True,
        webhook_supported=True,
        notes="Use the Box Events stream position for metadata deltas; webhooks can trigger focused polling.",
    ),
    ConnectorSourceManifest(
        provider_id=ICLOUD_PROVIDER_ID,
        display_name="iCloud Drive",
        source_type="local_file_provider_bridge",
        auth_method="local_permission",
        collector_mappings=_cloud_file_mappings("icloud", "iCloud Drive"),
        poller_supported=False,
        webhook_supported=False,
        requires_connector=False,
        notes="Use macOS File Provider/CloudDocs bridge events; no token is read by the collector.",
    ),
)


_COLLECTORS = {
    DROPBOX_PROVIDER_ID: DROPBOX_CLOUD_FILE_COLLECTOR,
    BOX_PROVIDER_ID: BOX_CLOUD_FILE_COLLECTOR,
    ICLOUD_PROVIDER_ID: ICLOUD_DRIVE_COLLECTOR,
}


def run_cloud_file_source_tick(config: AgentConfig, *, provider_id: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    from ..workspace_connectors import record_connector_source_health

    normalized = config.normalized()
    providers = [str(provider_id)] if provider_id else [DROPBOX_PROVIDER_ID, BOX_PROVIDER_ID, ICLOUD_PROVIDER_ID]
    log = CollectorEventLog(normalized.collector_events_db_path)
    state = log.consumer_state(CLOUD_FILE_CONSUMER)
    source_state = state.setdefault("sources", {})
    results = []
    for provider in providers:
        collector = _COLLECTORS[provider]
        provider_state = source_state.setdefault(provider, {})
        provider_state["last_tick_at"] = utc_now()
        provider_state["tick_count"] = int(provider_state.get("tick_count") or 0) + 1
        provider_state["collector_owner"] = "humungousaur.collectors.sources.cloud_files"
        readiness = _readiness(normalized, provider)
        if provider != ICLOUD_PROVIDER_ID and not readiness.get("collector_ready"):
            result = app_result(provider, "permission_denied", f"{provider} connector is not connected.", source_channel=getattr(collector, "source_channel", ""))
            if not dry_run:
                record_connector_source_health(normalized, provider_id=provider, status="permission_denied", message=result["message"], metadata={"last_tick_at": provider_state["last_tick_at"]})
            results.append({**result, "connector_readiness": readiness})
            continue
        runtime = None if provider == ICLOUD_PROVIDER_ID else ConnectorRuntime(normalized)
        try:
            result = collector.collect(
                normalized,
                runtime,  # type: ignore[arg-type]
                readiness,
                provider_state,
                dry_run=dry_run,
                max_events=CLOUD_FILE_MAX_EVENTS_PER_PROVIDER,
            )
        except PermissionError as exc:
            result = app_result(provider, "permission_denied", str(exc), source_channel=getattr(collector, "source_channel", ""))
        except Exception as exc:
            from .events import _append_dead_letter

            _append_dead_letter(normalized, provider, {"state_keys": sorted(provider_state.keys())}, f"{type(exc).__name__}: {exc}")
            result = app_result(provider, "failed", str(exc), source_channel=getattr(collector, "source_channel", ""))
        if not dry_run:
            record_connector_source_health(
                normalized,
                provider_id=provider,
                status=str(result.get("status") or "running"),
                message="Cloud-file source tick completed.",
                metadata={"last_tick_at": provider_state["last_tick_at"], "events_appended": int(result.get("events_appended") or 0)},
            )
        results.append({**result, "connector_readiness": readiness})
    if not dry_run:
        log.save_consumer_state(CLOUD_FILE_CONSUMER, state)
    return {"status": "succeeded", "sources": results, "source_count": len(results), "dry_run": dry_run}


def _readiness(config: AgentConfig, provider_id: str) -> dict[str, Any]:
    if provider_id == ICLOUD_PROVIDER_ID:
        return {
            "provider_id": provider_id,
            "configured": True,
            "connected": True,
            "connection_ready": True,
            "collector_ready": True,
            "local_bridge": True,
        }
    readiness = ConnectorRuntime(config).readiness(provider_id)
    readiness["connection_ready"] = bool(readiness.get("connected"))
    return readiness


__all__ = [
    "CLOUD_FILE_PROVIDER_IDS",
    "CLOUD_FILE_SOURCE_MANIFESTS",
    "run_cloud_file_source_tick",
]
