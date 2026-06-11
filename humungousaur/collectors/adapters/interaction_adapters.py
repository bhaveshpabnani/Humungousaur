from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile


DIRECT_USER_STIMULUS_TYPES = {
    "user_text_submitted",
    "global_hotkey_pressed",
    "approval_accepted",
    "approval_rejected",
}
VOICE_WAKEUP_STIMULUS_TYPES = {
    "wake_word_detected",
    "voice_transcript_final",
}
MEETING_AUDIO_STIMULUS_TYPES = {
    "meeting_transcript_chunk",
    "speaker_changed",
    "call_started",
    "call_ended",
}
WAKEUP_STIMULUS_TYPES = {
    "scheduled_wakeup_due",
    "followup_due",
}
CHANNEL_ACTIVITY_STIMULUS_TYPES = {
    "message_received",
    "mention_received",
    "dm_received",
    "thread_reply_received",
    "reaction_added",
    "message_sent",
    "draft_created",
    "call_invite_received",
    "channel_unread_changed",
}


def collect_direct_user(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "direct_user", DIRECT_USER_STIMULUS_TYPES, source="user_text", max_events=20)


def collect_voice_wakeup(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "voice_wakeup", VOICE_WAKEUP_STIMULUS_TYPES, source="voice_transcript", max_events=20)


def collect_meeting_audio(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "meeting_audio", MEETING_AUDIO_STIMULUS_TYPES, source="audio_transcript", max_events=20)


def collect_wakeups(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "wakeups", WAKEUP_STIMULUS_TYPES, source="system", max_events=20)


def collect_channel_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "channel_activity", CHANNEL_ACTIVITY_STIMULUS_TYPES, source="channel_message", max_events=20)
