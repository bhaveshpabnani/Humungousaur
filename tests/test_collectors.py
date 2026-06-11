import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import humungousaur.collectors.lifecycle as lifecycle_collectors
import humungousaur.collectors.adapters.local_context_adapters as local_context_collectors
from humungousaur.collectors import (
    append_ai_assistant_event,
    append_ai_assistant_health,
    append_browser_event,
    append_browser_health,
    append_communication_event,
    append_google_workspace_event,
    append_google_workspace_health,
    append_planning_event,
    append_bridge_event,
    collector_status,
    query_collector_events,
    run_connector_source_tick,
    run_collector_tick,
    save_collector_profile,
)
from humungousaur.config import AgentConfig
from humungousaur.collectors.definitions import COLLECTOR_DEFINITIONS
from humungousaur.collectors.registry import collector_registry
from humungousaur.memory.event_store import EventStore
from humungousaur.tools.activity.implementation import ActivityPolicyStore, activity_policy_path


class CollectorTests(unittest.TestCase):
    def test_collector_definitions_are_wired_to_manager_registry(self) -> None:
        missing = [definition.name for definition in COLLECTOR_DEFINITIONS if collector_registry.get(definition.name) is None]

        self.assertEqual(missing, [])

    def test_collector_profile_persists_safe_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config = AgentConfig(workspace=root / "workspace", data_dir=root / "data", planner_provider="explicit").normalized()
            profile = save_collector_profile(
                config,
                {
                    "enabled": True,
                    "collectors": {"clipboard": True, "screenshot": False},
                    "poll_seconds": 2,
                    "watch_paths": [str(config.workspace)],
                },
            )

            status = collector_status(config)

        self.assertTrue(profile.enabled)
        self.assertTrue(status["profile"]["collectors"]["clipboard"])
        self.assertFalse(status["profile"]["collectors"]["screenshot"])
        self.assertEqual(status["profile"]["privacy_mode"], "privacy_first")
        self.assertFalse(status["profile"]["rich_capture_opt_in"]["clipboard"])
        self.assertIn("audio_activity", status["capabilities"]["collectors"])
        self.assertEqual(status["capabilities"]["source_manifests"]["browser_page_activity"]["implementation_stage"], "native_metadata_ready")
        self.assertEqual(status["capabilities"]["source_manifests"]["direct_user"]["implementation_stage"], "ingress_ready")
        self.assertIn("input_device", status["capabilities"]["collectors"])
        self.assertIn("keyboard_input_activity", status["capabilities"]["collectors"])
        self.assertIn("ime_activity", status["capabilities"]["collectors"])
        self.assertIn("text_input_surface_activity", status["capabilities"]["collectors"])
        self.assertIn("pasteboard_workflow_activity", status["capabilities"]["collectors"])
        self.assertIn("browser_lifecycle", status["capabilities"]["collectors"])
        self.assertIn("browser_window_activity", status["capabilities"]["collectors"])
        self.assertIn("browser_tab_group_activity", status["capabilities"]["collectors"])
        self.assertIn("browser_profile_activity", status["capabilities"]["collectors"])
        self.assertIn("browser_extension_activity", status["capabilities"]["collectors"])
        self.assertIn("browser_web_app_activity", status["capabilities"]["collectors"])
        self.assertIn("browser_view_mode_activity", status["capabilities"]["collectors"])
        self.assertIn("browser_page_activity", status["capabilities"]["collectors"])
        self.assertIn("terminal_activity", status["capabilities"]["collectors"])
        self.assertIn("ide_activity", status["capabilities"]["collectors"])
        self.assertIn("package_manager_activity", status["capabilities"]["collectors"])
        self.assertIn("build_tool_activity", status["capabilities"]["collectors"])
        self.assertIn("test_runner_activity", status["capabilities"]["collectors"])
        self.assertIn("local_service_activity", status["capabilities"]["collectors"])
        self.assertIn("debugger_activity", status["capabilities"]["collectors"])
        self.assertIn("accessibility_context", status["capabilities"]["collectors"])
        self.assertIn("notification_activity", status["capabilities"]["collectors"])
        self.assertIn("calendar_activity", status["capabilities"]["collectors"])
        self.assertIn("calendar_scheduling_activity", status["capabilities"]["collectors"])
        self.assertIn("reminder_todo_activity", status["capabilities"]["collectors"])
        self.assertIn("communication_activity", status["capabilities"]["collectors"])
        self.assertIn("security_context", status["capabilities"]["collectors"])
        self.assertIn("device_state", status["capabilities"]["collectors"])
        self.assertIn("software_activity", status["capabilities"]["collectors"])
        self.assertIn("print_scan_activity", status["capabilities"]["collectors"])
        self.assertIn("search_activity", status["capabilities"]["collectors"])
        self.assertIn("peripheral_activity", status["capabilities"]["collectors"])
        self.assertIn("media_activity", status["capabilities"]["collectors"])
        self.assertIn("focus_task_activity", status["capabilities"]["collectors"])
        self.assertIn("cloud_sync_activity", status["capabilities"]["collectors"])
        self.assertIn("auth_activity", status["capabilities"]["collectors"])
        self.assertIn("network_activity", status["capabilities"]["collectors"])
        self.assertIn("automation_activity", status["capabilities"]["collectors"])
        self.assertIn("virtual_runtime_activity", status["capabilities"]["collectors"])
        self.assertIn("remote_session_activity", status["capabilities"]["collectors"])
        self.assertIn("permission_activity", status["capabilities"]["collectors"])
        self.assertIn("location_activity", status["capabilities"]["collectors"])
        self.assertIn("resource_activity", status["capabilities"]["collectors"])
        self.assertIn("storage_activity", status["capabilities"]["collectors"])
        self.assertIn("wellbeing_activity", status["capabilities"]["collectors"])
        self.assertIn("policy_activity", status["capabilities"]["collectors"])
        self.assertIn("notes_activity", status["capabilities"]["collectors"])
        self.assertIn("bookmark_history_activity", status["capabilities"]["collectors"])
        self.assertIn("contact_activity", status["capabilities"]["collectors"])
        self.assertIn("commerce_activity", status["capabilities"]["collectors"])
        self.assertIn("finance_activity", status["capabilities"]["collectors"])
        self.assertIn("social_feed_activity", status["capabilities"]["collectors"])
        self.assertIn("task_manager_activity", status["capabilities"]["collectors"])
        self.assertIn("issue_tracker_activity", status["capabilities"]["collectors"])
        self.assertIn("knowledge_base_activity", status["capabilities"]["collectors"])
        self.assertIn("whiteboard_activity", status["capabilities"]["collectors"])
        self.assertIn("form_survey_activity", status["capabilities"]["collectors"])
        self.assertIn("learning_activity", status["capabilities"]["collectors"])
        self.assertIn("crm_activity", status["capabilities"]["collectors"])
        self.assertIn("support_desk_activity", status["capabilities"]["collectors"])
        self.assertIn("analytics_activity", status["capabilities"]["collectors"])
        self.assertIn("database_activity", status["capabilities"]["collectors"])
        self.assertIn("cloud_console_activity", status["capabilities"]["collectors"])
        self.assertIn("incident_activity", status["capabilities"]["collectors"])
        self.assertIn("file_operation_activity", status["capabilities"]["collectors"])
        self.assertIn("folder_navigation_activity", status["capabilities"]["collectors"])
        self.assertIn("file_preview_activity", status["capabilities"]["collectors"])
        self.assertIn("trash_activity", status["capabilities"]["collectors"])
        file_source_status = status["capabilities"]["collectors"]["file_operation_activity"]["source_status"]
        self.assertIn("directory_metadata_polling", file_source_status["local_fallbacks"])
        self.assertIn("recommended_native_emitters", file_source_status)
        self.assertIn("implemented_native_emitters", file_source_status)
        if file_source_status["platform"] == "Darwin":
            self.assertIn("directory_changes", file_source_status["implemented_native_emitters"])
        self.assertIn("file_preview_activity", file_source_status["bridge_only_until_emitter_exists"])
        self.assertIn("credential_activity", status["capabilities"]["collectors"])
        self.assertIn("passkey_activity", status["capabilities"]["collectors"])
        self.assertIn("autofill_activity", status["capabilities"]["collectors"])
        self.assertIn("verification_code_activity", status["capabilities"]["collectors"])
        self.assertIn("ai_assistant_activity", status["capabilities"]["collectors"])
        self.assertIn("pdf_activity", status["capabilities"]["collectors"])
        self.assertIn("spreadsheet_activity", status["capabilities"]["collectors"])
        self.assertIn("presentation_activity", status["capabilities"]["collectors"])
        self.assertIn("file_dialog_activity", status["capabilities"]["collectors"])
        self.assertIn("system_settings_activity", status["capabilities"]["collectors"])
        self.assertIn("text_composition_activity", status["capabilities"]["collectors"])
        self.assertIn("dictation_activity", status["capabilities"]["collectors"])
        self.assertIn("writing_assist_activity", status["capabilities"]["collectors"])
        self.assertIn("translation_activity", status["capabilities"]["collectors"])
        self.assertIn("workspace_layout_activity", status["capabilities"]["collectors"])
        self.assertIn("window_arrangement_activity", status["capabilities"]["collectors"])
        self.assertIn("display_arrangement_activity", status["capabilities"]["collectors"])
        self.assertIn("app_workspace_activity", status["capabilities"]["collectors"])
        self.assertIn("file_transfer_activity", status["capabilities"]["collectors"])
        self.assertIn("archive_activity", status["capabilities"]["collectors"])
        self.assertIn("camera_capture_activity", status["capabilities"]["collectors"])
        self.assertIn("continuity_activity", status["capabilities"]["collectors"])
        self.assertIn("command_activity", status["capabilities"]["collectors"])
        self.assertIn("selection_activity", status["capabilities"]["collectors"])
        self.assertIn("navigation_activity", status["capabilities"]["collectors"])
        self.assertIn("edit_history_activity", status["capabilities"]["collectors"])
        self.assertIn("dock_taskbar_activity", status["capabilities"]["collectors"])
        self.assertIn("menu_bar_tray_activity", status["capabilities"]["collectors"])
        self.assertIn("quick_settings_activity", status["capabilities"]["collectors"])
        self.assertIn("widget_activity", status["capabilities"]["collectors"])
        self.assertIn("visual_state", status["capabilities"]["collectors"])
        self.assertIn("share_activity", status["capabilities"]["collectors"])
        self.assertIn("downloads", status["capabilities"]["collectors"])
        self.assertIn("git_activity", status["capabilities"]["collectors"])
        self.assertIn("github_activity", status["capabilities"]["collectors"])
        self.assertIn("direct_user", status["capabilities"]["collectors"])
        self.assertIn("voice_wakeup", status["capabilities"]["collectors"])
        self.assertIn("meeting_audio", status["capabilities"]["collectors"])
        self.assertIn("meeting_app_activity", status["capabilities"]["collectors"])
        self.assertIn("call_control_activity", status["capabilities"]["collectors"])
        self.assertIn("meeting_presentation_activity", status["capabilities"]["collectors"])
        self.assertIn("meeting_artifact_activity", status["capabilities"]["collectors"])
        self.assertIn("wakeups", status["capabilities"]["collectors"])
        self.assertIn("channel_activity", status["capabilities"]["collectors"])
        self.assertIn("chat_composition_activity", status["capabilities"]["collectors"])
        self.assertIn("chat_thread_activity", status["capabilities"]["collectors"])
        self.assertIn("chat_channel_navigation_activity", status["capabilities"]["collectors"])
        self.assertIn("chat_presence_activity", status["capabilities"]["collectors"])
        self.assertIn("mail_composition_activity", status["capabilities"]["collectors"])
        self.assertIn("mail_organization_activity", status["capabilities"]["collectors"])
        self.assertIn("document_composition_activity", status["capabilities"]["collectors"])
        self.assertIn("document_review_activity", status["capabilities"]["collectors"])
        self.assertIn("document_structure_activity", status["capabilities"]["collectors"])
        self.assertIn("document_export_publish_activity", status["capabilities"]["collectors"])
        self.assertIn("google_workspace", status["capabilities"]["sources"])
        self.assertIn("sheets", status["capabilities"]["sources"]["google_workspace"]["supported_apps"])
        self.assertIn("linear", status["capabilities"]["sources"])
        self.assertIn("todoist", status["capabilities"]["sources"])
        self.assertIn("knowledge_bases", status["capabilities"]["sources"])
        self.assertIn("notion", status["capabilities"]["sources"]["knowledge_bases"]["supported_apps"])
        self.assertIn("obsidian", status["capabilities"]["sources"]["knowledge_bases"]["supported_apps"])
        self.assertIn("browsers", status["capabilities"]["sources"])
        self.assertEqual(status["capabilities"]["sources"]["browsers"]["supported_browsers"], ["brave", "chrome", "edge", "firefox", "safari"])
        self.assertEqual(status["capabilities"]["sources"]["browsers"]["implementation_level"], "real_webextension_emitter")
        self.assertEqual(
            status["capabilities"]["sources"]["browsers"]["emitter_package"],
            "browser_extensions/humungousaur_collector",
        )

    def test_browser_source_events_enter_collector_log_with_redaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()

            accepted = append_browser_event(
                config,
                {
                    "browser": "chrome",
                    "event_type": "navigation_committed",
                    "provider_event_id": "nav-secret",
                    "tab_id": "tab-secret",
                    "window_id": "window-secret",
                    "url": "https://example.com/private/payroll?token=secret#section",
                    "title": "Secret Payroll",
                    "occurred_at": "2026-06-11T00:00:00+00:00",
                    "metadata": {"profile_id": "profile-secret", "selected_text": "do not leak"},
                },
            )
            events = query_collector_events(config, collector="browser_lifecycle", limit=5)["events"]
            status = collector_status(config)

        serialized = json.dumps({"accepted": accepted, "events": events, "status": status}, ensure_ascii=False)
        self.assertTrue(accepted["accepted"])
        self.assertEqual(events[0]["source"], "browsers")
        self.assertEqual(events[0]["stimulus_type"], "browser_url_changed")
        self.assertEqual(events[0]["privacy_tier"], "sensitive_metadata")
        self.assertTrue(events[0]["metadata"]["url_redacted"])
        self.assertTrue(events[0]["metadata"]["title_redacted"])
        self.assertIn("url_hash", events[0]["metadata"])
        self.assertIn("tab_id_hash", events[0]["metadata"])
        self.assertEqual(status["capabilities"]["sources"]["browsers"]["pending_event_count"], 1)
        self.assertNotIn("Secret Payroll", serialized)
        self.assertNotIn("payroll", serialized)
        self.assertNotIn("token=secret", serialized)
        self.assertNotIn("do not leak", serialized)

    def test_source_ingestion_gate_respects_profile_disable_and_rate_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(config, {"enabled": False, "collectors": {"browser_lifecycle": True}})

            disabled = append_browser_event(
                config,
                {
                    "browser": "chrome",
                    "event_type": "navigation_committed",
                    "provider_event_id": "disabled-nav",
                    "url": "https://example.com/private",
                },
            )

            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "collectors": {"browser_lifecycle": True},
                    "collector_rate_limits_per_minute": {"browser_lifecycle": 1},
                },
            )
            first = append_browser_event(
                config,
                {
                    "browser": "chrome",
                    "event_type": "navigation_committed",
                    "provider_event_id": "first-nav",
                    "url": "https://example.com/one",
                },
            )
            limited = append_browser_event(
                config,
                {
                    "browser": "chrome",
                    "event_type": "navigation_committed",
                    "provider_event_id": "second-nav",
                    "url": "https://example.com/two",
                },
            )
            events = query_collector_events(config, collector="browser_lifecycle", limit=5)["events"]

        self.assertFalse(disabled["accepted"])
        self.assertEqual(disabled["reason"], "collector profile disabled")
        self.assertTrue(first["accepted"])
        self.assertFalse(limited["accepted"])
        self.assertIn("collector minute budget exceeded", limited["reason"])
        self.assertEqual(len(events), 1)

    def test_browser_source_covers_requested_browser_event_families(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            samples = [
                ("edge", "download_completed", "browser_page_activity", "download_finished"),
                ("brave", "file_uploaded", "browser_page_activity", "file_uploaded"),
                ("firefox", "form_submitted", "browser_page_activity", "form_submitted"),
                ("safari", "page_error", "browser_page_activity", "page_error"),
                ("chrome", "extension_clicked", "browser_extension_activity", "extension_action_clicked"),
                ("chrome", "web_app_installed", "browser_web_app_activity", "web_app_installed"),
                ("firefox", "reader_mode_enabled", "browser_view_mode_activity", "reader_mode_enabled"),
                ("edge", "find_in_page", "browser_view_mode_activity", "find_in_page_performed"),
                ("brave", "zoom_changed", "browser_view_mode_activity", "page_zoom_changed"),
                ("safari", "page_muted", "browser_view_mode_activity", "page_muted"),
                ("chrome", "pip_started", "browser_view_mode_activity", "picture_in_picture_started"),
                ("edge", "translation_accepted", "browser_view_mode_activity", "page_translation_accepted"),
                ("firefox", "profile_switched", "browser_profile_activity", "browser_profile_switched"),
                ("brave", "window_created", "browser_window_activity", "browser_window_opened"),
            ]

            for index, (browser, event_type, _collector, _stimulus) in enumerate(samples):
                append_browser_event(
                    config,
                    {
                        "browser": browser,
                        "event_type": event_type,
                        "provider_event_id": f"browser-event-{index}",
                        "url": f"https://example.com/{index}?secret=value",
                        "occurred_at": f"2026-06-11T00:00:{index:02d}+00:00",
                    },
                )

            for _browser, _event_type, collector, stimulus_type in samples:
                queried = query_collector_events(config, collector=collector, stimulus_type=stimulus_type, limit=5)["events"]
                self.assertGreaterEqual(len(queried), 1)

    def test_browser_source_rejects_invalid_events_and_records_dead_letter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()

            with self.assertRaises(ValueError):
                append_browser_event(config, {"browser": "chrome", "event_type": "raw_page_dump", "url": "https://secret.example"})
            status = collector_status(config)

        source_status = status["capabilities"]["sources"]["browsers"]
        self.assertEqual(source_status["dead_letter_count"], 1)
        self.assertEqual(source_status["pending_event_count"], 0)

    def test_browser_source_health_is_visible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()

            result = append_browser_health(
                config,
                {
                    "browser": "firefox",
                    "collector": "browser_page_activity",
                    "status": "running",
                    "permission_state": "extension_connected",
                    "metadata": {"profile_id": "profile-secret", "url": "https://secret.example/private"},
                },
            )
            status = collector_status(config)

        serialized = json.dumps(status, ensure_ascii=False)
        self.assertTrue(result["accepted"])
        self.assertEqual(status["capabilities"]["sources"]["browsers"]["status"], "running")
        helper_metadata = status["event_log"]["helper_health"][0]["metadata"]
        self.assertEqual(helper_metadata["source"], "browsers")
        self.assertIn("profile_id_hash", helper_metadata)
        self.assertNotIn("secret.example", serialized)

    def test_google_workspace_source_events_enter_collector_log_with_redaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()

            accepted = append_google_workspace_event(
                config,
                {
                    "app": "sheets",
                    "event_type": "range_edited",
                    "provider_event_id": "evt-123",
                    "spreadsheet_id": "spreadsheet-secret-id",
                    "sheet_name": "Payroll 2026",
                    "title": "Confidential model",
                    "cell_value": "9000000",
                    "formula": "=IMPORTDATA(\"secret\")",
                    "range_cell_count": 12,
                    "occurred_at": "2026-06-11T00:00:00+00:00",
                },
            )
            events = query_collector_events(config, collector="spreadsheet_editing_activity", limit=5)["events"]
            status = collector_status(config)

        serialized = json.dumps({"accepted": accepted, "events": events}, ensure_ascii=False)
        self.assertTrue(accepted["accepted"])
        self.assertEqual(events[0]["source"], "google_workspace")
        self.assertEqual(events[0]["stimulus_type"], "cell_range_edited")
        self.assertEqual(events[0]["privacy_tier"], "sensitive_metadata")
        self.assertTrue(events[0]["metadata"]["title_redacted"])
        self.assertIn("object_id_hash", events[0]["metadata"])
        self.assertIn("range_cell_count", events[0]["metadata"])
        self.assertNotIn("Payroll 2026", serialized)
        self.assertNotIn("Confidential model", serialized)
        self.assertNotIn("9000000", serialized)
        self.assertNotIn("IMPORTDATA", serialized)
        self.assertEqual(status["capabilities"]["sources"]["google_workspace"]["pending_event_count"], 1)

    def test_google_workspace_source_rejects_invalid_events_and_records_dead_letter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()

            with self.assertRaises(ValueError):
                append_google_workspace_event(
                    config,
                    {
                        "app": "sheets",
                        "event_type": "raw_cell_dump",
                        "title": "Sensitive workbook",
                        "cell_value": "secret cell",
                    },
                )
            status = collector_status(config)

        source_status = status["capabilities"]["sources"]["google_workspace"]
        self.assertEqual(source_status["dead_letter_count"], 1)
        self.assertEqual(source_status["pending_event_count"], 0)

    def test_google_workspace_source_health_is_visible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()

            result = append_google_workspace_health(
                config,
                {
                    "status": "degraded",
                    "collector": "spreadsheet_editing_activity",
                    "permission_state": "granted",
                    "message": "Drive Activity API retry window active",
                    "metadata": {"provider_event_id": "event-secret", "title": "private title"},
                },
            )
            status = collector_status(config)

        self.assertTrue(result["accepted"])
        source_status = status["capabilities"]["sources"]["google_workspace"]
        self.assertEqual(source_status["status"], "degraded")
        helper_metadata = status["event_log"]["helper_health"][0]["metadata"]
        self.assertEqual(helper_metadata["provider_id"], "google_workspace")
        self.assertIn("provider_event_id_hash", helper_metadata)
        self.assertNotIn("private title", json.dumps(status, ensure_ascii=False))

    def test_planning_source_events_are_visible_in_collector_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()

            accepted = append_planning_event(
                config,
                {
                    "provider_id": "todoist",
                    "event_name": "item:completed",
                    "task_id": "todoist-task-secret",
                    "project_id": "todoist-project-secret",
                    "title": "Private task",
                    "occurred_at": "2026-06-11T00:00:00+00:00",
                },
            )
            status = collector_status(config)

        serialized = json.dumps({"accepted": accepted, "status": status}, ensure_ascii=False)
        self.assertTrue(accepted["accepted"])
        self.assertEqual(accepted["stimulus_type"], "task_completed")
        self.assertEqual(status["capabilities"]["sources"]["todoist"]["pending_event_count"], 1)
        self.assertEqual(status["capabilities"]["sources"]["todoist"]["mapping_count"], 11)
        self.assertNotIn("Private task", serialized)

    def test_communication_source_events_enter_collector_log_with_redaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()

            accepted = append_communication_event(
                config,
                {
                    "app": "slack",
                    "event_type": "message_edited",
                    "message_id": "msg-secret-id",
                    "channel_name": "exec-comp",
                    "workspace_name": "private-workspace",
                    "message": "raw private message",
                    "participants": ["alice@example.com"],
                    "attachment_count": 2,
                    "occurred_at": "2026-06-11T00:00:00+00:00",
                },
            )
            events = query_collector_events(config, collector="chat_composition_activity", limit=5)["events"]
            status = collector_status(config)

        serialized = json.dumps({"accepted": accepted, "events": events, "status": status}, ensure_ascii=False)
        self.assertTrue(accepted["accepted"])
        self.assertEqual(events[0]["source"], "slack")
        self.assertEqual(events[0]["stimulus_type"], "chat_message_edited")
        self.assertEqual(events[0]["privacy_tier"], "sensitive_metadata")
        self.assertEqual(events[0]["metadata"]["app"], "slack")
        self.assertIn("object_id_hash", events[0]["metadata"])
        self.assertIn("attachment_count", events[0]["metadata"])
        self.assertIn("communication", status["capabilities"]["sources"])
        self.assertIn("slack", status["capabilities"]["sources"]["communication"]["supported_apps"])
        self.assertNotIn("exec-comp", serialized)
        self.assertNotIn("private-workspace", serialized)
        self.assertNotIn("raw private message", serialized)
        self.assertNotIn("alice@example.com", serialized)

    def test_communication_source_maps_mail_labels_and_rejects_invalid_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()

            accepted = append_communication_event(
                config,
                {
                    "app": "gmail",
                    "event_type": "label_changed",
                    "message_id": "gmail-secret-id",
                    "label_name": "Legal",
                    "subject": "Confidential",
                },
            )
            with self.assertRaises(ValueError):
                append_communication_event(config, {"app": "discord", "event_type": "raw_message_dump", "message": "raw-discord-body-123"})
            events = query_collector_events(config, collector="mail_organization_activity", limit=5)["events"]
            status = collector_status(config)

        serialized = json.dumps({"accepted": accepted, "events": events, "status": status}, ensure_ascii=False)
        self.assertTrue(accepted["accepted"])
        self.assertEqual(events[0]["source"], "google_workspace")
        self.assertEqual(events[0]["stimulus_type"], "email_labeled")
        self.assertEqual(status["capabilities"]["sources"]["communication"]["dead_letter_count"], 1)
        self.assertNotIn("Legal", serialized)
        self.assertNotIn("Confidential", serialized)
        self.assertNotIn("raw-discord-body-123", serialized)

    def test_communication_source_tick_is_available_as_group_tick(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()

            result = run_connector_source_tick(config, provider_id="communication", dry_run=True)

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["source_count"], 1)
        apps = {app["app"] for app in result["sources"][0]["apps"]}
        self.assertEqual({"slack", "teams", "discord", "google_chat", "gmail", "outlook", "telegram", "whatsapp", "signal"}, apps)

    def test_filesystem_collector_records_post_baseline_modifications(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            watched = root / "watched"
            workspace.mkdir()
            watched.mkdir()
            (watched / "note.txt").write_text("hello", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": False,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": True,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                    },
                    "watch_paths": [str(watched)],
                    "max_file_events": 1,
                },
            )

            baseline = run_collector_tick(config)
            (watched / "note.txt").write_text("hello again", encoding="utf-8")
            changed = run_collector_tick(config)
            second = run_collector_tick(config)
            events = [event for event in EventStore(config.memory_db_path).tail(limit=10) if event["event_type"] == "collector_stimulus"]

        self.assertEqual(baseline.collected, [])
        self.assertEqual(len(changed.collected), 1)
        self.assertEqual(changed.collected[0]["stimulus_type"], "file_modified")
        self.assertEqual(len(second.collected), 0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["stimulus_type"], "file_modified")

    def test_filesystem_collector_dedupes_multiple_file_signatures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            watched = root / "watched"
            workspace.mkdir()
            watched.mkdir()
            (watched / "one.txt").write_text("one", encoding="utf-8")
            (watched / "two.txt").write_text("two", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": False,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": True,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                    },
                    "watch_paths": [str(watched)],
                    "max_file_events": 2,
                },
            )

            baseline = run_collector_tick(config)
            (watched / "one.txt").write_text("one changed", encoding="utf-8")
            (watched / "two.txt").write_text("two changed", encoding="utf-8")
            first = run_collector_tick(config)
            second = run_collector_tick(config)
            events = [event for event in EventStore(config.memory_db_path).tail(limit=10) if event["event_type"] == "collector_stimulus"]

        self.assertEqual(baseline.collected, [])
        self.assertEqual(len(first.collected), 2)
        self.assertEqual(len(second.collected), 0)
        self.assertEqual(len(events), 2)

    def test_filesystem_collector_ignores_local_secret_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            watched = root / "watched"
            workspace.mkdir()
            watched.mkdir()
            (watched / ".env").write_text("SECRET=value", encoding="utf-8")
            (watched / "public.txt").write_text("public", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": False,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": True,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                    },
                    "watch_paths": [str(watched)],
                    "max_file_events": 5,
                },
            )

            baseline = run_collector_tick(config)
            (watched / "public.txt").write_text("public changed", encoding="utf-8")
            result = run_collector_tick(config)

        self.assertEqual(baseline.collected, [])
        paths = [item["payload"]["relative_path"] for item in result.collected]
        self.assertEqual(paths, [str(watched / "public.txt")])

    def test_filesystem_collector_records_deleted_files_after_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            watched = root / "watched"
            workspace.mkdir()
            watched.mkdir()
            deleted = watched / "remove-me.txt"
            deleted.write_text("temporary", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": False,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": True,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                    },
                    "watch_paths": [str(watched)],
                    "max_file_events": 5,
                },
            )

            baseline = run_collector_tick(config)
            deleted.unlink()
            result = run_collector_tick(config)

        self.assertEqual(baseline.collected, [])
        self.assertEqual(len(result.collected), 1)
        self.assertEqual(result.collected[0]["stimulus_type"], "file_deleted")
        self.assertEqual(result.collected[0]["payload"]["relative_path"], str(deleted))

    def test_activity_policy_blocks_collector_before_recording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            watched = root / "watched"
            workspace.mkdir()
            watched.mkdir()
            (watched / "secret.txt").write_text("blocked", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            ActivityPolicyStore(activity_policy_path(config)).save(
                {
                    "retention_days": 30,
                    "disabled_sources": ["filesystem"],
                    "excluded_apps": [],
                    "excluded_window_terms": [],
                    "excluded_url_domains": [],
                    "excluded_text_terms": [],
                }
            )
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": False,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": True,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                    },
                    "watch_paths": [str(watched)],
                    "max_file_events": 1,
                },
            )

            baseline = run_collector_tick(config)
            (watched / "secret.txt").write_text("blocked changed", encoding="utf-8")
            result = run_collector_tick(config)
            events = [event for event in EventStore(config.memory_db_path).tail(limit=10) if event["event_type"] == "collector_stimulus"]

        self.assertEqual(baseline.collected, [])
        self.assertEqual(result.collected, [])
        self.assertTrue(any("source disabled" in item["reason"] for item in result.skipped))
        self.assertEqual(events, [])

    def test_file_burst_coalesces_into_attention_batch_for_llm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            watched = root / "watched"
            workspace.mkdir()
            watched.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": True,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                    },
                    "watch_paths": [str(watched)],
                    "max_file_events": 2,
                    "max_events_per_tick": 5,
                },
            )

            baseline = run_collector_tick(config, force=True)
            (watched / "one.txt").write_text("one", encoding="utf-8")
            (watched / "two.txt").write_text("two", encoding="utf-8")
            result = run_collector_tick(config, force=True)
            memory = EventStore(config.memory_db_path).tail(limit=20)
            context_exists = Path(result.current_context["current_context_path"]).exists()

        self.assertEqual(baseline.collected, [])
        self.assertEqual(len(result.collected), 2)
        self.assertEqual(len(result.attention_batches), 1)
        self.assertEqual(len(result.submitted), 1)
        self.assertEqual(result.submitted[0]["collector"], "attention_batch")
        self.assertEqual(result.attention_batches[0]["collector_counts"]["filesystem"], 2)
        self.assertIn("Filesystem changes: 2 file(s)", result.attention_batches[0]["text"])
        self.assertEqual(len([event for event in memory if event["event_type"] == "attention_batch"]), 1)
        self.assertEqual(result.semantic_events[0]["event_type"], "project_files_changed")
        self.assertEqual(result.action_candidates[0]["action_type"], "update_context")
        self.assertTrue(context_exists)

    def test_rich_capture_collector_requires_explicit_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": False,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": True,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                    },
                },
            )

            with patch.object(local_context_collectors, "_clipboard_text", return_value="very secret clipboard"):
                result = run_collector_tick(config, force=True)

        self.assertEqual(result.collected, [])
        self.assertTrue(any(item["reason"] == "rich capture collector is not opted in" for item in result.skipped))

    def test_clipboard_attention_batch_omits_clipboard_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": True,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                    },
                    "rich_capture_opt_in": {"clipboard": True},
                },
            )

            with patch.object(local_context_collectors, "_clipboard_text", return_value="super secret clipboard"):
                result = run_collector_tick(config, force=True)

        self.assertEqual(len(result.attention_batches), 1)
        batch = result.attention_batches[0]
        self.assertIn("Clipboard changed", batch["text"])
        self.assertNotIn("super secret", batch["text"])
        self.assertNotIn("super secret", str(batch["events"]))

    def test_ambient_voice_activity_does_not_submit_to_llm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": True,
                    },
                    "rich_capture_opt_in": {"audio_activity": True},
                },
            )

            with patch.object(local_context_collectors, "_audio_rms_sample", return_value={"rms": 0.2, "sample_rate": 16000, "sample_seconds": 1.5}):
                result = run_collector_tick(config, force=True)

        self.assertEqual(len(result.collected), 1)
        self.assertEqual(result.attention_batches, [])
        self.assertEqual(result.submitted, [])

    def test_collector_rate_limit_caps_event_floods(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            watched = root / "watched"
            workspace.mkdir()
            watched.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": False,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": True,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                    },
                    "watch_paths": [str(watched)],
                    "max_file_events": 3,
                    "collector_rate_limits_per_minute": {"filesystem": 1},
                },
            )

            baseline = run_collector_tick(config)
            for index in range(3):
                (watched / f"{index}.txt").write_text(str(index), encoding="utf-8")
            result = run_collector_tick(config)

        self.assertEqual(baseline.collected, [])
        self.assertEqual(len(result.collected), 1)
        self.assertEqual(len([item for item in result.skipped if "minute budget exceeded" in item["reason"]]), 2)

    def test_input_device_collector_reads_native_bridge_spool_without_text_logging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            spool_dir = config.data_dir / "collector_spool"
            spool_dir.mkdir(parents=True)
            (spool_dir / "input_device.jsonl").write_text(
                '{"event_id":"mouse-forward-1","stimulus_type":"mouse_forward","metadata":{"button":"forward"},"payload":{"button":4}}\n',
                encoding="utf-8",
            )
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": False,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "input_device": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(len(result.collected), 1)
        self.assertEqual(result.collected[0]["collector"], "input_device")
        self.assertEqual(result.collected[0]["stimulus_type"], "mouse_forward")
        self.assertNotIn("typed", str(result.collected[0]).lower())

    def test_append_bridge_event_validates_and_feeds_collector_tick(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            accepted = append_bridge_event(
                config,
                {
                    "collector": "terminal_activity",
                    "stimulus_type": "tests_failed",
                    "text": "Tests failed in backend suite.",
                    "metadata": {"app_name": "Terminal"},
                    "payload": {"summary": "2 tests failed", "raw_output": "SECRET RAW OUTPUT"},
                },
            )
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "terminal_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertTrue(accepted["accepted"])
        self.assertNotIn("SECRET RAW OUTPUT", str(accepted))
        self.assertEqual(result.collected[0]["collector"], "terminal_activity")
        self.assertEqual(result.semantic_events[0]["event_type"], "terminal_activity")
        self.assertEqual(result.action_candidates[0]["action_type"], "analyze")
        self.assertIn("Terminal activity event", result.attention_batches[0]["text"])
        self.assertNotIn("SECRET RAW OUTPUT", str(result.attention_batches[0]))

    def test_append_bridge_event_rejects_unknown_stimulus_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config = AgentConfig(workspace=root / "workspace", data_dir=root / "data", planner_provider="explicit").normalized()
            with self.assertRaises(ValueError):
                append_bridge_event(
                    config,
                    {
                        "collector": "notification_activity",
                        "stimulus_type": "raw_password_seen",
                        "text": "bad",
                    },
                )
            with self.assertRaises(ValueError):
                append_bridge_event(
                    config,
                    {
                        "collector": "not_a_collector",
                        "stimulus_type": "tests_failed",
                        "text": "bad",
                    },
                )

    def test_app_lifecycle_collector_detects_opened_process_after_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": False,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "app_lifecycle": True,
                    },
                },
            )

            with patch.object(lifecycle_collectors, "_process_names", side_effect=[{"Finder"}, {"Finder", "Xcode"}]):
                baseline = run_collector_tick(config, force=True)
                opened = run_collector_tick(config, force=True)

        self.assertEqual(baseline.collected, [])
        self.assertEqual(len(opened.collected), 1)
        self.assertEqual(opened.collected[0]["collector"], "app_lifecycle")
        self.assertEqual(opened.collected[0]["stimulus_type"], "app_opened")
        self.assertEqual(opened.collected[0]["metadata"]["app_name"], "Xcode")

    def test_lifecycle_bridge_collectors_accept_richer_app_and_window_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            append_bridge_event(
                config,
                {
                    "collector": "app_lifecycle",
                    "stimulus_type": "app_crashed",
                    "text": "App crashed: Preview.",
                    "metadata": {"app_name": "Preview"},
                    "payload": {"crash_report_path": "/private/tmp/SECRET.crash"},
                },
            )
            append_bridge_event(
                config,
                {
                    "collector": "window_lifecycle",
                    "stimulus_type": "window_resized",
                    "text": "Window resized: Preview document.",
                    "metadata": {"app_name": "Preview", "window_title": "Document.pdf"},
                    "payload": {"bounds": {"x": 0, "y": 0, "width": 900, "height": 700}},
                },
            )
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "app_lifecycle": True,
                        "window_lifecycle": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual({event["collector"] for event in result.collected}, {"app_lifecycle", "window_lifecycle"})
        self.assertIn("app_lifecycle_changed", {event["event_type"] for event in result.semantic_events})
        self.assertIn("window_lifecycle_changed", {event["event_type"] for event in result.semantic_events})
        self.assertIn("App lifecycle event(s): 1", result.attention_batches[0]["text"])
        self.assertIn("Window lifecycle:", result.attention_batches[0]["text"])
        self.assertNotIn("SECRET.crash", str(result.attention_batches[0]))

    def test_terminal_bridge_collector_batches_semantic_failure_without_raw_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            spool_dir = config.data_dir / "collector_spool"
            spool_dir.mkdir(parents=True)
            (spool_dir / "terminal_activity.jsonl").write_text(
                '{"event_id":"tests-failed-1","stimulus_type":"tests_failed","text":"Tests failed in backend suite.","metadata":{"app_name":"Terminal"},"payload":{"summary":"2 tests failed","raw_output":"SECRET RAW OUTPUT"}}\n',
                encoding="utf-8",
            )
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "terminal_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(len(result.collected), 1)
        self.assertEqual(result.collected[0]["collector"], "terminal_activity")
        self.assertEqual(result.semantic_events[0]["event_type"], "terminal_activity")
        self.assertEqual(result.action_candidates[0]["action_type"], "analyze")
        self.assertIn("Terminal activity event", result.attention_batches[0]["text"])
        self.assertNotIn("SECRET RAW OUTPUT", str(result.attention_batches[0]))

    def test_calendar_bridge_collector_queues_briefing_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            spool_dir = config.data_dir / "collector_spool"
            spool_dir.mkdir(parents=True)
            (spool_dir / "calendar_activity.jsonl").write_text(
                '{"event_id":"meeting-starting-1","stimulus_type":"meeting_starting","text":"Meeting starting soon.","metadata":{"calendar_id":"work"}}\n',
                encoding="utf-8",
            )
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "calendar_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(result.semantic_events[0]["event_type"], "calendar_activity")
        self.assertEqual(result.action_candidates[0]["action_type"], "prepare_briefing")
        self.assertIn("Calendar event", result.attention_batches[0]["text"])

    def test_security_bridge_collector_requires_rich_capture_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            spool_dir = config.data_dir / "collector_spool"
            spool_dir.mkdir(parents=True)
            (spool_dir / "security_context.jsonl").write_text(
                '{"event_id":"password-field-1","stimulus_type":"password_field_focused","text":"Password field focused."}\n',
                encoding="utf-8",
            )
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "security_context": True,
                    },
                },
            )

            blocked = run_collector_tick(config, force=True)
            save_collector_profile(config, {"rich_capture_opt_in": {"security_context": True}})
            with (spool_dir / "security_context.jsonl").open("a", encoding="utf-8") as handle:
                handle.write('{"event_id":"private-mode-1","stimulus_type":"private_browsing_detected","text":"Private browsing detected."}\n')
            allowed = run_collector_tick(config, force=True)

        self.assertEqual(blocked.collected, [])
        self.assertTrue(any(item["reason"] == "rich capture collector is not opted in" for item in blocked.skipped))
        self.assertEqual(allowed.semantic_events[0]["event_type"], "security_context_changed")
        self.assertEqual(allowed.action_candidates[0]["action_type"], "suppress_collection")

    def test_browser_organization_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "browser_window_activity",
                    "stimulus_type": "browser_session_restored",
                    "text": "Browser restored SECRET TAB LIST.",
                    "metadata": {"app_name": "Chrome", "window_title": "SECRET WINDOW TITLE", "url": "https://secret.example/session", "browser_window_kind": "session_restore"},
                    "payload": {"tabs": ["SECRET TAB LIST"], "window_title": "SECRET WINDOW TITLE"},
                },
                {
                    "collector": "browser_tab_group_activity",
                    "stimulus_type": "tab_group_saved",
                    "text": "Saved SECRET GROUP.",
                    "metadata": {"app_name": "Chrome", "tab_group_kind": "saved", "url": "https://secret.example/group", "privacy_level": "redacted"},
                    "payload": {"group_name": "SECRET GROUP", "tab_titles": ["SECRET TAB TITLE"]},
                },
                {
                    "collector": "browser_profile_activity",
                    "stimulus_type": "private_window_opened",
                    "text": "Private window opened for SECRET PROFILE.",
                    "metadata": {"app_name": "Chrome", "browser_profile_kind": "private", "window_title": "SECRET PROFILE WINDOW", "privacy_level": "redacted"},
                    "payload": {"profile_name": "SECRET PROFILE", "account": "SECRET ACCOUNT"},
                },
                {
                    "collector": "browser_extension_activity",
                    "stimulus_type": "extension_permission_requested",
                    "text": "SECRET EXTENSION requested permissions.",
                    "metadata": {"app_name": "Chrome", "extension_kind": "permission", "url": "https://secret.example/extension", "privacy_level": "redacted"},
                    "payload": {"extension_name": "SECRET EXTENSION", "permission_details": "SECRET PERMISSIONS"},
                },
                {
                    "collector": "browser_web_app_activity",
                    "stimulus_type": "web_app_notification_permission_requested",
                    "text": "SECRET WEB APP requested notifications.",
                    "metadata": {"app_name": "Chrome", "web_app_kind": "notification", "url": "https://secret.example/app", "privacy_level": "redacted"},
                    "payload": {"app_name": "SECRET WEB APP", "origin": "SECRET ORIGIN"},
                },
                {
                    "collector": "browser_view_mode_activity",
                    "stimulus_type": "find_in_page_performed",
                    "text": "Find in page searched SECRET QUERY.",
                    "metadata": {"app_name": "Chrome", "view_mode_kind": "find", "window_title": "SECRET PAGE TITLE", "privacy_level": "redacted"},
                    "payload": {"query": "SECRET QUERY", "media_title": "SECRET MEDIA TITLE"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "browser_window_activity": True,
                        "browser_tab_group_activity": True,
                        "browser_profile_activity": True,
                        "browser_extension_activity": True,
                        "browser_web_app_activity": True,
                        "browser_view_mode_activity": True,
                    },
                    "rich_capture_opt_in": {
                        "browser_tab_group_activity": True,
                        "browser_profile_activity": True,
                        "browser_extension_activity": True,
                        "browser_web_app_activity": True,
                        "browser_view_mode_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {
                "browser_window_activity",
                "browser_tab_group_activity",
                "browser_profile_activity",
                "browser_extension_activity",
                "browser_web_app_activity",
                "browser_view_mode_activity",
            },
        )
        batch = result.attention_batches[0]
        self.assertIn("Browser window/session event(s): 1", batch["text"])
        self.assertIn("Browser tab-group event(s): 1", batch["text"])
        self.assertIn("Browser profile event(s): 1", batch["text"])
        self.assertIn("Browser extension event(s): 1", batch["text"])
        self.assertIn("Browser web-app event(s): 1", batch["text"])
        self.assertIn("Browser view-mode event(s): 1", batch["text"])
        self.assertNotIn("SECRET TAB LIST", str(batch))
        self.assertNotIn("SECRET WINDOW TITLE", str(batch))
        self.assertNotIn("secret.example", str(batch))
        self.assertNotIn("SECRET GROUP", str(batch))
        self.assertNotIn("SECRET TAB TITLE", str(batch))
        self.assertNotIn("SECRET PROFILE", str(batch))
        self.assertNotIn("SECRET ACCOUNT", str(batch))
        self.assertNotIn("SECRET EXTENSION", str(batch))
        self.assertNotIn("SECRET PERMISSIONS", str(batch))
        self.assertNotIn("SECRET WEB APP", str(batch))
        self.assertNotIn("SECRET ORIGIN", str(batch))
        self.assertNotIn("SECRET QUERY", str(batch))
        self.assertNotIn("SECRET PAGE TITLE", str(batch))
        self.assertNotIn("SECRET MEDIA TITLE", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("browser_window_activity", semantic_types)
        self.assertIn("browser_tab_group_activity", semantic_types)
        self.assertIn("browser_profile_activity", semantic_types)
        self.assertIn("browser_extension_activity", semantic_types)
        self.assertIn("browser_web_app_activity", semantic_types)
        self.assertIn("browser_view_mode_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("prepare_resume_context", action_types)
        self.assertIn("update_context", action_types)
        self.assertIn("suppress_collection", action_types)
        self.assertIn("review_attention", action_types)

    def test_bridge_activity_collectors_feed_compact_attention_batches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            spool_dir = config.data_dir / "collector_spool"
            spool_dir.mkdir(parents=True)
            (spool_dir / "terminal_activity.jsonl").write_text(
                '{"event_id":"terminal-fail-1","stimulus_type":"terminal_command_failed","text":"Terminal command failed: pytest exited 1.","metadata":{"app_name":"Terminal"},"payload":{"exit_code":1}}\n',
                encoding="utf-8",
            )
            (spool_dir / "browser_page_activity.jsonl").write_text(
                '{"event_id":"browser-error-1","stimulus_type":"console_error","text":"Browser console error observed.","metadata":{"app_name":"Chrome","url":"http://localhost:3000"},"payload":{"error_count":1}}\n',
                encoding="utf-8",
            )
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "batch_seconds": 1,
                    "llm_attention_interval_seconds": 1,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "terminal_activity": True,
                        "browser_page_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual({event["collector"] for event in result.collected}, {"terminal_activity", "browser_page_activity"})
        self.assertEqual(len(result.attention_batches), 1)
        batch_text = result.attention_batches[0]["text"]
        self.assertIn("Terminal activity event(s): 1", batch_text)
        self.assertIn("Browser page activity event(s): 1", batch_text)
        self.assertIn("terminal_activity", {event["event_type"] for event in result.semantic_events})
        self.assertIn("browser_page_activity", {event["event_type"] for event in result.semantic_events})

    def test_developer_tooling_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "package_manager_activity",
                    "stimulus_type": "dependency_conflict_detected",
                    "text": "Dependency conflict detected for SECRET PACKAGE.",
                    "metadata": {"app_name": "npm", "package_manager": "npm", "privacy_level": "redacted"},
                    "payload": {"package_name": "SECRET PACKAGE", "install_log": "SECRET INSTALL LOG"},
                },
                {
                    "collector": "build_tool_activity",
                    "stimulus_type": "compile_error_detected",
                    "text": "Compile error in SECRET TARGET.",
                    "metadata": {"app_name": "Xcode", "build_tool": "swift-build", "privacy_level": "redacted"},
                    "payload": {"target": "SECRET TARGET", "path": "/secret/Build.swift", "log": "SECRET BUILD LOG"},
                },
                {
                    "collector": "test_runner_activity",
                    "stimulus_type": "coverage_threshold_failed",
                    "text": "Coverage threshold failed for SECRET TEST.",
                    "metadata": {"app_name": "pytest", "test_runner": "pytest", "privacy_level": "redacted"},
                    "payload": {"test_name": "SECRET TEST", "assertion": "SECRET ASSERTION", "coverage": "SECRET COVERAGE"},
                },
                {
                    "collector": "local_service_activity",
                    "stimulus_type": "port_conflict_detected",
                    "text": "Port conflict detected at SECRET ENDPOINT.",
                    "metadata": {"app_name": "dev-server", "service_kind": "web", "privacy_level": "redacted"},
                    "payload": {"endpoint": "http://localhost:3000/secret", "log": "SECRET SERVICE LOG"},
                },
                {
                    "collector": "debugger_activity",
                    "stimulus_type": "exception_breakpoint_hit",
                    "text": "Debugger hit SECRET STACK FRAME.",
                    "metadata": {"app_name": "VS Code", "debugger_kind": "exception", "privacy_level": "redacted"},
                    "payload": {"stack_frame": "SECRET STACK FRAME", "watch_expression": "SECRET WATCH", "variable_value": "SECRET VALUE"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "package_manager_activity": True,
                        "build_tool_activity": True,
                        "test_runner_activity": True,
                        "local_service_activity": True,
                        "debugger_activity": True,
                    },
                    "rich_capture_opt_in": {
                        "package_manager_activity": True,
                        "build_tool_activity": True,
                        "test_runner_activity": True,
                        "local_service_activity": True,
                        "debugger_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {
                "package_manager_activity",
                "build_tool_activity",
                "test_runner_activity",
                "local_service_activity",
                "debugger_activity",
            },
        )
        batch = result.attention_batches[0]
        self.assertIn("Package manager event(s): 1", batch["text"])
        self.assertIn("Build tool event(s): 1", batch["text"])
        self.assertIn("Test runner event(s): 1", batch["text"])
        self.assertIn("Local service event(s): 1", batch["text"])
        self.assertIn("Debugger event(s): 1", batch["text"])
        self.assertNotIn("SECRET PACKAGE", str(batch))
        self.assertNotIn("SECRET INSTALL LOG", str(batch))
        self.assertNotIn("SECRET TARGET", str(batch))
        self.assertNotIn("/secret/Build.swift", str(batch))
        self.assertNotIn("SECRET BUILD LOG", str(batch))
        self.assertNotIn("SECRET TEST", str(batch))
        self.assertNotIn("SECRET ASSERTION", str(batch))
        self.assertNotIn("SECRET COVERAGE", str(batch))
        self.assertNotIn("SECRET ENDPOINT", str(batch))
        self.assertNotIn("/secret", str(batch))
        self.assertNotIn("SECRET SERVICE LOG", str(batch))
        self.assertNotIn("SECRET STACK FRAME", str(batch))
        self.assertNotIn("SECRET WATCH", str(batch))
        self.assertNotIn("SECRET VALUE", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("package_manager_activity", semantic_types)
        self.assertIn("build_tool_activity", semantic_types)
        self.assertIn("test_runner_activity", semantic_types)
        self.assertIn("local_service_activity", semantic_types)
        self.assertIn("debugger_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("analyze", action_types)

    def test_productivity_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            spool_dir = config.data_dir / "collector_spool"
            spool_dir.mkdir(parents=True)
            (spool_dir / "communication_activity.jsonl").write_text(
                '{"event_id":"mention-1","stimulus_type":"mention_received","text":"Mention received in Slack.","metadata":{"channel_id":"slack","conversation_id":"C123"},"payload":{"body":"SECRET MESSAGE BODY"}}\n',
                encoding="utf-8",
            )
            (spool_dir / "calendar_activity.jsonl").write_text(
                '{"event_id":"meeting-1","stimulus_type":"meeting_starting","text":"Meeting starting in 5 minutes.","metadata":{"app_name":"Calendar"},"payload":{"title":"Planning"}}\n',
                encoding="utf-8",
            )
            (spool_dir / "notification_activity.jsonl").write_text(
                '{"event_id":"alert-1","stimulus_type":"critical_alert_received","text":"Critical notification received.","metadata":{"app_name":"PagerDuty"},"payload":{"body":"SECRET ALERT BODY"}}\n',
                encoding="utf-8",
            )
            (spool_dir / "security_context.jsonl").write_text(
                '{"event_id":"security-1","stimulus_type":"private_browsing_detected","text":"Private browsing detected.","metadata":{"privacy_level":"sensitive"},"payload":{"url":"SECRET PRIVATE URL"}}\n',
                encoding="utf-8",
            )
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "communication_activity": True,
                        "calendar_activity": True,
                        "notification_activity": True,
                        "security_context": True,
                    },
                    "rich_capture_opt_in": {"security_context": True},
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {"communication_activity", "calendar_activity", "notification_activity", "security_context"},
        )
        batch = result.attention_batches[0]
        self.assertIn("Communication event(s): 1", batch["text"])
        self.assertIn("Calendar event(s): 1", batch["text"])
        self.assertIn("Notification event(s): 1", batch["text"])
        self.assertIn("Security context event(s): 1", batch["text"])
        self.assertNotIn("SECRET MESSAGE BODY", str(batch))
        self.assertNotIn("SECRET ALERT BODY", str(batch))
        self.assertNotIn("SECRET PRIVATE URL", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("communication_activity", semantic_types)
        self.assertIn("calendar_activity", semantic_types)
        self.assertIn("notification_activity", semantic_types)
        self.assertIn("security_context_changed", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("review_message", action_types)
        self.assertIn("prepare_briefing", action_types)
        self.assertIn("review_attention", action_types)
        self.assertIn("suppress_collection", action_types)

    def test_mail_calendar_workflow_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "calendar_scheduling_activity",
                    "stimulus_type": "calendar_invite_received",
                    "text": "Calendar invite received for SECRET MEETING.",
                    "metadata": {"app_name": "Calendar", "calendar_action": "invite", "privacy_level": "redacted"},
                    "payload": {"title": "SECRET MEETING", "attendees": "SECRET ATTENDEES", "location": "SECRET LOCATION"},
                },
                {
                    "collector": "reminder_todo_activity",
                    "stimulus_type": "reminder_snoozed",
                    "text": "Reminder snoozed: SECRET REMINDER.",
                    "metadata": {"app_name": "Reminders", "reminder_action": "snooze", "privacy_level": "redacted"},
                    "payload": {"title": "SECRET REMINDER", "notes": "SECRET TODO NOTES", "list": "SECRET LIST"},
                },
                {
                    "collector": "mail_composition_activity",
                    "stimulus_type": "email_reply_started",
                    "text": "Email reply started to SECRET RECIPIENT.",
                    "metadata": {"app_name": "Mail", "mail_action": "reply", "privacy_level": "redacted"},
                    "payload": {"subject": "SECRET SUBJECT", "recipient": "SECRET RECIPIENT", "body": "SECRET MAIL BODY", "filename": "secret.pdf"},
                },
                {
                    "collector": "mail_organization_activity",
                    "stimulus_type": "email_search_performed",
                    "text": "Mail search performed for SECRET QUERY.",
                    "metadata": {"app_name": "Mail", "mailbox_action": "search", "privacy_level": "redacted"},
                    "payload": {"sender": "SECRET SENDER", "query": "SECRET QUERY", "label": "SECRET LABEL", "rule": "SECRET RULE"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "calendar_scheduling_activity": True,
                        "reminder_todo_activity": True,
                        "mail_composition_activity": True,
                        "mail_organization_activity": True,
                    },
                    "rich_capture_opt_in": {
                        "calendar_scheduling_activity": True,
                        "reminder_todo_activity": True,
                        "mail_composition_activity": True,
                        "mail_organization_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {"calendar_scheduling_activity", "reminder_todo_activity", "mail_composition_activity", "mail_organization_activity"},
        )
        batch = result.attention_batches[0]
        self.assertIn("Calendar scheduling event(s): 1", batch["text"])
        self.assertIn("Reminder/to-do event(s): 1", batch["text"])
        self.assertIn("Mail composition event(s): 1", batch["text"])
        self.assertIn("Mail organization event(s): 1", batch["text"])
        self.assertNotIn("SECRET MEETING", str(batch))
        self.assertNotIn("SECRET ATTENDEES", str(batch))
        self.assertNotIn("SECRET LOCATION", str(batch))
        self.assertNotIn("SECRET REMINDER", str(batch))
        self.assertNotIn("SECRET TODO NOTES", str(batch))
        self.assertNotIn("SECRET LIST", str(batch))
        self.assertNotIn("SECRET SUBJECT", str(batch))
        self.assertNotIn("SECRET RECIPIENT", str(batch))
        self.assertNotIn("SECRET MAIL BODY", str(batch))
        self.assertNotIn("secret.pdf", str(batch))
        self.assertNotIn("SECRET SENDER", str(batch))
        self.assertNotIn("SECRET QUERY", str(batch))
        self.assertNotIn("SECRET LABEL", str(batch))
        self.assertNotIn("SECRET RULE", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("calendar_scheduling_activity", semantic_types)
        self.assertIn("reminder_todo_activity", semantic_types)
        self.assertIn("mail_composition_activity", semantic_types)
        self.assertIn("mail_organization_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("prepare_briefing", action_types)
        self.assertIn("prepare_reply", action_types)
        self.assertIn("review_attention", action_types)
        self.assertIn("update_context", action_types)

    def test_chat_collaboration_workflow_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "chat_composition_activity",
                    "stimulus_type": "chat_draft_started",
                    "text": "Draft started for SECRET RECIPIENT.",
                    "metadata": {
                        "app_name": "Slack",
                        "chat_action": "draft",
                        "channel_id": "SECRET CHANNEL ID",
                        "conversation_id": "SECRET CONVO",
                        "privacy_level": "redacted",
                    },
                    "payload": {"body": "SECRET MESSAGE BODY", "recipient": "SECRET RECIPIENT", "attachment": "SECRET FILE"},
                },
                {
                    "collector": "chat_thread_activity",
                    "stimulus_type": "thread_reply_sent",
                    "text": "Thread reply sent in SECRET THREAD.",
                    "metadata": {"app_name": "Slack", "thread_action": "reply", "window_title": "SECRET THREAD WINDOW", "privacy_level": "redacted"},
                    "payload": {"thread_title": "SECRET THREAD", "reply": "SECRET REPLY", "participants": "SECRET PEOPLE"},
                },
                {
                    "collector": "chat_channel_navigation_activity",
                    "stimulus_type": "chat_channel_search_performed",
                    "text": "Channel search performed for SECRET QUERY.",
                    "metadata": {"app_name": "Slack", "channel_action": "search", "channel_id": "SECRET CHANNEL", "privacy_level": "redacted"},
                    "payload": {"workspace": "SECRET WORKSPACE", "channel": "SECRET CHANNEL", "query": "SECRET QUERY"},
                },
                {
                    "collector": "chat_presence_activity",
                    "stimulus_type": "chat_status_changed",
                    "text": "Status changed to SECRET STATUS.",
                    "metadata": {"app_name": "Slack", "presence_action": "status", "privacy_level": "redacted"},
                    "payload": {"status_text": "SECRET STATUS", "availability_note": "SECRET AVAILABILITY"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "chat_composition_activity": True,
                        "chat_thread_activity": True,
                        "chat_channel_navigation_activity": True,
                        "chat_presence_activity": True,
                    },
                    "rich_capture_opt_in": {
                        "chat_composition_activity": True,
                        "chat_thread_activity": True,
                        "chat_channel_navigation_activity": True,
                        "chat_presence_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {"chat_composition_activity", "chat_thread_activity", "chat_channel_navigation_activity", "chat_presence_activity"},
        )
        batch = result.attention_batches[0]
        self.assertIn("Chat composition event(s): 1", batch["text"])
        self.assertIn("Chat thread event(s): 1", batch["text"])
        self.assertIn("Chat channel navigation event(s): 1", batch["text"])
        self.assertIn("Chat presence event(s): 1", batch["text"])
        self.assertNotIn("SECRET RECIPIENT", str(batch))
        self.assertNotIn("SECRET CHANNEL ID", str(batch))
        self.assertNotIn("SECRET CONVO", str(batch))
        self.assertNotIn("SECRET MESSAGE BODY", str(batch))
        self.assertNotIn("SECRET FILE", str(batch))
        self.assertNotIn("SECRET THREAD", str(batch))
        self.assertNotIn("SECRET THREAD WINDOW", str(batch))
        self.assertNotIn("SECRET REPLY", str(batch))
        self.assertNotIn("SECRET PEOPLE", str(batch))
        self.assertNotIn("SECRET QUERY", str(batch))
        self.assertNotIn("SECRET CHANNEL", str(batch))
        self.assertNotIn("SECRET WORKSPACE", str(batch))
        self.assertNotIn("SECRET STATUS", str(batch))
        self.assertNotIn("SECRET AVAILABILITY", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("chat_composition_activity", semantic_types)
        self.assertIn("chat_thread_activity", semantic_types)
        self.assertIn("chat_channel_navigation_activity", semantic_types)
        self.assertIn("chat_presence_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("prepare_reply", action_types)
        self.assertIn("review_message", action_types)
        self.assertIn("update_context", action_types)

    def test_document_workflow_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "document_composition_activity",
                    "stimulus_type": "document_outline_updated",
                    "text": "Outline updated for SECRET DOC.",
                    "metadata": {
                        "app_name": "Docs",
                        "document_action": "outline",
                        "window_title": "SECRET DOC WINDOW",
                        "privacy_level": "redacted",
                    },
                    "payload": {"title": "SECRET DOC", "selected_text": "SECRET SELECTED TEXT", "path": "/secret/document.docx"},
                },
                {
                    "collector": "document_review_activity",
                    "stimulus_type": "document_comment_added",
                    "text": "Comment added by SECRET REVIEWER.",
                    "metadata": {"app_name": "Docs", "review_action": "comment", "privacy_level": "redacted"},
                    "payload": {"comment": "SECRET COMMENT", "reviewer": "SECRET REVIEWER", "mention": "SECRET PERSON"},
                },
                {
                    "collector": "document_structure_activity",
                    "stimulus_type": "document_section_moved",
                    "text": "Moved SECRET SECTION.",
                    "metadata": {"app_name": "Docs", "structure_action": "move", "privacy_level": "redacted"},
                    "payload": {"section": "SECRET SECTION", "heading": "SECRET HEADING", "outline": "SECRET OUTLINE"},
                },
                {
                    "collector": "document_export_publish_activity",
                    "stimulus_type": "document_share_link_created",
                    "text": "Share link created for SECRET DESTINATION.",
                    "metadata": {"app_name": "Docs", "publish_action": "share", "privacy_level": "redacted"},
                    "payload": {
                        "filename": "secret-plan.pdf",
                        "link": "https://secret.example/doc",
                        "recipient": "SECRET RECIPIENT",
                        "permissions": "SECRET PERMISSIONS",
                    },
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "document_composition_activity": True,
                        "document_review_activity": True,
                        "document_structure_activity": True,
                        "document_export_publish_activity": True,
                    },
                    "rich_capture_opt_in": {
                        "document_composition_activity": True,
                        "document_review_activity": True,
                        "document_structure_activity": True,
                        "document_export_publish_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {"document_composition_activity", "document_review_activity", "document_structure_activity", "document_export_publish_activity"},
        )
        batch = result.attention_batches[0]
        self.assertIn("Document composition event(s): 1", batch["text"])
        self.assertIn("Document review event(s): 1", batch["text"])
        self.assertIn("Document structure event(s): 1", batch["text"])
        self.assertIn("Document export/publish event(s): 1", batch["text"])
        self.assertNotIn("SECRET DOC", str(batch))
        self.assertNotIn("SECRET DOC WINDOW", str(batch))
        self.assertNotIn("SECRET SELECTED TEXT", str(batch))
        self.assertNotIn("/secret/document.docx", str(batch))
        self.assertNotIn("SECRET COMMENT", str(batch))
        self.assertNotIn("SECRET REVIEWER", str(batch))
        self.assertNotIn("SECRET PERSON", str(batch))
        self.assertNotIn("SECRET SECTION", str(batch))
        self.assertNotIn("SECRET HEADING", str(batch))
        self.assertNotIn("SECRET OUTLINE", str(batch))
        self.assertNotIn("SECRET DESTINATION", str(batch))
        self.assertNotIn("secret-plan.pdf", str(batch))
        self.assertNotIn("https://secret.example/doc", str(batch))
        self.assertNotIn("SECRET RECIPIENT", str(batch))
        self.assertNotIn("SECRET PERMISSIONS", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("document_composition_activity", semantic_types)
        self.assertIn("document_review_activity", semantic_types)
        self.assertIn("document_structure_activity", semantic_types)
        self.assertIn("document_export_publish_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("review_attention", action_types)
        self.assertIn("update_context", action_types)

    def test_environment_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "device_state",
                    "stimulus_type": "network_changed",
                    "text": "Network changed to office Wi-Fi.",
                    "metadata": {"network_id": "office"},
                },
                {
                    "collector": "downloads",
                    "stimulus_type": "downloaded_file",
                    "text": "Download finished: report.pdf.",
                    "metadata": {"app_name": "Chrome", "filename": "report.pdf"},
                    "payload": {"absolute_path": "/secret/path/report.pdf"},
                },
                {
                    "collector": "git_activity",
                    "stimulus_type": "merge_conflict_detected",
                    "text": "Merge conflict detected in workspace.",
                    "metadata": {"repository": "Humungousaur"},
                    "payload": {"patch": "SECRET DIFF"},
                },
                {
                    "collector": "github_activity",
                    "stimulus_type": "ci_failed",
                    "text": "GitHub CI failed for pull request.",
                    "metadata": {"repository": "Humungousaur", "url": "https://github.example/pr/1"},
                    "payload": {"log_excerpt": "SECRET CI LOG"},
                },
                {
                    "collector": "visual_state",
                    "stimulus_type": "loading_spinner_stuck",
                    "text": "Loading spinner appears stuck.",
                    "metadata": {"app_name": "Chrome", "privacy_level": "redacted"},
                    "payload": {"ocr_text": "SECRET SCREEN TEXT"},
                },
                {
                    "collector": "share_activity",
                    "stimulus_type": "drag_drop_text",
                    "text": "Text drag/drop action observed.",
                    "metadata": {"app_name": "Notes", "privacy_level": "redacted"},
                    "payload": {"text": "SECRET DRAGGED TEXT"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "device_state": True,
                        "downloads": True,
                        "git_activity": True,
                        "github_activity": True,
                        "visual_state": True,
                        "share_activity": True,
                    },
                    "rich_capture_opt_in": {"visual_state": True, "share_activity": True},
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {"device_state", "downloads", "git_activity", "github_activity", "visual_state", "share_activity"},
        )
        batch = result.attention_batches[0]
        self.assertIn("Device/session state event(s): 1", batch["text"])
        self.assertIn("Download/export event(s): 1", batch["text"])
        self.assertIn("Git activity event(s): 1", batch["text"])
        self.assertIn("GitHub activity event(s): 1", batch["text"])
        self.assertIn("Visual-state event(s): 1", batch["text"])
        self.assertIn("Share/drag-drop event(s): 1", batch["text"])
        self.assertNotIn("SECRET DIFF", str(batch))
        self.assertNotIn("SECRET CI LOG", str(batch))
        self.assertNotIn("SECRET SCREEN TEXT", str(batch))
        self.assertNotIn("SECRET DRAGGED TEXT", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("device_state_changed", semantic_types)
        self.assertIn("download_activity", semantic_types)
        self.assertIn("git_activity", semantic_types)
        self.assertIn("github_activity", semantic_types)
        self.assertIn("visual_state_changed", semantic_types)
        self.assertIn("share_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("analyze", action_types)

    def test_downloads_collector_polls_watch_paths_after_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            downloads = root / "Downloads"
            workspace.mkdir()
            downloads.mkdir()
            (downloads / "existing.pdf").write_text("old", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "watch_paths": [str(downloads)],
                    "max_file_events": 3,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "downloads": True,
                    },
                },
            )

            baseline = run_collector_tick(config, force=True)
            created = downloads / "report.pdf"
            created.write_text("new report body", encoding="utf-8")
            changed = run_collector_tick(config, force=True)

        self.assertEqual(baseline.collected, [])
        self.assertEqual(len(changed.collected), 1)
        self.assertEqual(changed.collected[0]["collector"], "downloads")
        self.assertEqual(changed.collected[0]["stimulus_type"], "downloaded_file")
        self.assertIn("Download/export event(s): 1", changed.attention_batches[0]["text"])
        self.assertIn("download_activity", {event["event_type"] for event in changed.semantic_events})
        self.assertNotIn(str(created), str(changed.attention_batches[0]))

    def test_git_activity_collector_polls_dirty_transition_after_baseline(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is not available")
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "repo"
            workspace.mkdir()
            subprocess.run(["git", "init"], cwd=workspace, check=True, capture_output=True, text=True)
            (workspace / "README.md").write_text("# Repo\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=workspace, check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "initial"],
                cwd=workspace,
                check=True,
                capture_output=True,
                text=True,
            )
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "git_activity": True,
                    },
                },
            )

            baseline = run_collector_tick(config, force=True)
            (workspace / "README.md").write_text("# Repo\n\nDirty worktree.\n", encoding="utf-8")
            dirty = run_collector_tick(config, force=True)

        self.assertEqual(baseline.collected, [])
        self.assertEqual(len(dirty.collected), 1)
        self.assertEqual(dirty.collected[0]["collector"], "git_activity")
        self.assertEqual(dirty.collected[0]["stimulus_type"], "working_tree_dirty")
        self.assertIn("Git activity event(s): 1", dirty.attention_batches[0]["text"])
        self.assertIn("git_activity", {event["event_type"] for event in dirty.semantic_events})
        self.assertIn("analyze", {candidate["action_type"] for candidate in dirty.action_candidates})
        self.assertNotIn("Dirty worktree", str(dirty.attention_batches[0]))

    def test_os_activity_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "software_activity",
                    "stimulus_type": "installer_failed",
                    "text": "Installer failed for local dependency.",
                    "metadata": {"app_name": "Installer", "package_name": "toolkit"},
                    "payload": {"install_log": "SECRET INSTALL LOG"},
                },
                {
                    "collector": "print_scan_activity",
                    "stimulus_type": "print_job_failed",
                    "text": "Print job failed for SECRET DOCUMENT TITLE.",
                    "metadata": {"printer_name": "Office Printer"},
                    "payload": {"document_title": "SECRET DOCUMENT TITLE"},
                },
                {
                    "collector": "search_activity",
                    "stimulus_type": "app_launched_from_search",
                    "text": "App launched from launcher search for SECRET SEARCH QUERY.",
                    "metadata": {"app_name": "Xcode", "privacy_level": "redacted"},
                    "payload": {"query": "SECRET SEARCH QUERY"},
                },
                {
                    "collector": "peripheral_activity",
                    "stimulus_type": "external_display_connected",
                    "text": "External display connected.",
                    "metadata": {"device_name": "Studio Display"},
                    "payload": {"serial_number": "SECRET SERIAL"},
                },
                {
                    "collector": "media_activity",
                    "stimulus_type": "screen_recording_started",
                    "text": "Screen recording started at /secret/recording.mov.",
                    "metadata": {"app_name": "QuickTime Player"},
                    "payload": {"recording_path": "/secret/recording.mov"},
                },
                {
                    "collector": "focus_task_activity",
                    "stimulus_type": "task_started",
                    "text": "Task session started.",
                    "metadata": {"task_id": "task-1"},
                    "payload": {"task_notes": "SECRET TASK NOTES"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "software_activity": True,
                        "print_scan_activity": True,
                        "search_activity": True,
                        "peripheral_activity": True,
                        "media_activity": True,
                        "focus_task_activity": True,
                    },
                    "rich_capture_opt_in": {"search_activity": True},
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {
                "software_activity",
                "print_scan_activity",
                "search_activity",
                "peripheral_activity",
                "media_activity",
                "focus_task_activity",
            },
        )
        batch = result.attention_batches[0]
        self.assertIn("Software/install event(s): 1", batch["text"])
        self.assertIn("Print/scan event(s): 1", batch["text"])
        self.assertIn("Search/launcher event(s): 1", batch["text"])
        self.assertIn("Peripheral event(s): 1", batch["text"])
        self.assertIn("Media event(s): 1", batch["text"])
        self.assertIn("Focus/task event(s): 1", batch["text"])
        self.assertNotIn("SECRET INSTALL LOG", str(batch))
        self.assertNotIn("SECRET DOCUMENT TITLE", str(batch))
        self.assertNotIn("SECRET SEARCH QUERY", str(batch))
        self.assertNotIn("SECRET SERIAL", str(batch))
        self.assertNotIn("/secret/recording.mov", str(batch))
        self.assertNotIn("SECRET TASK NOTES", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("software_activity", semantic_types)
        self.assertIn("print_scan_activity", semantic_types)
        self.assertIn("search_activity", semantic_types)
        self.assertIn("peripheral_activity", semantic_types)
        self.assertIn("media_activity", semantic_types)
        self.assertIn("focus_task_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("update_context", action_types)
        self.assertIn("review_attention", action_types)
        self.assertIn("prepare_resume_context", action_types)
        self.assertIn("suppress_collection", action_types)

    def test_workspace_layout_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "workspace_layout_activity",
                    "stimulus_type": "desktop_space_switched",
                    "text": "Desktop space switched to SECRET SPACE.",
                    "metadata": {"app_name": "Mission Control", "layout_mode": "spaces", "privacy_level": "redacted"},
                    "payload": {"space_name": "SECRET SPACE", "visible_windows": "SECRET WINDOWS"},
                },
                {
                    "collector": "window_arrangement_activity",
                    "stimulus_type": "split_view_started",
                    "text": "Split view started with SECRET WINDOW TITLE.",
                    "metadata": {"app_name": "WindowServer", "arrangement_kind": "split_view", "privacy_level": "redacted"},
                    "payload": {"window_title": "SECRET WINDOW TITLE", "layout_details": "SECRET LAYOUT"},
                },
                {
                    "collector": "display_arrangement_activity",
                    "stimulus_type": "display_arrangement_changed",
                    "text": "Display arrangement changed for SECRET DISPLAY.",
                    "metadata": {"app_name": "System Settings", "display_kind": "external"},
                    "payload": {"display_name": "SECRET DISPLAY", "visible_contents": "SECRET DISPLAY CONTENT"},
                },
                {
                    "collector": "app_workspace_activity",
                    "stimulus_type": "app_workspace_switched",
                    "text": "App workspace switched to SECRET PROJECT.",
                    "metadata": {"app_name": "VS Code", "workspace_kind": "project", "privacy_level": "redacted"},
                    "payload": {"workspace_name": "SECRET PROJECT", "restored_contents": "SECRET RESTORED CONTENTS"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "workspace_layout_activity": True,
                        "window_arrangement_activity": True,
                        "display_arrangement_activity": True,
                        "app_workspace_activity": True,
                    },
                    "rich_capture_opt_in": {
                        "workspace_layout_activity": True,
                        "window_arrangement_activity": True,
                        "app_workspace_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {"workspace_layout_activity", "window_arrangement_activity", "display_arrangement_activity", "app_workspace_activity"},
        )
        batch = result.attention_batches[0]
        self.assertIn("Workspace layout event(s): 1", batch["text"])
        self.assertIn("Window arrangement event(s): 1", batch["text"])
        self.assertIn("Display arrangement event(s): 1", batch["text"])
        self.assertIn("App workspace event(s): 1", batch["text"])
        self.assertNotIn("SECRET SPACE", str(batch))
        self.assertNotIn("SECRET WINDOWS", str(batch))
        self.assertNotIn("SECRET WINDOW TITLE", str(batch))
        self.assertNotIn("SECRET LAYOUT", str(batch))
        self.assertNotIn("SECRET DISPLAY", str(batch))
        self.assertNotIn("SECRET DISPLAY CONTENT", str(batch))
        self.assertNotIn("SECRET PROJECT", str(batch))
        self.assertNotIn("SECRET RESTORED CONTENTS", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("workspace_layout_activity", semantic_types)
        self.assertIn("window_arrangement_activity", semantic_types)
        self.assertIn("display_arrangement_activity", semantic_types)
        self.assertIn("app_workspace_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("prepare_resume_context", action_types)
        self.assertIn("update_context", action_types)

    def test_input_services_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "keyboard_input_activity",
                    "stimulus_type": "input_source_changed",
                    "text": "Input source changed from SECRET KEYBOARD LABEL.",
                    "metadata": {"app_name": "System Settings", "input_source_kind": "language"},
                    "payload": {"layout_name": "SECRET KEYBOARD LABEL", "shortcut_payload": "SECRET SHORTCUT PAYLOAD"},
                },
                {
                    "collector": "ime_activity",
                    "stimulus_type": "ime_candidate_selected",
                    "text": "IME candidate selected: SECRET CANDIDATE.",
                    "metadata": {"app_name": "Notes", "ime_kind": "candidate", "window_title": "SECRET IME WINDOW", "privacy_level": "redacted"},
                    "payload": {"candidate_text": "SECRET CANDIDATE", "committed_text": "SECRET COMMITTED TEXT"},
                },
                {
                    "collector": "text_input_surface_activity",
                    "stimulus_type": "secure_text_field_focused",
                    "text": "Secure text field focused with SECRET FIELD VALUE.",
                    "metadata": {"app_name": "Safari", "input_surface_kind": "secure", "url": "https://secret.example/login", "privacy_level": "redacted"},
                    "payload": {"field_label": "SECRET FIELD LABEL", "field_value": "SECRET FIELD VALUE"},
                },
                {
                    "collector": "pasteboard_workflow_activity",
                    "stimulus_type": "clipboard_history_item_selected",
                    "text": "Clipboard history item selected: SECRET CLIPBOARD VALUE.",
                    "metadata": {"app_name": "Clipboard Manager", "pasteboard_action": "history_select", "privacy_level": "redacted"},
                    "payload": {"clipboard_value": "SECRET CLIPBOARD VALUE", "history_title": "SECRET HISTORY TITLE"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "keyboard_input_activity": True,
                        "ime_activity": True,
                        "text_input_surface_activity": True,
                        "pasteboard_workflow_activity": True,
                    },
                    "rich_capture_opt_in": {
                        "ime_activity": True,
                        "text_input_surface_activity": True,
                        "pasteboard_workflow_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {"keyboard_input_activity", "ime_activity", "text_input_surface_activity", "pasteboard_workflow_activity"},
        )
        batch = result.attention_batches[0]
        self.assertIn("Keyboard/input-source event(s): 1", batch["text"])
        self.assertIn("IME/input composition event(s): 1", batch["text"])
        self.assertIn("Text input surface event(s): 1", batch["text"])
        self.assertIn("Pasteboard workflow event(s): 1", batch["text"])
        self.assertNotIn("SECRET KEYBOARD LABEL", str(batch))
        self.assertNotIn("SECRET SHORTCUT PAYLOAD", str(batch))
        self.assertNotIn("SECRET CANDIDATE", str(batch))
        self.assertNotIn("SECRET IME WINDOW", str(batch))
        self.assertNotIn("SECRET COMMITTED TEXT", str(batch))
        self.assertNotIn("SECRET FIELD VALUE", str(batch))
        self.assertNotIn("secret.example", str(batch))
        self.assertNotIn("SECRET FIELD LABEL", str(batch))
        self.assertNotIn("SECRET CLIPBOARD VALUE", str(batch))
        self.assertNotIn("SECRET HISTORY TITLE", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("keyboard_input_activity", semantic_types)
        self.assertIn("ime_activity", semantic_types)
        self.assertIn("text_input_surface_activity", semantic_types)
        self.assertIn("pasteboard_workflow_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("update_context", action_types)
        self.assertIn("suppress_collection", action_types)

    def test_workflow_environment_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "cloud_sync_activity",
                    "stimulus_type": "sync_conflict_detected",
                    "text": "Cloud sync conflict detected for /secret/client-plan.docx.",
                    "metadata": {"provider": "iCloud", "service_name": "Drive"},
                    "payload": {"path": "/secret/client-plan.docx", "contents": "SECRET CLOUD FILE CONTENT"},
                },
                {
                    "collector": "auth_activity",
                    "stimulus_type": "mfa_prompt_shown",
                    "text": "MFA prompt shown with SECRET MFA CODE.",
                    "metadata": {"provider": "Okta", "account_id": "acct-1", "privacy_level": "redacted"},
                    "payload": {"code": "SECRET MFA CODE", "token": "SECRET TOKEN"},
                },
                {
                    "collector": "network_activity",
                    "stimulus_type": "api_request_failed",
                    "text": "API request failed for https://api.example/SECRET-ENDPOINT.",
                    "metadata": {"service_name": "Payments API"},
                    "payload": {"request_body": "SECRET REQUEST BODY", "url": "https://api.example/SECRET-ENDPOINT"},
                },
                {
                    "collector": "automation_activity",
                    "stimulus_type": "workflow_failed",
                    "text": "Workflow failed with SECRET WORKFLOW PAYLOAD.",
                    "metadata": {"app_name": "Shortcuts"},
                    "payload": {"workflow_payload": "SECRET WORKFLOW PAYLOAD"},
                },
                {
                    "collector": "virtual_runtime_activity",
                    "stimulus_type": "container_failed",
                    "text": "Container failed with SECRET LOG.",
                    "metadata": {"runtime_name": "Docker"},
                    "payload": {"logs": "SECRET LOG"},
                },
                {
                    "collector": "remote_session_activity",
                    "stimulus_type": "screen_share_started",
                    "text": "Screen share started with SECRET SCREEN TITLE.",
                    "metadata": {"app_name": "Zoom", "session_id": "session-1", "privacy_level": "redacted"},
                    "payload": {"screen_title": "SECRET SCREEN TITLE"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "cloud_sync_activity": True,
                        "auth_activity": True,
                        "network_activity": True,
                        "automation_activity": True,
                        "virtual_runtime_activity": True,
                        "remote_session_activity": True,
                    },
                    "rich_capture_opt_in": {"auth_activity": True, "remote_session_activity": True},
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {
                "cloud_sync_activity",
                "auth_activity",
                "network_activity",
                "automation_activity",
                "virtual_runtime_activity",
                "remote_session_activity",
            },
        )
        batch = result.attention_batches[0]
        self.assertIn("Cloud sync event(s): 1", batch["text"])
        self.assertIn("Authentication event(s): 1", batch["text"])
        self.assertIn("Network/API event(s): 1", batch["text"])
        self.assertIn("Automation event(s): 1", batch["text"])
        self.assertIn("Container/VM runtime event(s): 1", batch["text"])
        self.assertIn("Remote/screen-share event(s): 1", batch["text"])
        self.assertNotIn("SECRET CLOUD FILE CONTENT", str(batch))
        self.assertNotIn("/secret/client-plan.docx", str(batch))
        self.assertNotIn("SECRET MFA CODE", str(batch))
        self.assertNotIn("SECRET TOKEN", str(batch))
        self.assertNotIn("SECRET-ENDPOINT", str(batch))
        self.assertNotIn("SECRET REQUEST BODY", str(batch))
        self.assertNotIn("SECRET WORKFLOW PAYLOAD", str(batch))
        self.assertNotIn("SECRET LOG", str(batch))
        self.assertNotIn("SECRET SCREEN TITLE", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("cloud_sync_activity", semantic_types)
        self.assertIn("auth_activity", semantic_types)
        self.assertIn("network_activity", semantic_types)
        self.assertIn("automation_activity", semantic_types)
        self.assertIn("virtual_runtime_activity", semantic_types)
        self.assertIn("remote_session_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("review_attention", action_types)
        self.assertIn("suppress_collection", action_types)
        self.assertIn("analyze", action_types)

    def test_platform_context_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "permission_activity",
                    "stimulus_type": "privacy_indicator_enabled",
                    "text": "Camera privacy indicator enabled for SECRET MEETING.",
                    "metadata": {"permission": "camera", "privacy_level": "redacted"},
                    "payload": {"prompt_text": "SECRET PERMISSION PROMPT"},
                },
                {
                    "collector": "location_activity",
                    "stimulus_type": "location_access_started",
                    "text": "Location access started at SECRET COORDINATES.",
                    "metadata": {"region": "IN", "timezone": "Asia/Kolkata", "privacy_level": "redacted"},
                    "payload": {"coordinates": "SECRET COORDINATES"},
                },
                {
                    "collector": "resource_activity",
                    "stimulus_type": "memory_pressure_high",
                    "text": "Memory pressure is high.",
                    "metadata": {"process_name": "Xcode"},
                    "payload": {"process_list": "SECRET PROCESS LIST"},
                },
                {
                    "collector": "storage_activity",
                    "stimulus_type": "disk_space_low",
                    "text": "Disk space low on private volume.",
                    "metadata": {"volume_name": "Macintosh HD"},
                    "payload": {"largest_files": "SECRET FILE LIST"},
                },
                {
                    "collector": "wellbeing_activity",
                    "stimulus_type": "screen_time_limit_reached",
                    "text": "Screen time limit reached.",
                    "metadata": {"app_name": "Browser"},
                    "payload": {"category_usage": "SECRET USAGE DETAILS"},
                },
                {
                    "collector": "policy_activity",
                    "stimulus_type": "policy_blocked_action",
                    "text": "Policy blocked action containing SECRET DOCUMENT.",
                    "metadata": {"policy_id": "policy-1"},
                    "payload": {"document_excerpt": "SECRET DOCUMENT"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "permission_activity": True,
                        "location_activity": True,
                        "resource_activity": True,
                        "storage_activity": True,
                        "wellbeing_activity": True,
                        "policy_activity": True,
                    },
                    "rich_capture_opt_in": {"permission_activity": True, "location_activity": True},
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {
                "permission_activity",
                "location_activity",
                "resource_activity",
                "storage_activity",
                "wellbeing_activity",
                "policy_activity",
            },
        )
        batch = result.attention_batches[0]
        self.assertIn("Permission/privacy event(s): 1", batch["text"])
        self.assertIn("Location/region event(s): 1", batch["text"])
        self.assertIn("Resource pressure event(s): 1", batch["text"])
        self.assertIn("Storage/backup event(s): 1", batch["text"])
        self.assertIn("Wellbeing/app-limit event(s): 1", batch["text"])
        self.assertIn("Policy/compliance event(s): 1", batch["text"])
        self.assertNotIn("SECRET MEETING", str(batch))
        self.assertNotIn("SECRET PERMISSION PROMPT", str(batch))
        self.assertNotIn("SECRET COORDINATES", str(batch))
        self.assertNotIn("SECRET PROCESS LIST", str(batch))
        self.assertNotIn("SECRET FILE LIST", str(batch))
        self.assertNotIn("SECRET USAGE DETAILS", str(batch))
        self.assertNotIn("SECRET DOCUMENT", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("permission_activity", semantic_types)
        self.assertIn("location_activity", semantic_types)
        self.assertIn("resource_activity", semantic_types)
        self.assertIn("storage_activity", semantic_types)
        self.assertIn("wellbeing_activity", semantic_types)
        self.assertIn("policy_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("suppress_collection", action_types)
        self.assertIn("update_context", action_types)
        self.assertIn("analyze", action_types)
        self.assertIn("review_attention", action_types)

    def test_personal_workflow_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "notes_activity",
                    "stimulus_type": "note_edited",
                    "text": "Note edited with SECRET NOTE BODY.",
                    "metadata": {"app_name": "Notes", "note_id": "note-1", "privacy_level": "redacted"},
                    "payload": {"body": "SECRET NOTE BODY"},
                },
                {
                    "collector": "bookmark_history_activity",
                    "stimulus_type": "bookmark_added",
                    "text": "Bookmark added for https://secret.example/private.",
                    "metadata": {"app_name": "Safari", "privacy_level": "redacted"},
                    "payload": {"url": "https://secret.example/private", "query": "SECRET HISTORY QUERY"},
                },
                {
                    "collector": "contact_activity",
                    "stimulus_type": "address_copied",
                    "text": "Address copied: SECRET HOME ADDRESS.",
                    "metadata": {"app_name": "Contacts", "contact_id": "contact-1", "privacy_level": "redacted"},
                    "payload": {"address": "SECRET HOME ADDRESS", "phone": "SECRET PHONE"},
                },
                {
                    "collector": "commerce_activity",
                    "stimulus_type": "checkout_started",
                    "text": "Checkout started for SECRET ITEM.",
                    "metadata": {"merchant": "Store", "privacy_level": "redacted"},
                    "payload": {"item": "SECRET ITEM", "shipping_address": "SECRET SHIPPING ADDRESS"},
                },
                {
                    "collector": "finance_activity",
                    "stimulus_type": "payment_prompt_shown",
                    "text": "Payment prompt shown for SECRET AMOUNT.",
                    "metadata": {"provider_name": "Wallet", "privacy_level": "redacted"},
                    "payload": {"amount": "SECRET AMOUNT", "card": "SECRET CARD"},
                },
                {
                    "collector": "social_feed_activity",
                    "stimulus_type": "comment_received",
                    "text": "Comment received: SECRET COMMENT BODY.",
                    "metadata": {"social_network": "Social", "privacy_level": "redacted"},
                    "payload": {"comment": "SECRET COMMENT BODY"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "notes_activity": True,
                        "bookmark_history_activity": True,
                        "contact_activity": True,
                        "commerce_activity": True,
                        "finance_activity": True,
                        "social_feed_activity": True,
                    },
                    "rich_capture_opt_in": {
                        "notes_activity": True,
                        "bookmark_history_activity": True,
                        "contact_activity": True,
                        "commerce_activity": True,
                        "finance_activity": True,
                        "social_feed_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {
                "notes_activity",
                "bookmark_history_activity",
                "contact_activity",
                "commerce_activity",
                "finance_activity",
                "social_feed_activity",
            },
        )
        batch = result.attention_batches[0]
        self.assertIn("Notes/checklist event(s): 1", batch["text"])
        self.assertIn("Bookmark/history event(s): 1", batch["text"])
        self.assertIn("Contact event(s): 1", batch["text"])
        self.assertIn("Commerce event(s): 1", batch["text"])
        self.assertIn("Finance/wallet event(s): 1", batch["text"])
        self.assertIn("Social/feed event(s): 1", batch["text"])
        self.assertNotIn("SECRET NOTE BODY", str(batch))
        self.assertNotIn("secret.example", str(batch))
        self.assertNotIn("SECRET HISTORY QUERY", str(batch))
        self.assertNotIn("SECRET HOME ADDRESS", str(batch))
        self.assertNotIn("SECRET PHONE", str(batch))
        self.assertNotIn("SECRET ITEM", str(batch))
        self.assertNotIn("SECRET SHIPPING ADDRESS", str(batch))
        self.assertNotIn("SECRET AMOUNT", str(batch))
        self.assertNotIn("SECRET CARD", str(batch))
        self.assertNotIn("SECRET COMMENT BODY", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("notes_activity", semantic_types)
        self.assertIn("bookmark_history_activity", semantic_types)
        self.assertIn("contact_activity", semantic_types)
        self.assertIn("commerce_activity", semantic_types)
        self.assertIn("finance_activity", semantic_types)
        self.assertIn("social_feed_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("update_context", action_types)
        self.assertIn("monitor_research", action_types)
        self.assertIn("suppress_collection", action_types)
        self.assertIn("review_attention", action_types)
        self.assertIn("review_message", action_types)

    def test_planning_collaboration_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "task_manager_activity",
                    "stimulus_type": "task_assigned",
                    "text": "Task assigned: SECRET TASK TITLE.",
                    "metadata": {"app_name": "Linear", "task_id": "task-1", "privacy_level": "redacted"},
                    "payload": {"title": "SECRET TASK TITLE", "body": "SECRET TASK BODY"},
                },
                {
                    "collector": "issue_tracker_activity",
                    "stimulus_type": "issue_blocker_added",
                    "text": "Issue blocker added: SECRET ISSUE BODY.",
                    "metadata": {"app_name": "Jira", "issue_id": "ISSUE-1", "privacy_level": "redacted"},
                    "payload": {"body": "SECRET ISSUE BODY"},
                },
                {
                    "collector": "knowledge_base_activity",
                    "stimulus_type": "page_edited",
                    "text": "Wiki page edited with SECRET WIKI TEXT.",
                    "metadata": {"app_name": "Notion", "page_id": "page-1", "privacy_level": "redacted"},
                    "payload": {"page_text": "SECRET WIKI TEXT"},
                },
                {
                    "collector": "whiteboard_activity",
                    "stimulus_type": "whiteboard_comment_added",
                    "text": "Whiteboard comment added: SECRET BOARD CONTENT.",
                    "metadata": {"app_name": "Miro", "board_id": "board-1", "privacy_level": "redacted"},
                    "payload": {"board_text": "SECRET BOARD CONTENT"},
                },
                {
                    "collector": "form_survey_activity",
                    "stimulus_type": "form_validation_error",
                    "text": "Form validation error with SECRET FORM ANSWER.",
                    "metadata": {"app_name": "Forms", "form_id": "form-1", "privacy_level": "redacted"},
                    "payload": {"answer": "SECRET FORM ANSWER"},
                },
                {
                    "collector": "learning_activity",
                    "stimulus_type": "quiz_submitted",
                    "text": "Quiz submitted.",
                    "metadata": {"app_name": "Course", "course_id": "course-1"},
                    "payload": {"quiz_answers": "SECRET QUIZ ANSWERS"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "task_manager_activity": True,
                        "issue_tracker_activity": True,
                        "knowledge_base_activity": True,
                        "whiteboard_activity": True,
                        "form_survey_activity": True,
                        "learning_activity": True,
                    },
                    "rich_capture_opt_in": {
                        "task_manager_activity": True,
                        "issue_tracker_activity": True,
                        "knowledge_base_activity": True,
                        "whiteboard_activity": True,
                        "form_survey_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {
                "task_manager_activity",
                "issue_tracker_activity",
                "knowledge_base_activity",
                "whiteboard_activity",
                "form_survey_activity",
                "learning_activity",
            },
        )
        batch = result.attention_batches[0]
        self.assertIn("Task manager event(s): 1", batch["text"])
        self.assertIn("Issue tracker event(s): 1", batch["text"])
        self.assertIn("Knowledge-base event(s): 1", batch["text"])
        self.assertIn("Whiteboard event(s): 1", batch["text"])
        self.assertIn("Form/survey event(s): 1", batch["text"])
        self.assertIn("Learning/course event(s): 1", batch["text"])
        self.assertNotIn("SECRET TASK TITLE", str(batch))
        self.assertNotIn("SECRET TASK BODY", str(batch))
        self.assertNotIn("SECRET ISSUE BODY", str(batch))
        self.assertNotIn("SECRET WIKI TEXT", str(batch))
        self.assertNotIn("SECRET BOARD CONTENT", str(batch))
        self.assertNotIn("SECRET FORM ANSWER", str(batch))
        self.assertNotIn("SECRET QUIZ ANSWERS", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("task_manager_activity", semantic_types)
        self.assertIn("issue_tracker_activity", semantic_types)
        self.assertIn("knowledge_base_activity", semantic_types)
        self.assertIn("whiteboard_activity", semantic_types)
        self.assertIn("form_survey_activity", semantic_types)
        self.assertIn("learning_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("prepare_resume_context", action_types)
        self.assertIn("analyze", action_types)
        self.assertIn("update_context", action_types)
        self.assertIn("review_attention", action_types)

    def test_business_operations_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "crm_activity",
                    "stimulus_type": "customer_note_added",
                    "text": "Customer note added with SECRET CUSTOMER NOTE.",
                    "metadata": {"app_name": "Salesforce", "customer_id": "cust-1", "privacy_level": "redacted"},
                    "payload": {"note": "SECRET CUSTOMER NOTE", "email": "SECRET CUSTOMER EMAIL"},
                },
                {
                    "collector": "support_desk_activity",
                    "stimulus_type": "ticket_escalated",
                    "text": "Ticket escalated with SECRET CUSTOMER MESSAGE.",
                    "metadata": {"app_name": "Zendesk", "ticket_id": "ticket-1", "privacy_level": "redacted"},
                    "payload": {"message": "SECRET CUSTOMER MESSAGE"},
                },
                {
                    "collector": "analytics_activity",
                    "stimulus_type": "metric_threshold_crossed",
                    "text": "Metric threshold crossed for SECRET REVENUE.",
                    "metadata": {"app_name": "Looker", "dashboard_id": "dash-1", "privacy_level": "redacted"},
                    "payload": {"metric_value": "SECRET REVENUE", "rows": "SECRET ROWS"},
                },
                {
                    "collector": "database_activity",
                    "stimulus_type": "query_failed",
                    "text": "Database query failed: SELECT * FROM SECRET_TABLE.",
                    "metadata": {"app_name": "DataGrip", "database_name": "prod", "privacy_level": "redacted"},
                    "payload": {"sql": "SELECT * FROM SECRET_TABLE", "rows": "SECRET ROWS"},
                },
                {
                    "collector": "cloud_console_activity",
                    "stimulus_type": "secret_view_attempted",
                    "text": "Secret view attempted for SECRET RESOURCE ID.",
                    "metadata": {"app_name": "AWS Console", "resource_type": "secret", "privacy_level": "redacted"},
                    "payload": {"resource_id": "SECRET RESOURCE ID", "secret_value": "SECRET VALUE"},
                },
                {
                    "collector": "incident_activity",
                    "stimulus_type": "on_call_alert_received",
                    "text": "On-call alert received with SECRET INCIDENT LOG.",
                    "metadata": {"app_name": "PagerDuty", "incident_id": "incident-1", "privacy_level": "redacted"},
                    "payload": {"log": "SECRET INCIDENT LOG"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "crm_activity": True,
                        "support_desk_activity": True,
                        "analytics_activity": True,
                        "database_activity": True,
                        "cloud_console_activity": True,
                        "incident_activity": True,
                    },
                    "rich_capture_opt_in": {
                        "crm_activity": True,
                        "support_desk_activity": True,
                        "analytics_activity": True,
                        "database_activity": True,
                        "cloud_console_activity": True,
                        "incident_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {
                "crm_activity",
                "support_desk_activity",
                "analytics_activity",
                "database_activity",
                "cloud_console_activity",
                "incident_activity",
            },
        )
        batch = result.attention_batches[0]
        self.assertIn("CRM event(s): 1", batch["text"])
        self.assertIn("Support desk event(s): 1", batch["text"])
        self.assertIn("Analytics event(s): 1", batch["text"])
        self.assertIn("Database event(s): 1", batch["text"])
        self.assertIn("Cloud console event(s): 1", batch["text"])
        self.assertIn("Incident/on-call event(s): 1", batch["text"])
        self.assertNotIn("SECRET CUSTOMER NOTE", str(batch))
        self.assertNotIn("SECRET CUSTOMER EMAIL", str(batch))
        self.assertNotIn("SECRET CUSTOMER MESSAGE", str(batch))
        self.assertNotIn("SECRET REVENUE", str(batch))
        self.assertNotIn("SECRET_TABLE", str(batch))
        self.assertNotIn("SECRET RESOURCE ID", str(batch))
        self.assertNotIn("SECRET VALUE", str(batch))
        self.assertNotIn("SECRET INCIDENT LOG", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("crm_activity", semantic_types)
        self.assertIn("support_desk_activity", semantic_types)
        self.assertIn("analytics_activity", semantic_types)
        self.assertIn("database_activity", semantic_types)
        self.assertIn("cloud_console_activity", semantic_types)
        self.assertIn("incident_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("prepare_resume_context", action_types)
        self.assertIn("review_attention", action_types)
        self.assertIn("analyze", action_types)
        self.assertIn("suppress_collection", action_types)

    def test_file_activity_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "file_operation_activity",
                    "stimulus_type": "file_saved",
                    "text": "File saved at /tmp/humungousaur-fixtures/SECRET_PATH/plan.md.",
                    "metadata": {"app_name": "Finder", "file_action": "save", "privacy_level": "redacted"},
                    "payload": {"path": "/tmp/humungousaur-fixtures/SECRET_PATH/plan.md", "filename": "SECRET FILE", "contents": "SECRET FILE CONTENT"},
                },
                {
                    "collector": "folder_navigation_activity",
                    "stimulus_type": "folder_changed",
                    "text": "Folder changed to /tmp/humungousaur-fixtures/SECRET_FOLDER.",
                    "metadata": {"app_name": "Finder", "folder_action": "navigate", "privacy_level": "redacted"},
                    "payload": {"folder_path": "/tmp/humungousaur-fixtures/SECRET_FOLDER", "folder_name": "SECRET FOLDER"},
                },
                {
                    "collector": "file_preview_activity",
                    "stimulus_type": "quick_look_opened",
                    "text": "Quick Look opened SECRET PREVIEW.",
                    "metadata": {"app_name": "Finder", "preview_kind": "quick_look", "privacy_level": "redacted"},
                    "payload": {"preview_text": "SECRET PREVIEW", "metadata": "SECRET METADATA", "filename": "SECRET PREVIEW FILE"},
                },
                {
                    "collector": "trash_activity",
                    "stimulus_type": "trash_item_deleted",
                    "text": "Trash item deleted: SECRET TRASH ITEM.",
                    "metadata": {"app_name": "Finder", "trash_action": "delete", "privacy_level": "redacted"},
                    "payload": {"item_path": "/tmp/humungousaur-fixtures/.Trash/SECRET TRASH ITEM", "contents": "SECRET TRASH CONTENT"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "file_operation_activity": True,
                        "folder_navigation_activity": True,
                        "file_preview_activity": True,
                        "trash_activity": True,
                    },
                    "rich_capture_opt_in": {
                        "file_operation_activity": True,
                        "folder_navigation_activity": True,
                        "file_preview_activity": True,
                        "trash_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {"file_operation_activity", "folder_navigation_activity", "file_preview_activity", "trash_activity"},
        )
        batch = result.attention_batches[0]
        self.assertIn("File operation event(s): 1", batch["text"])
        self.assertIn("Folder navigation event(s): 1", batch["text"])
        self.assertIn("File preview event(s): 1", batch["text"])
        self.assertIn("Trash/recycle-bin event(s): 1", batch["text"])
        self.assertNotIn("SECRET_PATH", str(batch))
        self.assertNotIn("SECRET FILE", str(batch))
        self.assertNotIn("SECRET FILE CONTENT", str(batch))
        self.assertNotIn("SECRET_FOLDER", str(batch))
        self.assertNotIn("SECRET FOLDER", str(batch))
        self.assertNotIn("SECRET PREVIEW", str(batch))
        self.assertNotIn("SECRET METADATA", str(batch))
        self.assertNotIn("SECRET PREVIEW FILE", str(batch))
        self.assertNotIn("SECRET TRASH ITEM", str(batch))
        self.assertNotIn("SECRET TRASH CONTENT", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("file_operation_activity", semantic_types)
        self.assertIn("folder_navigation_activity", semantic_types)
        self.assertIn("file_preview_activity", semantic_types)
        self.assertIn("trash_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("update_context", action_types)
        self.assertIn("prepare_resume_context", action_types)
        self.assertIn("review_attention", action_types)

    def test_file_operation_activity_emits_local_open_save_close_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            watched_file = workspace / "plan.md"
            watched_file.write_text("v1", encoding="utf-8")
            resolved = str(watched_file.resolve())
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "file_operation_activity": True,
                    },
                    "rich_capture_opt_in": {"file_operation_activity": True},
                    "watch_paths": [str(workspace)],
                    "max_file_events": 5,
                },
            )

            with patch("humungousaur.collectors.adapters.file_activity_adapters._open_handle_supported", return_value=True), patch(
                "humungousaur.collectors.adapters.file_activity_adapters._open_file_paths",
                side_effect=[set(), {resolved}, set()],
            ):
                baseline = run_collector_tick(config, force=True)
                watched_file.write_text("v2", encoding="utf-8")
                os.utime(watched_file, (watched_file.stat().st_atime, watched_file.stat().st_mtime + 5))
                changed = run_collector_tick(config, force=True)
                closed = run_collector_tick(config, force=True)

        self.assertEqual(baseline.collected, [])
        self.assertEqual({event["stimulus_type"] for event in changed.collected}, {"file_opened", "file_saved"})
        self.assertEqual([event["stimulus_type"] for event in closed.collected], ["file_closed"])
        batch_text = " ".join(batch["text"] for batch in changed.attention_batches + closed.attention_batches)
        self.assertIn("File operation event(s):", batch_text)
        self.assertNotIn("plan.md", str(changed.attention_batches + closed.attention_batches))
        semantic_types = {event["event_type"] for event in changed.semantic_events + closed.semantic_events}
        self.assertIn("file_operation_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in changed.action_candidates + closed.action_candidates}
        self.assertIn("update_context", action_types)

    def test_file_operation_activity_classifies_local_rename_and_move(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            destination = workspace / "destination"
            workspace.mkdir()
            destination.mkdir()
            file_path = workspace / "draft.md"
            file_path.write_text("v1", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": False,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "file_operation_activity": True,
                    },
                    "rich_capture_opt_in": {"file_operation_activity": True},
                    "watch_paths": [str(workspace)],
                    "max_file_events": 5,
                },
            )

            baseline = run_collector_tick(config, force=True)
            renamed = workspace / "renamed.md"
            file_path.rename(renamed)
            rename_result = run_collector_tick(config, force=True)
            moved = destination / "renamed.md"
            renamed.rename(moved)
            move_result = run_collector_tick(config, force=True)

        self.assertEqual(baseline.collected, [])
        self.assertIn("file_renamed", {event["stimulus_type"] for event in rename_result.collected})
        self.assertIn("file_moved", {event["stimulus_type"] for event in move_result.collected})
        self.assertTrue(any("previous_path_digest" in event["payload"] for event in rename_result.collected))
        self.assertTrue(any("previous_path_digest" in event["payload"] for event in move_result.collected))

    def test_folder_navigation_activity_emits_local_folder_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            existing = workspace / "existing"
            existing.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "folder_navigation_activity": True,
                    },
                    "rich_capture_opt_in": {"folder_navigation_activity": True},
                    "watch_paths": [str(workspace)],
                    "max_file_events": 5,
                },
            )

            baseline = run_collector_tick(config, force=True)
            created = workspace / "SECRET_FOLDER_NAME"
            created.mkdir()
            changed = run_collector_tick(config, force=True)

        self.assertEqual(baseline.collected, [])
        self.assertIn("folder_created", {event["stimulus_type"] for event in changed.collected})
        self.assertNotIn("SECRET_FOLDER_NAME", str(changed.attention_batches))
        semantic_types = {event["event_type"] for event in changed.semantic_events}
        self.assertIn("folder_navigation_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in changed.action_candidates}
        self.assertIn("prepare_resume_context", action_types)

    def test_folder_navigation_activity_classifies_local_rename_and_move(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            destination = workspace / "destination"
            destination.mkdir()
            folder = workspace / "drafts"
            folder.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": False,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "folder_navigation_activity": True,
                    },
                    "rich_capture_opt_in": {"folder_navigation_activity": True},
                    "watch_paths": [str(workspace)],
                    "max_file_events": 5,
                },
            )

            baseline = run_collector_tick(config, force=True)
            renamed = workspace / "renamed-drafts"
            folder.rename(renamed)
            rename_result = run_collector_tick(config, force=True)
            moved = destination / "renamed-drafts"
            renamed.rename(moved)
            move_result = run_collector_tick(config, force=True)

        self.assertEqual(baseline.collected, [])
        self.assertIn("folder_renamed", {event["stimulus_type"] for event in rename_result.collected})
        self.assertIn("folder_moved", {event["stimulus_type"] for event in move_result.collected})
        self.assertTrue(any("previous_path_digest" in event["payload"] for event in rename_result.collected))
        self.assertTrue(any("previous_path_digest" in event["payload"] for event in move_result.collected))

    def test_trash_activity_emits_local_trash_item_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            trash = root / "trash"
            workspace.mkdir()
            trash.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "trash_activity": True,
                    },
                    "rich_capture_opt_in": {"trash_activity": True},
                    "max_file_events": 5,
                },
            )

            with patch("humungousaur.collectors.adapters.file_activity_adapters._trash_roots", return_value=[trash]):
                baseline = run_collector_tick(config, force=True)
                trashed = trash / "SECRET_TRASH_FILE.txt"
                trashed.write_text("SECRET TRASH CONTENT", encoding="utf-8")
                moved = run_collector_tick(config, force=True)
                trashed.unlink()
                deleted = run_collector_tick(config, force=True)

        self.assertEqual(baseline.collected, [])
        self.assertEqual([event["stimulus_type"] for event in moved.collected], ["file_moved_to_trash"])
        self.assertEqual([event["stimulus_type"] for event in deleted.collected], ["trash_item_deleted"])
        self.assertNotIn("SECRET_TRASH_FILE", str(moved.attention_batches + deleted.attention_batches))
        self.assertNotIn("SECRET TRASH CONTENT", str(moved.attention_batches + deleted.attention_batches))
        semantic_types = {event["event_type"] for event in moved.semantic_events + deleted.semantic_events}
        self.assertIn("trash_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in moved.action_candidates + deleted.action_candidates}
        self.assertIn("review_attention", action_types)

    def test_trash_activity_classifies_folders_and_empty_trash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            trash = root / "trash"
            workspace.mkdir()
            trash.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": False,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "trash_activity": True,
                    },
                    "rich_capture_opt_in": {"trash_activity": True},
                    "max_file_events": 5,
                },
            )

            with patch("humungousaur.collectors.adapters.file_activity_adapters._trash_roots", return_value=[trash]):
                baseline = run_collector_tick(config, force=True)
                trashed_folder = trash / "folder"
                trashed_folder.mkdir()
                trashed_file = trash / "file.txt"
                trashed_file.write_text("deleted", encoding="utf-8")
                moved = run_collector_tick(config, force=True)
                trashed_folder.rmdir()
                trashed_file.unlink()
                emptied = run_collector_tick(config, force=True)

        self.assertEqual(baseline.collected, [])
        self.assertIn("folder_moved_to_trash", [event["stimulus_type"] for event in moved.collected])
        self.assertEqual([event["stimulus_type"] for event in emptied.collected], ["trash_emptied"])

    def test_app_surface_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "ai_assistant_activity",
                    "stimulus_type": "ai_tool_call_failed",
                    "text": "AI tool call failed with SECRET PROMPT and SECRET RESPONSE.",
                    "metadata": {"app_name": "ChatGPT", "model": "gpt-test", "privacy_level": "redacted"},
                    "payload": {"prompt": "SECRET PROMPT", "response": "SECRET RESPONSE", "tool_payload": "SECRET TOOL PAYLOAD"},
                },
                {
                    "collector": "pdf_activity",
                    "stimulus_type": "pdf_signature_requested",
                    "text": "PDF signature requested for SECRET PDF TEXT.",
                    "metadata": {"app_name": "Preview", "document_id": "pdf-1", "privacy_level": "redacted"},
                    "payload": {"document_text": "SECRET PDF TEXT", "signature": "SECRET SIGNATURE"},
                },
                {
                    "collector": "spreadsheet_activity",
                    "stimulus_type": "formula_error_detected",
                    "text": "Spreadsheet formula error with SECRET CELL VALUE.",
                    "metadata": {"app_name": "Excel", "workbook_id": "sheet-1", "privacy_level": "redacted"},
                    "payload": {"cell_value": "SECRET CELL VALUE", "formula": "SECRET FORMULA"},
                },
                {
                    "collector": "presentation_activity",
                    "stimulus_type": "slideshow_started",
                    "text": "Slideshow started with SECRET SPEAKER NOTES.",
                    "metadata": {"app_name": "Keynote", "deck_id": "deck-1", "privacy_level": "redacted"},
                    "payload": {"speaker_notes": "SECRET SPEAKER NOTES", "slide_text": "SECRET SLIDE"},
                },
                {
                    "collector": "file_dialog_activity",
                    "stimulus_type": "save_confirmed",
                    "text": "Save confirmed for /tmp/humungousaur-fixtures/SECRET_PATH/report.pdf.",
                    "metadata": {"app_name": "Preview", "dialog_kind": "save", "privacy_level": "redacted"},
                    "payload": {"selected_path": "/tmp/humungousaur-fixtures/SECRET_PATH/report.pdf", "filename": "SECRET_FILE"},
                },
                {
                    "collector": "system_settings_activity",
                    "stimulus_type": "accessibility_setting_changed",
                    "text": "Accessibility setting changed.",
                    "metadata": {"app_name": "System Settings", "settings_pane": "Accessibility"},
                    "payload": {"setting_value": "SECRET SETTING VALUE"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "ai_assistant_activity": True,
                        "pdf_activity": True,
                        "spreadsheet_activity": True,
                        "presentation_activity": True,
                        "file_dialog_activity": True,
                        "system_settings_activity": True,
                    },
                    "rich_capture_opt_in": {
                        "ai_assistant_activity": True,
                        "pdf_activity": True,
                        "spreadsheet_activity": True,
                        "presentation_activity": True,
                        "file_dialog_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {
                "ai_assistant_activity",
                "pdf_activity",
                "spreadsheet_activity",
                "presentation_activity",
                "file_dialog_activity",
                "system_settings_activity",
            },
        )
        batch = result.attention_batches[0]
        self.assertIn("AI assistant event(s): 1", batch["text"])
        self.assertIn("PDF event(s): 1", batch["text"])
        self.assertIn("Spreadsheet event(s): 1", batch["text"])
        self.assertIn("Presentation event(s): 1", batch["text"])
        self.assertIn("File dialog event(s): 1", batch["text"])
        self.assertIn("System settings event(s): 1", batch["text"])
        self.assertNotIn("SECRET PROMPT", str(batch))
        self.assertNotIn("SECRET RESPONSE", str(batch))
        self.assertNotIn("SECRET TOOL PAYLOAD", str(batch))
        self.assertNotIn("SECRET PDF TEXT", str(batch))
        self.assertNotIn("SECRET SIGNATURE", str(batch))
        self.assertNotIn("SECRET CELL VALUE", str(batch))
        self.assertNotIn("SECRET FORMULA", str(batch))
        self.assertNotIn("SECRET SPEAKER NOTES", str(batch))
        self.assertNotIn("SECRET SLIDE", str(batch))
        self.assertNotIn("SECRET_PATH", str(batch))
        self.assertNotIn("SECRET_FILE", str(batch))
        self.assertNotIn("SECRET SETTING VALUE", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("ai_assistant_activity", semantic_types)
        self.assertIn("pdf_activity", semantic_types)
        self.assertIn("spreadsheet_activity", semantic_types)
        self.assertIn("presentation_activity", semantic_types)
        self.assertIn("file_dialog_activity", semantic_types)
        self.assertIn("system_settings_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("review_agent_runtime", action_types)
        self.assertIn("review_attention", action_types)
        self.assertIn("analyze", action_types)
        self.assertIn("prepare_briefing", action_types)
        self.assertIn("update_context", action_types)

    def test_ai_assistant_source_events_are_redacted_and_queryable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            health = append_ai_assistant_health(
                config,
                {"assistant": "chatgpt", "status": "running", "metadata": {"window_title": "SECRET CHAT TITLE"}},
            )
            accepted = append_ai_assistant_event(
                config,
                {
                    "assistant": "ChatGPT",
                    "event_type": "file_context_attached",
                    "conversation_id": "conversation-secret",
                    "request_id": "request-secret",
                    "model": "secret-model-name",
                    "surface": "browser_app",
                    "metadata": {
                        "file_path": "/tmp/humungousaur-fixtures/SECRET_PATH/app.py",
                        "file_context_count": 2,
                        "prompt": "SECRET PROMPT BODY",
                        "response": "SECRET RESPONSE BODY",
                        "tool_payload": "SECRET TOOL PAYLOAD",
                    },
                    "occurred_at": "2026-06-11T00:00:00+00:00",
                },
            )
            suggestion = append_ai_assistant_event(
                config,
                {
                    "assistant": "cursor",
                    "source_event": "code_suggestion_rejected",
                    "metadata": {"language": "python", "code": "SECRET CODE"},
                },
            )
            with self.assertRaises(ValueError):
                append_ai_assistant_event(config, {"assistant": "chatgpt", "event_type": "raw_prompt_dump", "prompt": "SECRET RAW"})
            queried = query_collector_events(config, collector="ai_assistant_activity", limit=10)
            status = collector_status(config)

        serialized = json.dumps({"health": health, "accepted": accepted, "suggestion": suggestion, "queried": queried, "status": status}, ensure_ascii=False)
        self.assertTrue(health["accepted"])
        self.assertTrue(accepted["accepted"])
        self.assertEqual(accepted["stimulus_type"], "ai_file_context_attached")
        self.assertEqual(suggestion["stimulus_type"], "ai_code_suggestion_rejected")
        self.assertEqual({event["source"] for event in queried["events"]}, {"ai_assistants"})
        self.assertEqual(status["capabilities"]["sources"]["ai_assistants"]["dead_letter_count"], 1)
        self.assertIn("chatgpt", status["capabilities"]["sources"]["ai_assistants"]["supported_assistants"])
        self.assertNotIn("SECRET CHAT TITLE", serialized)
        self.assertNotIn("SECRET_PATH", serialized)
        self.assertNotIn("SECRET PROMPT BODY", serialized)
        self.assertNotIn("SECRET RESPONSE BODY", serialized)
        self.assertNotIn("SECRET TOOL PAYLOAD", serialized)
        self.assertNotIn("secret-model-name", serialized)
        self.assertNotIn("SECRET CODE", serialized)

    def test_content_exchange_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "file_transfer_activity",
                    "stimulus_type": "upload_failed",
                    "text": "Upload failed for SECRET FILE to SECRET RECIPIENT.",
                    "metadata": {"app_name": "Finder", "transfer_kind": "upload", "privacy_level": "redacted"},
                    "payload": {"filename": "SECRET FILE", "recipient": "SECRET RECIPIENT", "url": "SECRET URL"},
                },
                {
                    "collector": "archive_activity",
                    "stimulus_type": "archive_password_requested",
                    "text": "Archive password requested for SECRET ARCHIVE.",
                    "metadata": {"app_name": "Archive Utility", "archive_format": "zip", "privacy_level": "redacted"},
                    "payload": {"archive_path": "SECRET ARCHIVE", "password_prompt": "SECRET PASSWORD PROMPT"},
                },
                {
                    "collector": "camera_capture_activity",
                    "stimulus_type": "qr_code_scanned",
                    "text": "QR code scanned with SECRET QR CONTENT.",
                    "metadata": {"app_name": "Camera", "capture_device": "camera", "privacy_level": "redacted"},
                    "payload": {"qr_content": "SECRET QR CONTENT", "photo": "SECRET PHOTO BYTES"},
                },
                {
                    "collector": "continuity_activity",
                    "stimulus_type": "sms_relay_received",
                    "text": "SMS relay received from SECRET DEVICE.",
                    "metadata": {"app_name": "Messages", "continuity_kind": "sms_relay", "privacy_level": "redacted"},
                    "payload": {"device_name": "SECRET DEVICE", "message_body": "SECRET MESSAGE BODY"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "file_transfer_activity": True,
                        "archive_activity": True,
                        "camera_capture_activity": True,
                        "continuity_activity": True,
                    },
                    "rich_capture_opt_in": {
                        "file_transfer_activity": True,
                        "archive_activity": True,
                        "camera_capture_activity": True,
                        "continuity_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {"file_transfer_activity", "archive_activity", "camera_capture_activity", "continuity_activity"},
        )
        batch = result.attention_batches[0]
        self.assertIn("File transfer event(s): 1", batch["text"])
        self.assertIn("Archive/compression event(s): 1", batch["text"])
        self.assertIn("Camera/photo capture event(s): 1", batch["text"])
        self.assertIn("Continuity event(s): 1", batch["text"])
        self.assertNotIn("SECRET FILE", str(batch))
        self.assertNotIn("SECRET RECIPIENT", str(batch))
        self.assertNotIn("SECRET URL", str(batch))
        self.assertNotIn("SECRET ARCHIVE", str(batch))
        self.assertNotIn("SECRET PASSWORD PROMPT", str(batch))
        self.assertNotIn("SECRET QR CONTENT", str(batch))
        self.assertNotIn("SECRET PHOTO BYTES", str(batch))
        self.assertNotIn("SECRET DEVICE", str(batch))
        self.assertNotIn("SECRET MESSAGE BODY", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("file_transfer_activity", semantic_types)
        self.assertIn("archive_activity", semantic_types)
        self.assertIn("camera_capture_activity", semantic_types)
        self.assertIn("continuity_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("analyze", action_types)
        self.assertIn("suppress_collection", action_types)

    def test_ui_operation_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "command_activity",
                    "stimulus_type": "command_executed",
                    "text": "Command executed: SECRET COMMAND LABEL.",
                    "metadata": {"app_name": "Cursor", "command_kind": "palette", "control_role": "menu_item", "privacy_level": "redacted"},
                    "payload": {"command_label": "SECRET COMMAND LABEL", "menu_path": "SECRET MENU PATH"},
                },
                {
                    "collector": "selection_activity",
                    "stimulus_type": "text_selection_changed",
                    "text": "Selected text changed: SECRET SELECTED TEXT.",
                    "metadata": {"app_name": "Pages", "selection_kind": "text", "privacy_level": "redacted"},
                    "payload": {"selected_text": "SECRET SELECTED TEXT", "object_name": "SECRET OBJECT"},
                },
                {
                    "collector": "navigation_activity",
                    "stimulus_type": "sidebar_item_selected",
                    "text": "Sidebar item selected: SECRET ROUTE LABEL.",
                    "metadata": {"app_name": "Notion", "navigation_target_type": "sidebar", "privacy_level": "redacted"},
                    "payload": {"route_label": "SECRET ROUTE LABEL", "search_text": "SECRET SEARCH TEXT"},
                },
                {
                    "collector": "edit_history_activity",
                    "stimulus_type": "version_restored",
                    "text": "Version restored with SECRET VERSION DETAILS.",
                    "metadata": {"app_name": "Numbers", "history_action": "restore", "privacy_level": "redacted"},
                    "payload": {"version_details": "SECRET VERSION DETAILS", "document_text": "SECRET DOC TEXT"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "command_activity": True,
                        "selection_activity": True,
                        "navigation_activity": True,
                        "edit_history_activity": True,
                    },
                    "rich_capture_opt_in": {
                        "command_activity": True,
                        "selection_activity": True,
                        "navigation_activity": True,
                        "edit_history_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {"command_activity", "selection_activity", "navigation_activity", "edit_history_activity"},
        )
        batch = result.attention_batches[0]
        self.assertIn("In-app command event(s): 1", batch["text"])
        self.assertIn("In-app selection event(s): 1", batch["text"])
        self.assertIn("In-app navigation event(s): 1", batch["text"])
        self.assertIn("Edit history event(s): 1", batch["text"])
        self.assertNotIn("SECRET COMMAND LABEL", str(batch))
        self.assertNotIn("SECRET MENU PATH", str(batch))
        self.assertNotIn("SECRET SELECTED TEXT", str(batch))
        self.assertNotIn("SECRET OBJECT", str(batch))
        self.assertNotIn("SECRET ROUTE LABEL", str(batch))
        self.assertNotIn("SECRET SEARCH TEXT", str(batch))
        self.assertNotIn("SECRET VERSION DETAILS", str(batch))
        self.assertNotIn("SECRET DOC TEXT", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("command_activity", semantic_types)
        self.assertIn("selection_activity", semantic_types)
        self.assertIn("navigation_activity", semantic_types)
        self.assertIn("edit_history_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("update_context", action_types)
        self.assertIn("prepare_resume_context", action_types)
        self.assertIn("review_attention", action_types)

    def test_system_surface_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "dock_taskbar_activity",
                    "stimulus_type": "dock_badge_changed",
                    "text": "Dock badge changed for SECRET APP.",
                    "metadata": {"app_name": "Dock", "surface_kind": "dock", "privacy_level": "redacted"},
                    "payload": {"app_label": "SECRET APP", "badge_text": "SECRET BADGE"},
                },
                {
                    "collector": "menu_bar_tray_activity",
                    "stimulus_type": "tray_notification_clicked",
                    "text": "Tray notification clicked with SECRET PAYLOAD.",
                    "metadata": {"app_name": "Menu Bar", "status_item_kind": "tray", "privacy_level": "redacted"},
                    "payload": {"item_label": "SECRET TRAY ITEM", "notification_body": "SECRET PAYLOAD"},
                },
                {
                    "collector": "quick_settings_activity",
                    "stimulus_type": "screen_mirroring_changed",
                    "text": "Screen mirroring changed to SECRET DISPLAY.",
                    "metadata": {"app_name": "Control Center", "setting_kind": "screen_mirroring"},
                    "payload": {"display_name": "SECRET DISPLAY", "network_name": "SECRET NETWORK"},
                },
                {
                    "collector": "widget_activity",
                    "stimulus_type": "widget_alert_seen",
                    "text": "Widget alert seen with SECRET WIDGET CONTENT.",
                    "metadata": {"app_name": "Widgets", "widget_kind": "calendar", "privacy_level": "redacted"},
                    "payload": {"widget_name": "SECRET WIDGET", "alert_body": "SECRET WIDGET CONTENT"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "dock_taskbar_activity": True,
                        "menu_bar_tray_activity": True,
                        "quick_settings_activity": True,
                        "widget_activity": True,
                    },
                    "rich_capture_opt_in": {
                        "dock_taskbar_activity": True,
                        "menu_bar_tray_activity": True,
                        "widget_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {"dock_taskbar_activity", "menu_bar_tray_activity", "quick_settings_activity", "widget_activity"},
        )
        batch = result.attention_batches[0]
        self.assertIn("Dock/taskbar event(s): 1", batch["text"])
        self.assertIn("Menu bar/tray event(s): 1", batch["text"])
        self.assertIn("Quick settings event(s): 1", batch["text"])
        self.assertIn("Widget event(s): 1", batch["text"])
        self.assertNotIn("SECRET APP", str(batch))
        self.assertNotIn("SECRET BADGE", str(batch))
        self.assertNotIn("SECRET TRAY ITEM", str(batch))
        self.assertNotIn("SECRET PAYLOAD", str(batch))
        self.assertNotIn("SECRET DISPLAY", str(batch))
        self.assertNotIn("SECRET NETWORK", str(batch))
        self.assertNotIn("SECRET WIDGET", str(batch))
        self.assertNotIn("SECRET WIDGET CONTENT", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("dock_taskbar_activity", semantic_types)
        self.assertIn("menu_bar_tray_activity", semantic_types)
        self.assertIn("quick_settings_activity", semantic_types)
        self.assertIn("widget_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("review_attention", action_types)
        self.assertIn("suppress_collection", action_types)

    def test_credential_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "credential_activity",
                    "stimulus_type": "credential_fill_failed",
                    "text": "Credential fill failed for SECRET USERNAME and SECRET PASSWORD.",
                    "metadata": {"app_name": "1Password", "credential_provider": "1password", "privacy_level": "redacted"},
                    "payload": {"username": "SECRET USERNAME", "password": "SECRET PASSWORD", "vault_item": "SECRET VAULT ITEM"},
                },
                {
                    "collector": "passkey_activity",
                    "stimulus_type": "passkey_failed",
                    "text": "Passkey failed for SECRET RELYING PARTY.",
                    "metadata": {"app_name": "Safari", "passkey_provider": "platform", "privacy_level": "redacted"},
                    "payload": {"relying_party": "SECRET RELYING PARTY", "key_handle": "SECRET KEY HANDLE", "biometric": "SECRET BIOMETRIC"},
                },
                {
                    "collector": "autofill_activity",
                    "stimulus_type": "form_autofill_failed",
                    "text": "Autofill failed with SECRET CARD and SECRET ADDRESS.",
                    "metadata": {"app_name": "Chrome", "autofill_kind": "payment", "privacy_level": "redacted"},
                    "payload": {"card_number": "SECRET CARD", "address": "SECRET ADDRESS", "field_value": "SECRET FIELD VALUE"},
                },
                {
                    "collector": "verification_code_activity",
                    "stimulus_type": "verification_code_failed",
                    "text": "Verification code failed with SECRET OTP.",
                    "metadata": {"app_name": "Messages", "verification_channel": "sms", "privacy_level": "redacted"},
                    "payload": {"otp": "SECRET OTP", "backup_code": "SECRET BACKUP CODE", "message_body": "SECRET MESSAGE"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "credential_activity": True,
                        "passkey_activity": True,
                        "autofill_activity": True,
                        "verification_code_activity": True,
                    },
                    "rich_capture_opt_in": {
                        "credential_activity": True,
                        "passkey_activity": True,
                        "autofill_activity": True,
                        "verification_code_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {"credential_activity", "passkey_activity", "autofill_activity", "verification_code_activity"},
        )
        batch = result.attention_batches[0]
        self.assertIn("Credential manager event(s): 1", batch["text"])
        self.assertIn("Passkey/security-key event(s): 1", batch["text"])
        self.assertIn("Autofill event(s): 1", batch["text"])
        self.assertIn("Verification-code event(s): 1", batch["text"])
        self.assertNotIn("SECRET USERNAME", str(batch))
        self.assertNotIn("SECRET PASSWORD", str(batch))
        self.assertNotIn("SECRET VAULT ITEM", str(batch))
        self.assertNotIn("SECRET RELYING PARTY", str(batch))
        self.assertNotIn("SECRET KEY HANDLE", str(batch))
        self.assertNotIn("SECRET BIOMETRIC", str(batch))
        self.assertNotIn("SECRET CARD", str(batch))
        self.assertNotIn("SECRET ADDRESS", str(batch))
        self.assertNotIn("SECRET FIELD VALUE", str(batch))
        self.assertNotIn("SECRET OTP", str(batch))
        self.assertNotIn("SECRET BACKUP CODE", str(batch))
        self.assertNotIn("SECRET MESSAGE", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("credential_activity", semantic_types)
        self.assertIn("passkey_activity", semantic_types)
        self.assertIn("autofill_activity", semantic_types)
        self.assertIn("verification_code_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("review_attention", action_types)

    def test_composition_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "text_composition_activity",
                    "stimulus_type": "composition_submitted",
                    "text": "Composition submitted with SECRET DRAFT BODY.",
                    "metadata": {"app_name": "Mail", "composition_surface": "email", "privacy_level": "redacted"},
                    "payload": {"draft_body": "SECRET DRAFT BODY", "snippet": "SECRET SNIPPET", "template": "SECRET TEMPLATE"},
                },
                {
                    "collector": "dictation_activity",
                    "stimulus_type": "dictation_error",
                    "text": "Dictation error with SECRET TRANSCRIPT.",
                    "metadata": {"app_name": "Notes", "dictation_provider": "system", "privacy_level": "redacted"},
                    "payload": {"transcript": "SECRET TRANSCRIPT", "audio": "SECRET AUDIO"},
                },
                {
                    "collector": "writing_assist_activity",
                    "stimulus_type": "rewrite_suggestion_accepted",
                    "text": "Rewrite suggestion accepted from SECRET ORIGINAL to SECRET REWRITE.",
                    "metadata": {"app_name": "Pages", "assist_kind": "rewrite", "privacy_level": "redacted"},
                    "payload": {"original": "SECRET ORIGINAL", "suggestion": "SECRET SUGGESTION", "replacement": "SECRET REWRITE"},
                },
                {
                    "collector": "translation_activity",
                    "stimulus_type": "translation_completed",
                    "text": "Translation completed with SECRET SOURCE and SECRET TRANSLATION.",
                    "metadata": {"app_name": "Safari", "translation_provider": "system", "privacy_level": "redacted"},
                    "payload": {"source_text": "SECRET SOURCE", "translated_text": "SECRET TRANSLATION", "language": "SECRET LANGUAGE"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "text_composition_activity": True,
                        "dictation_activity": True,
                        "writing_assist_activity": True,
                        "translation_activity": True,
                    },
                    "rich_capture_opt_in": {
                        "text_composition_activity": True,
                        "dictation_activity": True,
                        "writing_assist_activity": True,
                        "translation_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {"text_composition_activity", "dictation_activity", "writing_assist_activity", "translation_activity"},
        )
        batch = result.attention_batches[0]
        self.assertIn("Text composition event(s): 1", batch["text"])
        self.assertIn("Dictation event(s): 1", batch["text"])
        self.assertIn("Writing assist event(s): 1", batch["text"])
        self.assertIn("Translation event(s): 1", batch["text"])
        self.assertNotIn("SECRET DRAFT BODY", str(batch))
        self.assertNotIn("SECRET SNIPPET", str(batch))
        self.assertNotIn("SECRET TEMPLATE", str(batch))
        self.assertNotIn("SECRET TRANSCRIPT", str(batch))
        self.assertNotIn("SECRET AUDIO", str(batch))
        self.assertNotIn("SECRET ORIGINAL", str(batch))
        self.assertNotIn("SECRET SUGGESTION", str(batch))
        self.assertNotIn("SECRET REWRITE", str(batch))
        self.assertNotIn("SECRET SOURCE", str(batch))
        self.assertNotIn("SECRET TRANSLATION", str(batch))
        self.assertNotIn("SECRET LANGUAGE", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("text_composition_activity", semantic_types)
        self.assertIn("dictation_activity", semantic_types)
        self.assertIn("writing_assist_activity", semantic_types)
        self.assertIn("translation_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("update_context", action_types)
        self.assertIn("review_attention", action_types)

    def test_realtime_collaboration_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "meeting_app_activity",
                    "stimulus_type": "meeting_joined",
                    "text": "Joined SECRET MEETING with SECRET PARTICIPANT.",
                    "metadata": {"app_name": "Zoom", "meeting_surface": "meeting"},
                    "payload": {"meeting_title": "SECRET MEETING", "participant": "SECRET PARTICIPANT"},
                },
                {
                    "collector": "call_control_activity",
                    "stimulus_type": "camera_enabled",
                    "text": "Camera enabled while SECRET CHAT was visible.",
                    "metadata": {"app_name": "Zoom", "meeting_control": "camera", "privacy_level": "redacted"},
                    "payload": {"chat": "SECRET CHAT", "caption": "SECRET CAPTION"},
                },
                {
                    "collector": "meeting_presentation_activity",
                    "stimulus_type": "screen_share_started",
                    "text": "Screen share started for SECRET WINDOW.",
                    "metadata": {"app_name": "Zoom", "share_kind": "screen", "privacy_level": "redacted"},
                    "payload": {"shared_window": "SECRET WINDOW", "screen_contents": "SECRET SCREEN"},
                },
                {
                    "collector": "meeting_artifact_activity",
                    "stimulus_type": "meeting_action_items_detected",
                    "text": "Meeting action items detected from SECRET NOTES.",
                    "metadata": {"app_name": "Zoom", "artifact_kind": "action_items", "privacy_level": "redacted"},
                    "payload": {"notes": "SECRET NOTES", "action_items": "SECRET ACTION ITEMS"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "meeting_app_activity": True,
                        "call_control_activity": True,
                        "meeting_presentation_activity": True,
                        "meeting_artifact_activity": True,
                    },
                    "rich_capture_opt_in": {
                        "meeting_app_activity": True,
                        "call_control_activity": True,
                        "meeting_presentation_activity": True,
                        "meeting_artifact_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {"meeting_app_activity", "call_control_activity", "meeting_presentation_activity", "meeting_artifact_activity"},
        )
        batch = result.attention_batches[0]
        self.assertIn("Meeting app event(s): 1", batch["text"])
        self.assertIn("Meeting call-control event(s): 1", batch["text"])
        self.assertIn("Meeting presentation/share event(s): 1", batch["text"])
        self.assertIn("Meeting artifact event(s): 1", batch["text"])
        self.assertNotIn("SECRET MEETING", str(batch))
        self.assertNotIn("SECRET PARTICIPANT", str(batch))
        self.assertNotIn("SECRET CHAT", str(batch))
        self.assertNotIn("SECRET CAPTION", str(batch))
        self.assertNotIn("SECRET WINDOW", str(batch))
        self.assertNotIn("SECRET SCREEN", str(batch))
        self.assertNotIn("SECRET NOTES", str(batch))
        self.assertNotIn("SECRET ACTION ITEMS", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("meeting_app_activity", semantic_types)
        self.assertIn("call_control_activity", semantic_types)
        self.assertIn("meeting_presentation_activity", semantic_types)
        self.assertIn("meeting_artifact_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("prepare_briefing", action_types)
        self.assertIn("suppress_collection", action_types)
        self.assertIn("review_attention", action_types)

    def test_interaction_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            for payload in (
                {
                    "collector": "direct_user",
                    "stimulus_type": "global_hotkey_pressed",
                    "text": "Global assistant hotkey pressed.",
                    "metadata": {"app_name": "Humungousaur"},
                },
                {
                    "collector": "voice_wakeup",
                    "stimulus_type": "voice_transcript_final",
                    "text": "Voice command received.",
                    "metadata": {"provider": "local"},
                    "payload": {"transcript": "SECRET VOICE TRANSCRIPT"},
                },
                {
                    "collector": "meeting_audio",
                    "stimulus_type": "meeting_transcript_chunk",
                    "text": "Meeting transcript chunk summarized by helper.",
                    "metadata": {"app_name": "Zoom", "privacy_level": "redacted"},
                    "payload": {"transcript": "SECRET MEETING TRANSCRIPT"},
                },
                {
                    "collector": "wakeups",
                    "stimulus_type": "followup_due",
                    "text": "Scheduled follow-up is due.",
                    "metadata": {"wakeup_id": "wake-1"},
                },
                {
                    "collector": "channel_activity",
                    "stimulus_type": "mention_received",
                    "text": "Mention received in team channel.",
                    "metadata": {"channel_id": "slack", "conversation_id": "C123"},
                    "payload": {"body": "SECRET CHANNEL BODY"},
                },
            ):
                append_bridge_event(config, payload)
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "agent_runtime": False,
                        "direct_user": True,
                        "voice_wakeup": True,
                        "meeting_audio": True,
                        "wakeups": True,
                        "channel_activity": True,
                    },
                    "rich_capture_opt_in": {"voice_wakeup": True, "meeting_audio": True},
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {"direct_user", "voice_wakeup", "meeting_audio", "wakeups", "channel_activity"},
        )
        batch = result.attention_batches[0]
        self.assertIn("Direct user intent event(s): 1", batch["text"])
        self.assertIn("Voice wakeup event(s): 1", batch["text"])
        self.assertIn("Meeting audio event(s): 1", batch["text"])
        self.assertIn("Wakeup event(s): 1", batch["text"])
        self.assertIn("Channel activity event(s): 1", batch["text"])
        self.assertNotIn("SECRET VOICE TRANSCRIPT", str(batch))
        self.assertNotIn("SECRET MEETING TRANSCRIPT", str(batch))
        self.assertNotIn("SECRET CHANNEL BODY", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("explicit_user_request", semantic_types)
        self.assertIn("voice_command_received", semantic_types)
        self.assertIn("meeting_audio_activity", semantic_types)
        self.assertIn("wakeup_activity", semantic_types)
        self.assertIn("channel_activity", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("prepare_briefing", action_types)
        self.assertIn("review_message", action_types)


if __name__ == "__main__":
    unittest.main()
