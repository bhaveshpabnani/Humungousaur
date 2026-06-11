from __future__ import annotations

import platform
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime
from humungousaur.collectors.event_log import CollectorEventLog

from ..workspace_connectors import (
    append_connector_source_event,
    connector_source_status,
    record_connector_source_health,
    run_connector_source_tick,
)
from .catalog import meeting_provider_entry, meeting_provider_ids


_PROVIDER_ALIASES = {
    "zoom": "zoom",
    "google_meet": "google_workspace",
    "meet": "google_workspace",
    "google_workspace": "google_workspace",
    "teams": "microsoft_365",
    "microsoft_teams": "microsoft_365",
    "msteams": "microsoft_365",
    "microsoft_365": "microsoft_365",
    "webex": "webex",
    "discord": "discord",
    "discord_calls": "discord",
    "discord_call": "discord",
}

_SOURCE_PREFIXES = {
    "zoom": "zoom",
    "google_workspace": "meet",
    "microsoft_365": "teams",
    "webex": "webex",
    "discord": "discord_call",
}

_EVENT_ALIASES = {
    "meeting_joined": "joined",
    "joined": "joined",
    "join": "joined",
    "call_started": "joined",
    "meeting_started": "joined",
    "meeting_left": "left",
    "left": "left",
    "leave": "left",
    "call_ended": "left",
    "meeting_ended": "left",
    "participant_jbh_waiting": "waiting_room_joined",
    "waiting_room_joined": "waiting_room_joined",
    "waiting_room_admitted": "waiting_room_admitted",
    "participant_admitted": "waiting_room_admitted",
    "participant_joined": "participant_joined",
    "participant_left": "participant_left",
    "voice_state_joined": "participant_joined",
    "voice_state_left": "participant_left",
    "breakout_room_joined": "breakout_room_joined",
    "breakout_room_left": "breakout_room_left",
    "meeting_recording_started": "recording_started",
    "recording_started": "recording_started",
    "recording.start": "recording_started",
    "meeting_recording_stopped": "recording_stopped",
    "recording_stopped": "recording_stopped",
    "recording.stop": "recording_stopped",
    "microphone_muted": "microphone_muted",
    "mic_muted": "microphone_muted",
    "self_mute_enabled": "microphone_muted",
    "microphone_unmuted": "microphone_unmuted",
    "mic_unmuted": "microphone_unmuted",
    "self_mute_disabled": "microphone_unmuted",
    "camera_enabled": "camera_enabled",
    "video_enabled": "camera_enabled",
    "self_video_enabled": "camera_enabled",
    "camera_disabled": "camera_disabled",
    "video_disabled": "camera_disabled",
    "self_video_disabled": "camera_disabled",
    "hand_raised": "hand_raised",
    "request_to_speak": "hand_raised",
    "hand_lowered": "hand_lowered",
    "reaction_sent": "reaction_sent",
    "voice_channel_effect_send": "reaction_sent",
    "captions_enabled": "captions_enabled",
    "captions_disabled": "captions_disabled",
    "meeting_chat_opened": "meeting_chat_opened",
    "chat_opened": "meeting_chat_opened",
    "screen_share_started": "screen_share_started",
    "self_stream_enabled": "screen_share_started",
    "go_live_started": "screen_share_started",
    "screen_share_stopped": "screen_share_stopped",
    "self_stream_disabled": "screen_share_stopped",
    "go_live_stopped": "screen_share_stopped",
    "window_share_started": "window_share_started",
    "window_share_stopped": "window_share_stopped",
    "presentation_started": "presentation_started",
    "presentation_stopped": "presentation_stopped",
    "presenter_changed": "presenter_changed",
    "remote_control_requested": "remote_control_requested",
    "remote_control_granted": "remote_control_granted",
    "remote_control_revoked": "remote_control_revoked",
    "meeting_recording_available": "recording_available",
    "recording_available": "recording_available",
    "recording.completed": "recording_available",
    "recording_completed": "recording_available",
    "meeting_transcript_available": "transcript_available",
    "transcript_available": "transcript_available",
    "transcript.created": "transcript_available",
    "transcript_created": "transcript_available",
    "meeting_summary_generated": "summary_generated",
    "summary_generated": "summary_generated",
    "summary.completed": "summary_generated",
    "summary_completed": "summary_generated",
    "meeting_action_items_detected": "action_items_detected",
    "action_items_detected": "action_items_detected",
    "action_items_available": "action_items_detected",
    "meeting_notes_shared": "notes_shared",
    "notes_shared": "notes_shared",
    "meeting_whiteboard_exported": "whiteboard_exported",
    "whiteboard_exported": "whiteboard_exported",
    "meeting_followup_created": "followup_created",
    "followup_created": "followup_created",
}


def append_meeting_source_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        provider_id = _provider_id(payload)
        source_event = _source_event(provider_id, payload)
        return append_connector_source_event(
            config,
            provider_id=provider_id,
            source_event=source_event,
            object_type=str(payload.get("object_type") or "meeting"),
            object_id=_object_id(payload),
            metadata=_metadata_from_payload(provider_id, payload, source_event),
            payload=payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
            occurred_at=str(payload.get("occurred_at") or payload.get("timestamp") or ""),
        )
    except (KeyError, ValueError) as exc:
        _append_dead_letter(config, payload, str(exc))
        raise ValueError(str(exc)) from exc


def append_zoom_webhook_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    _require_connector_ready(config, "zoom")
    event_type = str(payload.get("event") or payload.get("event_type") or "")
    object_payload = payload.get("payload", {}).get("object") if isinstance(payload.get("payload"), dict) else {}
    if not isinstance(object_payload, dict):
        object_payload = {}
    return append_meeting_source_event(
        config,
        {
            "provider_id": "zoom",
            "event_type": _zoom_event_type(event_type),
            "meeting_id": object_payload.get("id") or object_payload.get("uuid"),
            "recording_id": object_payload.get("recording_file_id"),
            "participant_count": object_payload.get("participant_count"),
            "duration_seconds": object_payload.get("duration"),
            "has_recording": "recording" in event_type,
            "metadata": {
                "account_id": payload.get("account_id"),
                "meeting_uuid": object_payload.get("uuid"),
                "host_id": object_payload.get("host_id"),
                "event_ts": payload.get("event_ts"),
                "webhook_event": event_type,
                "title": object_payload.get("topic"),
                "participant_name": (object_payload.get("participant") or {}).get("user_name") if isinstance(object_payload.get("participant"), dict) else "",
            },
            "source_channel": "zoom_webhook",
            "occurred_at": str(payload.get("event_ts") or object_payload.get("start_time") or object_payload.get("end_time") or ""),
        },
    )


def append_google_meet_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    _require_connector_ready(config, "google_workspace")
    event_type = str(payload.get("eventType") or payload.get("event_type") or payload.get("type") or "")
    resource = payload.get("resource") if isinstance(payload.get("resource"), dict) else {}
    name = str(resource.get("name") or payload.get("name") or "")
    return append_meeting_source_event(
        config,
        {
            "provider_id": "google_workspace",
            "event_type": _google_meet_event_type(event_type, name),
            "conference_record_id": resource.get("conferenceRecord") or _conference_record_id(name),
            "recording_id": resource.get("recording") or _last_segment(name) if "recording" in name.lower() else "",
            "transcript_id": resource.get("transcript") or _last_segment(name) if "transcript" in name.lower() else "",
            "metadata": {
                "event_type": event_type,
                "resource_name": name,
                "space_id": resource.get("space"),
                "participant_id": resource.get("participant"),
                "artifact_content_omitted": True,
            },
            "source_channel": "google_workspace_events_or_meet_api",
            "occurred_at": str(payload.get("eventTime") or payload.get("occurred_at") or ""),
        },
    )


def append_teams_meeting_graph_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    _require_connector_ready(config, "microsoft_365")
    notification = _first_graph_notification(payload)
    resource_data = notification.get("resourceData") if isinstance(notification.get("resourceData"), dict) else {}
    resource = str(notification.get("resource") or resource_data.get("@odata.id") or "")
    return append_meeting_source_event(
        config,
        {
            "provider_id": "microsoft_365",
            "event_type": _teams_meeting_event_type(notification, resource),
            "online_meeting_id": resource_data.get("id") or _last_segment(resource),
            "call_id": resource_data.get("callId"),
            "recording_id": resource_data.get("recordingId"),
            "transcript_id": resource_data.get("transcriptId"),
            "metadata": {
                "change_type": notification.get("changeType"),
                "resource": resource,
                "resource_type": resource_data.get("@odata.type"),
                "subscription_id": notification.get("subscriptionId"),
                "encrypted_content_omitted": bool(notification.get("encryptedContent")),
            },
            "source_channel": "microsoft_graph_meeting_change_notification",
            "occurred_at": str(notification.get("subscriptionExpirationDateTime") or ""),
        },
    )


def append_webex_webhook_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    _require_connector_ready(config, "webex")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    resource = str(payload.get("resource") or data.get("resource") or "")
    event = str(payload.get("event") or data.get("event") or "")
    return append_meeting_source_event(
        config,
        {
            "provider_id": "webex",
            "event_type": _webex_event_type(resource, event, data),
            "meeting_id": data.get("meetingId") or data.get("id"),
            "recording_id": data.get("recordingId"),
            "transcript_id": data.get("transcriptId"),
            "metadata": {
                "webhook_id": payload.get("id"),
                "resource": resource,
                "event": event,
                "org_id": data.get("orgId"),
                "host_id": data.get("hostId"),
                "room_id": data.get("roomId"),
                "title": data.get("title") or data.get("meetingTitle"),
            },
            "source_channel": "webex_webhook",
            "occurred_at": str(payload.get("created") or data.get("created") or ""),
        },
    )


def append_discord_call_gateway_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    _require_connector_ready(config, "discord")
    dispatch_type = str(payload.get("t") or payload.get("event_type") or "").upper()
    data = payload.get("d") if isinstance(payload.get("d"), dict) else payload
    return append_meeting_source_event(
        config,
        {
            "provider_id": "discord",
            "event_type": _discord_call_event_type(dispatch_type, data),
            "voice_state_id": data.get("session_id"),
            "channel_id": data.get("channel_id"),
            "room_id": data.get("guild_id"),
            "metadata": {
                "guild_id": data.get("guild_id"),
                "channel_id": data.get("channel_id"),
                "user_id": data.get("user_id"),
                "session_id": data.get("session_id"),
                "self_mute": data.get("self_mute"),
                "self_deaf": data.get("self_deaf"),
                "self_video": data.get("self_video"),
                "self_stream": data.get("self_stream"),
                "gateway_sequence": payload.get("s"),
            },
            "source_channel": "discord_gateway_voice_state",
            "occurred_at": str(payload.get("op") or ""),
        },
    )


def append_meeting_source_health(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        provider_id = _provider_id(payload)
        return record_connector_source_health(
            config,
            provider_id=provider_id,
            status=str(payload.get("status") or "running"),
            message=str(payload.get("message") or ""),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
    except (KeyError, ValueError) as exc:
        _append_dead_letter(config, payload, str(exc))
        raise ValueError(str(exc)) from exc


def meeting_source_status(config: AgentConfig, provider_id: str | None = None) -> dict[str, Any]:
    provider = _normalize_provider(provider_id) if provider_id else None
    if provider:
        status = connector_source_status(config, provider_id=provider)
        sources = status.get("sources", [])
    else:
        sources = []
        for item in meeting_provider_ids():
            try:
                sources.extend(connector_source_status(config, provider_id=item).get("sources", []))
            except KeyError:
                continue
    return {
        "sources": [
            {
                **source,
                "meeting_app": meeting_provider_entry(str(source.get("provider_id"))).app,
                "meeting_source_channel": meeting_provider_entry(str(source.get("provider_id"))).source_channel,
                "docs_url": meeting_provider_entry(str(source.get("provider_id"))).docs_url,
            }
            for source in sources
        ],
        "source_count": len(sources),
        "owner": "humungousaur.collectors.sources.meetings",
    }


def run_meeting_source_tick(config: AgentConfig, provider_id: str | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    provider_ids = (_normalize_provider(provider_id),) if provider_id else meeting_provider_ids()
    sources = []
    for item in provider_ids:
        tick = run_connector_source_tick(config, provider_id=item, dry_run=dry_run)
        sources.extend(tick.get("sources", []))
    return {
        "status": "succeeded",
        "sources": sources,
        "source_count": len(sources),
        "dry_run": dry_run,
        "owner": "humungousaur.collectors.sources.meetings",
    }


def read_meeting_source_events(
    config: AgentConfig,
    state: dict[str, Any],
    collector: str,
    allowed_stimulus_types: set[str],
    *,
    max_events: int = 20,
) -> list[Any]:
    del config, state, collector, allowed_stimulus_types, max_events
    return []


def _require_connector_ready(config: AgentConfig, provider_id: str) -> dict[str, Any]:
    readiness = ConnectorRuntime(config.normalized()).readiness(provider_id)
    connected = bool(readiness.get("connection_ready") or readiness.get("connected") or readiness.get("collector_ready"))
    if not connected:
        raise PermissionError(f"{provider_id} connector is not ready for meeting source ingestion")
    return readiness


def _zoom_event_type(event_type: str) -> str:
    event = event_type.lower()
    if "participant_joined" in event:
        return "participant_joined"
    if "participant_left" in event:
        return "participant_left"
    if "participant_jbh_waiting" in event:
        return "participant_jbh_waiting"
    if "admitted" in event:
        return "waiting_room_admitted"
    if "recording.started" in event:
        return "recording_started"
    if "recording.stopped" in event:
        return "recording_stopped"
    if "recording.completed" in event or "recording_completed" in event:
        return "recording.completed"
    if "transcript" in event:
        return "transcript.created"
    if "sharing_started" in event or "screen_share_started" in event:
        return "screen_share_started"
    if "sharing_ended" in event or "screen_share_stopped" in event:
        return "screen_share_stopped"
    if event.endswith("meeting.started") or "meeting_started" in event:
        return "meeting_started"
    if event.endswith("meeting.ended") or "meeting_ended" in event:
        return "meeting_ended"
    raise ValueError(f"unsupported Zoom meeting webhook event: {event_type or '<event>'}")


def _google_meet_event_type(event_type: str, resource_name: str) -> str:
    text = f"{event_type} {resource_name}".lower()
    if "recording" in text:
        return "recording_available"
    if "transcript" in text:
        return "transcript_available"
    if "participant" in text and ("left" in text or "deleted" in text):
        return "participant_left"
    if "participant" in text:
        return "participant_joined"
    if "ended" in text:
        return "meeting_ended"
    if "started" in text or "conference" in text:
        return "meeting_started"
    raise ValueError(f"unsupported Google Meet event: {event_type or resource_name or '<event>'}")


def _teams_meeting_event_type(notification: dict[str, Any], resource: str) -> str:
    resource_text = resource.lower()
    explicit = str(notification.get("eventType") or notification.get("event_type") or "").lower()
    combined = f"{resource_text} {explicit}"
    if "transcript" in combined:
        return "transcript_available"
    if "recording" in combined:
        return "recording_available"
    if "callrecords" in combined:
        return "meeting_started"
    if "ended" in combined or "callended" in combined:
        return "meeting_ended"
    if "roster" in combined:
        return "participant_joined"
    if "onlinemeeting" in combined or "onlinemeetings" in combined:
        return "meeting_started"
    raise ValueError(f"unsupported Teams meeting Graph notification: {resource or '<resource>'}")


def _webex_event_type(resource: str, event: str, data: dict[str, Any]) -> str:
    text = f"{resource} {event} {data.get('type') or ''}".lower()
    if "transcript" in text:
        return "transcript_available"
    if "recording" in text:
        return "recording_available"
    if "participant" in text and ("left" in text or "deleted" in text):
        return "participant_left"
    if "participant" in text or "membership" in text:
        return "participant_joined"
    if "ended" in text or "deleted" in text or "stopped" in text:
        return "meeting_ended"
    if "meeting" in text or "started" in text or "created" in text:
        return "meeting_started"
    raise ValueError(f"unsupported Webex webhook event: {resource or '<resource>'}:{event or '<event>'}")


def _discord_call_event_type(dispatch_type: str, data: dict[str, Any]) -> str:
    if dispatch_type == "VOICE_STATE_UPDATE":
        if data.get("self_stream"):
            return "screen_share_started"
        if data.get("self_video"):
            return "camera_enabled"
        if data.get("self_mute"):
            return "microphone_muted"
        if data.get("channel_id"):
            return "voice_state_joined"
        return "voice_state_left"
    if dispatch_type in {"VOICE_CHANNEL_EFFECT_SEND", "MESSAGE_REACTION_ADD"}:
        return "reaction_sent"
    raise ValueError(f"unsupported Discord call Gateway event: {dispatch_type or '<event>'}")


def _first_graph_notification(payload: dict[str, Any]) -> dict[str, Any]:
    values = payload.get("value")
    if isinstance(values, list) and values and isinstance(values[0], dict):
        return values[0]
    return payload


def _conference_record_id(name: str) -> str:
    parts = [part for part in name.split("/") if part]
    if "conferenceRecords" in parts:
        index = parts.index("conferenceRecords")
        if index + 1 < len(parts):
            return parts[index + 1]
    return ""


def _last_segment(value: str) -> str:
    parts = [part for part in str(value or "").split("/") if part]
    return parts[-1] if parts else ""


def _provider_id(payload: dict[str, Any]) -> str:
    return _normalize_provider(payload.get("provider_id") or payload.get("provider") or payload.get("app") or payload.get("service"))


def _normalize_provider(value: Any) -> str:
    key = _clean_token(value)
    provider = _PROVIDER_ALIASES.get(key)
    if not provider:
        raise ValueError(f"unsupported meeting provider: {value or '<provider>'}")
    return provider


def _source_event(provider_id: str, payload: dict[str, Any]) -> str:
    explicit = str(payload.get("source_event") or "").strip()
    if explicit:
        return explicit
    event_type = _clean_event_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type"))
    alias = _EVENT_ALIASES.get(event_type)
    if not alias:
        raise ValueError(f"unsupported meeting event mapping: {provider_id}:{event_type or '<event_type>'}")
    return f"{_SOURCE_PREFIXES[provider_id]}_{alias}"


def _object_id(payload: dict[str, Any]) -> str:
    for key in (
        "meeting_id",
        "conference_id",
        "conference_record_id",
        "online_meeting_id",
        "call_id",
        "voice_state_id",
        "channel_id",
        "room_id",
        "recording_id",
        "transcript_id",
        "object_id",
    ):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return ""


def _metadata_from_payload(provider_id: str, payload: dict[str, Any], source_event: str) -> dict[str, Any]:
    entry = meeting_provider_entry(provider_id)
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    clean = dict(metadata)
    clean.update(
        {
            "app": entry.app,
            "source_event": source_event,
            "source_channel": entry.source_channel,
            "implementation_level": entry.implementation_level,
        }
    )
    event_type = _clean_event_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type"))
    if event_type:
        clean["provider_event_type"] = event_type
    for key in (
        "meeting_id",
        "conference_id",
        "conference_record_id",
        "online_meeting_id",
        "call_id",
        "voice_state_id",
        "channel_id",
        "room_id",
        "recording_id",
        "transcript_id",
        "artifact_count",
        "duration_seconds",
        "participant_count",
        "has_recording",
        "has_transcript",
        "has_summary",
        "has_action_items",
        "is_host",
        "is_presenter",
    ):
        if key in payload:
            clean[key] = payload[key]
    return clean


def _append_dead_letter(config: AgentConfig, payload: dict[str, Any], reason: str) -> None:
    normalized = config.normalized()
    path = _dead_letters_path(normalized)
    path.parent.mkdir(parents=True, exist_ok=True)
    event_log = CollectorEventLog(normalized.collector_events_db_path)
    event_log.record_dead_letter(
        consumer="meeting_sources_ingest",
        sequence=0,
        attempts=1,
        error=reason,
        event_payload={
            "source": "meetings",
            "platform": platform.system(),
            "payload_keys": sorted(str(key) for key in payload.keys()),
        },
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{reason}\n")


def _dead_letters_path(config: AgentConfig) -> Path:
    return config.data_dir / "collector_sources" / "meetings" / "dead_letters.jsonl"


def _clean_token(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return "".join(char for char in text if char.isalnum() or char == "_")


def _clean_event_token(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return "".join(char for char in text if char.isalnum() or char in {"_", "."})


__all__ = [
    "append_discord_call_gateway_event",
    "append_google_meet_event",
    "append_meeting_source_event",
    "append_meeting_source_health",
    "append_teams_meeting_graph_event",
    "append_webex_webhook_event",
    "append_zoom_webhook_event",
    "meeting_source_status",
    "read_meeting_source_events",
    "run_meeting_source_tick",
]
