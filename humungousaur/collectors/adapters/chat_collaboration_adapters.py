from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile


CHAT_COMPOSITION_ACTIVITY_STIMULUS_TYPES = {
    "chat_draft_started",
    "chat_draft_updated",
    "chat_message_sent",
    "chat_message_edited",
    "chat_message_deleted",
    "chat_attachment_added",
    "chat_attachment_removed",
    "slash_command_used",
    "emoji_picker_opened",
}
CHAT_THREAD_ACTIVITY_STIMULUS_TYPES = {
    "thread_opened",
    "thread_followed",
    "thread_muted",
    "thread_reply_started",
    "thread_reply_sent",
    "thread_resolved",
    "thread_saved",
    "thread_unread_changed",
}
CHAT_CHANNEL_NAVIGATION_ACTIVITY_STIMULUS_TYPES = {
    "chat_workspace_switched",
    "chat_channel_opened",
    "chat_channel_joined",
    "chat_channel_left",
    "chat_channel_muted",
    "chat_channel_pinned",
    "chat_channel_search_performed",
    "chat_saved_item_opened",
}
CHAT_PRESENCE_ACTIVITY_STIMULUS_TYPES = {
    "chat_status_changed",
    "chat_status_cleared",
    "presence_changed",
    "do_not_disturb_scheduled",
    "do_not_disturb_enabled",
    "do_not_disturb_disabled",
    "availability_set",
    "notification_preference_changed",
}


def collect_chat_composition_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "chat_composition_activity", CHAT_COMPOSITION_ACTIVITY_STIMULUS_TYPES, source="channel_message", max_events=20)


def collect_chat_thread_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "chat_thread_activity", CHAT_THREAD_ACTIVITY_STIMULUS_TYPES, source="channel_message", max_events=20)


def collect_chat_channel_navigation_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(
        config,
        state,
        "chat_channel_navigation_activity",
        CHAT_CHANNEL_NAVIGATION_ACTIVITY_STIMULUS_TYPES,
        source="channel_message",
        max_events=20,
    )


def collect_chat_presence_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "chat_presence_activity", CHAT_PRESENCE_ACTIVITY_STIMULUS_TYPES, source="channel_message", max_events=20)
