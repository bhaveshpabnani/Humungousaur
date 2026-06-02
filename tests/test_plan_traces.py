import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from humungousaur.config import AgentConfig
from humungousaur.orchestrator import AgentOrchestrator
from humungousaur.safety.audit import AuditLog


class PlanTraceTests(unittest.TestCase):
    def test_explicit_plan_trace_is_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Demo\n\nLocal assistant.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

            result = AgentOrchestrator(config).run('list_files {"path":"."}')
            trace = AuditLog(config.audit_db_path).get_plan_trace(result.run_id)

            self.assertIsNotNone(trace)
            assert trace is not None
            self.assertEqual(trace["requested_provider"], "explicit")
            self.assertEqual(trace["used_provider"], "explicit")
            self.assertFalse(trace["fallback_used"])
            self.assertEqual(trace["steps"][0]["tool_name"], "list_files")

    def test_model_fallback_plan_trace_records_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Demo\n\nLocal assistant.", encoding="utf-8")
            config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                planner_provider="model",
                model_provider="openai-responses",
                model_name="test-model",
                model_api_key_env="MISSING_OPENAI_API_KEY",
            ).normalized()

            with patch.dict("os.environ", {}, clear=True):
                result = AgentOrchestrator(config).run("summarize this project")
            trace = AuditLog(config.audit_db_path).get_plan_trace(result.run_id)

            self.assertIsNotNone(trace)
            assert trace is not None
            self.assertEqual(trace["requested_provider"], "model")
            self.assertEqual(trace["used_provider"], "explicit")
            self.assertTrue(trace["fallback_used"])
            self.assertIn("OPENAI_API_KEY", trace["error"])
            self.assertEqual(trace["steps"], [])


if __name__ == "__main__":
    unittest.main()
