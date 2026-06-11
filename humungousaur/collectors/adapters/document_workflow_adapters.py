from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile
from ..sources.google_workspace import read_google_workspace_events


DOCUMENT_COMPOSITION_ACTIVITY_STIMULUS_TYPES = {
    "document_draft_started",
    "document_edited",
    "document_section_edited",
    "document_outline_updated",
    "document_style_applied",
    "document_template_applied",
    "document_citation_inserted",
    "document_media_inserted",
    "document_saved",
}
DOCUMENT_REVIEW_ACTIVITY_STIMULUS_TYPES = {
    "document_comment_added",
    "document_comment_replied",
    "document_comment_resolved",
    "document_suggestion_received",
    "document_suggestion_accepted",
    "document_suggestion_rejected",
    "tracked_changes_enabled",
    "tracked_changes_disabled",
    "document_review_requested",
    "document_mention_added",
}
DOCUMENT_STRUCTURE_ACTIVITY_STIMULUS_TYPES = {
    "document_heading_changed",
    "document_section_added",
    "document_section_moved",
    "document_page_break_inserted",
    "document_toc_updated",
    "document_footnote_added",
    "document_header_footer_edited",
    "document_outline_opened",
    "document_navigation_pane_used",
}
DOCUMENT_EXPORT_PUBLISH_ACTIVITY_STIMULUS_TYPES = {
    "document_export_started",
    "document_export_completed",
    "document_export_failed",
    "document_print_preview_opened",
    "document_publish_started",
    "document_publish_completed",
    "document_share_link_created",
    "document_permissions_changed",
    "document_submitted",
}


def collect_document_composition_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "document_composition_activity", DOCUMENT_COMPOSITION_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "document_composition_activity", DOCUMENT_COMPOSITION_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_document_review_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "document_review_activity", DOCUMENT_REVIEW_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "document_review_activity", DOCUMENT_REVIEW_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_document_structure_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "document_structure_activity", DOCUMENT_STRUCTURE_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "document_structure_activity", DOCUMENT_STRUCTURE_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_document_export_publish_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "document_export_publish_activity", DOCUMENT_EXPORT_PUBLISH_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config,
        state,
        "document_export_publish_activity",
        DOCUMENT_EXPORT_PUBLISH_ACTIVITY_STIMULUS_TYPES,
        source="activity",
        max_events=20,
    )
