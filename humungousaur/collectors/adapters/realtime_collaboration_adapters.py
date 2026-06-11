from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile
from ..sources.google_workspace import read_google_workspace_events


MEETING_APP_ACTIVITY_STIMULUS_TYPES = {
    "meeting_joined",
    "meeting_left",
    "waiting_room_joined",
    "waiting_room_admitted",
    "participant_joined",
    "participant_left",
    "breakout_room_joined",
    "breakout_room_left",
    "meeting_recording_started",
    "meeting_recording_stopped",
}
CALL_CONTROL_ACTIVITY_STIMULUS_TYPES = {
    "microphone_muted",
    "microphone_unmuted",
    "camera_enabled",
    "camera_disabled",
    "hand_raised",
    "hand_lowered",
    "reaction_sent",
    "captions_enabled",
    "captions_disabled",
    "meeting_chat_opened",
}
MEETING_PRESENTATION_ACTIVITY_STIMULUS_TYPES = {
    "screen_share_started",
    "screen_share_stopped",
    "window_share_started",
    "window_share_stopped",
    "presentation_started",
    "presentation_stopped",
    "presenter_changed",
    "remote_control_requested",
    "remote_control_granted",
    "remote_control_revoked",
}
MEETING_ARTIFACT_ACTIVITY_STIMULUS_TYPES = {
    "meeting_recording_available",
    "meeting_transcript_available",
    "meeting_summary_generated",
    "meeting_action_items_detected",
    "meeting_notes_shared",
    "meeting_whiteboard_exported",
    "meeting_followup_created",
}


def collect_meeting_app_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "meeting_app_activity", MEETING_APP_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "meeting_app_activity", MEETING_APP_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_call_control_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "call_control_activity", CALL_CONTROL_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "call_control_activity", CALL_CONTROL_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_meeting_presentation_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "meeting_presentation_activity", MEETING_PRESENTATION_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "meeting_presentation_activity", MEETING_PRESENTATION_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_meeting_artifact_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "meeting_artifact_activity", MEETING_ARTIFACT_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "meeting_artifact_activity", MEETING_ARTIFACT_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )
