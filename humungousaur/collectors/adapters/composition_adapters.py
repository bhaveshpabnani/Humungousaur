from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile


TEXT_COMPOSITION_ACTIVITY_STIMULUS_TYPES = {
    "composition_started",
    "composition_submitted",
    "composition_abandoned",
    "draft_autosaved",
    "snippet_inserted",
    "template_inserted",
    "text_expansion_used",
}
DICTATION_ACTIVITY_STIMULUS_TYPES = {
    "dictation_started",
    "dictation_stopped",
    "dictation_transcript_ready",
    "dictation_error",
    "voice_typing_started",
    "voice_typing_stopped",
}
WRITING_ASSIST_ACTIVITY_STIMULUS_TYPES = {
    "spellcheck_suggestion_shown",
    "spellcheck_suggestion_accepted",
    "grammar_suggestion_shown",
    "grammar_suggestion_accepted",
    "autocorrect_applied",
    "predictive_text_accepted",
    "rewrite_suggestion_accepted",
}
TRANSLATION_ACTIVITY_STIMULUS_TYPES = {
    "translation_offered",
    "translation_requested",
    "translation_completed",
    "translation_failed",
    "language_detected",
    "translated_text_inserted",
}


def collect_text_composition_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "text_composition_activity", TEXT_COMPOSITION_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_dictation_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "dictation_activity", DICTATION_ACTIVITY_STIMULUS_TYPES, source="audio_transcript", max_events=20)


def collect_writing_assist_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "writing_assist_activity", WRITING_ASSIST_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_translation_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "translation_activity", TRANSLATION_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)
