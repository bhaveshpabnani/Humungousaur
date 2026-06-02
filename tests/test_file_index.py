import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.indexing import FileIndex
from humungousaur.tools.file_tools import SearchWorkspaceTool


class FileIndexTests(unittest.TestCase):
    def test_rebuild_indexes_allowed_text_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("alpha needle\nsecond line", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            status = FileIndex(config.file_index_db_path).rebuild(config)
            matches = FileIndex(config.file_index_db_path).search("needle", config)

            self.assertTrue(status["usable"])
            self.assertEqual(status["indexed_files"], 1)
            self.assertEqual(matches[0]["path"], "README.md")
            self.assertEqual(matches[0]["source"], "index")

    def test_search_tool_uses_index_when_read_roots_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("indexedneedle", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            FileIndex(config.file_index_db_path).rebuild(config)

            result = SearchWorkspaceTool().execute({"query": "indexedneedle"}, config)

            self.assertEqual(result.output["source"], "index")
            self.assertEqual(result.output["matches"][0]["source"], "index")

    def test_search_tool_falls_back_when_read_roots_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            extra = root / "extra"
            extra.mkdir()
            (workspace / "README.md").write_text("workspace only", encoding="utf-8")
            (extra / "notes.md").write_text("fallbackneedle", encoding="utf-8")
            base_config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            expanded_config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                allowed_read_roots=(workspace, extra),
            ).normalized()
            FileIndex(base_config.file_index_db_path).rebuild(base_config)

            result = SearchWorkspaceTool().execute({"query": "fallbackneedle"}, expanded_config)

            self.assertEqual(result.output["source"], "scan")
            self.assertEqual(result.output["matches"][0]["path"], str((extra / "notes.md").resolve()))

    def test_status_reports_stale_when_indexed_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            readme = workspace / "README.md"
            readme.write_text("old needle", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            index = FileIndex(config.file_index_db_path)
            index.rebuild(config)

            readme.write_text("fresh needle with a different size", encoding="utf-8")
            status = index.status(config)

            self.assertFalse(status["usable"])
            self.assertTrue(status["stale"])
            self.assertIn("changed_files:1", status["stale_reasons"])

    def test_search_tool_falls_back_when_index_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            readme = workspace / "README.md"
            readme.write_text("oldneedle", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            FileIndex(config.file_index_db_path).rebuild(config)

            readme.write_text("freshneedle with a different size", encoding="utf-8")
            result = SearchWorkspaceTool().execute({"query": "freshneedle"}, config)

            self.assertEqual(result.output["source"], "scan")
            self.assertEqual(result.output["matches"][0]["source"], "scan")
            self.assertEqual(result.output["matches"][0]["path"], "README.md")

    def test_status_reports_stale_when_new_file_appears(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("indexed", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            index = FileIndex(config.file_index_db_path)
            index.rebuild(config)

            (workspace / "notes.md").write_text("new file", encoding="utf-8")
            status = index.status(config)

            self.assertFalse(status["usable"])
            self.assertTrue(status["stale"])
            self.assertIn("new_files:1", status["stale_reasons"])


if __name__ == "__main__":
    unittest.main()
