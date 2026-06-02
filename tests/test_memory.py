import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from humungousaur.memory.event_store import EventStore
from humungousaur.memory.profile import build_user_profile, compact_user_profile
from humungousaur.memory.summary import summarize_memory
from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.memory_tools import MemoryProfileTool, MemorySearchTool, MemorySummaryTool, MemoryWriteTool


class EventStoreTests(unittest.TestCase):
    def test_append_tail_and_search_memory_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = EventStore(Path(tmp_dir) / "memory.sqlite3")

            event_id = store.append("agent_run", {"request": "summarize project"})

            recent = store.tail(limit=1)
            matches = store.search("summarize", limit=5)
            self.assertEqual(recent[0]["event_id"], event_id)
            self.assertEqual(matches[0]["payload"]["request"], "summarize project")

    def test_between_returns_events_inside_time_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = EventStore(Path(tmp_dir) / "memory.sqlite3")
            start = datetime.now(timezone.utc) - timedelta(seconds=1)
            event_id = store.append("agent_run", {"request": "windowed recap"})
            end = datetime.now(timezone.utc) + timedelta(seconds=1)

            matches = store.between(start_at=start, end_at=end)

            self.assertEqual(matches[0]["event_id"], event_id)

    def test_memory_tools_write_and_search_local_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            written = MemoryWriteTool().execute(
                {"kind": "preference", "text": "User prefers concise project updates."},
                config,
            )
            searched = MemorySearchTool().execute({"query": "concise", "limit": 5}, config)

            self.assertEqual(written.status, ActionStatus.SUCCEEDED)
            self.assertEqual(searched.status, ActionStatus.SUCCEEDED)
            self.assertEqual(searched.output["matches"][0]["payload"]["text"], "User prefers concise project updates.")

    def test_memory_summary_recaps_runs_and_preferences(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            store = EventStore(config.memory_db_path)
            store.append("agent_run", {"request": "summarize PDFs", "status": "succeeded", "approvals_requested": 0})
            store.append("user_memory", {"kind": "preference", "text": "User likes concise updates with no secrets sk-test."})

            payload = summarize_memory(store, period="recent")
            result = MemorySummaryTool().execute({"period": "recent", "limit": 20}, config)

            self.assertEqual(payload["total_events"], 2)
            self.assertIn("agent_run", payload["event_counts"])
            self.assertIn("summarize PDFs", payload["summary"])
            self.assertIn("sk-REDACTED", payload["preferences"][0])
            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertEqual(result.output["total_events"], 2)

    def test_memory_profile_projects_explicit_user_memories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            store = EventStore(config.memory_db_path)
            store.append("user_memory", {"kind": "preference", "text": "Use compact status updates."})
            store.append("user_memory", {"kind": "workflow", "text": "For releases, check tests then summarize changes."})
            store.append("user_memory", {"kind": "fact", "text": "Token is Bearer abc123."})

            profile = build_user_profile(store)
            compact = compact_user_profile(profile)
            result = MemoryProfileTool().execute({"limit": 20}, config)

            self.assertEqual(profile["total_memories"], 3)
            self.assertEqual(profile["preferences"][0]["text"], "Use compact status updates.")
            self.assertIn("For releases", profile["workflows"][0]["text"])
            self.assertIn("Bearer REDACTED", profile["facts"][0]["text"])
            self.assertEqual(compact["preferences"][0]["text"], "Use compact status updates.")
            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertIn("User profile: 3", result.summary)

    def test_memory_write_respects_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", dry_run=True).normalized()

            result = MemoryWriteTool().execute({"kind": "fact", "text": "dry run fact"}, config)
            matches = EventStore(config.memory_db_path).search("dry run fact")

            self.assertEqual(result.status, ActionStatus.SKIPPED)
            self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
