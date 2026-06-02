import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.orchestrator import AgentOrchestrator
from humungousaur.runtime import approve_pending_action, update_pending_approval_input
from humungousaur.safety.approvals import ApprovalStore
from humungousaur.safety.audit import AuditLog


class ApprovalQueueTests(unittest.TestCase):
    def test_pending_approval_can_be_replayed_and_executed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

            run_result = AgentOrchestrator(config).run('run_shell_command {"argv":["python","--version"]}')
            token = run_result.approvals[0].approval_token

            pending = ApprovalStore(config.approvals_db_path).list()
            self.assertEqual(pending[0].approval_token, token)
            paused_run = AuditLog(config.audit_db_path).get_run(run_result.run_id)
            self.assertEqual(paused_run["status"], "needs_approval")
            self.assertIsNone(paused_run["finished_at"])

            replay = approve_pending_action(config, token, "test approval")

            self.assertIn("Command exited with code 0", replay["summary"])
            self.assertIn("Python", replay["stdout"])
            self.assertEqual(replay["run_id"], run_result.run_id)
            updated = ApprovalStore(config.approvals_db_path).get(token)
            self.assertIsNotNone(updated)
            self.assertEqual(updated.status, "executed")
            self.assertIsNotNone(updated.result)
            source_run = AuditLog(config.audit_db_path).get_run(run_result.run_id)
            self.assertEqual(source_run["status"], "succeeded")
            timeline = AuditLog(config.audit_db_path).get_run_events(run_result.run_id)
            event_types = [event["event_type"] for event in timeline]
            self.assertIn("approval_approved", event_types)
            self.assertIn("run_waiting_for_approval", event_types)
            self.assertIn("run_finished", event_types)

    def test_pending_approval_can_be_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

            run_result = AgentOrchestrator(config).run('run_shell_command {"argv":["python","--version"]}')
            token = run_result.approvals[0].approval_token

            rejected = ApprovalStore(config.approvals_db_path).reject(token, "not now")

            self.assertEqual(rejected.status, "rejected")
            self.assertEqual(rejected.decision_note, "not now")

    def test_pending_approval_input_can_be_edited_before_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

            run_result = AgentOrchestrator(config).run('run_shell_command {"argv":["python","--version"]}')
            token = run_result.approvals[0].approval_token

            updated = update_pending_approval_input(
                config,
                token,
                {"argv": ["python", "-V"]},
                "use shorter version flag",
            )
            replay = approve_pending_action(config, token, "approved edited input")

            self.assertEqual(updated["approval"]["tool_input"], {"argv": ["python", "-V"]})
            self.assertIn("Python", replay["stdout"])
            timeline = AuditLog(config.audit_db_path).get_run_events(run_result.run_id)
            event_types = [event["event_type"] for event in timeline]
            self.assertIn("approval_updated", event_types)

    def test_pending_approval_edit_validates_tool_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

            run_result = AgentOrchestrator(config).run('run_shell_command {"argv":["python","--version"]}')
            token = run_result.approvals[0].approval_token

            with self.assertRaises(ValueError):
                update_pending_approval_input(config, token, {"argv": "python -V"}, "bad edit")

            pending = ApprovalStore(config.approvals_db_path).get(token)
            self.assertEqual(pending.tool_input, {"argv": ["python", "--version"]})


if __name__ == "__main__":
    unittest.main()
