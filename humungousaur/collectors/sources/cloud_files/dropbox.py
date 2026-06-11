from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime

from .common import DROPBOX_METADATA_SCOPES, DROPBOX_PROVIDER_ID, app_result, connector_request, hash_text, path_fingerprint, utc_now


class DropboxCloudFileCollector:
    provider_id = DROPBOX_PROVIDER_ID
    source_channel = "dropbox_files_list_folder_cursor+webhook"
    implementation_level = "poller_and_webhook_ingress"
    required_scopes = DROPBOX_METADATA_SCOPES

    def collect(
        self,
        config: AgentConfig,
        runtime: ConnectorRuntime,
        readiness: dict[str, Any],
        provider_state: dict[str, Any],
        *,
        dry_run: bool,
        max_events: int,
    ) -> dict[str, Any]:
        del readiness
        if dry_run:
            return app_result(self.provider_id, "running", "Dry run skipped Dropbox API calls.", cursor=provider_state.get("cursor", ""), source_channel=self.source_channel, implementation_level=self.implementation_level)
        cursor = str(provider_state.get("cursor") or "").strip()
        if not cursor:
            response = connector_request(
                runtime,
                provider_id=self.provider_id,
                operation="dropbox_list_folder_latest_cursor",
                method="POST",
                path="/2/files/list_folder/get_latest_cursor",
                body={"path": "", "recursive": True, "include_deleted": True, "include_has_explicit_shared_members": True},
                required_scopes=self.required_scopes,
            )
            cursor = str((response.get("response") or {}).get("cursor") or "")
            provider_state["cursor"] = cursor
            provider_state["baseline_at"] = utc_now()
            provider_state.setdefault("items", {})
            return app_result(self.provider_id, "running", "Dropbox cursor baseline recorded.", cursor=cursor, source_channel=self.source_channel, implementation_level=self.implementation_level)

        events_appended = 0
        has_more = True
        while cursor and has_more and events_appended < max_events:
            response = connector_request(
                runtime,
                provider_id=self.provider_id,
                operation="dropbox_list_folder_continue",
                method="POST",
                path="/2/files/list_folder/continue",
                body={"cursor": cursor},
                required_scopes=self.required_scopes,
            )
            body = response.get("response") if isinstance(response.get("response"), dict) else {}
            for entry in body.get("entries") if isinstance(body.get("entries"), list) else []:
                if events_appended >= max_events:
                    break
                for event_payload in _dropbox_entry_events(entry, provider_state):
                    if events_appended >= max_events:
                        break
                    from .events import append_cloud_file_event

                    append_cloud_file_event(config, event_payload)
                    events_appended += 1
            cursor = str(body.get("cursor") or cursor)
            has_more = bool(body.get("has_more", False))
            provider_state["cursor"] = cursor
        provider_state["last_polled_at"] = utc_now()
        return app_result(self.provider_id, "running", "Dropbox changes polled.", cursor=cursor, events_appended=events_appended, source_channel=self.source_channel, implementation_level=self.implementation_level)


def _dropbox_entry_events(entry: Any, provider_state: dict[str, Any]) -> list[dict[str, Any]]:
    payload = entry if isinstance(entry, dict) else {}
    tag = str(payload.get(".tag") or "")
    item_id = str(payload.get("id") or payload.get("path_lower") or payload.get("path_display") or "")
    if not item_id:
        return []
    item_key = hash_text(item_id)
    items = provider_state.setdefault("items", {})
    previous = items.get(item_key) if isinstance(items.get(item_key), dict) else {}
    fp = path_fingerprint(payload.get("path_lower") or payload.get("path_display"))
    object_type = "folder" if tag == "folder" else "cloud_file"
    deleted = tag == "deleted"
    event_type = _change_type(object_type, deleted, previous, fp)
    event_payload = {
        "provider_id": DROPBOX_PROVIDER_ID,
        "event_type": event_type,
        "object_type": "folder" if object_type == "folder" else "cloud_file",
        "object_id": item_id,
        "item_id": item_id,
        "provider_event_id": f"dropbox:{item_id}:{payload.get('rev') or payload.get('server_modified') or tag}",
        "occurred_at": str(payload.get("server_modified") or ""),
        "mime_type": str(payload.get("mime_type") or ""),
        "rev": str(payload.get("rev") or ""),
        "metadata": {
            "source_channel": "dropbox_files_list_folder_cursor",
            "has_explicit_shared_members": bool(payload.get("has_explicit_shared_members")),
        },
    }
    events = [event_payload]
    if payload.get("sharing_info") or payload.get("has_explicit_shared_members"):
        events.append({**event_payload, "event_type": "file_shared", "provider_event_id": f"{event_payload['provider_event_id']}:shared"})
    if previous and str(payload.get("rev") or "") and previous.get("rev") != str(payload.get("rev") or ""):
        events.append({**event_payload, "event_type": "file_version_event", "provider_event_id": f"{event_payload['provider_event_id']}:version"})
    if deleted:
        items.pop(item_key, None)
    else:
        items[item_key] = {"object_type": object_type, "path_hash": fp.get("path_hash", ""), "parent_path_hash": fp.get("parent_path_hash", ""), "basename_hash": fp.get("basename_hash", ""), "rev": str(payload.get("rev") or "")}
    return events


def _change_type(object_type: str, deleted: bool, previous: dict[str, Any], fp: dict[str, str]) -> str:
    prefix = "folder" if object_type == "folder" else "file"
    if deleted:
        return f"{prefix}_deleted"
    if not previous:
        return f"{prefix}_created"
    if fp.get("basename_hash") and previous.get("basename_hash") != fp.get("basename_hash"):
        return f"{prefix}_renamed"
    if fp.get("parent_path_hash") and previous.get("parent_path_hash") != fp.get("parent_path_hash"):
        return f"{prefix}_moved"
    return "remote_file_changed"


DROPBOX_CLOUD_FILE_COLLECTOR = DropboxCloudFileCollector()
