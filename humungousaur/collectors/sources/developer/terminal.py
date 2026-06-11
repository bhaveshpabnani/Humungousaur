from __future__ import annotations

from ..workspace_connectors import ConnectorEventMapping
from .common import DeveloperAppCollector


TERMINAL_SOURCE_MANIFESTS = (
    DeveloperAppCollector(
        provider_id="terminal",
        app="Terminal",
        description="Shell integration events for command lifecycle, build/test delegation, package managers, and local service changes.",
        source_channel="shell_integration_bridge",
        implementation_level="local_shell_hook_ingress",
        official_docs=(
            "https://zsh.sourceforge.io/Doc/Release/Functions.html",
            "https://www.gnu.org/software/bash/manual/bash.html",
        ),
    ),
)

TERMINAL_EVENT_MAPPINGS = (
    ConnectorEventMapping("terminal_command_started", "terminal_activity", "terminal_command_started", "Terminal command started"),
    ConnectorEventMapping("terminal_command_finished", "terminal_activity", "terminal_command_finished", "Terminal command finished"),
    ConnectorEventMapping("terminal_command_failed", "terminal_activity", "terminal_command_failed", "Terminal command failed"),
    ConnectorEventMapping("build_started", "terminal_activity", "build_started", "Terminal build started"),
    ConnectorEventMapping("build_failed", "terminal_activity", "build_failed", "Terminal build failed"),
    ConnectorEventMapping("tests_started", "terminal_activity", "tests_started", "Terminal tests started"),
    ConnectorEventMapping("tests_failed", "terminal_activity", "tests_failed", "Terminal tests failed"),
    ConnectorEventMapping("server_started", "terminal_activity", "server_started", "Terminal local server started"),
    ConnectorEventMapping("server_crashed", "terminal_activity", "server_crashed", "Terminal local server crashed"),
    ConnectorEventMapping("dependency_install_started", "package_manager_activity", "dependency_install_started", "Dependency install started"),
    ConnectorEventMapping("dependency_install_completed", "package_manager_activity", "dependency_install_completed", "Dependency install completed"),
    ConnectorEventMapping("dependency_install_failed", "package_manager_activity", "dependency_install_failed", "Dependency install failed"),
    ConnectorEventMapping("dependency_audit_warning", "package_manager_activity", "dependency_audit_warning", "Dependency audit warning observed"),
    ConnectorEventMapping("lockfile_changed", "package_manager_activity", "lockfile_changed", "Dependency lockfile changed"),
    ConnectorEventMapping("dev_server_started", "local_service_activity", "dev_server_started", "Local dev server started"),
    ConnectorEventMapping("dev_server_stopped", "local_service_activity", "dev_server_stopped", "Local dev server stopped"),
    ConnectorEventMapping("dev_server_crashed", "local_service_activity", "dev_server_crashed", "Local dev server crashed"),
    ConnectorEventMapping("port_conflict_detected", "local_service_activity", "port_conflict_detected", "Local port conflict detected"),
    ConnectorEventMapping("service_health_changed", "local_service_activity", "service_health_changed", "Local service health changed"),
    ConnectorEventMapping("hot_reload_failed", "local_service_activity", "hot_reload_failed", "Hot reload failed"),
)
