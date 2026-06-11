from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from humungousaur.config import AgentConfig

from .adapters.activity_adapters import collect_browser_page_activity, collect_ide_activity, collect_terminal_activity
from .adapters.app_surface_adapters import (
    collect_ai_assistant_activity,
    collect_file_dialog_activity,
    collect_pdf_activity,
    collect_presentation_activity,
    collect_spreadsheet_activity,
    collect_system_settings_activity,
)
from .adapters.browser_organization_adapters import (
    collect_browser_extension_activity,
    collect_browser_profile_activity,
    collect_browser_tab_group_activity,
    collect_browser_view_mode_activity,
    collect_browser_web_app_activity,
    collect_browser_window_activity,
)
from .adapters.business_operations_adapters import (
    collect_analytics_activity,
    collect_cloud_console_activity,
    collect_crm_activity,
    collect_database_activity,
    collect_incident_activity,
    collect_support_desk_activity,
)
from .adapters.chat_collaboration_adapters import (
    collect_chat_channel_navigation_activity,
    collect_chat_composition_activity,
    collect_chat_presence_activity,
    collect_chat_thread_activity,
)
from .adapters.composition_adapters import (
    collect_dictation_activity,
    collect_text_composition_activity,
    collect_translation_activity,
    collect_writing_assist_activity,
)
from .adapters.content_exchange_adapters import (
    collect_archive_activity,
    collect_camera_capture_activity,
    collect_continuity_activity,
    collect_file_transfer_activity,
)
from .adapters.context_adapters import collect_active_window, collect_browser_context
from .adapters.credential_adapters import (
    collect_autofill_activity,
    collect_credential_activity,
    collect_passkey_activity,
    collect_verification_code_activity,
)
from .adapters.developer_tooling_adapters import (
    collect_build_tool_activity,
    collect_code_hosting_activity,
    collect_debugger_activity,
    collect_local_service_activity,
    collect_package_manager_activity,
    collect_test_runner_activity,
)
from .adapters.document_workflow_adapters import (
    collect_document_composition_activity,
    collect_document_export_publish_activity,
    collect_document_review_activity,
    collect_document_structure_activity,
)
from .adapters.environment_adapters import (
    collect_device_state,
    collect_downloads,
    collect_git_activity,
    collect_github_activity,
    collect_share_activity,
    collect_visual_state,
)
from .adapters.file_activity_adapters import (
    collect_file_operation_activity,
    collect_file_preview_activity,
    collect_folder_navigation_activity,
    collect_trash_activity,
)
from .adapters.filesystem_adapters import collect_filesystem
from .adapters.input_services_adapters import (
    collect_ime_activity,
    collect_keyboard_input_activity,
    collect_pasteboard_workflow_activity,
    collect_text_input_surface_activity,
)
from .adapters.interaction_adapters import (
    collect_channel_activity,
    collect_direct_user,
    collect_meeting_audio,
    collect_voice_wakeup,
    collect_wakeups,
)
from .adapters.local_context_adapters import (
    collect_audio_activity,
    collect_clipboard,
    collect_screen_ocr,
    collect_screenshot,
    collect_video_frame,
)
from .adapters.mail_calendar_workflow_adapters import (
    collect_calendar_scheduling_activity,
    collect_mail_composition_activity,
    collect_mail_organization_activity,
    collect_reminder_todo_activity,
)
from .adapters.os_activity_adapters import (
    collect_focus_task_activity,
    collect_media_activity,
    collect_peripheral_activity,
    collect_print_scan_activity,
    collect_search_activity,
    collect_software_activity,
)
from .adapters.personal_workflow_adapters import (
    collect_bookmark_history_activity,
    collect_commerce_activity,
    collect_contact_activity,
    collect_finance_activity,
    collect_notes_activity,
    collect_social_feed_activity,
)
from .adapters.planning_collaboration_adapters import (
    collect_form_survey_activity,
    collect_issue_tracker_activity,
    collect_knowledge_base_activity,
    collect_learning_activity,
    collect_task_manager_activity,
    collect_whiteboard_activity,
)
from .adapters.platform_context_adapters import (
    collect_location_activity,
    collect_permission_activity,
    collect_policy_activity,
    collect_resource_activity,
    collect_storage_activity,
    collect_wellbeing_activity,
)
from .adapters.presentation_workflow_adapters import (
    collect_presentation_authoring_activity,
    collect_presentation_delivery_activity,
    collect_presentation_design_activity,
    collect_presentation_export_activity,
)
from .adapters.productivity_adapters import (
    collect_accessibility_context,
    collect_agent_runtime,
    collect_calendar_activity,
    collect_communication_activity,
    collect_creative_activity,
    collect_document_activity,
    collect_mail_activity,
    collect_notification_activity,
    collect_security_context,
)
from .adapters.realtime_collaboration_adapters import (
    collect_call_control_activity,
    collect_meeting_app_activity,
    collect_meeting_artifact_activity,
    collect_meeting_presentation_activity,
)
from .adapters.spreadsheet_workflow_adapters import (
    collect_spreadsheet_data_analysis_activity,
    collect_spreadsheet_editing_activity,
    collect_spreadsheet_formula_activity,
    collect_spreadsheet_import_export_activity,
)
from .adapters.system_surface_adapters import (
    collect_dock_taskbar_activity,
    collect_menu_bar_tray_activity,
    collect_quick_settings_activity,
    collect_widget_activity,
)
from .adapters.ui_operation_adapters import (
    collect_command_activity,
    collect_edit_history_activity,
    collect_navigation_activity,
    collect_selection_activity,
)
from .adapters.workflow_environment_adapters import (
    collect_auth_activity,
    collect_automation_activity,
    collect_cloud_sync_activity,
    collect_network_activity,
    collect_remote_session_activity,
    collect_virtual_runtime_activity,
)
from .adapters.workspace_layout_adapters import (
    collect_app_workspace_activity,
    collect_display_arrangement_activity,
    collect_window_arrangement_activity,
    collect_workspace_layout_activity,
)
from .definitions import DEFINITIONS_BY_NAME
from .lifecycle import collect_app_lifecycle, collect_browser_lifecycle, collect_input_device, collect_window_lifecycle
from .models import CollectorEvent, CollectorProfile


CollectorFunction = Callable[[AgentConfig, CollectorProfile, dict[str, Any]], list[CollectorEvent]]


@dataclass(frozen=True, slots=True)
class CollectorRegistration:
    name: str
    collect: CollectorFunction


class CollectorRegistry:
    def __init__(self) -> None:
        self._registrations: dict[str, CollectorRegistration] = {}

    def register(self, name: str, collect: CollectorFunction) -> None:
        cleaned = str(name or "").strip()
        if not cleaned:
            raise ValueError("collector registration requires a name")
        if cleaned not in DEFINITIONS_BY_NAME:
            raise ValueError(f"collector registration has no definition: {cleaned}")
        if cleaned in self._registrations:
            raise ValueError(f"duplicate collector registration: {cleaned}")
        self._registrations[cleaned] = CollectorRegistration(cleaned, collect)

    def get(self, name: str) -> CollectorFunction | None:
        registration = self._registrations.get(name)
        return registration.collect if registration is not None else None

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._registrations))

    def validate_complete(self) -> list[str]:
        return sorted(name for name in DEFINITIONS_BY_NAME if name not in self._registrations)

    def as_dict(self) -> dict[str, CollectorFunction]:
        return {name: registration.collect for name, registration in self._registrations.items()}


def build_default_collector_registry() -> CollectorRegistry:
    registry = CollectorRegistry()
    for name, collect in _DEFAULT_COLLECTORS.items():
        registry.register(name, collect)
    return registry


_DEFAULT_COLLECTORS: dict[str, CollectorFunction] = {
    "direct_user": collect_direct_user,
    "active_window": collect_active_window,
    "browser": collect_browser_context,
    "clipboard": collect_clipboard,
    "filesystem": collect_filesystem,
    "downloads": collect_downloads,
    "file_operation_activity": collect_file_operation_activity,
    "folder_navigation_activity": collect_folder_navigation_activity,
    "file_preview_activity": collect_file_preview_activity,
    "trash_activity": collect_trash_activity,
    "screenshot": collect_screenshot,
    "screen_ocr": collect_screen_ocr,
    "video_frame": collect_video_frame,
    "visual_state": collect_visual_state,
    "audio_activity": collect_audio_activity,
    "voice_wakeup": collect_voice_wakeup,
    "meeting_audio": collect_meeting_audio,
    "meeting_app_activity": collect_meeting_app_activity,
    "call_control_activity": collect_call_control_activity,
    "meeting_presentation_activity": collect_meeting_presentation_activity,
    "meeting_artifact_activity": collect_meeting_artifact_activity,
    "device_state": collect_device_state,
    "software_activity": collect_software_activity,
    "print_scan_activity": collect_print_scan_activity,
    "search_activity": collect_search_activity,
    "peripheral_activity": collect_peripheral_activity,
    "media_activity": collect_media_activity,
    "focus_task_activity": collect_focus_task_activity,
    "workspace_layout_activity": collect_workspace_layout_activity,
    "window_arrangement_activity": collect_window_arrangement_activity,
    "display_arrangement_activity": collect_display_arrangement_activity,
    "app_workspace_activity": collect_app_workspace_activity,
    "cloud_sync_activity": collect_cloud_sync_activity,
    "auth_activity": collect_auth_activity,
    "credential_activity": collect_credential_activity,
    "passkey_activity": collect_passkey_activity,
    "autofill_activity": collect_autofill_activity,
    "verification_code_activity": collect_verification_code_activity,
    "network_activity": collect_network_activity,
    "automation_activity": collect_automation_activity,
    "virtual_runtime_activity": collect_virtual_runtime_activity,
    "remote_session_activity": collect_remote_session_activity,
    "permission_activity": collect_permission_activity,
    "location_activity": collect_location_activity,
    "resource_activity": collect_resource_activity,
    "storage_activity": collect_storage_activity,
    "wellbeing_activity": collect_wellbeing_activity,
    "policy_activity": collect_policy_activity,
    "notes_activity": collect_notes_activity,
    "bookmark_history_activity": collect_bookmark_history_activity,
    "contact_activity": collect_contact_activity,
    "commerce_activity": collect_commerce_activity,
    "finance_activity": collect_finance_activity,
    "social_feed_activity": collect_social_feed_activity,
    "task_manager_activity": collect_task_manager_activity,
    "issue_tracker_activity": collect_issue_tracker_activity,
    "knowledge_base_activity": collect_knowledge_base_activity,
    "whiteboard_activity": collect_whiteboard_activity,
    "form_survey_activity": collect_form_survey_activity,
    "learning_activity": collect_learning_activity,
    "crm_activity": collect_crm_activity,
    "support_desk_activity": collect_support_desk_activity,
    "analytics_activity": collect_analytics_activity,
    "database_activity": collect_database_activity,
    "cloud_console_activity": collect_cloud_console_activity,
    "incident_activity": collect_incident_activity,
    "ai_assistant_activity": collect_ai_assistant_activity,
    "pdf_activity": collect_pdf_activity,
    "spreadsheet_activity": collect_spreadsheet_activity,
    "presentation_activity": collect_presentation_activity,
    "spreadsheet_editing_activity": collect_spreadsheet_editing_activity,
    "spreadsheet_formula_activity": collect_spreadsheet_formula_activity,
    "spreadsheet_data_analysis_activity": collect_spreadsheet_data_analysis_activity,
    "spreadsheet_import_export_activity": collect_spreadsheet_import_export_activity,
    "presentation_authoring_activity": collect_presentation_authoring_activity,
    "presentation_design_activity": collect_presentation_design_activity,
    "presentation_delivery_activity": collect_presentation_delivery_activity,
    "presentation_export_activity": collect_presentation_export_activity,
    "file_dialog_activity": collect_file_dialog_activity,
    "system_settings_activity": collect_system_settings_activity,
    "text_composition_activity": collect_text_composition_activity,
    "dictation_activity": collect_dictation_activity,
    "writing_assist_activity": collect_writing_assist_activity,
    "translation_activity": collect_translation_activity,
    "file_transfer_activity": collect_file_transfer_activity,
    "archive_activity": collect_archive_activity,
    "camera_capture_activity": collect_camera_capture_activity,
    "continuity_activity": collect_continuity_activity,
    "command_activity": collect_command_activity,
    "selection_activity": collect_selection_activity,
    "navigation_activity": collect_navigation_activity,
    "edit_history_activity": collect_edit_history_activity,
    "dock_taskbar_activity": collect_dock_taskbar_activity,
    "menu_bar_tray_activity": collect_menu_bar_tray_activity,
    "quick_settings_activity": collect_quick_settings_activity,
    "widget_activity": collect_widget_activity,
    "input_device": collect_input_device,
    "keyboard_input_activity": collect_keyboard_input_activity,
    "ime_activity": collect_ime_activity,
    "text_input_surface_activity": collect_text_input_surface_activity,
    "pasteboard_workflow_activity": collect_pasteboard_workflow_activity,
    "app_lifecycle": collect_app_lifecycle,
    "window_lifecycle": collect_window_lifecycle,
    "browser_lifecycle": collect_browser_lifecycle,
    "browser_window_activity": collect_browser_window_activity,
    "browser_tab_group_activity": collect_browser_tab_group_activity,
    "browser_profile_activity": collect_browser_profile_activity,
    "browser_extension_activity": collect_browser_extension_activity,
    "browser_web_app_activity": collect_browser_web_app_activity,
    "browser_view_mode_activity": collect_browser_view_mode_activity,
    "browser_page_activity": collect_browser_page_activity,
    "terminal_activity": collect_terminal_activity,
    "ide_activity": collect_ide_activity,
    "package_manager_activity": collect_package_manager_activity,
    "build_tool_activity": collect_build_tool_activity,
    "test_runner_activity": collect_test_runner_activity,
    "local_service_activity": collect_local_service_activity,
    "debugger_activity": collect_debugger_activity,
    "git_activity": collect_git_activity,
    "github_activity": collect_github_activity,
    "code_hosting_activity": collect_code_hosting_activity,
    "accessibility_context": collect_accessibility_context,
    "notification_activity": collect_notification_activity,
    "share_activity": collect_share_activity,
    "calendar_activity": collect_calendar_activity,
    "wakeups": collect_wakeups,
    "calendar_scheduling_activity": collect_calendar_scheduling_activity,
    "reminder_todo_activity": collect_reminder_todo_activity,
    "channel_activity": collect_channel_activity,
    "communication_activity": collect_communication_activity,
    "chat_composition_activity": collect_chat_composition_activity,
    "chat_thread_activity": collect_chat_thread_activity,
    "chat_channel_navigation_activity": collect_chat_channel_navigation_activity,
    "chat_presence_activity": collect_chat_presence_activity,
    "mail_activity": collect_mail_activity,
    "mail_composition_activity": collect_mail_composition_activity,
    "mail_organization_activity": collect_mail_organization_activity,
    "document_composition_activity": collect_document_composition_activity,
    "document_review_activity": collect_document_review_activity,
    "document_structure_activity": collect_document_structure_activity,
    "document_export_publish_activity": collect_document_export_publish_activity,
    "document_activity": collect_document_activity,
    "creative_activity": collect_creative_activity,
    "security_context": collect_security_context,
    "agent_runtime": collect_agent_runtime,
}


collector_registry = build_default_collector_registry()
