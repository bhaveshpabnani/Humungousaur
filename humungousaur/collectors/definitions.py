from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CollectorDefinition:
    name: str
    family: str
    source: str
    default_enabled: bool
    sensitive: bool
    status: str
    rate_limit_per_minute: int
    description: str
    stimulus_types: tuple[str, ...]
    rich_capture_required: bool = False
    bridge_supported: bool = False


COLLECTOR_DEFINITIONS: tuple[CollectorDefinition, ...] = (
    CollectorDefinition(
        name="active_window",
        family="system_context",
        source="activity",
        default_enabled=True,
        sensitive=False,
        status="implemented",
        rate_limit_per_minute=6,
        description="Foreground app/window metadata without reading screen contents.",
        stimulus_types=("active_window_changed",),
    ),
    CollectorDefinition(
        name="browser",
        family="browser_context",
        source="browser",
        default_enabled=True,
        sensitive=False,
        status="implemented_best_effort",
        rate_limit_per_minute=6,
        description="Foreground browser URL/title metadata.",
        stimulus_types=("browser_tab_changed",),
    ),
    CollectorDefinition(
        name="clipboard",
        family="user_context",
        source="activity",
        default_enabled=False,
        sensitive=True,
        status="implemented_best_effort",
        rate_limit_per_minute=3,
        description="Clipboard text-change detection with content redacted from attention batches.",
        stimulus_types=("clipboard_changed",),
        rich_capture_required=True,
    ),
    CollectorDefinition(
        name="filesystem",
        family="filesystem",
        source="activity",
        default_enabled=True,
        sensitive=False,
        status="implemented_polling",
        rate_limit_per_minute=10,
        description="Recent file changes under configured watch paths.",
        stimulus_types=("file_changed",),
    ),
    CollectorDefinition(
        name="screenshot",
        family="screen_context",
        source="screen_ocr",
        default_enabled=False,
        sensitive=True,
        status="implemented_opt_in",
        rate_limit_per_minute=2,
        description="Opt-in periodic screenshot capture; raw image is not sent to the LLM attention batch.",
        stimulus_types=("screenshot_captured",),
        rich_capture_required=True,
    ),
    CollectorDefinition(
        name="screen_ocr",
        family="screen_context",
        source="screen_ocr",
        default_enabled=False,
        sensitive=True,
        status="implemented_when_tesseract_or_pillow_available",
        rate_limit_per_minute=2,
        description="Opt-in screen OCR using local capture and OCR tooling.",
        stimulus_types=("screen_text_changed",),
        rich_capture_required=True,
    ),
    CollectorDefinition(
        name="video_frame",
        family="screen_context",
        source="screen_ocr",
        default_enabled=False,
        sensitive=True,
        status="implemented_as_periodic_screen_keyframe",
        rate_limit_per_minute=1,
        description="Opt-in periodic visual keyframe capture.",
        stimulus_types=("video_keyframe_captured",),
        rich_capture_required=True,
    ),
    CollectorDefinition(
        name="audio_activity",
        family="audio",
        source="audio_transcript",
        default_enabled=False,
        sensitive=True,
        status="implemented_when_sounddevice_and_numpy_available",
        rate_limit_per_minute=12,
        description="Local RMS voice activity detection without transcript submission.",
        stimulus_types=("voice_activity_detected",),
        rich_capture_required=True,
    ),
    CollectorDefinition(
        name="input_device",
        family="device_input",
        source="activity",
        default_enabled=False,
        sensitive=False,
        status="implemented_bridge_and_idle_best_effort",
        rate_limit_per_minute=30,
        description="Low-level user input events from a native bridge plus coarse idle/active state; never records typed text.",
        stimulus_types=(
            "mouse_clicked",
            "mouse_double_clicked",
            "mouse_right_clicked",
            "mouse_forward",
            "mouse_back",
            "mouse_scroll_burst",
            "mouse_drag_started",
            "mouse_drag_dropped",
            "trackpad_gesture",
            "keyboard_shortcut_pressed",
            "user_idle_state_changed",
        ),
        bridge_supported=True,
    ),
    CollectorDefinition(
        name="app_lifecycle",
        family="application_lifecycle",
        source="activity",
        default_enabled=False,
        sensitive=False,
        status="implemented_process_snapshot",
        rate_limit_per_minute=20,
        description="Best-effort process/app open and close detection from a local process snapshot.",
        stimulus_types=("app_opened", "app_closed"),
    ),
    CollectorDefinition(
        name="window_lifecycle",
        family="window_lifecycle",
        source="activity",
        default_enabled=False,
        sensitive=False,
        status="implemented_active_window_diff",
        rate_limit_per_minute=12,
        description="Foreground window focus/open-style lifecycle from active-window metadata diffs.",
        stimulus_types=("window_focused", "window_title_changed"),
    ),
    CollectorDefinition(
        name="browser_lifecycle",
        family="browser_lifecycle",
        source="browser",
        default_enabled=False,
        sensitive=False,
        status="implemented_active_tab_diff_bridge_ready",
        rate_limit_per_minute=20,
        description="Browser URL/title lifecycle diffs plus optional extension bridge events for tab opened/closed.",
        stimulus_types=("browser_tab_observed", "browser_url_changed", "browser_title_changed", "browser_tab_opened", "browser_tab_closed"),
        bridge_supported=True,
    ),
    CollectorDefinition(
        name="browser_page_activity",
        family="browser_page",
        source="browser",
        default_enabled=False,
        sensitive=False,
        status="implemented_bridge",
        rate_limit_per_minute=30,
        description="Browser extension bridge events for page actions such as form submit, downloads, selected text, and console errors.",
        stimulus_types=(
            "link_clicked",
            "form_changed",
            "form_submitted",
            "file_uploaded",
            "download_started",
            "download_finished",
            "page_error",
            "console_error",
            "selected_page_text_changed",
        ),
        bridge_supported=True,
    ),
    CollectorDefinition(
        name="terminal_activity",
        family="developer_activity",
        source="activity",
        default_enabled=False,
        sensitive=False,
        status="implemented_bridge",
        rate_limit_per_minute=30,
        description="Shell integration bridge events for command, build, test, and local server status.",
        stimulus_types=(
            "terminal_command_started",
            "terminal_command_finished",
            "terminal_command_failed",
            "build_started",
            "build_failed",
            "tests_started",
            "tests_failed",
            "server_started",
            "server_crashed",
        ),
        bridge_supported=True,
    ),
    CollectorDefinition(
        name="ide_activity",
        family="developer_activity",
        source="activity",
        default_enabled=False,
        sensitive=False,
        status="implemented_bridge",
        rate_limit_per_minute=30,
        description="IDE/editor bridge events for active files, diagnostics, debugging, git branch changes, commits, and merge conflicts.",
        stimulus_types=(
            "file_opened_in_ide",
            "diagnostic_added",
            "diagnostic_resolved",
            "breakpoint_hit",
            "debug_session_started",
            "git_branch_changed",
            "commit_created",
            "merge_conflict_detected",
        ),
        bridge_supported=True,
    ),
)


DEFINITIONS_BY_NAME = {definition.name: definition for definition in COLLECTOR_DEFINITIONS}
DEFAULT_COLLECTORS = {definition.name: definition.default_enabled for definition in COLLECTOR_DEFINITIONS}
SENSITIVE_COLLECTORS = {definition.name for definition in COLLECTOR_DEFINITIONS if definition.sensitive}
DEFAULT_RICH_CAPTURE_OPT_IN = {name: False for name in SENSITIVE_COLLECTORS}
DEFAULT_COLLECTOR_RATE_LIMITS_PER_MINUTE = {
    definition.name: definition.rate_limit_per_minute for definition in COLLECTOR_DEFINITIONS
}
COLLECTOR_SOURCES = {definition.name: definition.source for definition in COLLECTOR_DEFINITIONS}


def collector_capability_records(extra_status: dict[str, dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    extras = extra_status or {}
    records: dict[str, dict[str, Any]] = {}
    for definition in COLLECTOR_DEFINITIONS:
        records[definition.name] = {
            "family": definition.family,
            "source": definition.source,
            "sensitive": definition.sensitive,
            "status": definition.status,
            "default_enabled": definition.default_enabled,
            "rich_capture_required": definition.rich_capture_required,
            "bridge_supported": definition.bridge_supported,
            "rate_limit_per_minute": definition.rate_limit_per_minute,
            "description": definition.description,
            "stimulus_types": list(definition.stimulus_types),
            **extras.get(definition.name, {}),
        }
    return records
