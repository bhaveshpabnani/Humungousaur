from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile


FILE_TRANSFER_ACTIVITY_STIMULUS_TYPES = {
    "upload_started",
    "upload_completed",
    "upload_failed",
    "file_transfer_started",
    "file_transfer_completed",
    "file_transfer_failed",
    "airdrop_sent",
    "airdrop_received",
    "nearby_share_sent",
    "nearby_share_received",
    "network_share_connected",
    "network_share_disconnected",
}
ARCHIVE_ACTIVITY_STIMULUS_TYPES = {
    "archive_created",
    "archive_extracted",
    "compression_started",
    "compression_failed",
    "extraction_started",
    "extraction_failed",
    "archive_encrypted",
    "archive_password_requested",
}
CAMERA_CAPTURE_ACTIVITY_STIMULUS_TYPES = {
    "camera_capture_started",
    "camera_capture_stopped",
    "photo_captured",
    "photo_imported",
    "video_recording_started",
    "video_recording_stopped",
    "qr_code_scanned",
}
CONTINUITY_ACTIVITY_STIMULUS_TYPES = {
    "handoff_started",
    "handoff_completed",
    "universal_clipboard_received",
    "phone_call_relay_started",
    "phone_call_relay_ended",
    "sms_relay_received",
    "mobile_hotspot_connected",
    "mobile_hotspot_disconnected",
}


def collect_file_transfer_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "file_transfer_activity", FILE_TRANSFER_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_archive_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "archive_activity", ARCHIVE_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_camera_capture_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "camera_capture_activity", CAMERA_CAPTURE_ACTIVITY_STIMULUS_TYPES, source="screen_ocr", max_events=20)


def collect_continuity_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "continuity_activity", CONTINUITY_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)
