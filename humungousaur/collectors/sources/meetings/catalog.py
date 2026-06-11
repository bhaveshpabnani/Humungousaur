from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MeetingProviderCatalogEntry:
    provider_id: str
    app: str
    display_name: str
    source_type: str
    source_channel: str
    implementation_level: str
    poller_supported: bool = False
    webhook_supported: bool = True
    notes: str = ""
    docs_url: str = ""


@dataclass(frozen=True, slots=True)
class MeetingMappingSpec:
    source_event: str
    collector: str
    stimulus_type: str
    text: str


MEETING_PROVIDER_CATALOG: tuple[MeetingProviderCatalogEntry, ...] = (
    MeetingProviderCatalogEntry(
        provider_id="zoom",
        app="zoom",
        display_name="Zoom",
        source_type="saas_webhook_or_desktop_bridge",
        source_channel="zoom_webhooks+desktop_or_browser_bridge",
        implementation_level="webhook_and_bridge_ingress",
        notes=(
            "Zoom meeting webhooks cover meeting lifecycle, waiting-room, participant, recording, "
            "and recording-completed signals; local/browser bridges provide in-call controls."
        ),
        docs_url="https://developers.zoom.us/docs/api/meetings/events/",
    ),
    MeetingProviderCatalogEntry(
        provider_id="google_workspace",
        app="meet",
        display_name="Google Meet",
        source_type="workspace_api_webhook_or_browser_bridge",
        source_channel="meet_api+workspace_events+browser_extension+calendar_context",
        implementation_level="conference_records_artifacts_and_bridge_ingress",
        poller_supported=True,
        notes=(
            "Google Meet API exposes conference records, participants, recordings, transcripts, "
            "and Workspace Events notifications; browser/add-on ingress provides local controls."
        ),
        docs_url="https://developers.google.com/workspace/meet/api/guides/overview",
    ),
    MeetingProviderCatalogEntry(
        provider_id="microsoft_365",
        app="teams",
        display_name="Microsoft Teams",
        source_type="graph_change_notification_or_app_bridge",
        source_channel="graph_online_meetings+teams_change_notifications+app_bridge",
        implementation_level="graph_artifacts_and_bridge_ingress",
        poller_supported=True,
        notes=(
            "Microsoft Graph exposes Teams online meetings, attendance, transcript, recording, "
            "and change-notification surfaces; Teams app/native bridges provide local controls."
        ),
        docs_url="https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/meeting-transcripts/overview-transcripts",
    ),
    MeetingProviderCatalogEntry(
        provider_id="webex",
        app="webex",
        display_name="Webex",
        source_type="saas_api_webhook_or_desktop_bridge",
        source_channel="webex_meetings_api+webhooks+desktop_or_browser_bridge",
        implementation_level="meetings_api_artifacts_and_bridge_ingress",
        poller_supported=True,
        notes=(
            "Webex Meetings APIs expose meeting metadata, participants, recordings, and meeting "
            "transcripts; local/browser bridges provide in-call controls."
        ),
        docs_url="https://developer.webex.com/docs/api/v1/meeting-transcripts",
    ),
    MeetingProviderCatalogEntry(
        provider_id="discord",
        app="discord_calls",
        display_name="Discord Calls",
        source_type="gateway_event_or_desktop_bridge",
        source_channel="discord_gateway_voice_state+social_sdk+desktop_bridge",
        implementation_level="gateway_voice_state_and_bridge_ingress",
        notes=(
            "Discord Gateway voice-state events expose join, leave, mute, video, and stream state; "
            "summary or transcript availability must come from an opt-in bot or local bridge."
        ),
        docs_url="https://docs.discord.com/developers/resources/voice",
    ),
)


_MEETING_APP_EVENTS: tuple[tuple[str, str, str], ...] = (
    ("joined", "meeting_joined", "meeting_app_activity"),
    ("left", "meeting_left", "meeting_app_activity"),
    ("waiting_room_joined", "waiting_room_joined", "meeting_app_activity"),
    ("waiting_room_admitted", "waiting_room_admitted", "meeting_app_activity"),
    ("participant_joined", "participant_joined", "meeting_app_activity"),
    ("participant_left", "participant_left", "meeting_app_activity"),
    ("breakout_room_joined", "breakout_room_joined", "meeting_app_activity"),
    ("breakout_room_left", "breakout_room_left", "meeting_app_activity"),
    ("recording_started", "meeting_recording_started", "meeting_app_activity"),
    ("recording_stopped", "meeting_recording_stopped", "meeting_app_activity"),
)

_CALL_CONTROL_EVENTS: tuple[tuple[str, str, str], ...] = (
    ("microphone_muted", "microphone_muted", "call_control_activity"),
    ("microphone_unmuted", "microphone_unmuted", "call_control_activity"),
    ("camera_enabled", "camera_enabled", "call_control_activity"),
    ("camera_disabled", "camera_disabled", "call_control_activity"),
    ("hand_raised", "hand_raised", "call_control_activity"),
    ("hand_lowered", "hand_lowered", "call_control_activity"),
    ("reaction_sent", "reaction_sent", "call_control_activity"),
    ("captions_enabled", "captions_enabled", "call_control_activity"),
    ("captions_disabled", "captions_disabled", "call_control_activity"),
    ("meeting_chat_opened", "meeting_chat_opened", "call_control_activity"),
)

_PRESENTATION_EVENTS: tuple[tuple[str, str, str], ...] = (
    ("screen_share_started", "screen_share_started", "meeting_presentation_activity"),
    ("screen_share_stopped", "screen_share_stopped", "meeting_presentation_activity"),
    ("window_share_started", "window_share_started", "meeting_presentation_activity"),
    ("window_share_stopped", "window_share_stopped", "meeting_presentation_activity"),
    ("presentation_started", "presentation_started", "meeting_presentation_activity"),
    ("presentation_stopped", "presentation_stopped", "meeting_presentation_activity"),
    ("presenter_changed", "presenter_changed", "meeting_presentation_activity"),
    ("remote_control_requested", "remote_control_requested", "meeting_presentation_activity"),
    ("remote_control_granted", "remote_control_granted", "meeting_presentation_activity"),
    ("remote_control_revoked", "remote_control_revoked", "meeting_presentation_activity"),
)

_ARTIFACT_EVENTS: tuple[tuple[str, str, str], ...] = (
    ("recording_available", "meeting_recording_available", "meeting_artifact_activity"),
    ("transcript_available", "meeting_transcript_available", "meeting_artifact_activity"),
    ("summary_generated", "meeting_summary_generated", "meeting_artifact_activity"),
    ("action_items_detected", "meeting_action_items_detected", "meeting_artifact_activity"),
    ("notes_shared", "meeting_notes_shared", "meeting_artifact_activity"),
    ("whiteboard_exported", "meeting_whiteboard_exported", "meeting_artifact_activity"),
    ("followup_created", "meeting_followup_created", "meeting_artifact_activity"),
)

_EVENT_GROUPS: tuple[tuple[str, str, str], ...] = (
    *_MEETING_APP_EVENTS,
    *_CALL_CONTROL_EVENTS,
    *_PRESENTATION_EVENTS,
    *_ARTIFACT_EVENTS,
)

_SOURCE_PREFIXES = {
    "zoom": "zoom",
    "google_workspace": "meet",
    "microsoft_365": "teams",
    "webex": "webex",
    "discord": "discord_call",
}

_TEXT_PREFIXES = {
    "zoom": "Zoom",
    "google_workspace": "Google Meet",
    "microsoft_365": "Teams",
    "webex": "Webex",
    "discord": "Discord call",
}


def meeting_mapping_specs(provider_id: str) -> tuple[MeetingMappingSpec, ...]:
    prefix = _SOURCE_PREFIXES[provider_id]
    text_prefix = _TEXT_PREFIXES[provider_id]
    return tuple(
        MeetingMappingSpec(
            source_event=f"{prefix}_{alias}",
            collector=collector,
            stimulus_type=stimulus_type,
            text=f"{text_prefix} {stimulus_type.replace('_', ' ')}",
        )
        for alias, stimulus_type, collector in _EVENT_GROUPS
    )


def meeting_provider_entry(provider_id: str) -> MeetingProviderCatalogEntry:
    for entry in MEETING_PROVIDER_CATALOG:
        if entry.provider_id == provider_id:
            return entry
    raise KeyError(f"unknown meeting provider: {provider_id}")


def meeting_provider_ids() -> tuple[str, ...]:
    return tuple(entry.provider_id for entry in MEETING_PROVIDER_CATALOG)


__all__ = [
    "MEETING_PROVIDER_CATALOG",
    "MeetingMappingSpec",
    "MeetingProviderCatalogEntry",
    "meeting_mapping_specs",
    "meeting_provider_entry",
    "meeting_provider_ids",
]
