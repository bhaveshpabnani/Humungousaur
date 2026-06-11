from __future__ import annotations

from ..workspace_connectors import ConnectorEventMapping
from .common import DeveloperAppCollector


IDE_SOURCE_MANIFESTS = (
    DeveloperAppCollector(
        provider_id="vscode",
        app="VS Code",
        description="VS Code extension events for active editor metadata, saves, diagnostics, tasks, tests, and debug sessions.",
        source_channel="vscode_extension_bridge",
        implementation_level="local_extension_ingress",
        official_docs=(
            "https://code.visualstudio.com/api/references/vscode-api",
            "https://code.visualstudio.com/api/extension-capabilities/overview",
        ),
    ),
    DeveloperAppCollector(
        provider_id="jetbrains",
        app="JetBrains IDEs",
        description="IntelliJ Platform plugin events for active editors, inspections/problems, run configurations, tests, and debugger lifecycle.",
        source_channel="jetbrains_plugin_bridge",
        implementation_level="local_extension_ingress",
        official_docs=(
            "https://plugins.jetbrains.com/docs/intellij/plugin-listeners.html",
            "https://plugins.jetbrains.com/docs/intellij/execution.html",
        ),
    ),
    DeveloperAppCollector(
        provider_id="xcode",
        app="Xcode",
        description="Xcode source-editor extension, xcodebuild, test, and debugger metadata events with paths and diagnostics redacted.",
        source_channel="xcode_extension_or_xcodebuild_bridge",
        implementation_level="local_extension_or_build_log_ingress",
        official_docs=(
            "https://developer.apple.com/documentation/XcodeKit/creating-a-source-editor-extension",
            "https://developer.apple.com/xcode/",
        ),
    ),
)

IDE_EVENT_MAPPINGS = (
    ConnectorEventMapping("active_file_changed", "ide_activity", "file_opened_in_ide", "Active IDE file changed"),
    ConnectorEventMapping("file_opened", "ide_activity", "file_opened_in_ide", "File was opened in IDE"),
    ConnectorEventMapping("file_saved", "file_operation_activity", "file_saved", "File was saved from IDE"),
    ConnectorEventMapping("diagnostic_added", "ide_activity", "diagnostic_added", "IDE diagnostic was added"),
    ConnectorEventMapping("diagnostic_resolved", "ide_activity", "diagnostic_resolved", "IDE diagnostic was resolved"),
    ConnectorEventMapping("breakpoint_hit", "ide_activity", "breakpoint_hit", "IDE breakpoint was hit"),
    ConnectorEventMapping("debug_session_started", "ide_activity", "debug_session_started", "IDE debug session started"),
    ConnectorEventMapping("debugger_attached", "debugger_activity", "debugger_attached", "Debugger attached"),
    ConnectorEventMapping("debugger_detached", "debugger_activity", "debugger_detached", "Debugger detached"),
    ConnectorEventMapping("debugger_paused", "debugger_activity", "debugger_paused", "Debugger paused"),
    ConnectorEventMapping("debugger_resumed", "debugger_activity", "debugger_resumed", "Debugger resumed"),
    ConnectorEventMapping("test_suite_started", "test_runner_activity", "test_suite_started", "IDE test suite started"),
    ConnectorEventMapping("test_suite_completed", "test_runner_activity", "test_suite_completed", "IDE test suite completed"),
    ConnectorEventMapping("test_suite_failed", "test_runner_activity", "test_suite_failed", "IDE test suite failed"),
    ConnectorEventMapping("build_task_started", "build_tool_activity", "build_task_started", "IDE build task started"),
    ConnectorEventMapping("build_task_completed", "build_tool_activity", "build_task_completed", "IDE build task completed"),
    ConnectorEventMapping("build_task_failed", "build_tool_activity", "build_task_failed", "IDE build task failed"),
)
