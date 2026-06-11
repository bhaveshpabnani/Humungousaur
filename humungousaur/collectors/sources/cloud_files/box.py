from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime

from .common import BOX_METADATA_SCOPES, BOX_PROVIDER_ID, app_result, connector_request, utc_now


class BoxCloudFileCollector:
    provider_id = BOX_PROVIDER_ID
    source_channel = "box_events_stream+webhook"
    implementation_level = "poller_and_webhook_ingress"
    required_scopes = BOX_METADATA_SCOPES

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
            return app_result(self.provider_id, "running", "Dry run skipped Box Events API calls.", cursor=provider_state.get("stream_position", ""), source_channel=self.source_channel, implementation_level=self.implementation_level)
        stream_position = str(provider_state.get("stream_position") or "").strip()
        if not stream_position:
            response = connector_request(
                runtime,
                provider_id=self.provider_id,
                operation="box_events_baseline",
                path="/2.0/events",
                query={"stream_position": "now", "limit": max_events},
                required_scopes=self.required_scopes,
            )
            body = response.get("response") if isinstance(response.get("response"), dict) else {}
            stream_position = str(body.get("next_stream_position") or "")
            provider_state["stream_position"] = stream_position
            provider_state["baseline_at"] = utc_now()
            return app_result(self.provider_id, "running", "Box event stream baseline recorded.", cursor=stream_position, source_channel=self.source_channel, implementation_level=self.implementation_level)

        response = connector_request(
            runtime,
            provider_id=self.provider_id,
            operation="box_events",
            path="/2.0/events",
            query={"stream_position": stream_position, "limit": max_events},
            required_scopes=self.required_scopes,
        )
        body = response.get("response") if isinstance(response.get("response"), dict) else {}
        events_appended = 0
        for event in body.get("entries") if isinstance(body.get("entries"), list) else []:
            if events_appended >= max_events:
                break
            event_payload = _box_event_to_payload(event)
            if event_payload is None:
                continue
            from .events import append_cloud_file_event

            append_cloud_file_event(config, event_payload)
            events_appended += 1
        provider_state["stream_position"] = str(body.get("next_stream_position") or stream_position)
        provider_state["last_polled_at"] = utc_now()
        return app_result(self.provider_id, "running", "Box events polled.", cursor=provider_state["stream_position"], events_appended=events_appended, source_channel=self.source_channel, implementation_level=self.implementation_level)


def _box_event_to_payload(event: Any) -> dict[str, Any] | None:
    payload = event if isinstance(event, dict) else {}
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    event_type = _BOX_EVENT_TYPES.get(str(payload.get("event_type") or "").upper())
    if not event_type:
        return None
    item_id = str(source.get("id") or payload.get("event_id") or "")
    item_type = str(source.get("type") or "")
    object_type = "folder" if item_type == "folder" or "folder" in event_type else "cloud_file"
    return {
        "provider_id": BOX_PROVIDER_ID,
        "event_type": event_type,
        "object_type": object_type,
        "object_id": item_id,
        "item_id": item_id,
        "provider_event_id": str(payload.get("event_id") or f"box:{item_id}:{payload.get('created_at') or payload.get('event_type')}"),
        "occurred_at": str(payload.get("created_at") or ""),
        "mime_type": str(source.get("mime_type") or ""),
        "metadata": {
            "source_channel": "box_events_stream",
            "box_event_type": str(payload.get("event_type") or ""),
        },
    }


_BOX_EVENT_TYPES = {
    "ITEM_CREATE": "file_created",
    "ITEM_UPLOAD": "file_created",
    "ITEM_RENAME": "file_renamed",
    "ITEM_MOVE": "file_moved",
    "ITEM_TRASH": "file_deleted",
    "ITEM_UNDELETE_VIA_TRASH": "file_restored",
    "ITEM_RESTORE": "file_restored",
    "ITEM_SHARED_UPDATE": "file_shared",
    "COLLABORATION_CREATED": "permission_changed",
    "COLLABORATION_ACCEPTED": "permission_changed",
    "COLLABORATION_ROLE_CHANGE": "permission_changed",
    "COLLABORATION_REMOVED": "permission_changed",
    "LOCK_CREATE": "sync_conflict_detected",
    "ITEM_SYNC": "remote_file_changed",
    "ITEM_VERSION_UPLOAD": "file_version_event",
}


BOX_CLOUD_FILE_COLLECTOR = BoxCloudFileCollector()
