from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime

from .common import (
    MICROSOFT_365_FILES_SCOPE,
    MICROSOFT_365_SITES_SCOPE,
    _app_result,
    _connector_request,
    _connector_request_from_link,
    _store_delta_cursor,
    _utc_now,
)
from .events import append_microsoft_365_event
from .onedrive import _drive_item_to_event


class SharePointCollector:
    app = "sharepoint"
    required_scopes = (MICROSOFT_365_FILES_SCOPE, MICROSOFT_365_SITES_SCOPE)
    description = "Polls configured SharePoint document-library drive deltas and accepts Graph change notifications."
    source_channel = "graph_sharepoint_drive_delta+change_notifications"
    implementation_level = "configured_poller_and_webhook_ingress"
    poller_supported = True
    webhook_supported = True
    derived_from: tuple[str, ...] = ()

    def collect(
        self,
        config: AgentConfig,
        runtime: ConnectorRuntime,
        readiness: dict[str, Any],
        app_state: dict[str, Any],
        *,
        dry_run: bool,
        max_events: int,
    ) -> dict[str, Any]:
        del readiness
        site_id = str(app_state.get("site_id") or "").strip()
        drive_id = str(app_state.get("drive_id") or "").strip()
        if not site_id and not drive_id:
            app_state.setdefault("baseline_at", _utc_now())
            return _app_result("sharepoint", "running", "SharePoint collector is registered; configure site_id or drive_id for polling, or ingest change notifications.", cursor=app_state.get("baseline_at", ""), source_channel=self.source_channel, implementation_level=self.implementation_level)
        if dry_run:
            return _app_result("sharepoint", "running", "Dry run skipped SharePoint drive delta calls.", cursor=app_state.get("delta_link", ""), source_channel=self.source_channel, implementation_level=self.implementation_level)

        delta_link = str(app_state.get("delta_link") or "").strip()
        if not delta_link:
            path = f"/v1.0/drives/{drive_id}/root/delta" if drive_id else f"/v1.0/sites/{site_id}/drive/root/delta"
            response = _connector_request(
                runtime,
                operation="sharepoint_delta_baseline",
                path=path,
                query={"$select": "id,eTag,cTag,createdDateTime,lastModifiedDateTime,file,folder,deleted,shared,parentReference"},
                required_scopes=self.required_scopes,
            )
            body = response.get("response") if isinstance(response.get("response"), dict) else {}
            _store_delta_cursor(app_state, body)
            app_state["baseline_at"] = _utc_now()
            return _app_result("sharepoint", "running", "SharePoint drive delta cursor baseline recorded.", cursor=app_state.get("delta_link", ""), source_channel=self.source_channel, implementation_level=self.implementation_level)

        response = _connector_request_from_link(runtime, operation="sharepoint_delta", link=delta_link, required_scopes=self.required_scopes)
        body = response.get("response") if isinstance(response.get("response"), dict) else {}
        events_appended = 0
        for item in body.get("value") if isinstance(body.get("value"), list) else []:
            if events_appended >= max_events:
                break
            event_payload = _drive_item_to_event(item, source_app="sharepoint", source_channel=self.source_channel)
            if event_payload.get("app") == "onedrive":
                event_payload["app"] = "sharepoint"
            append_microsoft_365_event(config, event_payload)
            events_appended += 1
        _store_delta_cursor(app_state, body)
        app_state["last_polled_at"] = _utc_now()
        return _app_result("sharepoint", "running", "SharePoint drive delta polled.", cursor=app_state.get("delta_link", ""), events_appended=events_appended, source_channel=self.source_channel, implementation_level=self.implementation_level)


MICROSOFT_SHAREPOINT_COLLECTOR = SharePointCollector()
