import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.orchestrator import AgentOrchestrator
from humungousaur.safety.audit import AuditLog
from humungousaur.schemas import ActionStatus
from humungousaur.tools.browser_tools import BrowserSessionStore
from tests.pdf_utils import pdf_dependencies_available, write_pdf


class OrchestratorTests(unittest.TestCase):
    def test_summarize_project_writes_note_and_audit_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "task.md").write_text("Build a safe local assistant. Add audit logs next.", encoding="utf-8")
            (workspace / "README.md").write_text("# Demo\n\nThis project is a local agent runtime.", encoding="utf-8")

            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit")
            result = AgentOrchestrator(config).run(
                '{"steps":['
                '{"tool_name":"read_file","tool_input":{"path":"README.md"},"reason":"summarize project"},'
                '{"tool_name":"read_file","tool_input":{"path":"task.md"},"reason":"summarize project"}'
                "]}"
            )

            self.assertIn("README.md", result.final_response)
            self.assertIsNotNone(result.note_path)
            self.assertTrue(Path(result.note_path or "").exists())
            self.assertTrue((workspace / "artifacts" / "audit.sqlite3").exists())
            self.assertTrue(any(tool_result.status == ActionStatus.SUCCEEDED for tool_result in result.results))

    def test_search_workspace_returns_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "notes.md").write_text("The agent should remember workflows.", encoding="utf-8")

            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit")
            result = AgentOrchestrator(config).run('search_workspace {"query":"workflows"}')

            self.assertIn("search_workspace: succeeded", result.final_response)

    def test_system_status_reports_runtime_health(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit")

            result = AgentOrchestrator(config).run("system_status {}")

            self.assertIn("System status:", result.final_response)
            self.assertEqual(result.results[0].tool_name, "system_status")

    def test_active_window_request_uses_os_observation_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit")

            result = AgentOrchestrator(config).run("os_active_window {}")

            self.assertIn("Active window:", result.final_response)
            self.assertEqual(result.results[0].tool_name, "os_active_window")

    def test_open_app_request_pauses_for_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit")

            result = AgentOrchestrator(config).run('open_app {"app_id":"notepad"}')

            self.assertIn("needs_approval", result.final_response)
            self.assertEqual(result.results[0].tool_name, "open_app")
            self.assertEqual(result.results[0].status, ActionStatus.NEEDS_APPROVAL)

    def test_remember_request_writes_searchable_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit")

            remembered = AgentOrchestrator(config).run(
                'memory_write {"kind":"preference","text":"I prefer concise project updates"}'
            )
            recalled = AgentOrchestrator(config).run('memory_search {"query":"concise project updates"}')

            self.assertIn("memory_write: succeeded", remembered.final_response)
            self.assertEqual(remembered.results[0].tool_name, "memory_write")
            self.assertIn("memory_search: succeeded", recalled.final_response)
            self.assertIn("concise project updates", recalled.final_response)
            self.assertEqual(recalled.results[0].tool_name, "memory_search")

    def test_planning_context_includes_recent_memory_and_browser_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            skill_dir = workspace / "skills" / "demo-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: Demo workspace skill.\n---\n# Demo\n",
                encoding="utf-8",
            )
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()
            orchestrator = AgentOrchestrator(config)
            orchestrator.memory.append("user_memory", {"kind": "preference", "text": "context needle"})
            session = BrowserSessionStore(config.browser_sessions_db_path).create_or_update(
                {
                    "url": "http://127.0.0.1/example",
                    "title": "Context Browser",
                    "text": "Browser context",
                    "links": [],
                    "forms": [],
                }
            )

            context = orchestrator._planning_context()

            self.assertEqual(context["recent_memory"][0]["payload"]["text"], "context needle")
            self.assertEqual(context["user_profile"]["preferences"][0]["text"], "context needle")
            self.assertEqual(context["browser_sessions"][0]["session_id"], session["session_id"])
            self.assertEqual(context["screen_captures"]["count"], 0)
            self.assertEqual(context["available_workspace_skills"][0]["name"], "demo-skill")
            self.assertIn("channels.slack", {plugin["plugin_id"] for plugin in context["capability_plugins"]})
            self.assertIn("slack", {channel["channel_id"] for channel in context["gateway_channels"]})
            self.assertIn("system", context)
            self.assertIn("active_window", context)

    def test_planning_context_collection_is_audited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Demo", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

            result = AgentOrchestrator(config).run('list_files {"path":"."}')
            events = AuditLog(config.audit_db_path).get_run_events(result.run_id)

            event_types = [event["event_type"] for event in events]
            self.assertIn("planning_context_collected", event_types)

    @unittest.skipUnless(pdf_dependencies_available(), "PDF test dependencies are unavailable")
    def test_summarize_pdfs_uses_pdf_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            write_pdf(workspace / "research.pdf", "Agent memory roadmap\nSummarize PDFs safely.")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit")

            result = AgentOrchestrator(config).run('summarize_pdfs {"path":"."}')

            self.assertIn("PDF summaries: 1 files", result.final_response)
            self.assertIn("Agent memory roadmap", result.final_response)
            self.assertEqual(result.results[0].tool_name, "summarize_pdfs")

    @unittest.skipUnless(pdf_dependencies_available(), "PDF test dependencies are unavailable")
    def test_summarize_pdfs_can_use_named_allowed_read_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            downloads = root / "Downloads"
            workspace.mkdir()
            downloads.mkdir()
            write_pdf(downloads / "downloaded.pdf", "Downloads summary needle")
            config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                allowed_read_roots=(workspace, downloads),
                planner_provider="explicit",
            )

            result = AgentOrchestrator(config).run(f'summarize_pdfs {{"path":"{downloads}"}}')

            self.assertIn("Downloads summary needle", result.final_response)
            self.assertEqual(result.results[0].tool_name, "summarize_pdfs")


if __name__ == "__main__":
    unittest.main()
