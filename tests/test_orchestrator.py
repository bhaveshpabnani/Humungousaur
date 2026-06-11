import json
import tempfile
import unittest
from pathlib import Path

from humungousaur.active_agent.models import (
    ActiveAgentActivation,
    ActiveEpisode,
    DeepDiveRequest,
    MutedScope,
    MutedScopeMode,
    ReflexPosture,
    TaskContext,
)
from humungousaur.active_agent.store import ActiveAgentStore
from humungousaur.cognition.knowledge import KnowledgeStore
from humungousaur.cognition.models import KnowledgeKind
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
            orchestrator.memory.append(
                "active_agent_memory_candidate",
                {"summary": "unaccepted active-agent candidate should not be generic recent memory", "payload": {"raw_text": "private"}},
            )
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
            self.assertEqual(len(context["recent_memory"]), 1)
            self.assertEqual(context["user_profile"]["preferences"][0]["text"], "context needle")
            self.assertEqual(context["active_agent_memory"]["source"], "active_agent_memory_candidate")
            self.assertEqual(context["active_agent_memory"]["items"], [])
            self.assertEqual(context["active_agent_state"]["source"], "active_agent_runtime")
            self.assertEqual(context["active_agent_state"]["task_contexts"], [])
            self.assertEqual(context["browser_sessions"][0]["session_id"], session["session_id"])
            self.assertEqual(context["screen_captures"]["count"], 0)
            self.assertEqual(context["available_workspace_skills"][0]["name"], "demo-skill")
            self.assertIn("channels.slack", {plugin["plugin_id"] for plugin in context["capability_plugins"]})
            self.assertIn("slack", {channel["channel_id"] for channel in context["gateway_channels"]})
            self.assertIn("system", context)
            self.assertIn("active_window", context)

    def test_planning_context_includes_only_active_agent_promoted_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()
            knowledge = KnowledgeStore(config.cognition_db_path)
            promoted = knowledge.append(
                kind=KnowledgeKind.CONTEXT,
                text="User is preparing the Acme proposal from active-agent memory.",
                source="active_agent_memory_candidate",
                evidence_refs=["active_memory_candidate:mem-1", "collector_event:42"],
                confidence=0.82,
            )
            manual = knowledge.append(
                kind=KnowledgeKind.CONTEXT,
                text="Manual context should stay in generic cognition only.",
                source="manual",
                evidence_refs=["manual:1"],
                confidence=0.7,
            )
            archived = knowledge.append(
                kind=KnowledgeKind.CONTEXT,
                text="Archived active-agent memory should not influence planning.",
                source="active_agent_memory_candidate",
                evidence_refs=["active_memory_candidate:old"],
                confidence=0.8,
            )
            low_confidence = knowledge.append(
                kind=KnowledgeKind.CONTEXT,
                text="Low confidence active-agent memory should not influence planning yet.",
                source="active_agent_memory_candidate",
                evidence_refs=["active_memory_candidate:low"],
                confidence=0.2,
            )
            knowledge.archive(archived.knowledge_id, reason="private correction")

            context = AgentOrchestrator(config)._planning_context("what should I continue?")
            active_items = context["active_agent_memory"]["items"]
            generic_knowledge_ids = {item["knowledge_id"] for item in context["cognition"]["knowledge"]}
            active_ids = {item["knowledge_id"] for item in active_items}

        self.assertEqual([item["knowledge_id"] for item in active_items], [promoted.knowledge_id])
        self.assertEqual(active_items[0]["text"], promoted.text)
        self.assertIn("active_memory_candidate:mem-1", active_items[0]["evidence_refs"])
        self.assertEqual(context["active_agent_memory"]["min_confidence"], 0.5)
        self.assertEqual(context["active_agent_memory"]["recency"], "most_recent_updated_at")
        self.assertIn(manual.knowledge_id, generic_knowledge_ids)
        self.assertNotIn(archived.knowledge_id, active_ids)
        self.assertNotIn(low_confidence.knowledge_id, active_ids)

    def test_planning_context_includes_active_agent_state_without_raw_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()
            store = ActiveAgentStore(config.active_agent_db_path)
            store.upsert_episode(
                ActiveEpisode(
                    episode_id="episode-acme",
                    status="active",
                    hypothesis="User is drafting the Acme proposal.",
                    summary="Acme proposal drafting session.",
                    confidence="high",
                    primary_entities=[{"kind": "document", "ref": "document_id_hash:doc123", "raw_text": "private text"}],
                    evidence_refs=["collector_event:10", "reflex_decision:episode"],
                    last_event_sequence=10,
                )
            )
            store.upsert_task_context(
                TaskContext(
                    task_context_id="ctx-proposal",
                    status="active",
                    source="user_declared",
                    user_declared_goal="Finish the Acme proposal.",
                    episode_id="episode-acme",
                    primary_entities=[{"kind": "document", "ref": "document_id_hash:doc123", "raw_text": "should be compact"}],
                    assistant_mode="supportive",
                    allowed_help=["resume_capsule", "outline"],
                    privacy_mode="metadata_first",
                    summary="User is drafting the Acme proposal.",
                    evidence_refs=["correction:helpful"],
                )
            )
            store.upsert_task_context(
                TaskContext(
                    task_context_id="ctx-completed",
                    status="completed",
                    summary="Completed task should not be current active state.",
                )
            )
            store.record_activation(
                ActiveAgentActivation(
                    activation_id="act-prepare",
                    decision_id="decision-1",
                    route_id="route-1",
                    event_sequence=12,
                    posture=ReflexPosture.PREPARE,
                    status="prepared",
                    response_mode="silent",
                    stimulus_id="stimulus-1",
                    user_visible_text="",
                    agent_stimulus="Prepare a resume capsule for the Acme proposal.",
                    reason="User returned after a gap.",
                    allowed_actions=["prepare_silent_help"],
                    forbidden_actions=["read_rich_content_without_approval"],
                    evidence_refs=["reflex_decision:decision-1", "collector_event:12"],
                )
            )
            store.record_activation(
                ActiveAgentActivation(
                    activation_id="act-skipped",
                    decision_id="decision-2",
                    route_id="route-2",
                    event_sequence=11,
                    posture=ReflexPosture.PREPARE,
                    status="skipped",
                    response_mode="silent",
                    stimulus_id="stimulus-2",
                )
            )
            store.record_resume_capsule(
                {
                    "boundary_id": "stable_context:entity:doc123",
                    "boundary_type": "stable_context",
                    "event_sequence": 12,
                    "reason": "Stable document context.",
                }
            )
            store.record_deep_dive_request(
                DeepDiveRequest(
                    request_id="deep-1",
                    episode_id="episode-acme",
                    requested_by="reflex",
                    purpose="Read richer document context only after approval.",
                    source="document",
                    requested_access="document_body",
                    status="needs_approval",
                    evidence_refs=["activation:act-prepare"],
                )
            )
            store.create_muted_scope(
                MutedScope(
                    scope_id="mute-1",
                    mode=MutedScopeMode.NOT_NOW,
                    scope_type="manual",
                    entity_refs=["document_id_hash:private"],
                    reason="User said not now.",
                )
            )

            state = AgentOrchestrator(config)._planning_context("continue")["active_agent_state"]
            serialized = str(state)

        self.assertEqual(state["task_contexts"][0]["task_context_id"], "ctx-proposal")
        self.assertEqual(state["episodes"][0]["episode_id"], "episode-acme")
        self.assertEqual(state["episodes"][0]["event_count"], 0)
        self.assertIn("document_id_hash:doc123", serialized)
        self.assertEqual(state["task_contexts"][0]["summary"], "User is drafting the Acme proposal.")
        self.assertNotIn("raw_text", serialized)
        self.assertNotIn("private text", serialized)
        self.assertNotIn("should be compact", serialized)
        self.assertNotIn("ctx-completed", serialized)
        self.assertEqual(state["activations"][0]["activation_id"], "act-prepare")
        self.assertIn("collector_event:12", state["activations"][0]["evidence_refs"])
        self.assertNotIn("act-skipped", serialized)
        self.assertEqual(state["resume_capsules"][0]["boundary_id"], "stable_context:entity:doc123")
        self.assertEqual(state["deep_dive_requests"][0]["request_id"], "deep-1")
        self.assertEqual(state["muted_scopes"][0]["mode"], "not_now")
        self.assertNotIn("harness_result", serialized)

    def test_active_agent_planner_context_preview_exposes_only_planner_lanes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()
            KnowledgeStore(config.cognition_db_path).append(
                kind=KnowledgeKind.CONTEXT,
                text="Preview should include promoted active-agent memory.",
                source="active_agent_memory_candidate",
                evidence_refs=["active_memory_candidate:preview"],
                confidence=0.72,
            )
            ActiveAgentStore(config.active_agent_db_path).upsert_task_context(
                TaskContext(
                    task_context_id="ctx-preview",
                    status="active",
                    primary_entities=[{"kind": "document", "ref": "document_id_hash:preview", "raw_text": "private entity text"}],
                    summary="Preview-safe active task.",
                    evidence_refs=["task_context:ctx-preview"],
                )
            )

            preview = AgentOrchestrator(config).active_agent_planner_context_preview("Bearer secret-token continue")
            serialized = json.dumps(preview, sort_keys=True, default=str)

        self.assertEqual(preview["source"], "planner_runtime_context_preview")
        self.assertIn("active_agent_memory", preview)
        self.assertIn("active_agent_state", preview)
        self.assertIn("safety", preview)
        self.assertIn("Preview-safe active task.", serialized)
        self.assertIn("Preview should include promoted active-agent memory.", serialized)
        self.assertNotIn("secret-token", serialized)
        self.assertNotIn("private entity text", serialized)
        self.assertNotIn("raw_text", serialized)
        self.assertNotIn("routes", preview)
        self.assertNotIn("decisions", preview)
        self.assertNotIn("memory_candidates", preview)
        self.assertNotIn("store_path", serialized)

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
