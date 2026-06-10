from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from .bridge import read_bridge_events
from .models import CollectorEvent, CollectorProfile


BROWSER_PAGE_STIMULUS_TYPES = {
    "link_clicked",
    "form_changed",
    "form_submitted",
    "file_uploaded",
    "download_started",
    "download_finished",
    "page_error",
    "console_error",
    "selected_page_text_changed",
}
TERMINAL_STIMULUS_TYPES = {
    "terminal_command_started",
    "terminal_command_finished",
    "terminal_command_failed",
    "build_started",
    "build_failed",
    "tests_started",
    "tests_failed",
    "server_started",
    "server_crashed",
}
IDE_STIMULUS_TYPES = {
    "file_opened_in_ide",
    "diagnostic_added",
    "diagnostic_resolved",
    "breakpoint_hit",
    "debug_session_started",
    "git_branch_changed",
    "commit_created",
    "merge_conflict_detected",
}


def collect_browser_page_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(
        config,
        state,
        "browser_page_activity",
        BROWSER_PAGE_STIMULUS_TYPES,
        source="browser",
        max_events=20,
    )


def collect_terminal_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(
        config,
        state,
        "terminal_activity",
        TERMINAL_STIMULUS_TYPES,
        source="activity",
        max_events=20,
    )


def collect_ide_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(
        config,
        state,
        "ide_activity",
        IDE_STIMULUS_TYPES,
        source="activity",
        max_events=20,
    )
