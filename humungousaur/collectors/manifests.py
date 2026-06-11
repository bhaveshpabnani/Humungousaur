from __future__ import annotations

import platform
from dataclasses import asdict, dataclass, field
from typing import Any

from humungousaur.config import AgentConfig

from .definitions import COLLECTOR_DEFINITIONS, CollectorDefinition
from .event_log import CollectorEventLog


@dataclass(frozen=True, slots=True)
class CollectorSourceManifest:
    collector: str
    family: str
    source_level: str
    implementation_stage: str
    privacy_tier: str
    bridge_supported: bool
    local_fallbacks: tuple[str, ...] = ()
    recommended_native_helpers: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()
    notes: str = ""
    helper_health: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def collector_source_manifest_records(config: AgentConfig) -> dict[str, dict[str, Any]]:
    health_by_collector: dict[str, list[dict[str, Any]]] = {}
    for helper in CollectorEventLog(config.normalized().collector_events_db_path).helper_health():
        health_by_collector.setdefault(str(helper.get("collector") or ""), []).append(helper)
    return {
        definition.name: _manifest_for_definition(definition, tuple(health_by_collector.get(definition.name, ()))).to_record()
        for definition in COLLECTOR_DEFINITIONS
    }


def _manifest_for_definition(definition: CollectorDefinition, helper_health: tuple[dict[str, Any], ...]) -> CollectorSourceManifest:
    helper_plan = _helper_plan(definition)
    return CollectorSourceManifest(
        collector=definition.name,
        family=definition.family,
        source_level=_source_level(definition),
        implementation_stage=_implementation_stage(definition),
        privacy_tier="sensitive_metadata" if definition.sensitive else "metadata",
        bridge_supported=definition.bridge_supported,
        local_fallbacks=_local_fallbacks(definition),
        recommended_native_helpers=helper_plan["helpers"],
        required_permissions=helper_plan["permissions"],
        notes=helper_plan["notes"],
        helper_health=helper_health,
    )


def _source_level(definition: CollectorDefinition) -> str:
    status = definition.status
    if "native" in status or "fsevents" in status:
        return "native_helper_plus_local_fallback"
    if "polling" in status:
        return "local_polling"
    if "best_effort" in status:
        return "local_best_effort"
    if definition.bridge_supported:
        return "bridge_ingress_contract"
    if status == "implemented":
        return "local_os_state"
    return "contract_only"


def _implementation_stage(definition: CollectorDefinition) -> str:
    status = definition.status
    if status == "implemented":
        return "local_source_ready"
    if "connector_source" in status:
        return "source_ingest_ready"
    if "native" in status or "fsevents" in status:
        return "native_metadata_ready"
    if "polling" in status:
        return "poller_ready"
    if "best_effort" in status:
        return "local_fallback_ready"
    if definition.bridge_supported:
        return "ingress_ready"
    return "contract_only"


def _local_fallbacks(definition: CollectorDefinition) -> tuple[str, ...]:
    status = definition.status
    fallbacks: list[str] = []
    if "polling" in status:
        fallbacks.append("stateful_metadata_polling")
    if "best_effort" in status:
        fallbacks.append("best_effort_os_snapshot")
    if definition.name in {"active_window", "browser"}:
        fallbacks.append("foreground_context_snapshot")
    return tuple(fallbacks)


def _helper_plan(definition: CollectorDefinition) -> dict[str, Any]:
    system = platform.system().lower()
    family = definition.family
    permissions: list[str] = []
    helpers: list[str] = []
    notes = ""

    if family in {"filesystem", "file_activity"}:
        helpers = _platform_helpers(system, "file")
        permissions = _platform_permissions(system, "file")
        notes = "Use kernel/file-manager helpers for high-fidelity file events; keep Python polling as the safe fallback."
    elif family == "workspace_layout":
        helpers = _platform_helpers(system, "workspace")
        permissions = _platform_permissions(system, "workspace")
        notes = "Workspace/layout helpers should emit redacted monitor, geometry, overview, and foreground-app workspace metadata only."
    elif family in {"system_context", "screen_context"}:
        helpers = _platform_helpers(system, "ui")
        permissions = _platform_permissions(system, "ui")
        notes = "UI and window signals should remain metadata-only unless the profile explicitly opts into rich capture."
    elif family in {"browser_context", "browser_memory", "browser_lifecycle", "browser_organization", "browser_page"}:
        helpers = tuple(dict.fromkeys(_platform_helpers(system, "browser") + ("browser_extension", "native_messaging_host")))
        permissions = tuple(dict.fromkeys(_platform_permissions(system, "browser") + ("browser extension permission",)))
        notes = "Browser OS helpers may emit redacted foreground/profile-store metadata; tab, URL, page, and form semantics should come from explicit browser extensions/native messaging."
    elif family in {"developer_activity", "developer_tooling", "database", "cloud_console"}:
        helpers = _platform_helpers(system, "developer")
        permissions = _platform_permissions(system, "developer")
        notes = "Developer workflow helpers emit process/app/window/workspace metadata only; command lines, output, logs, SQL, test names, stack frames, cloud resource IDs, and GitHub content require explicit bridge/tool emitters."
    elif family in {"calendar", "mail", "mail_calendar_workflow"}:
        helpers = _platform_helpers(system, "mail_calendar")
        permissions = _platform_permissions(system, "mail_calendar")
        notes = "Mail/calendar helpers emit app/process/window/store and EventKit count/timing metadata only; message bodies, subjects, attendees, reminder titles, locations, notes, mailbox names, and exact invite/send actions require explicit MailKit/EventKit/app bridge emitters."
    elif family in {"voice", "realtime_collaboration", "communication", "chat_collaboration_workflow"}:
        helpers = tuple(dict.fromkeys(_platform_helpers(system, "communication") + ("app_or_browser_bridge", "native_messaging_host")))
        permissions = tuple(dict.fromkeys(_platform_permissions(system, "communication") + ("app or browser extension permission for message/meeting detail",)))
        notes = "Communication helpers should emit app-specific process, foreground, shortcut, and call-state metadata only; transcripts, message bodies, participants, channels, and meeting titles require explicit app/extension bridges."
    elif family in {"device_session", "peripherals", "media", "resource_pressure", "storage_backup"}:
        helpers = _platform_helpers(system, "device")
        permissions = _platform_permissions(system, "device")
        notes = "Device and resource collectors should prefer OS notifications over polling."
    elif family.startswith("identity") or family in {"platform_privacy", "policy_compliance"}:
        helpers = _platform_helpers(system, "security")
        permissions = _platform_permissions(system, "security")
        notes = "Credential, permission, and policy collectors must emit prompt/action metadata only."
    elif definition.bridge_supported:
        helpers = ("app_or_browser_bridge",)
        notes = "Bridge ingress is supported; the specific app/helper emitter still owns native capture."

    return {"helpers": tuple(helpers), "permissions": tuple(permissions), "notes": notes}


def _platform_helpers(system: str, kind: str) -> tuple[str, ...]:
    plans = {
        "darwin": {
            "file": ("macos_fsevents_helper", "macos_endpoint_security_helper", "macos_finder_accessibility_helper"),
            "ui": ("macos_nsworkspace_helper", "macos_accessibility_helper", "macos_coregraphics_helper", "macos_workspace_layout_helper", "macos_display_metadata_helper"),
            "device": ("macos_iokit_helper", "macos_corebluetooth_helper", "macos_media_remote_helper"),
            "security": ("macos_permissions_helper", "macos_auth_prompt_observer"),
            "browser": ("macos_browser_context_helper",),
            "workspace": ("macos_accessibility_helper", "macos_coregraphics_helper", "macos_nsworkspace_helper"),
            "communication": ("macos_nsworkspace_communication_helper", "macos_accessibility_communication_helper"),
            "developer": ("macos_developer_workflow_helper", "shell_integration", "ide_extension"),
            "mail_calendar": ("macos_mail_calendar_metadata_helper", "eventkit_access", "mailkit_extension"),
        },
        "windows": {
            "file": ("windows_read_directory_changes_helper", "windows_etw_file_helper", "windows_explorer_uia_helper"),
            "ui": ("windows_uia_helper", "windows_winevent_helper"),
            "device": ("windows_wmi_helper", "windows_device_notification_helper", "windows_media_session_helper"),
            "security": ("windows_uac_credential_prompt_helper", "windows_security_center_helper"),
            "browser": ("windows_browser_profile_store_helper", "windows_winevent_browser_helper"),
            "workspace": ("windows_monitor_topology_helper", "windows_winevent_workspace_helper"),
            "communication": ("windows_communication_app_helper", "windows_winevent_communication_helper"),
            "developer": ("windows_process_devtool_helper", "shell_integration", "ide_extension"),
            "mail_calendar": ("windows_mail_calendar_app_helper", "calendar_provider_bridge", "mail_provider_bridge"),
        },
        "linux": {
            "file": ("linux_inotify_helper", "linux_fanotify_helper", "linux_file_manager_extension"),
            "ui": ("linux_dbus_desktop_helper", "linux_at_spi_helper"),
            "device": ("linux_udev_helper", "linux_dbus_power_helper"),
            "security": ("linux_polkit_prompt_helper", "linux_desktop_portal_permissions_helper"),
            "browser": ("browser_extension", "native_messaging_host"),
            "workspace": ("linux_dbus_desktop_helper", "linux_at_spi_helper"),
            "communication": ("linux_dbus_desktop_helper", "linux_at_spi_helper"),
            "developer": ("linux_process_devtool_helper", "shell_integration", "ide_extension"),
            "mail_calendar": ("linux_mail_calendar_app_helper", "calendar_provider_bridge", "mail_provider_bridge"),
        },
    }
    return plans.get(system, plans["linux"]).get(kind, ())


def _platform_permissions(system: str, kind: str) -> tuple[str, ...]:
    plans = {
        "darwin": {
            "file": ("Full Disk Access for broad paths", "Endpoint Security entitlement for open/close auditing"),
            "ui": ("Accessibility permission", "Screen Recording permission for rich capture"),
            "device": ("Bluetooth permission where needed",),
            "security": ("Accessibility permission for prompt metadata",),
            "browser": ("Browser extension permission for page/action detail",),
            "workspace": ("Accessibility permission for window metadata",),
            "communication": ("Accessibility permission for app/window metadata",),
            "developer": ("workspace read permission for metadata signatures",),
            "mail_calendar": ("Calendar permission for EventKit event metadata", "Reminders permission for EventKit reminder metadata", "MailKit extension permission for message/compose detail"),
        },
        "windows": {
            "file": ("Directory read permission", "Admin/audit policy for privileged ETW file access"),
            "ui": ("UI Automation access",),
            "device": ("WMI/device notification access",),
            "security": ("Admin policy only where required",),
            "browser": ("Read access to local browser profile metadata", "UI Automation access for foreground browser windows"),
            "workspace": ("WinEvent foreground/window metadata access", "Monitor topology access"),
            "communication": ("WinEvent foreground/window metadata access", "Optional notification listener permission for notification detail"),
            "developer": ("workspace read permission for metadata signatures",),
            "mail_calendar": ("calendar provider permission", "mail provider or app bridge permission"),
        },
        "linux": {
            "file": ("watch path read permission", "fanotify capabilities where privileged"),
            "ui": ("DBus/AT-SPI access",),
            "device": ("udev monitor access",),
            "security": ("desktop portal/polkit metadata only",),
            "browser": ("Browser extension permission",),
            "workspace": ("DBus/AT-SPI access",),
            "communication": ("DBus/AT-SPI access",),
            "developer": ("workspace read permission for metadata signatures",),
            "mail_calendar": ("calendar provider permission", "mail provider or app bridge permission"),
        },
    }
    return plans.get(system, plans["linux"]).get(kind, ())
