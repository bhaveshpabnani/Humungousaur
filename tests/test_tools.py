import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from humungousaur.config import AgentConfig
from humungousaur.planning.model_clients import ModelClientError, StaticModelClient
from humungousaur.planning.prompt_templates import load_prompt_templates
from humungousaur.schemas import ActionStatus
from humungousaur.tools.codex_tools import (
    CodexCliPlanTool,
    CodexCliRunTool,
    CodexCliStatusTool,
    CodexPluginCatalogTool,
    CodexSkillCatalogTool,
    CodexSkillImportTool,
    CodexSkillReadTool,
    CodexSkillSyncTool,
)
from humungousaur.tools.file_tools import (
    ExtractPDFPagesTool,
    ListFilesTool,
    ListPDFsTool,
    MergePDFsTool,
    OCRProviderStatusTool,
    ReadFileTool,
    ReadPDFTool,
    SearchWorkspaceTool,
    ShellCommandTool,
    SummarizePDFsTool,
    WriteNoteTool,
    summarize_text,
)
from humungousaur.tools import default_tools
from humungousaur.tools.os_tools import (
    APP_ALLOWLIST,
    ActiveWindowTool,
    OpenAppTool,
    OsAppsTool,
    OsClipboardReadTool,
    OsClipboardWriteTool,
    OsClickCoordinatesTool,
    OsClickElementTool,
    OsCursorTool,
    OsLaunchAppTool,
    OsMoveWindowToDesktopTool,
    OsObserveUiTool,
    OsResizeWindowTool,
    OsScrollElementTool,
    OsSendKeysTool,
    OsSwitchWindowTool,
    OsTypeTextTool,
    OsUiaPatternActionTool,
    OsVirtualDesktopActionTool,
    OsVirtualDesktopsTool,
    OsWindowStateTool,
    OsWindowsTool,
    ScreenCaptureDeleteTool,
    ScreenCapturesTool,
    ScreenshotCaptureTool,
    cursor_snapshot,
    load_ui_observation_element,
    list_screenshot_captures,
    save_ui_observation,
    start_apps_snapshot,
    virtual_desktops_snapshot,
    visible_windows_snapshot,
)
from humungousaur.tools.plugin_tools import PluginManifestTool, PluginManifestsTool, discover_plugin_manifests
from humungousaur.tools.system_tools import SystemStatusTool, collect_system_status
from tests.pdf_utils import pdf_dependencies_available, write_pdf


CODEX_PROMPT_RESOURCE = "resources/prompts/codex.yaml"


class RecordingStaticModelClient(StaticModelClient):
    def __init__(self, response: str, name: str = "recording-static") -> None:
        super().__init__(response=response, name=name)
        self.prompts: list[str] = []

    def complete_json(self, prompt, schema):
        self.prompts.append(prompt)
        return super().complete_json(prompt, schema)


class ToolTests(unittest.TestCase):
    def test_default_tools_expose_input_schemas(self) -> None:
        tools = default_tools()

        self.assertEqual(tools["read_file"].input_schema["required"], ["path"])
        self.assertEqual(tools["run_shell_command"].input_schema["properties"]["argv"]["type"], "array")
        self.assertEqual(
            tools["run_shell_command"].input_schema["properties"]["command_profile"]["enum"],
            ["read_only", "workspace_write", "trusted_dev", "blocked"],
        )
        self.assertEqual(tools["run_shell_command"].capability_group, "shell")
        self.assertEqual(tools["pdf_merge"].capability_group, "files")
        self.assertEqual(tools["pdf_extract_pages"].capability_group, "files")
        self.assertEqual(tools["ocr_provider_status"].capability_group, "files")
        self.assertEqual(tools["python_interpreter"].input_schema["required"], ["code", "reason"])
        self.assertEqual(tools["python_interpreter"].input_schema["properties"]["import_mode"]["enum"], ["stdlib", "allowlist", "all"])
        self.assertEqual(tools["python_interpreter"].input_schema["properties"]["allowed_imports"]["items"]["type"], "string")
        self.assertEqual(
            tools["python_interpreter"].input_schema["properties"]["sandbox_profile"]["enum"],
            ["read_only", "data_write", "workspace_write", "trusted_dev"],
        )
        self.assertEqual(tools["python_interpreter"].input_schema["properties"]["replay_session"]["type"], "boolean")
        self.assertEqual(tools["python_interpreter"].capability_group, "code")
        self.assertTrue(tools["python_interpreter"].requires_approval)
        self.assertEqual(tools["python_interpreter_runs"].capability_group, "code")
        self.assertFalse(tools["python_interpreter_runs"].requires_approval)
        self.assertEqual(tools["python_interpreter_run"].input_schema["required"], ["run_id"])
        self.assertEqual(tools["python_interpreter_artifact"].input_schema["required"], ["run_id", "filename"])
        self.assertEqual(tools["python_interpreter_sessions"].capability_group, "code")
        self.assertFalse(tools["python_interpreter_sessions"].requires_approval)
        self.assertEqual(tools["python_interpreter_session"].input_schema["required"], ["session_id"])
        self.assertEqual(tools["plugin_manifests"].capability_group, "plugins")
        self.assertEqual(tools["plugin_manifest"].input_schema["required"], ["name"])
        self.assertEqual(tools["capability_surface"].capability_group, "capabilities")
        self.assertIn("include_records", tools["capability_surface"].input_schema["properties"])
        self.assertEqual(tools["tool_search"].capability_group, "capabilities")
        self.assertEqual(tools["tool_search"].input_schema["required"], ["query"])
        self.assertEqual(tools["tool_describe"].capability_group, "capabilities")
        self.assertEqual(tools["tool_describe"].input_schema["required"], ["record_id"])
        self.assertEqual(tools["tool_call"].capability_group, "capabilities")
        self.assertTrue(tools["tool_call"].requires_approval)
        self.assertEqual(tools["tool_call"].input_schema["required"], ["name", "arguments"])
        self.assertEqual(tools["write_file"].capability_group, "files")
        self.assertTrue(tools["write_file"].requires_approval)
        self.assertEqual(tools["patch"].capability_group, "files")
        self.assertTrue(tools["patch"].requires_approval)
        self.assertEqual(tools["process"].capability_group, "shell")
        self.assertTrue(tools["process"].requires_approval)
        self.assertEqual(tools["terminal"].input_schema, tools["run_shell_command"].input_schema)
        self.assertEqual(tools["web_extract"].input_schema, tools["fetch_web_page"].input_schema)
        self.assertEqual(tools["send_message"].input_schema, tools["channel_message_send"].input_schema)
        self.assertEqual(tools["native_toolset_catalog"].capability_group, "toolsets")
        self.assertEqual(tools["native_toolset_describe"].input_schema["required"], ["toolset"])
        self.assertEqual(tools["mcp_server_catalog"].capability_group, "mcp")
        self.assertEqual(tools["mcp_server_manifest"].input_schema["required"], ["server_id"])
        self.assertTrue(tools["mcp_server_launch"].requires_approval)
        self.assertEqual(tools["mcp_tool_discover"].input_schema["required"], ["server_id"])
        self.assertTrue(tools["mcp_tool_call"].requires_approval)
        self.assertEqual(tools["mcp_oauth_status"].capability_group, "mcp")
        self.assertTrue(tools["plugin_state"].requires_approval)
        self.assertEqual(tools["provider_registry"].capability_group, "providers")
        self.assertEqual(tools["runtime_hook_catalog"].capability_group, "runtime")
        self.assertEqual(tools["native_skill_pack_build"].capability_group, "skills")
        self.assertTrue(tools["native_skill_pack_build"].requires_approval)
        self.assertEqual(tools["codex_capability_status"].capability_group, "codex")
        self.assertEqual(tools["codex_cli_status"].capability_group, "codex")
        self.assertEqual(tools["codex_cli_plan"].capability_group, "codex")
        self.assertEqual(tools["codex_cli_plan"].input_schema["required"], ["objective"])
        self.assertEqual(tools["codex_cli_run"].capability_group, "codex")
        self.assertTrue(tools["codex_cli_run"].requires_approval)
        self.assertEqual(tools["codex_cli_run"].input_schema["required"], ["task"])
        self.assertEqual(tools["codex_plugin_catalog"].capability_group, "codex")
        self.assertIn("codex_home", tools["codex_plugin_catalog"].input_schema["properties"])
        self.assertIn("app", tools["codex_plugin_catalog"].input_schema["properties"]["source"]["enum"])
        self.assertEqual(tools["codex_skill_catalog"].capability_group, "codex")
        self.assertIn("query", tools["codex_skill_catalog"].input_schema["properties"])
        self.assertIn("app", tools["codex_skill_catalog"].input_schema["properties"]["source"]["enum"])
        self.assertEqual(tools["codex_skill_read"].input_schema["required"], ["skill_id"])
        self.assertEqual(tools["codex_skill_import"].input_schema["required"], ["skill_ids", "reason"])
        self.assertIn("profile", tools["codex_skill_sync"].input_schema["properties"])
        self.assertIn("url", tools["browser_open"].input_schema["properties"])
        self.assertEqual(tools["browser_open"].capability_group, "browser")
        self.assertIn("limit", tools["browser_sessions"].input_schema["properties"])
        self.assertEqual(tools["browser_sessions"].capability_group, "browser")
        self.assertEqual(tools["browser_observe"].input_schema["required"], ["session_id"])
        self.assertEqual(tools["browser_observe"].capability_group, "browser")
        self.assertEqual(tools["browser_extract"].input_schema["required"], ["session_id", "query"])
        self.assertEqual(tools["browser_extract"].capability_group, "browser")
        self.assertEqual(tools["browser_click_element"].input_schema["required"], ["session_id", "element_id"])
        self.assertEqual(tools["browser_click_element"].capability_group, "browser")
        self.assertEqual(tools["browser_back"].input_schema["required"], ["session_id"])
        self.assertEqual(tools["browser_back"].capability_group, "browser")
        self.assertEqual(tools["browser_type"].input_schema["required"], ["session_id", "element_id", "text"])
        self.assertEqual(tools["browser_type"].capability_group, "browser")
        self.assertEqual(tools["browser_find_text"].input_schema["required"], ["session_id", "text"])
        self.assertEqual(tools["browser_find_text"].capability_group, "browser")
        self.assertEqual(tools["browser_live_status"].capability_group, "browser")
        self.assertEqual(tools["browser_live_open"].input_schema["required"], ["url"])
        self.assertEqual(tools["browser_live_open"].capability_group, "browser")
        self.assertEqual(tools["browser_live_observe"].input_schema["required"], ["live_session_id"])
        self.assertEqual(tools["browser_live_observe"].capability_group, "browser")
        self.assertEqual(tools["browser_live_click"].input_schema["required"], ["live_session_id", "element_id", "reason"])

        self.assertTrue(tools["browser_live_click"].requires_approval)
        self.assertEqual(tools["browser_live_type"].input_schema["required"], ["live_session_id", "element_id", "text", "reason"])
        self.assertTrue(tools["browser_live_type"].requires_approval)
        self.assertEqual(tools["browser_live_scroll"].input_schema["required"], ["live_session_id", "direction"])
        self.assertEqual(tools["browser_live_scroll"].capability_group, "browser")
        self.assertEqual(tools["browser_live_scroll_to_text"].input_schema["required"], ["live_session_id", "text"])
        self.assertEqual(tools["browser_live_scroll_to_text"].capability_group, "browser")
        self.assertEqual(tools["browser_live_wait"].input_schema["required"], ["live_session_id", "mode"])
        self.assertEqual(tools["browser_live_wait"].capability_group, "browser")
        self.assertEqual(tools["browser_live_tabs"].input_schema["required"], ["live_session_id"])
        self.assertEqual(tools["browser_live_tabs"].capability_group, "browser")
        self.assertEqual(tools["browser_live_search"].input_schema["required"], ["live_session_id", "query"])
        self.assertEqual(tools["browser_live_search"].capability_group, "browser")
        self.assertEqual(tools["browser_live_new_tab"].input_schema["required"], ["live_session_id"])
        self.assertEqual(tools["browser_live_new_tab"].capability_group, "browser")
        self.assertEqual(tools["browser_live_switch_tab"].input_schema["required"], ["live_session_id", "index"])
        self.assertEqual(tools["browser_live_switch_tab"].capability_group, "browser")
        self.assertEqual(tools["browser_live_close_tab"].input_schema["required"], ["live_session_id", "reason"])
        self.assertTrue(tools["browser_live_close_tab"].requires_approval)
        self.assertEqual(tools["browser_live_query_selector"].input_schema["required"], ["live_session_id", "selector"])
        self.assertEqual(tools["browser_live_query_selector"].capability_group, "browser")
        self.assertEqual(tools["browser_live_extract"].input_schema["required"], ["live_session_id", "query"])
        self.assertEqual(tools["browser_live_extract"].capability_group, "browser")
        self.assertEqual(tools["browser_live_html"].input_schema["required"], ["live_session_id"])
        self.assertEqual(tools["browser_live_html"].capability_group, "browser")
        self.assertEqual(tools["browser_live_page_search"].input_schema["required"], ["live_session_id", "pattern"])
        self.assertEqual(tools["browser_live_page_search"].capability_group, "browser")
        self.assertEqual(tools["browser_live_find_elements"].input_schema["required"], ["live_session_id", "selector"])
        self.assertEqual(tools["browser_live_find_elements"].capability_group, "browser")
        self.assertEqual(tools["browser_live_dropdown_options"].input_schema["required"], ["live_session_id", "element_id"])
        self.assertEqual(tools["browser_live_dropdown_options"].capability_group, "browser")
        self.assertEqual(tools["browser_live_select_option"].input_schema["required"], ["live_session_id", "element_id", "values", "reason"])
        self.assertTrue(tools["browser_live_select_option"].requires_approval)
        self.assertEqual(tools["browser_live_press_key"].input_schema["required"], ["live_session_id", "shortcut", "reason"])
        self.assertTrue(tools["browser_live_press_key"].requires_approval)
        self.assertEqual(tools["browser_live_click_coordinates"].input_schema["required"], ["live_session_id", "x", "y", "reason"])
        self.assertTrue(tools["browser_live_click_coordinates"].requires_approval)
        self.assertEqual(tools["browser_live_upload_file"].input_schema["required"], ["live_session_id", "element_id", "path", "reason"])
        self.assertTrue(tools["browser_live_upload_file"].requires_approval)
        self.assertEqual(tools["browser_live_download"].input_schema["required"], ["live_session_id", "element_id", "reason"])
        self.assertTrue(tools["browser_live_download"].requires_approval)
        self.assertEqual(tools["browser_live_save_pdf"].input_schema["required"], ["live_session_id", "reason"])
        self.assertTrue(tools["browser_live_save_pdf"].requires_approval)
        self.assertEqual(tools["browser_live_evaluate_js"].input_schema["required"], ["live_session_id", "code", "reason"])
        self.assertTrue(tools["browser_live_evaluate_js"].requires_approval)
        self.assertEqual(tools["browser_live_screenshot"].input_schema["required"], ["live_session_id", "reason"])
        self.assertTrue(tools["browser_live_screenshot"].requires_approval)
        self.assertEqual(tools["browser_live_close"].input_schema["required"], ["live_session_id"])
        self.assertTrue(tools["browser_live_close"].requires_approval)
        self.assertEqual(tools["os_windows"].capability_group, "os")
        self.assertEqual(tools["os_observe_ui"].capability_group, "os")
        self.assertTrue(tools["os_observe_ui"].requires_approval)
        self.assertEqual(tools["os_click_element"].input_schema["required"], ["observation_id", "element_id", "reason"])
        self.assertTrue(tools["os_click_element"].requires_approval)
        self.assertEqual(tools["os_type_text"].input_schema["required"], ["observation_id", "element_id", "text", "reason"])
        self.assertTrue(tools["os_type_text"].requires_approval)
        self.assertEqual(tools["os_send_keys"].input_schema["required"], ["shortcut", "reason"])
        self.assertTrue(tools["os_send_keys"].requires_approval)
        self.assertEqual(tools["os_scroll_element"].input_schema["required"], ["observation_id", "element_id", "direction", "reason"])
        self.assertTrue(tools["os_scroll_element"].requires_approval)
        self.assertEqual(tools["os_switch_window"].input_schema["required"], ["window_id", "reason"])
        self.assertTrue(tools["os_switch_window"].requires_approval)
        self.assertEqual(tools["os_resize_window"].input_schema["required"], ["window_id", "x", "y", "width", "height", "reason"])
        self.assertTrue(tools["os_resize_window"].requires_approval)
        self.assertEqual(tools["os_cursor"].capability_group, "os")
        self.assertFalse(tools["os_cursor"].requires_approval)
        self.assertEqual(tools["os_click_coordinates"].input_schema["required"], ["x", "y", "reason"])
        self.assertTrue(tools["os_click_coordinates"].requires_approval)
        self.assertEqual(tools["os_uia_pattern_action"].input_schema["required"], ["observation_id", "element_id", "action", "reason"])
        self.assertTrue(tools["os_uia_pattern_action"].requires_approval)
        self.assertEqual(tools["os_window_state"].input_schema["required"], ["window_id", "action", "reason"])
        self.assertTrue(tools["os_window_state"].requires_approval)
        self.assertEqual(tools["os_virtual_desktops"].capability_group, "os")
        self.assertFalse(tools["os_virtual_desktops"].requires_approval)
        self.assertEqual(tools["os_move_window_to_desktop"].input_schema["required"], ["window_id", "desktop_id", "reason"])
        self.assertTrue(tools["os_move_window_to_desktop"].requires_approval)
        self.assertEqual(tools["os_virtual_desktop_action"].input_schema["required"], ["action", "reason"])
        self.assertTrue(tools["os_virtual_desktop_action"].requires_approval)
        self.assertEqual(tools["os_apps"].capability_group, "os")
        self.assertFalse(tools["os_apps"].requires_approval)
        self.assertEqual(tools["os_launch_app"].input_schema["required"], ["app", "reason"])
        self.assertTrue(tools["os_launch_app"].requires_approval)
        self.assertEqual(tools["os_clipboard_read"].input_schema["required"], ["reason"])
        self.assertTrue(tools["os_clipboard_read"].requires_approval)
        self.assertEqual(tools["os_clipboard_write"].input_schema["required"], ["text", "reason"])
        self.assertTrue(tools["os_clipboard_write"].requires_approval)
        self.assertEqual(tools["open_app"].input_schema["required"], ["app_id"])
        self.assertEqual(tools["open_app"].capability_group, "os")
        self.assertEqual(tools["screenshot_capture"].input_schema["required"], ["reason"])
        self.assertEqual(tools["screenshot_capture"].capability_group, "screen")
        self.assertEqual(tools["screen_captures"].capability_group, "screen")
        self.assertEqual(tools["screen_capture_delete"].input_schema["required"], ["filename", "reason"])
        self.assertEqual(tools["screen_capture_delete"].capability_group, "screen")
        self.assertEqual(tools["dependency_inventory_create"].capability_group, "security")
        self.assertEqual(tools["dependency_inventory_create"].input_schema["required"], ["title", "reason"])
        self.assertEqual(tools["secret_scan_report_create"].input_schema["required"], ["title", "reason"])
        self.assertEqual(tools["prompt_injection_review_create"].input_schema["required"], ["title", "source", "content", "reason"])
        self.assertEqual(tools["approval_policy_review_create"].input_schema["required"], ["title", "actions", "reason"])
        self.assertEqual(tools["security_review_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["github_issue_packet_create"].capability_group, "github")
        self.assertEqual(tools["github_issue_packet_create"].input_schema["required"], ["repo", "title", "reason"])
        self.assertEqual(tools["github_pr_packet_create"].input_schema["required"], ["repo", "branch", "title", "reason"])
        self.assertEqual(tools["ci_failure_report_create"].input_schema["required"], ["repo", "check_name", "reason"])
        self.assertEqual(tools["github_repo_state_report_create"].input_schema["required"], ["repo", "reason"])
        self.assertEqual(tools["github_artifact_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["memory_search"].input_schema["required"], ["query"])
        self.assertEqual(tools["memory_search"].capability_group, "memory")
        self.assertEqual(tools["memory_write"].input_schema["required"], ["kind", "text"])
        self.assertEqual(tools["memory_summary"].input_schema["required"], ["period"])
        self.assertEqual(tools["memory_summary"].capability_group, "memory")
        self.assertEqual(tools["memory_profile"].capability_group, "memory")
        self.assertEqual(tools["cognitive_brain_files_refresh"].capability_group, "cognition")
        self.assertEqual(tools["cognitive_brain_files_status"].capability_group, "cognition")
        self.assertEqual(tools["cognitive_briefing_prepare"].capability_group, "cognition")
        self.assertIn("horizon_hours", tools["cognitive_briefing_prepare"].input_schema["properties"])
        self.assertEqual(tools["cognitive_briefing_status"].capability_group, "cognition")
        self.assertEqual(tools["cognitive_memory_curate"].capability_group, "cognition")
        self.assertIn("max_archive", tools["cognitive_memory_curate"].input_schema["properties"])
        self.assertEqual(tools["cognitive_curation_status"].capability_group, "cognition")
        self.assertEqual(tools["cognitive_skill_evolve"].capability_group, "cognition")
        self.assertIn("max_new_skills", tools["cognitive_skill_evolve"].input_schema["properties"])
        self.assertEqual(tools["cognitive_skill_evolution_status"].capability_group, "cognition")
        self.assertEqual(tools["skill_forge_draft"].capability_group, "skills")
        self.assertIn("write_pack", tools["skill_forge_draft"].input_schema["properties"])
        self.assertEqual(tools["skill_forge_packs"].capability_group, "skills")
        self.assertEqual(tools["automation_daemon_status"].capability_group, "cognition")
        self.assertEqual(tools["automation_daemon_configure"].capability_group, "cognition")
        self.assertTrue(tools["automation_daemon_tick"].requires_approval)
        self.assertEqual(tools["multi_agent_coordinate"].input_schema["required"], ["goal_title", "tasks"])
        self.assertEqual(tools["multi_agent_board"].capability_group, "cognition")
        self.assertEqual(tools["cognitive_persona_evolve"].capability_group, "cognition")
        self.assertIn("purpose", tools["cognitive_persona_evolve"].input_schema["properties"])
        self.assertEqual(tools["creative_brief_create"].capability_group, "creative")
        self.assertEqual(tools["creative_brief_create"].input_schema["required"], ["title", "creative_type", "reason"])
        self.assertEqual(tools["creative_brief_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["song_structure_create"].input_schema["required"], ["title", "sections", "reason"])
        self.assertEqual(tools["song_structure_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["creative_revision_packet_create"].input_schema["required"], ["title", "source_draft", "reason"])
        self.assertEqual(tools["creative_revision_packet_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["cognitive_persona_evolution_status"].capability_group, "cognition")
        self.assertEqual(tools["cognitive_self_review"].capability_group, "cognition")
        self.assertIn("include_state", tools["cognitive_self_review"].input_schema["properties"])
        self.assertEqual(tools["cognitive_self_review_status"].capability_group, "cognition")
        self.assertEqual(tools["cognitive_interaction_review"].capability_group, "cognition")
        self.assertIn("purpose", tools["cognitive_interaction_review"].input_schema["properties"])
        self.assertEqual(tools["cognitive_interaction_review_status"].capability_group, "cognition")
        self.assertEqual(tools["cognitive_commitment_record"].capability_group, "cognition")
        self.assertEqual(tools["cognitive_commitment_record"].input_schema["required"], ["title"])
        self.assertEqual(tools["cognitive_commitment_update"].capability_group, "cognition")
        self.assertEqual(tools["cognitive_commitment_update"].input_schema["required"], ["commitment_id"])
        self.assertEqual(tools["cognitive_commitment_review"].capability_group, "cognition")
        self.assertIn("max_new_commitments", tools["cognitive_commitment_review"].input_schema["properties"])
        self.assertEqual(tools["cognitive_commitment_status"].capability_group, "cognition")
        self.assertEqual(tools["cognitive_environment_record"].capability_group, "cognition")
        self.assertEqual(tools["cognitive_environment_record"].input_schema["required"], ["kind", "title", "summary"])
        self.assertEqual(tools["cognitive_environment_update"].capability_group, "cognition")
        self.assertEqual(tools["cognitive_environment_update"].input_schema["required"], ["environment_id"])
        self.assertEqual(tools["cognitive_environment_review"].capability_group, "cognition")
        self.assertIn("max_new_records", tools["cognitive_environment_review"].input_schema["properties"])
        self.assertEqual(tools["cognitive_environment_status"].capability_group, "cognition")
        self.assertEqual(tools["cognitive_priority_review"].capability_group, "cognition")
        self.assertIn("include_state", tools["cognitive_priority_review"].input_schema["properties"])
        self.assertEqual(tools["cognitive_priority_status"].capability_group, "cognition")
        self.assertEqual(tools["cognitive_trigger_record"].capability_group, "cognition")
        self.assertEqual(tools["cognitive_trigger_record"].input_schema["required"], ["name", "text"])
        self.assertEqual(tools["cognitive_trigger_status"].capability_group, "cognition")
        self.assertEqual(tools["cognitive_trigger_evaluate"].input_schema["required"], ["source"])
        self.assertEqual(tools["cognitive_trigger_cancel"].input_schema["required"], ["trigger_id"])
        self.assertEqual(tools["activity_ingest"].input_schema["required"], ["source", "text"])
        self.assertEqual(tools["activity_ingest"].capability_group, "activity")
        self.assertEqual(tools["activity_search"].input_schema["required"], ["query"])
        self.assertEqual(tools["activity_search"].capability_group, "activity")
        self.assertEqual(tools["activity_policy"].capability_group, "activity")
        self.assertEqual(tools["activity_policy_update"].input_schema["required"], ["reason"])
        self.assertTrue(tools["activity_policy_update"].requires_approval)
        self.assertEqual(tools["activity_prune"].input_schema["required"], ["reason"])
        self.assertTrue(tools["activity_prune"].requires_approval)
        self.assertEqual(tools["external_integrations_status"].capability_group, "integrations")
        self.assertEqual(tools["browser_use_capability_map"].capability_group, "integrations")
        self.assertEqual(tools["browser_use_agent_run"].input_schema["required"], ["task", "reason"])
        self.assertTrue(tools["browser_use_agent_run"].requires_approval)
        self.assertEqual(tools["screenpipe_search"].capability_group, "integrations")
        self.assertTrue(tools["screenpipe_search"].requires_approval)
        self.assertEqual(tools["rss_feed_read"].input_schema["required"], ["source"])
        self.assertEqual(tools["rss_watch_prepare"].input_schema["required"], ["source", "cadence", "reason"])
        self.assertEqual(tools["rss_watch_list"].capability_group, "integrations")
        self.assertEqual(tools["transcript_summary_create"].capability_group, "content")
        self.assertEqual(tools["transcript_summary_create"].input_schema["required"], ["title", "summary", "reason"])
        self.assertEqual(tools["transcript_summary_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["notion_operation_prepare"].input_schema["required"], ["operation", "reason"])
        self.assertEqual(tools["airtable_operation_prepare"].input_schema["required"], ["operation", "base_id", "reason"])
        self.assertEqual(tools["google_workspace_operation_prepare"].input_schema["required"], ["app", "operation", "reason"])
        self.assertEqual(tools["api_operation_inspect"].input_schema["required"], ["path"])

        self.assertEqual(tools["dns_lookup"].capability_group, "network")
        self.assertEqual(tools["dns_lookup"].input_schema["required"], ["hostname", "reason"])
        self.assertEqual(tools["http_endpoint_check"].input_schema["required"], ["url", "reason"])
        self.assertEqual(tools["tcp_connectivity_probe"].input_schema["required"], ["host", "port", "reason"])
        self.assertEqual(tools["citation_bibliography_create"].capability_group, "research")
        self.assertEqual(tools["citation_bibliography_create"].input_schema["required"], ["title", "entries", "reason"])
        self.assertEqual(tools["citation_bibliography_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["literature_set_create"].input_schema["required"], ["title", "papers", "reason"])
        self.assertEqual(tools["literature_set_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["sound_spec_create"].capability_group, "media")
        self.assertEqual(tools["sound_spec_create"].input_schema["required"], ["title", "sound_type", "reason"])
        self.assertEqual(tools["sound_spec_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["media_storyboard_create"].input_schema["required"], ["title", "media_type", "scenes", "reason"])
        self.assertEqual(tools["media_storyboard_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["travel_plan_create"].capability_group, "travel")
        self.assertEqual(tools["travel_plan_create"].input_schema["required"], ["title", "reason"])
        self.assertEqual(tools["travel_plan_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["rail_route_availability_lookup"].capability_group, "travel")
        self.assertEqual(tools["rail_route_availability_lookup"].input_schema["required"], ["journey_date", "reason"])
        self.assertEqual(tools["travel_booking_intent_prepare"].capability_group, "travel")
        self.assertEqual(tools["travel_booking_intent_prepare"].input_schema["required"], ["mode", "options", "reason"])
        self.assertEqual(tools["travel_booking_intent_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["shopping_comparison_create"].capability_group, "commerce")
        self.assertEqual(tools["shopping_comparison_create"].input_schema["required"], ["title", "products", "reason"])
        self.assertEqual(tools["shopping_comparison_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["purchase_intent_prepare"].capability_group, "commerce")
        self.assertEqual(tools["purchase_intent_prepare"].input_schema["required"], ["intent_type", "items", "reason"])
        self.assertEqual(tools["purchase_intent_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["contact_note_create"].capability_group, "personal")
        self.assertEqual(tools["contact_note_create"].input_schema["required"], ["person_name", "reason"])
        self.assertEqual(tools["contact_note_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["daily_plan_create"].input_schema["required"], ["title", "reason"])
        self.assertEqual(tools["daily_plan_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["brand_guidelines_create"].capability_group, "design")
        self.assertEqual(tools["brand_guidelines_create"].input_schema["required"], ["brand_name", "reason"])
        self.assertEqual(tools["brand_guidelines_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["theme_pack_create"].input_schema["required"], ["theme_name", "reason"])
        self.assertEqual(tools["theme_pack_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["presentation_plan_create"].capability_group, "office")
        self.assertEqual(tools["presentation_plan_create"].input_schema["required"], ["title", "audience", "goal", "reason"])
        self.assertEqual(tools["presentation_plan_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["diagram_artifact_create"].capability_group, "visuals")
        self.assertEqual(tools["diagram_artifact_create"].input_schema["required"], ["title", "reason"])
        self.assertEqual(tools["diagram_artifact_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["excalidraw_diagram_create"].input_schema["required"], ["title", "nodes", "reason"])
        self.assertEqual(tools["infographic_plan_create"].input_schema["required"], ["title", "key_message", "reason"])
        self.assertEqual(tools["infographic_plan_inspect"].input_schema["required"], ["path"])
        self.assertEqual(tools["channel_catalog"].capability_group, "channels")
        self.assertEqual(tools["channel_manifest"].input_schema["required"], ["channel_id"])
        self.assertEqual(tools["channel_message_prepare"].input_schema["required"], ["channel_id", "conversation_id", "reason"])
        self.assertEqual(tools["channel_outbox"].capability_group, "channels")
        self.assertEqual(tools["channel_listener_status"].capability_group, "channels")
        self.assertEqual(tools["channel_listener_tick"].input_schema["required"], ["reason"])
        self.assertTrue(tools["channel_listener_tick"].requires_approval)
        self.assertEqual(tools["channel_webhook_ingest"].input_schema["required"], ["channel_id", "payload", "reason"])
        self.assertTrue(tools["channel_webhook_ingest"].requires_approval)
        self.assertEqual(tools["agent_skill_catalog"].capability_group, "skills")
        self.assertEqual(tools["agent_skill_read"].input_schema["required"], ["skill_id"])
        self.assertEqual(tools["agent_skill_import"].input_schema["required"], ["skill_ids", "reason"])
        self.assertEqual(tools["agent_skill_script_catalog"].capability_group, "skills")
        self.assertEqual(tools["agent_skill_script_read"].input_schema["required"], ["script_id"])
        self.assertEqual(tools["agent_skill_script_run"].input_schema["required"], ["script_id", "reason"])
        self.assertTrue(tools["agent_skill_script_run"].requires_approval)
        self.assertFalse(tools["system_status"].input_schema["required"])
        self.assertEqual(tools["system_status"].capability_group, "system")
        self.assertEqual(tools["voice_provider_status"].capability_group, "voice")
        self.assertEqual(tools["voice_transcribe"].input_schema["required"], ["audio_path", "reason"])
        self.assertEqual(tools["voice_response_prepare"].input_schema["required"], ["text", "reason"])
        self.assertIn("tts_provider", tools["voice_response_prepare"].input_schema["properties"])
        self.assertEqual(tools["voice_response_prepare"].capability_group, "voice")
        self.assertEqual(tools["voice_speak"].input_schema["required"], ["text", "reason"])
        self.assertIn("provider", tools["voice_speak"].input_schema["properties"])
        self.assertEqual(tools["voice_speak"].capability_group, "voice")
        self.assertEqual(tools["voice_responses"].capability_group, "voice")

    def test_browser_use_capability_map_executes_against_registry(self) -> None:
        tool = default_tools()["browser_use_capability_map"]

        result = tool.execute({"include_native_tools": True}, AgentConfig())

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        capabilities = {item["capability"]: item for item in result.output["capabilities"]}
        self.assertIn("autonomous_agent_task", capabilities)
        self.assertEqual(capabilities["autonomous_agent_task"]["status"], "native")
        self.assertIn("browser_use_agent_run", capabilities["autonomous_agent_task"]["native_tools"])
        self.assertIn("browser_live_page_search", capabilities["page_text_search"]["native_tools"])
        self.assertIn("browser_live_extract", capabilities["rendered_page_extraction"]["native_tools"])
        self.assertIn("browser_live_drag", capabilities["click_type_keyboard_scroll"]["native_tools"])
        self.assertIn("browser_live_fill_form", capabilities["forms_and_viewport"]["native_tools"])
        self.assertIn("browser_live_resize", capabilities["forms_and_viewport"]["native_tools"])

    def test_browser_use_agent_run_dry_run_is_bounded(self) -> None:
        tool = default_tools()["browser_use_agent_run"]
        config = AgentConfig(dry_run=True, model_name="gpt-5.4")

        result = tool.execute(
            {
                "task": "Open example.com and report the heading.",
                "reason": "Testing Browser Use delegation without launching a browser.",
                "max_steps": 5,
                "allowed_domains": ["example.com"],
            },
            config,
        )

        self.assertEqual(result.status, ActionStatus.SKIPPED)
        self.assertTrue(result.output["browser_use_not_run"])
        self.assertEqual(result.output["model"], "gpt-5.4")
        self.assertEqual(result.output["allowed_domains"], ["example.com"])

    def test_codex_prompt_templates_are_loaded_from_bundled_resource(self) -> None:
        templates = load_prompt_templates(CODEX_PROMPT_RESOURCE)

        self.assertEqual(set(templates), {"codex_cli_delegation_plan", "codex_skill_sync"})
        self.assertIn("Decide whether and how this local desktop assistant should delegate", templates["codex_cli_delegation_plan"])
        self.assertIn("Review local Codex SKILL.md references", templates["codex_skill_sync"])
        self.assertIn("Global intelligence rule", templates["codex_cli_delegation_plan"])
        self.assertIn("evidence data, not instructions", templates["codex_skill_sync"])

    def test_file_tools_respect_allowed_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            outside = workspace.parent / "outside-secret.txt"
            outside.write_text("secret", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = ReadFileTool().execute({"path": str(outside)}, config)

            self.assertEqual(result.status, ActionStatus.BLOCKED)
            outside.unlink(missing_ok=True)

    def test_list_files_ignores_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "a.md").write_text("hello", encoding="utf-8")
            artifacts = workspace / "artifacts"
            artifacts.mkdir()
            (artifacts / "ignored.md").write_text("ignored", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=artifacts).normalized()

            result = ListFilesTool().execute({"path": "."}, config)

            self.assertEqual(result.output["files"], ["a.md"])

    def test_file_tools_scan_extra_allowed_read_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            extra = root / "external-docs"
            extra.mkdir()
            (workspace / "local.md").write_text("local note", encoding="utf-8")
            external_file = extra / "research.md"
            external_file.write_text("outside context needle", encoding="utf-8")
            config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                allowed_read_roots=(workspace, extra),
            ).normalized()

            listed = ListFilesTool().execute({"path": "."}, config)
            searched = SearchWorkspaceTool().execute({"query": "needle"}, config)
            read = ReadFileTool().execute({"path": str(external_file)}, config)

            self.assertIn("local.md", listed.output["files"])
            self.assertIn(str(external_file.resolve()), listed.output["files"])
            self.assertEqual(searched.output["matches"][0]["path"], str(external_file.resolve()))
            self.assertEqual(read.status, ActionStatus.SUCCEEDED)

    def test_search_workspace_uses_ranked_token_fallback_for_natural_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "voice.md").write_text("Voice response preparation writes local artifacts.", encoding="utf-8")
            (workspace / "activity.md").write_text("Activity policy controls retention and exclusions.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = SearchWorkspaceTool().execute({"query": "voice response behavior activity policy"}, config)

            self.assertEqual(result.output["source"], "token_scan")
            paths = {match["path"] for match in result.output["matches"]}
            self.assertIn("voice.md", paths)
            self.assertIn("activity.md", paths)

    @unittest.skipUnless(pdf_dependencies_available(), "PDF test dependencies are unavailable")
    def test_pdf_tools_list_read_and_summarize_pdfs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pdf_path = workspace / "brief.pdf"
            write_pdf(pdf_path, "PDF roadmap needle\nBuild the safe local assistant first.")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            listed = ListPDFsTool().execute({"path": "."}, config)
            read = ReadPDFTool().execute({"path": "brief.pdf"}, config)
            summarized = SummarizePDFsTool().execute({"path": "."}, config)

            self.assertEqual(listed.output["files"][0]["path"], "brief.pdf")
            self.assertIn("PDF roadmap needle", read.output["text"])
            self.assertEqual(summarized.status, ActionStatus.SUCCEEDED)
            self.assertIn("safe local assistant", summarized.output["summaries"][0]["summary"])

    @unittest.skipUnless(pdf_dependencies_available(), "PDF test dependencies are unavailable")
    def test_pdf_merge_and_extract_pages_create_native_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            write_pdf(workspace / "part-a.pdf", "Alpha PDF page")
            write_pdf(workspace / "part-b.pdf", "Beta PDF page")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            merged = MergePDFsTool().execute(
                {
                    "paths": ["part-a.pdf", "part-b.pdf"],
                    "filename": "combined.pdf",
                    "reason": "Verify native PDF merge.",
                },
                config,
            )
            extracted = ExtractPDFPagesTool().execute(
                {
                    "path": merged.output["path"],
                    "start_page": 2,
                    "end_page": 2,
                    "filename": "beta-only.pdf",
                    "reason": "Verify native PDF page extraction.",
                },
                config,
            )
            read = ReadPDFTool().execute({"path": extracted.output["path"]}, config)

            self.assertEqual(merged.status, ActionStatus.SUCCEEDED)
            self.assertTrue(Path(merged.output["path"]).exists())
            self.assertEqual(merged.output["input_count"], 2)
            self.assertEqual(extracted.status, ActionStatus.SUCCEEDED)
            self.assertEqual(extracted.output["page_count"], 1)
            self.assertIn("Beta PDF page", read.output["text"])

    def test_ocr_provider_status_reports_without_cloud_use(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = OCRProviderStatusTool().execute({}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertFalse(result.output["cloud_ocr_used"])
        self.assertIn("providers", result.output)

    @unittest.skipUnless(pdf_dependencies_available(), "PDF test dependencies are unavailable")
    def test_pdf_tools_respect_allowed_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            outside = workspace.parent / "outside.pdf"
            write_pdf(outside, "secret PDF")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = ReadPDFTool().execute({"path": str(outside)}, config)

            self.assertEqual(result.status, ActionStatus.BLOCKED)
            outside.unlink(missing_ok=True)

    def test_write_note_stays_in_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = WriteNoteTool().execute({"title": "Hello Note", "content": "body"}, config)

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertTrue(Path(result.output["path"]).exists())

    def test_system_status_reports_storage_without_reading_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            payload = collect_system_status(config)
            result = SystemStatusTool().execute({}, config)

            self.assertIn(payload["overall_status"], {"ok", "low_disk", "critical_disk"})
            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertEqual(result.output["workspace"], str(workspace.resolve()))
            self.assertIn("storage", result.output)

    def test_active_window_tool_reports_platform_without_screen_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = ActiveWindowTool().execute({}, config)

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertIn("platform", result.output)
            self.assertIn("supported", result.output)

    def test_open_app_blocks_unallowlisted_apps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = OpenAppTool().execute({"app_id": "unknown"}, config)

            self.assertEqual(result.status, ActionStatus.BLOCKED)
            self.assertEqual(result.output["allowed_apps"], sorted(APP_ALLOWLIST))

    def test_open_app_dry_run_does_not_launch_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            result = OpenAppTool().execute({"app_id": "notepad"}, config)

            self.assertEqual(result.status, ActionStatus.SKIPPED)
            self.assertEqual(result.output["app_id"], "notepad")

    def test_open_app_uses_macos_allowlist_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "humungousaur.tools.os_tools.platform.system",
            return_value="Darwin",
        ), patch("humungousaur.tools.os_tools.subprocess.Popen") as popen:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = OpenAppTool().execute({"app_id": "calculator"}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertEqual(result.output["command"], ["open", "-a", "Calculator"])
        popen.assert_called_once_with(("open", "-a", "Calculator"), cwd=config.workspace)

    def test_open_app_normalizes_macos_allowlist_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "humungousaur.tools.os_tools.platform.system",
            return_value="Darwin",
        ), patch("humungousaur.tools.os_tools.subprocess.Popen") as popen:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = OpenAppTool().execute({"app_id": " Calculator "}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertEqual(result.output["app_id"], "calculator")
        self.assertEqual(result.output["command"], ["open", "-a", "Calculator"])
        popen.assert_called_once_with(("open", "-a", "Calculator"), cwd=config.workspace)

    def test_os_launch_app_uses_macos_allowlist_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "humungousaur.tools.os_tools.platform.system",
            return_value="Darwin",
        ), patch("humungousaur.tools.os_tools.subprocess.Popen") as popen:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = OsLaunchAppTool().execute({"app": "Calculator", "reason": "test launch"}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertEqual(result.output["app_id"], "calculator")
        self.assertEqual(result.output["command"], ["open", "-a", "Calculator"])
        popen.assert_called_once_with(("open", "-a", "Calculator"), cwd=config.workspace)

    def test_visible_windows_snapshot_reports_unsupported_platform(self) -> None:
        with patch("humungousaur.tools.os_tools.platform.system", return_value="Linux"):
            payload = visible_windows_snapshot()

        self.assertFalse(payload["supported"])
        self.assertIn("Windows only", payload["error"])

    def test_os_windows_tool_returns_failure_when_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "humungousaur.tools.os_tools.visible_windows_snapshot",
            return_value={"supported": False, "windows": [], "error": "unsupported"},
        ):
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = OsWindowsTool().execute({"limit": 5}, config)

        self.assertEqual(result.status, ActionStatus.FAILED)
        self.assertEqual(result.error, "unsupported")

    def test_os_observe_ui_dry_run_does_not_read_ui_contents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            result = OsObserveUiTool().execute(
                {"max_elements": 5, "include_values": True, "reason": "test"},
                config,
            )

        self.assertEqual(result.status, ActionStatus.SKIPPED)
        self.assertTrue(result.output["ui_contents_not_read"])
        self.assertEqual(result.output["max_elements"], 5)

    def test_ui_observation_store_persists_and_loads_elements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            stored = save_ui_observation(
                config,
                {
                    "supported": True,
                    "active_window": {"title": "Editor"},
                    "elements": [
                        {
                            "element_id": "uia:1",
                            "name": "Save",
                            "control_type": "Button",
                            "bounds": {"left": 10, "top": 20, "width": 30, "height": 40},
                        }
                    ],
                },
            )

            observation, element = load_ui_observation_element(config, stored["observation_id"], "uia:1")
            observation_path_exists = Path(stored["observation_path"]).exists()

        self.assertEqual(observation["active_window"]["title"], "Editor")
        self.assertEqual(element["name"], "Save")
        self.assertTrue(observation_path_exists)

    def test_os_click_and_type_tools_use_observed_element_in_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()
            stored = save_ui_observation(
                config,
                {
                    "supported": True,
                    "active_window": {"title": "Editor"},
                    "elements": [
                        {
                            "element_id": "uia:2",
                            "name": "Name",
                            "control_type": "Edit",
                            "bounds": {"left": 100, "top": 200, "width": 80, "height": 20},
                        }
                    ],
                },
            )

            clicked = OsClickElementTool().execute(
                {"observation_id": stored["observation_id"], "element_id": "uia:2", "reason": "select field"},
                config,
            )
            typed = OsTypeTextTool().execute(
                {
                    "observation_id": stored["observation_id"],
                    "element_id": "uia:2",
                    "text": "Hello",
                    "clear": True,
                    "reason": "fill field",
                },
                config,
            )

        self.assertEqual(clicked.status, ActionStatus.SKIPPED)
        self.assertEqual(clicked.output["coordinates"], {"x": 140, "y": 210})
        self.assertTrue(clicked.output["ui_action_not_sent"])
        self.assertEqual(typed.status, ActionStatus.SKIPPED)
        self.assertEqual(typed.output["text_length"], 5)
        self.assertTrue(typed.output["clear"])

    def test_os_scroll_element_uses_observed_element_in_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()
            stored = save_ui_observation(
                config,
                {
                    "supported": True,
                    "active_window": {"title": "Editor"},
                    "elements": [
                        {
                            "element_id": "uia:3",
                            "name": "Document",
                            "control_type": "Pane",
                            "bounds": {"left": 10, "top": 20, "width": 100, "height": 200},
                        }
                    ],
                },
            )

            result = OsScrollElementTool().execute(
                {
                    "observation_id": stored["observation_id"],
                    "element_id": "uia:3",
                    "direction": "down",
                    "amount": 4,
                    "reason": "continue reading",
                },
                config,
            )

        self.assertEqual(result.status, ActionStatus.SKIPPED)
        self.assertEqual(result.output["coordinates"], {"x": 60, "y": 120})
        self.assertEqual(result.output["direction"], "down")
        self.assertEqual(result.output["amount"], 4)

    def test_os_ui_action_rejects_missing_observation_element(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = OsClickElementTool().execute(
                {"observation_id": "not-a-uuid", "element_id": "uia:1", "reason": "test"},
                config,
            )

        self.assertEqual(result.status, ActionStatus.FAILED)
        self.assertIn("invalid", result.error or "")

    def test_os_send_keys_validates_shortcut_and_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            sent = OsSendKeysTool().execute({"shortcut": "Ctrl+S", "reason": "save"}, config)
            bad = OsSendKeysTool().execute({"shortcut": "Ctrl+Dragon", "reason": "bad"}, config)

        self.assertEqual(sent.status, ActionStatus.SKIPPED)
        self.assertEqual(sent.output["shortcut"], "Ctrl+S")
        self.assertEqual(bad.status, ActionStatus.FAILED)
        self.assertIn("Unsupported", bad.error or "")

    def test_os_window_tools_validate_window_ids_and_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            switched = OsSwitchWindowTool().execute({"window_id": "window:1234", "reason": "focus app"}, config)
            resized = OsResizeWindowTool().execute(
                {
                    "window_id": "window:1234",
                    "x": 10,
                    "y": 20,
                    "width": 800,
                    "height": 600,
                    "reason": "arrange workspace",
                },
                config,
            )
            bad = OsSwitchWindowTool().execute({"window_id": "bad:1234", "reason": "bad"}, config)

        self.assertEqual(switched.status, ActionStatus.SKIPPED)
        self.assertEqual(switched.output["window_handle"], 1234)
        self.assertEqual(resized.status, ActionStatus.SKIPPED)
        self.assertEqual(resized.output["bounds"], {"left": 10, "top": 20, "width": 800, "height": 600})
        self.assertEqual(bad.status, ActionStatus.FAILED)
        self.assertIn("Window id", bad.error or "")

    def test_cursor_and_virtual_desktop_snapshots_report_unsupported_platform(self) -> None:
        with patch("humungousaur.tools.os_tools.platform.system", return_value="Linux"):
            cursor = cursor_snapshot()
            desktops = virtual_desktops_snapshot()
            apps = start_apps_snapshot()

        self.assertFalse(cursor["supported"])
        self.assertIn("Windows only", cursor["error"])
        self.assertFalse(desktops["supported"])
        self.assertIn("Windows only", desktops["error"])
        self.assertFalse(apps["supported"])
        self.assertIn("Windows only", apps["error"])

    def test_os_coordinate_and_window_state_tools_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            clicked = OsClickCoordinatesTool().execute({"x": 12, "y": 34, "button": "right", "reason": "test"}, config)
            stated = OsWindowStateTool().execute({"window_id": "window:1234", "action": "maximize", "reason": "test"}, config)

        self.assertEqual(clicked.status, ActionStatus.SKIPPED)
        self.assertEqual(clicked.output["coordinates"], {"x": 12, "y": 34})
        self.assertEqual(clicked.output["button"], "right")
        self.assertEqual(stated.status, ActionStatus.SKIPPED)
        self.assertEqual(stated.output["action"], "maximize")
        self.assertEqual(stated.output["window_handle"], 1234)

    def test_os_uia_pattern_action_uses_observed_element_in_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()
            stored = save_ui_observation(
                config,
                {
                    "supported": True,
                    "active_window": {"title": "Editor"},
                    "elements": [
                        {
                            "element_id": "uia:5",
                            "name": "Save",
                            "control_type": "Button",
                            "bounds": {"left": 20, "top": 30, "width": 60, "height": 30},
                        }
                    ],
                },
            )

            result = OsUiaPatternActionTool().execute(
                {
                    "observation_id": stored["observation_id"],
                    "element_id": "uia:5",
                    "action": "invoke",
                    "reason": "activate save",
                },
                config,
            )

        self.assertEqual(result.status, ActionStatus.SKIPPED)
        self.assertEqual(result.output["coordinates"], {"x": 50, "y": 45})
        self.assertEqual(result.output["action"], "invoke")

    def test_os_virtual_desktop_tools_validate_and_dry_run(self) -> None:
        desktop_id = "11111111-1111-1111-1111-111111111111"
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            moved = OsMoveWindowToDesktopTool().execute(
                {"window_id": "window:1234", "desktop_id": desktop_id, "reason": "organize workspace"},
                config,
            )
            action = OsVirtualDesktopActionTool().execute({"action": "next", "reason": "switch workspace"}, config)
            bad = OsMoveWindowToDesktopTool().execute(
                {"window_id": "window:1234", "desktop_id": "not-a-guid", "reason": "bad"},
                config,
            )

        self.assertEqual(moved.status, ActionStatus.SKIPPED)
        self.assertEqual(moved.output["desktop_id"], desktop_id)
        self.assertEqual(action.status, ActionStatus.SKIPPED)
        self.assertEqual(action.output["action"], "next")
        self.assertEqual(bad.status, ActionStatus.FAILED)

    def test_os_app_launch_and_clipboard_tools_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            launch = OsLaunchAppTool().execute({"app": "Notepad", "reason": "edit note"}, config)
            read = OsClipboardReadTool().execute({"max_chars": 20, "reason": "inspect clipboard"}, config)
            write = OsClipboardWriteTool().execute({"text": "Hello", "reason": "prepare paste"}, config)

        self.assertEqual(launch.status, ActionStatus.SKIPPED)
        self.assertTrue(launch.output["process_not_started"])
        self.assertEqual(read.status, ActionStatus.SKIPPED)
        self.assertTrue(read.output["clipboard_not_read"])
        self.assertEqual(write.status, ActionStatus.SKIPPED)
        self.assertTrue(write.output["clipboard_not_written"])
        self.assertEqual(write.output["text_length"], 5)

    def test_screenshot_capture_dry_run_does_not_read_screen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            result = ScreenshotCaptureTool().execute({"reason": "test"}, config)

            self.assertEqual(result.status, ActionStatus.SKIPPED)
            self.assertTrue(result.output["screen_content_not_read"])

    def test_screen_captures_lists_metadata_without_image_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
            ).normalized()
            screenshots = config.data_dir / "screenshots"
            screenshots.mkdir(parents=True)
            path = screenshots / "screenshot-test.png"
            path.write_bytes(b"not-real-image")
            path.with_suffix(".json").write_text(
                json.dumps(
                    {
                        "path": str(path),
                        "filename": path.name,
                        "width": 120,
                        "height": 80,
                        "reason": "unit test",
                        "created_at": "2026-06-01T00:00:00+00:00",
                        "active_window": {"title": "Test Window"},
                    }
                ),
                encoding="utf-8",
            )

            captures = list_screenshot_captures(config)
            result = ScreenCapturesTool().execute({"limit": 5}, config)

            self.assertEqual(captures[0]["filename"], "screenshot-test.png")
            self.assertEqual(captures[0]["width"], 120)
            self.assertEqual(captures[0]["active_window_title"], "Test Window")
            self.assertFalse(captures[0]["image_bytes_served"])
            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertFalse(result.output["image_bytes_served"])

    def test_screen_capture_delete_removes_only_registry_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
            ).normalized()
            screenshots = config.data_dir / "screenshots"
            screenshots.mkdir(parents=True)
            path = screenshots / "screenshot-test.png"
            sidecar = screenshots / "screenshot-test.json"
            path.write_bytes(b"not-real-image")
            sidecar.write_text("{}", encoding="utf-8")

            result = ScreenCaptureDeleteTool().execute(
                {"filename": path.name, "reason": "cleanup test"},
                config,
            )
            escaped = ScreenCaptureDeleteTool().execute(
                {"filename": "../secret.png", "reason": "bad path"},
                config,
            )

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertFalse(path.exists())
            self.assertFalse(sidecar.exists())
            self.assertEqual(escaped.status, ActionStatus.BLOCKED)
            self.assertIn("not a path", escaped.summary)

    def test_summarize_text_keeps_markdown_concise(self) -> None:
        text = "# Title\n\n- one\n- two\n- three\n\n```python\nprint('skip')\n```\n\nMore detail."

        summary = summarize_text(text, max_sentences=3)

        self.assertEqual(summary, "Title one two")

    def test_shell_command_profiles_gate_inline_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            tool = ShellCommandTool()

            read_only = tool.execute(
                {"argv": ["python", "-c", "print('blocked')"], "command_profile": "read_only"},
                config,
            )
            workspace_write = tool.execute(
                {"argv": ["python", "-c", "print('blocked')"], "command_profile": "workspace_write"},
                config,
            )
            blocked = tool.execute(
                {"argv": ["python", "--version"], "command_profile": "blocked"},
                config,
            )

            self.assertEqual(read_only.status, ActionStatus.BLOCKED)
            self.assertIn("Read-only", read_only.summary)
            self.assertEqual(workspace_write.status, ActionStatus.BLOCKED)
            self.assertIn("Inline shell", workspace_write.summary)
            self.assertEqual(blocked.status, ActionStatus.BLOCKED)
            self.assertIn("profile blocks", blocked.summary)

    def test_native_reference_file_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                allowed_read_roots=(workspace,),
                allowed_write_roots=(workspace,),
            ).normalized()
            tools = default_tools(config)

            written = tools["write_file"].execute(
                {"path": "notes/example.txt", "content": "alpha beta\n", "reason": "test"},
                config,
            )
            self.assertEqual(written.status, ActionStatus.SUCCEEDED)

            searched = tools["search_files"].execute({"query": "alpha", "path": "notes"}, config)
            self.assertEqual(searched.status, ActionStatus.SUCCEEDED)
            self.assertEqual(searched.output["matches"][0]["path"], "notes/example.txt")

            patched = tools["patch"].execute(
                {
                    "path": "notes/example.txt",
                    "search": "alpha",
                    "replace": "gamma",
                    "expected_replacements": 1,
                    "reason": "test",
                },
                config,
            )
            self.assertEqual(patched.status, ActionStatus.SUCCEEDED)
            self.assertEqual((workspace / "notes/example.txt").read_text(encoding="utf-8"), "gamma beta\n")

    def test_tool_call_invokes_low_risk_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "readme.txt").write_text("hello from tool_call\n", encoding="utf-8")
            config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                allowed_read_roots=(workspace,),
                allowed_write_roots=(workspace,),
            ).normalized()

            result = default_tools(config)["tool_call"].execute(
                {"name": "read_file", "arguments": {"path": "readme.txt"}},
                config,
            )

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertEqual(result.output["target_tool"], "read_file")
            self.assertEqual(result.output["target_result"]["text"], "hello from tool_call\n")

    def test_tool_call_requires_target_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                allowed_read_roots=(workspace,),
                allowed_write_roots=(workspace,),
            ).normalized()

            result = default_tools(config)["tool_call"].execute(
                {"name": "write_file", "arguments": {"path": "x.txt", "content": "x", "reason": "test"}},
                config,
            )

            self.assertEqual(result.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(result.output["target_tool"], "write_file")

    def test_process_list_has_registry_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = default_tools(config)["process"].execute({"action": "list"}, config)

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertEqual(result.output["processes"], [])

    def test_native_runtime_primitives_persist_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            tools = default_tools(config)

            clarify = tools["clarify"].execute({"question": "Which route?", "options": ["A", "B"]}, config)
            self.assertEqual(clarify.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(clarify.output["options"], ["A", "B"])

            added = tools["todo"].execute({"action": "add", "title": "Ship parity"}, config)
            self.assertEqual(added.status, ActionStatus.SUCCEEDED)
            todo_id = added.output["todo"]["todo_id"]
            updated = tools["todo"].execute({"action": "update", "todo_id": todo_id, "status": "completed"}, config)
            self.assertEqual(updated.output["todo"]["status"], "completed")
            listed = tools["todo"].execute({"action": "list"}, config)
            self.assertEqual(len(listed.output["todos"]), 1)

            created = tools["cronjob"].execute(
                {"action": "create", "name": "Daily note", "schedule": "0 9 * * *", "prompt": "Summarize yesterday."},
                config,
            )
            self.assertEqual(created.status, ActionStatus.SUCCEEDED)
            triggered = tools["cronjob"].execute({"action": "trigger", "job_id": created.output["job"]["job_id"]}, config)
            self.assertEqual(triggered.status, ActionStatus.SUCCEEDED)
            self.assertEqual(triggered.output["prompt"], "Summarize yesterday.")

            delegated = tools["delegate_task"].execute({"task": "Inspect MCP parity", "toolsets": ["file"]}, config)
            self.assertEqual(delegated.status, ActionStatus.SUCCEEDED)
            self.assertEqual(delegated.output["delegation"]["status"], "queued")

    def test_session_search_finds_notes_and_execute_code_wraps_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            data_dir = workspace / "artifacts"
            notes_dir = data_dir / "notes"
            notes_dir.mkdir(parents=True)
            (notes_dir / "session.md").write_text("native parity checkpoint\n", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=data_dir, dry_run=True).normalized()
            tools = default_tools(config)

            found = tools["session_search"].execute({"query": "parity"}, config)
            self.assertEqual(found.status, ActionStatus.SUCCEEDED)
            self.assertEqual(found.output["matches"][0]["path"], "artifacts/notes/session.md")

            executed = tools["execute_code"].execute({"code": "print('ok')", "reason": "test"}, config)
            self.assertEqual(executed.status, ActionStatus.SKIPPED)
            self.assertEqual(executed.tool_name, "execute_code")

    def test_native_toolsets_mcp_provider_and_hook_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            toolset_dir = workspace / ".humungousaur" / "toolsets"
            mcp_dir = workspace / ".humungousaur" / "mcp"
            toolset_dir.mkdir(parents=True)
            mcp_dir.mkdir(parents=True)
            (toolset_dir / "custom.json").write_text(
                json.dumps(
                    {
                        "name": "custom-minimal",
                        "description": "A custom toolset used by tests.",
                        "tools": ["read_file", "terminal", "not_native_yet"],
                    }
                ),
                encoding="utf-8",
            )
            (mcp_dir / "demo.json").write_text(
                json.dumps(
                    {
                        "server_id": "demo",
                        "display_name": "Demo MCP",
                        "transport": "stdio",
                        "command": "node",
                        "args": ["server.js"],
                        "tools": ["demo_echo"],
                        "required_env": ["DEMO_MCP_TOKEN"],
                    }
                ),
                encoding="utf-8",
            )
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", dry_run=True).normalized()
            tools = default_tools(config)

            catalog = tools["native_toolset_catalog"].execute({"query": "custom", "include_tools": True}, config)
            self.assertEqual(catalog.status, ActionStatus.SUCCEEDED)
            self.assertEqual(catalog.output["toolsets"][0]["name"], "custom-minimal")
            self.assertIn("not_native_yet", catalog.output["toolsets"][0]["missing_tools"])
            described = tools["native_toolset_describe"].execute({"toolset": "native-cli"}, config)
            self.assertEqual(described.output["toolset"]["name"], "native-cli")
            self.assertIn({"tool": "terminal", "target": "run_shell_command"}, described.output["toolset"]["alias_backed_tools"])

            mcp_catalog = tools["mcp_server_catalog"].execute({"server_id": "demo", "include_tools": True}, config)
            self.assertEqual(mcp_catalog.output["servers"][0]["server_id"], "demo")
            self.assertEqual(mcp_catalog.output["servers"][0]["missing_env"], ["DEMO_MCP_TOKEN"])
            manifest = tools["mcp_server_manifest"].execute({"server_id": "linear"}, config)
            self.assertEqual(manifest.status, ActionStatus.SUCCEEDED)
            discovered = tools["mcp_tool_discover"].execute({"server_id": "demo"}, config)
            self.assertEqual(discovered.output["tools"], ["demo_echo"])
            needs_approval = tools["mcp_tool_call"].execute({"server_id": "demo", "tool": "demo_echo", "arguments": {"x": 1}}, config)
            self.assertEqual(needs_approval.status, ActionStatus.NEEDS_APPROVAL)
            dry_call = tools["mcp_tool_call"].execute(
                {"server_id": "demo", "tool": "demo_echo", "arguments": {"x": 1}, "approved": True},
                config,
            )
            self.assertEqual(dry_call.status, ActionStatus.SKIPPED)
            launch = tools["mcp_server_launch"].execute({"server_id": "demo", "approved": True}, config)
            self.assertEqual(launch.status, ActionStatus.SKIPPED)
            oauth = tools["mcp_oauth_status"].execute({"server_id": "demo"}, config)
            self.assertFalse(oauth.output["servers"][0]["configured"])

            enabled = tools["plugin_state"].execute({"action": "enable", "plugin_id": "mcp.demo", "reason": "test"}, config)
            self.assertTrue(enabled.output["plugin"]["enabled"])
            providers = tools["provider_registry"].execute({"provider_id": "anthropic"}, config)
            self.assertEqual(providers.output["providers"][0]["missing_env"], ["ANTHROPIC_API_KEY"])
            hooks = tools["runtime_hook_catalog"].execute({"event": "tool_call"}, config)
            self.assertEqual({hook["hook_id"] for hook in hooks.output["hooks"]}, {"tool.before_execute", "tool.after_execute"})

            surface = tools["capability_surface"].execute({"include_records": True}, config)
            self.assertIn("native_parity", surface.output)
            self.assertGreaterEqual(surface.output["native_parity"]["toolset_count"], 57)
            search = tools["tool_search"].execute({"query": "demo mcp", "kind": "mcp_server"}, config)
            self.assertEqual(search.output["matches"][0]["record_id"], "mcp_server:demo")

    def test_native_exact_tool_families_have_native_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", dry_run=True).normalized()
            tools = default_tools(config)

            required = {
                "browser_console",
                "browser_dialog",
                "browser_get_images",
                "browser_vision",
                "computer_use",
                "discord",
                "discord_admin",
                "feishu_doc_read",
                "feishu_drive_add_comment",
                "feishu_drive_list_comment_replies",
                "feishu_drive_list_comments",
                "feishu_drive_reply_comment",
                "ha_call_service",
                "ha_get_state",
                "ha_list_entities",
                "ha_list_services",
                "image_generate",
                "kanban_block",
                "kanban_comment",
                "kanban_complete",
                "kanban_create",
                "kanban_heartbeat",
                "kanban_link",
                "kanban_list",
                "kanban_show",
                "kanban_unblock",
                "memory",
                "mixture_of_agents",
                "spotify_albums",
                "spotify_devices",
                "spotify_library",
                "spotify_playback",
                "spotify_playlists",
                "spotify_queue",
                "spotify_search",
                "video_analyze",
                "video_generate",
                "vision_analyze",
                "x_search",
                "yb_query_group_info",
                "yb_query_group_members",
                "yb_search_sticker",
                "yb_send_dm",
                "yb_send_sticker",
            }
            self.assertEqual(required - set(tools), set())

            created = tools["kanban_create"].execute({"title": "Wire native parity"}, config)
            self.assertEqual(created.status, ActionStatus.SUCCEEDED)
            task_id = created.output["task"]["task_id"]
            blocked = tools["kanban_block"].execute({"task_id": task_id, "blocked_reason": "waiting"}, config)
            self.assertEqual(blocked.output["task"]["status"], "blocked")
            commented = tools["kanban_comment"].execute({"task_id": task_id, "comment": "checkpoint"}, config)
            self.assertEqual(commented.output["task"]["comments"][0]["text"], "checkpoint")
            linked = tools["kanban_link"].execute({"task_id": task_id, "target_task_id": "task-other"}, config)
            self.assertEqual(linked.output["task"]["links"][0]["target_task_id"], "task-other")
            completed = tools["kanban_complete"].execute({"task_id": task_id}, config)
            self.assertEqual(completed.output["task"]["status"], "completed")
            listed = tools["kanban_list"].execute({}, config)
            self.assertEqual(listed.output["board"]["task_count"], 1)

            memory = tools["memory"].execute({"action": "summary", "period": "today"}, config)
            self.assertEqual(memory.status, ActionStatus.SUCCEEDED)
            image = tools["image_generate"].execute({"prompt": "diagram of parity", "reason": "test"}, config)
            self.assertEqual(image.status, ActionStatus.SKIPPED)
            video = tools["video_generate"].execute({"prompt": "product tour", "reason": "test"}, config)
            self.assertEqual(video.status, ActionStatus.SKIPPED)
            vision = tools["vision_analyze"].execute({"path": "screen.png"}, config)
            self.assertEqual(vision.status, ActionStatus.SUCCEEDED)
            ha = tools["ha_list_entities"].execute({}, config)
            self.assertEqual(ha.status, ActionStatus.BLOCKED)
            self.assertEqual(ha.output["missing_env"], ["HOME_ASSISTANT_URL", "HOME_ASSISTANT_TOKEN"])
            spotify = tools["spotify_search"].execute({"query": "song"}, config)
            self.assertEqual(spotify.output["missing_env"], ["SPOTIFY_ACCESS_TOKEN"])
            x_search = tools["x_search"].execute({"query": "humungousaur"}, config)
            self.assertEqual(x_search.output["missing_env"], ["XAI_API_KEY"])

    def test_native_gateway_security_ops_and_skill_pack_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", dry_run=True).normalized()
            tools = default_tools(config)

            paired = tools["gateway_control"].execute(
                {"action": "authorize", "channel_id": "slack", "principal": "user-1"},
                config,
            )
            self.assertEqual(paired.status, ActionStatus.SUCCEEDED)
            session_id = next(iter(paired.output["gateway"]["sessions"]))
            interrupted = tools["gateway_control"].execute({"action": "interrupt", "session_id": session_id, "reason": "stop"}, config)
            self.assertEqual(interrupted.output["gateway"]["interrupts"][0]["reason"], "stop")

            delivery = tools["channel_delivery"].execute(
                {"action": "record", "channel_id": "slack", "job_id": "cron-1", "message": "hello"},
                config,
            )
            self.assertEqual(delivery.output["delivery"]["status"], "queued")
            sent = tools["channel_delivery"].execute({"action": "mark_sent", "delivery_id": delivery.output["delivery"]["delivery_id"]}, config)
            self.assertEqual(sent.output["delivery"]["status"], "sent")

            policy = tools["native_security_policy"].execute({"url": "http://127.0.0.1/admin", "command": "rm -rf /tmp/x"}, config)
            self.assertFalse(policy.output["allowed"])
            credentials = tools["credential_file_policy"].execute(
                {"action": "declare", "skill_id": "apple-notes", "paths": ["~/.config/example"], "reason": "test"},
                config,
            )
            self.assertEqual(credentials.output["declaration"]["skill_id"], "apple-notes")
            dependency = tools["optional_dependency_installer"].execute({"package": "playwright", "reason": "browser support"}, config)
            self.assertEqual(dependency.status, ActionStatus.SKIPPED)

            stored = tools["tool_output_store"].execute({"action": "store", "tool_name": "terminal", "content": "a" * 50}, config)
            read = tools["tool_output_store"].execute({"action": "read", "output_id": stored.output["output"]["output_id"], "limit": 10}, config)
            self.assertEqual(read.output["content"], "a" * 10)
            self.assertTrue(read.output["truncated"])

            packs = tools["native_skill_pack_catalog"].execute({"category": "mlops"}, config)
            self.assertEqual(packs.output["packs"][0]["pack_id"], "mlops_data_science")
            built = tools["native_skill_pack_build"].execute(
                {"pack_ids": ["apple", "autonomous_devops"], "reason": "parity"},
                config,
            )
            self.assertEqual(built.status, ActionStatus.SKIPPED)
            self.assertEqual(len(built.output["builds"]), 2)
            self.assertFalse(built.output["builds"][0]["upstream_imported"])
            self.assertEqual(built.output["builds"][0]["security_review"], "passed_contract_review")
            self.assertTrue(built.output["builds"][0]["skills"][0]["path"].endswith("skills/desktop-control/apple-notes/SKILL.md"))

    def test_native_skill_pack_build_writes_native_skill_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            tools = default_tools(config)

            result = tools["native_skill_pack_build"].execute(
                {"pack_ids": ["apple"], "overwrite": True, "reason": "native skill test"},
                config,
            )
            skill_path = workspace / "skills" / "desktop-control" / "apple-notes" / "SKILL.md"
            text = skill_path.read_text(encoding="utf-8")

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertTrue(skill_path.exists())
            self.assertIn("Humungousaur-native skill", text)
            self.assertIn("Do not import, execute, or vendor upstream assistant code", text)
            self.assertFalse(result.output["builds"][0]["upstream_imported"])
            self.assertEqual(result.output["builds"][0]["skills"][0]["status"], "built_native")

    def test_shell_trusted_dev_profile_allows_approved_inline_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", dry_run=True).normalized()

            result = ShellCommandTool().execute(
                {"argv": ["python", "-c", "print('trusted ok')"], "command_profile": "trusted_dev"},
                config,
            )

            self.assertEqual(result.status, ActionStatus.SKIPPED)
            self.assertEqual(result.output["command_profile"], "trusted_dev")
            self.assertEqual(result.output["argv"], ["python", "-c", "print('trusted ok')"])

    def test_plugin_manifest_discovery_registers_blocked_declared_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            plugin_dir = workspace / ".humungousaur" / "plugins" / "notes"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "plugin.json").write_text(
                json.dumps(
                    {
                        "name": "notes-helper",
                        "version": "0.1.0",
                        "description": "Local notes plugin.",
                        "capability_group": "plugins.notes",
                        "enabled": True,
                        "tools": [
                            {
                                "name": "plugin_notes_summarize",
                                "description": "Summarize local notes.",
                                "risk_level": "low",
                                "input_schema": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {"topic": {"type": "string"}},
                                    "required": ["topic"],
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            manifests = discover_plugin_manifests(config)
            tools = default_tools(config)
            listed = PluginManifestsTool().execute({}, config)
            detail = PluginManifestTool().execute({"name": "notes-helper"}, config)
            blocked = tools["plugin_notes_summarize"].execute({"topic": "work"}, config)

            self.assertEqual(manifests[0].name, "notes-helper")
            self.assertIn("plugin_notes_summarize", tools)
            self.assertEqual(tools["plugin_notes_summarize"].risk_level.value, "blocked")
            self.assertEqual(tools["plugin_notes_summarize"].capability_group, "plugins.notes")
            self.assertEqual(listed.status, ActionStatus.SUCCEEDED)
            self.assertEqual(listed.output["manifests"][0]["tool_count"], 1)
            self.assertEqual(detail.output["manifest"]["tools"][0]["execution_status"], "blocked_until_trusted_runtime")
            self.assertEqual(blocked.status, ActionStatus.BLOCKED)
            self.assertIn("trusted plugin runtime", blocked.summary)

    def test_codex_plugin_and_skill_catalog_imports_local_codex_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            plugin_root = workspace / ".codex" / "plugins" / "cache" / "openai-bundled" / "browser" / "1.0"
            skill_root = plugin_root / "skills" / "control-in-app-browser"
            script_root = plugin_root / "scripts"
            (plugin_root / ".codex-plugin").mkdir(parents=True)
            skill_root.mkdir(parents=True)
            script_root.mkdir(parents=True)
            (plugin_root / ".codex-plugin" / "plugin.json").write_text(
                json.dumps(
                    {
                        "name": "browser",
                        "version": "1.0",
                        "description": "Control the in-app browser from Codex.",
                        "license": "Proprietary",
                        "keywords": ["browser", "automation", "chrome"],
                        "skills": "./skills/",
                    }
                ),
                encoding="utf-8",
            )
            (script_root / "browser-client.mjs").write_text("export const browserClient = true;\n", encoding="utf-8")
            (skill_root / "SKILL.md").write_text(
                "---\nname: control-in-app-browser\ndescription: Control the in-app Browser.\n---\n# Browser\nUse for browser automation.\n",
                encoding="utf-8",
            )
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            plugins = CodexPluginCatalogTool().execute({"query": "browser", "source": "workspace"}, config)
            catalog = CodexSkillCatalogTool().execute({"query": "in-app", "source": "workspace"}, config)
            skill_id = catalog.output["skills"][0]["skill_id"]
            read = CodexSkillReadTool().execute({"skill_id": skill_id}, config)
            imported = CodexSkillImportTool().execute({"skill_ids": [skill_id], "reason": "Enable browser skill guidance."}, config)

            self.assertEqual(plugins.status, ActionStatus.SUCCEEDED)
            self.assertEqual(plugins.output["plugins"][0]["name"], "browser")
            self.assertEqual(plugins.output["plugins"][0]["skill_count"], 1)
            self.assertIn("scripts/browser-client.mjs", plugins.output["plugins"][0]["scripts"])
            self.assertEqual(catalog.status, ActionStatus.SUCCEEDED)
            self.assertEqual(catalog.output["skills"][0]["name"], "control-in-app-browser")
            self.assertIn("# Browser", read.output["content"])
            self.assertEqual(imported.status, ActionStatus.SUCCEEDED)
            self.assertEqual(imported.output["imported_skills"][0]["name"], "Codex: control-in-app-browser")

    def test_codex_catalog_discovers_bundled_app_resource_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            app_root = workspace / "codex-app-resources"
            plugin_root = app_root / "plugins" / "openai-bundled" / "plugins" / "computer-use"
            skill_root = plugin_root / "skills" / "computer-use"
            (plugin_root / ".codex-plugin").mkdir(parents=True)
            skill_root.mkdir(parents=True)
            (plugin_root / ".codex-plugin" / "plugin.json").write_text(
                json.dumps(
                    {
                        "name": "computer-use",
                        "version": "26.0",
                        "description": "Control Windows desktop apps from Codex.",
                        "skills": "./skills/",
                        "keywords": ["computer-use", "windows"],
                    }
                ),
                encoding="utf-8",
            )
            (skill_root / "SKILL.md").write_text(
                "---\nname: computer-use\ndescription: Use Computer Use for Microsoft Windows apps.\n---\n# Computer Use\n",
                encoding="utf-8",
            )
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            with patch("humungousaur.tools.codex.implementation._codex_app_resource_roots", return_value=[app_root]):
                plugins = CodexPluginCatalogTool().execute({"query": "computer", "source": "app"}, config)
                skills = CodexSkillCatalogTool().execute({"query": "computer-use", "source": "app"}, config)

            self.assertEqual(plugins.status, ActionStatus.SUCCEEDED)
            self.assertEqual(plugins.output["plugins"][0]["name"], "computer-use")
            self.assertEqual(plugins.output["plugins"][0]["skill_count"], 1)
            self.assertEqual(skills.status, ActionStatus.SUCCEEDED)
            self.assertEqual(skills.output["skills"][0]["name"], "computer-use")
            self.assertEqual(skills.output["skills"][0]["source"], "app")

    def test_codex_cli_plan_uses_model_to_prepare_run_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            fake_codex = workspace / "codex.exe"
            fake_codex.write_text("", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            model_payload = json.dumps(
                {
                    "status": "planned",
                    "summary": "Codex should inspect the repo with a dry run first.",
                    "should_delegate": True,
                    "task": "Inspect this repository and summarize the next implementation step.",
                    "working_directory": "",
                    "sandbox": "read-only",
                    "approval_policy": "on-request",
                    "json_output": True,
                    "timeout_seconds": 120,
                    "dry_run_first": True,
                    "resume": "",
                    "extra_args": ["--search", "--sandbox", "danger-full-access"],
                    "verification_steps": ["Review the final Codex output before acting."],
                    "expected_outputs": ["Repository summary"],
                    "risk_notes": ["Read-only delegation only."],
                    "evidence_refs": ["model:test"],
                    "confidence": 0.82,
                }
            )
            client = RecordingStaticModelClient(model_payload)

            with (
                patch("humungousaur.tools.codex.implementation._codex_cli_candidates", return_value=[fake_codex]),
                patch("humungousaur.tools.codex.implementation.build_model_client", return_value=client),
            ):
                planned = CodexCliPlanTool().execute(
                    {
                        "objective": "Use Codex CLI to inspect this repository.",
                        "context": "Need a bounded read-only handoff.",
                        "preferred_sandbox": "workspace-write",
                    },
                    config,
                )

            self.assertEqual(planned.status, ActionStatus.SUCCEEDED)
            self.assertEqual(planned.output["next_tool"], "codex_cli_run")
            self.assertEqual(planned.output["codex_cli_run_input"]["task"], "Inspect this repository and summarize the next implementation step.")
            self.assertEqual(planned.output["codex_cli_run_input"]["sandbox"], "read-only")
            self.assertTrue(planned.output["codex_cli_run_input"]["dry_run"])
            self.assertIn("--search", planned.output["codex_cli_run_input"]["extra_args"])
            self.assertNotIn("danger-full-access", planned.output["codex_cli_run_input"]["extra_args"])
            self.assertIn("Decide whether and how this local desktop assistant should delegate", client.prompts[0])
            self.assertIn("Prefer read-only and dry-run-first", client.prompts[0])
            self.assertIn('"objective":"Use Codex CLI to inspect this repository."', client.prompts[0])

    def test_codex_cli_status_and_run_dry_run_build_exec_argv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            fake_codex = workspace / "codex.exe"
            fake_codex.write_text("", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", dry_run=True).normalized()

            with patch("humungousaur.tools.codex.implementation._codex_cli_candidates", return_value=[fake_codex]):
                status = CodexCliStatusTool().execute({}, config)
                run = CodexCliRunTool().execute(
                    {
                        "task": "summarize this repository",
                        "sandbox": "workspace-write",
                        "approval_policy": "never",
                        "json_output": True,
                        "extra_args": ["--search", "--sandbox", "danger-full-access"],
                    },
                    config,
                )

            self.assertEqual(status.status, ActionStatus.SUCCEEDED)
            self.assertTrue(status.output["cli"]["available"])
            self.assertEqual(run.status, ActionStatus.SKIPPED)
            self.assertEqual(run.output["argv"][:2], [str(fake_codex), "exec"])
            self.assertIn("--sandbox", run.output["argv"])
            self.assertIn("workspace-write", run.output["argv"])
            self.assertIn("--ask-for-approval", run.output["argv"])
            self.assertIn("never", run.output["argv"])
            self.assertIn("--json", run.output["argv"])
            self.assertIn("--search", run.output["argv"])
            self.assertNotIn("danger-full-access", run.output["argv"])
            self.assertEqual(run.output["argv"][-1], "summarize this repository")

    def test_codex_skill_sync_writes_relevant_agent_skill_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            skill_root = workspace / ".codex" / "plugins" / "cache" / "openai-bundled" / "browser" / "1.0" / "skills" / "control-in-app-browser"
            skill_root.mkdir(parents=True)
            (skill_root / "SKILL.md").write_text(
                "---\nname: control-in-app-browser\ndescription: Control the in-app Browser.\n---\n# Browser\nUse Browser before Computer Use fallback.\n",
                encoding="utf-8",
            )
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            catalog = CodexSkillCatalogTool().execute({"query": "in-app", "source": "workspace"}, config)
            skill_id = catalog.output["skills"][0]["skill_id"]
            model_payload = json.dumps(
                {
                    "status": "recorded",
                    "summary": "Browser skill should become reusable.",
                    "skills": [
                        {
                            "source_skill_id": skill_id,
                            "name": "Model-selected Browser workflow",
                            "purpose": "Use Codex browser guidance as evidence for browser UI verification tasks.",
                            "when_to_use": "Use when model reasoning determines a browser workflow is needed.",
                            "tools": ["browser_live_open", "browser_live_observe", "not_a_real_tool"],
                            "verification_steps": ["Read the source skill and observe page state before acting."],
                            "failure_modes": ["Using stale browser observations."],
                            "evidence_refs": ["model:test"],
                            "confidence": 0.83,
                        }
                    ],
                    "skipped_skill_ids": [],
                    "evidence_refs": [f"codex_skill:{skill_id}"],
                    "confidence": 0.83,
                }
            )
            client = RecordingStaticModelClient(model_payload)

            with patch("humungousaur.tools.codex.implementation.build_model_client", return_value=client):
                synced = CodexSkillSyncTool().execute({"profile": "browser_computer", "reason": "Bring browser skills into agent."}, config)

            self.assertEqual(synced.status, ActionStatus.SUCCEEDED)
            self.assertEqual(synced.output["synced_skills"][0]["name"], "Model-selected Browser workflow")
            self.assertIn("browser_live_open", synced.output["synced_skills"][0]["tools"])
            self.assertIn("codex_skill_read", synced.output["synced_skills"][0]["tools"])
            self.assertNotIn("not_a_real_tool", synced.output["synced_skills"][0]["tools"])
            self.assertEqual(synced.output["proposal"]["skills"][0]["source_skill_id"], skill_id)
            self.assertIn("Review local Codex SKILL.md references", client.prompts[0])
            self.assertIn("Each proposed source_skill_id must be one exact skill_id", client.prompts[0])
            self.assertIn(f'"skill_id":"{skill_id}"', client.prompts[0])

    def test_codex_skill_sync_skips_without_model_instead_of_template_matching(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            skill_root = workspace / ".codex" / "skills" / "control-in-app-browser"
            skill_root.mkdir(parents=True)
            (skill_root / "SKILL.md").write_text(
                "---\nname: control-in-app-browser\ndescription: Control the in-app Browser.\n---\n# Browser\n",
                encoding="utf-8",
            )
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            def fail_client(_config):
                raise ModelClientError("offline")

            with patch("humungousaur.tools.codex.implementation.build_model_client", side_effect=fail_client):
                synced = CodexSkillSyncTool().execute({"profile": "browser_computer", "reason": "test unavailable model"}, config)

            self.assertEqual(synced.status, ActionStatus.SKIPPED)
            self.assertIn("no semantic fallback", synced.summary)
            self.assertIn("does not guess", synced.output["safety_note"])


if __name__ == "__main__":
    unittest.main()
