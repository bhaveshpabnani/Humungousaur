from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime

from .common import GOOGLE_WORKSPACE_DRIVE_SCOPE, _app_result, _connector_request, _utc_now
from .events import append_google_workspace_event


class DriveCollector:
    app = "drive"
    required_scopes = (GOOGLE_WORKSPACE_DRIVE_SCOPE,)
    description = "Polls Google Drive change cursors for metadata-only file and Workspace file changes."
    source_channel = "drive_changes"
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
            return _app_result("drive", "running", "Dry run skipped Google Drive API calls.", cursor=app_state.get("page_token", ""), source_channel=self.source_channel)
        page_token = str(app_state.get("page_token") or "").strip()
        if not page_token:
            response = _connector_request(
                runtime,
                operation="drive_changes_start_token",
                path="/drive/v3/changes/startPageToken",
                query={"fields": "startPageToken"},
                required_scopes=self.required_scopes,
            )
            start_token = str((response.get("response") or {}).get("startPageToken") or "")
            if start_token:
                app_state["page_token"] = start_token
                app_state["baseline_at"] = _utc_now()
            return _app_result("drive", "running", "Google Drive cursor baseline recorded.", cursor=start_token, source_channel=self.source_channel)

        events_appended = 0
        next_token = page_token
        while next_token and events_appended < max_events:
            response = _connector_request(
                runtime,
                operation="drive_changes_list",
                path="/drive/v3/changes",
                query={
                    "pageToken": next_token,
                    "pageSize": max_events,
                    "fields": "changes(fileId,removed,time,file(id,mimeType,createdTime,modifiedTime,shared,trashed)),nextPageToken,newStartPageToken",
                },
                required_scopes=self.required_scopes,
            )
            body = response.get("response") if isinstance(response.get("response"), dict) else {}
            for change in body.get("changes") if isinstance(body.get("changes"), list) else []:
                if events_appended >= max_events:
                    break
                event_payload = _drive_change_to_event(change)
                if event_payload is None:
                    continue
                append_google_workspace_event(config, event_payload)
                events_appended += 1
            next_page = str(body.get("nextPageToken") or "")
            if next_page:
                next_token = next_page
                app_state["page_token"] = next_page
                continue
            new_start = str(body.get("newStartPageToken") or "")
            if new_start:
                app_state["page_token"] = new_start
            break
        app_state["last_polled_at"] = _utc_now()
        return _app_result("drive", "running", "Google Drive changes polled.", cursor=app_state.get("page_token", ""), events_appended=events_appended, source_channel=self.source_channel)


def _drive_change_to_event(change: Any) -> dict[str, Any] | None:
    if not isinstance(change, dict):
        return None
    file_payload = change.get("file") if isinstance(change.get("file"), dict) else {}
    mime_type = str(file_payload.get("mimeType") or "")
    removed = bool(change.get("removed") or file_payload.get("trashed"))
    created = str(file_payload.get("createdTime") or "")
    modified = str(file_payload.get("modifiedTime") or change.get("time") or "")
    is_folder = mime_type == "application/vnd.google-apps.folder"
    if removed:
        event_type = "folder_deleted" if is_folder else "file_deleted"
    elif created and modified and created == modified:
        event_type = "folder_created" if is_folder else "file_created"
    else:
        event_type = "file_modified"
    return {
        "app": _google_app_from_mime(mime_type) or "drive",
        "event_type": event_type,
        "object_type": _object_type_from_mime(mime_type),
        "object_id": str(change.get("fileId") or file_payload.get("id") or ""),
        "file_id": str(change.get("fileId") or file_payload.get("id") or ""),
        "mime_type": mime_type,
        "provider_event_id": f"drive-change:{change.get('fileId') or file_payload.get('id') or ''}:{change.get('time') or modified}",
        "occurred_at": str(change.get("time") or modified),
        "metadata": {
            "source_channel": "drive_changes",
            "removed": removed,
            "created": bool(created and modified and created == modified),
            "shared": bool(file_payload.get("shared", False)),
        },
    }


def _google_app_from_mime(mime_type: str) -> str:
    mapping = {
        "application/vnd.google-apps.document": "docs",
        "application/vnd.google-apps.spreadsheet": "sheets",
        "application/vnd.google-apps.presentation": "slides",
    }
    return mapping.get(mime_type, "drive")


def _object_type_from_mime(mime_type: str) -> str:
    mapping = {
        "application/vnd.google-apps.document": "document",
        "application/vnd.google-apps.spreadsheet": "spreadsheet",
        "application/vnd.google-apps.presentation": "presentation",
        "application/vnd.google-apps.folder": "folder",
    }
    return mapping.get(mime_type, "drive_file")


GOOGLE_DRIVE_COLLECTOR = DriveCollector()
