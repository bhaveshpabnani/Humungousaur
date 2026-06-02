import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.performance import run_benchmarks


class PerformanceTests(unittest.TestCase):
    def test_run_benchmarks_reports_core_operations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Demo\n\nproject benchmark needle", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = run_benchmarks(config, iterations=1, query="needle")

            names = {item["name"] for item in result["benchmarks"]}
            self.assertEqual(result["iterations"], 1)
            self.assertIn("permissions_snapshot", names)
            self.assertIn("explicit_planner", names)
            self.assertIn("planning_context", names)
            self.assertIn("tool_schema_validation", names)
            self.assertIn("list_files_allowed_roots", names)
            self.assertIn("search_allowed_roots", names)
            self.assertIn("memory_search", names)
            self.assertIn("memory_summary", names)
            self.assertIn("memory_profile", names)
            self.assertIn("memory_write_dry_run", names)
            self.assertIn("os_active_window", names)
            self.assertIn("screenshot_capture_dry_run", names)
            self.assertIn("screen_captures_metadata", names)
            self.assertIn("browser_sessions_metadata", names)
            self.assertIn("file_index_rebuild", names)
            self.assertIn("file_index_search", names)
            self.assertIn("agent_dry_run_summary", names)
            planning_context = next(item for item in result["benchmarks"] if item["name"] == "planning_context")
            browser_sessions = next(item for item in result["benchmarks"] if item["name"] == "browser_sessions_metadata")
            self.assertGreaterEqual(planning_context["last"]["recent_memory"], 1)
            self.assertGreaterEqual(planning_context["last"]["browser_sessions"], 1)
            self.assertGreaterEqual(browser_sessions["last"]["sessions"], 1)
            self.assertFalse(browser_sessions["last"]["page_text_returned"])
            for item in result["benchmarks"]:
                self.assertGreaterEqual(item["avg_ms"], 0)
                self.assertGreaterEqual(item["max_ms"], item["min_ms"])


if __name__ == "__main__":
    unittest.main()
