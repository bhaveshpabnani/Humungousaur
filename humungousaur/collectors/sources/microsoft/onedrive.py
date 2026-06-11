from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime

from .common import (
    MICROSOFT_365_FILES_SCOPE,
    _app_result,
    _connector_request,
    _connector_request_from_link,
    _store_delta_cursor,
    _utc_now,
)
from .events import append_microsoft_365_event


class OneDriveCollector:
    app = "onedrive"
    required_scopes = (MICROSOFT_365_FILES_SCOPE,)
    description = "Polls Microsoft Graph driveItem delta cursors for metadata-only OneDrive and Office file changes."
    source_channel = "graph_drive_delta"
    implementation_level = "poller"
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
        if dry_run:
            return _app_result("onedrive", "running", "Dry run skipped Microsoft Graph drive delta calls.", cursor=app_state.get("delta_link", ""), source_channel=self.source_channel)
        delta_link = str(app_state.get("delta_link") or "").strip()
        if not delta_link:
            response = _connector_request(
                runtime,
                operation="onedrive_delta_baseline",
                path="/v1.0/me/drive/root/delta",
                query={"$select": "id,eTag,cTag,createdDateTime,lastModifiedDateTime,file,folder,deleted,shared,parentReference"},
                required_scopes=self.required_scopes,
            )
            body = response.get("response") if isinstance(response.get("response"), dict) else {}
            _store_delta_cursor(app_state, body)
            app_state["baseline_at"] = _utc_now()
            return _app_result("onedrive", "running", "OneDrive delta cursor baseline recorded.", cursor=app_state.get("delta_link", ""), source_channel=self.source_channel)

        response = _connector_request_from_link(
            runtime,
            operation="onedrive_delta",
            link=delta_link,
            required_scopes=self.required_scopes,
        )
        body = response.get("response") if isinstance(response.get("response"), dict) else {}
        events_appended = 0
        for item in body.get("value") if isinstance(body.get("value"), list) else []:
            if events_appended >= max_events:
                break
            append_microsoft_365_event(config, _drive_item_to_event(item, source_app="onedrive", source_channel=self.source_channel))
            events_appended += 1
        _store_delta_cursor(app_state, body)
        app_state["last_polled_at"] = _utc_now()
        return _app_result("onedrive", "running", "OneDrive drive delta polled.", cursor=app_state.get("delta_link", ""), events_appended=events_appended, source_channel=self.source_channel)


def _drive_item_to_event(item: Any, *, source_app: str, source_channel: str) -> dict[str, Any]:
    payload = item if isinstance(item, dict) else {}
    file_payload = payload.get("file") if isinstance(payload.get("file"), dict) else {}
    parent = payload.get("parentReference") if isinstance(payload.get("parentReference"), dict) else {}
    mime_type = str(file_payload.get("mimeType") or "")
    app = _microsoft_app_from_mime(mime_type) or source_app
    deleted = isinstance(payload.get("deleted"), dict)
    is_folder = bool(payload.get("folder"))
    created = str(payload.get("createdDateTime") or "")
    modified = str(payload.get("lastModifiedDateTime") or "")
    if deleted:
        event_type = "folder_deleted" if is_folder else "file_deleted"
    elif created and modified and created == modified:
        event_type = "folder_created" if is_folder else "file_created"
    else:
        event_type = "file_modified"
    item_id = str(payload.get("id") or "")
    return {
        "app": app,
        "event_type": event_type,
        "object_type": _object_type_from_mime(mime_type, bool(payload.get("folder"))),
        "object_id": item_id,
        "file_id": item_id,
        "mime_type": mime_type,
        "provider_event_id": f"{source_channel}:{item_id}:{payload.get('eTag') or payload.get('cTag') or modified}",
        "occurred_at": modified,
        "metadata": {
            "source_channel": source_channel,
            "drive_id": str(parent.get("driveId") or ""),
            "created": bool(created and modified and created == modified),
            "deleted": deleted,
            "shared": bool(payload.get("shared")),
            "has_file_facet": bool(file_payload),
            "has_folder_facet": bool(payload.get("folder")),
        },
    }


def _microsoft_app_from_mime(mime_type: str) -> str:
    mapping = {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "word",
        "application/msword": "word",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "excel",
        "application/vnd.ms-excel": "excel",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "powerpoint",
        "application/vnd.ms-powerpoint": "powerpoint",
        "application/vnd.ms-powerpoint.presentation.macroenabled.12": "powerpoint",
        "application/onenote": "onenote",
    }
    return mapping.get(mime_type, "")


def _object_type_from_mime(mime_type: str, is_folder: bool) -> str:
    if is_folder:
        return "folder"
    mapping = {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "document",
        "application/msword": "document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "spreadsheet",
        "application/vnd.ms-excel": "spreadsheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "presentation",
        "application/vnd.ms-powerpoint": "presentation",
        "application/onenote": "note",
    }
    return mapping.get(mime_type, "drive_file")


MICROSOFT_ONEDRIVE_COLLECTOR = OneDriveCollector()
