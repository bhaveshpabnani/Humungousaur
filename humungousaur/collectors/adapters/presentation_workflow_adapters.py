from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile
from ..sources.google_workspace import read_google_workspace_events


PRESENTATION_AUTHORING_ACTIVITY_STIMULUS_TYPES = {
    "slide_created",
    "slide_edited",
    "slide_deleted",
    "slide_duplicated",
    "slide_reordered",
    "speaker_notes_edited",
    "outline_edited",
    "object_inserted",
    "object_edited",
}
PRESENTATION_DESIGN_ACTIVITY_STIMULUS_TYPES = {
    "theme_applied",
    "layout_changed",
    "master_slide_edited",
    "transition_changed",
    "animation_added",
    "animation_removed",
    "media_inserted",
    "chart_inserted",
    "accessibility_check_run",
}
PRESENTATION_DELIVERY_ACTIVITY_STIMULUS_TYPES = {
    "slideshow_started",
    "slideshow_ended",
    "presenter_view_opened",
    "presenter_view_closed",
    "slide_advanced",
    "slide_rewound",
    "laser_pointer_used",
    "rehearsal_started",
    "rehearsal_completed",
}
PRESENTATION_EXPORT_ACTIVITY_STIMULUS_TYPES = {
    "deck_export_started",
    "deck_exported",
    "deck_export_failed",
    "deck_shared",
    "deck_permissions_changed",
    "deck_publish_started",
    "deck_publish_completed",
    "handout_created",
    "recording_exported",
}


def collect_presentation_authoring_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "presentation_authoring_activity", PRESENTATION_AUTHORING_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "presentation_authoring_activity", PRESENTATION_AUTHORING_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_presentation_design_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "presentation_design_activity", PRESENTATION_DESIGN_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "presentation_design_activity", PRESENTATION_DESIGN_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_presentation_delivery_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "presentation_delivery_activity", PRESENTATION_DELIVERY_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "presentation_delivery_activity", PRESENTATION_DELIVERY_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_presentation_export_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "presentation_export_activity", PRESENTATION_EXPORT_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "presentation_export_activity", PRESENTATION_EXPORT_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )
