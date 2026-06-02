import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.executor import Executor
from humungousaur.memory.event_store import EventStore
from humungousaur.safety.policy import PolicyEngine
from humungousaur.schemas import ActionStatus, PlannedStep
from humungousaur.tools import default_tools
from humungousaur.tools.activity_tools import (
    ActivityIngestTool,
    ActivityPolicyStore,
    ActivityPolicyTool,
    ActivityPolicyUpdateTool,
    ActivityPruneTool,
    ActivitySearchTool,
    activity_policy_path,
)
from humungousaur.tools.memory_tools import MemorySearchTool, MemorySummaryTool


class ActivityToolTests(unittest.TestCase):
    def test_activity_ingest_requires_approval_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            step = PlannedStep(
                "activity_ingest",
                {"source": "accessibility", "text": "Worked on project notes", "app_name": "Code"},
                "Record observed local activity.",
            )

            result = Executor(default_tools(), PolicyEngine()).execute(step, config)

            self.assertEqual(result.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(result.output["approval"]["tool_name"], "activity_ingest")

    def test_activity_ingest_and_search_native_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            ingested = ActivityIngestTool().execute(
                {
                    "source": "accessibility",
                    "text": "Reviewed Browser Use adapter implementation for project integration.",
                    "app_name": "Code",
                    "window_title": "Humungousaur",
                    "metadata": {"repo": "browser-use"},
                },
                config,
            )
            searched = ActivitySearchTool().execute({"query": "Browser Use adapter", "limit": 5}, config)

            self.assertEqual(ingested.status, ActionStatus.SUCCEEDED)
            self.assertEqual(searched.status, ActionStatus.SUCCEEDED)
            self.assertEqual(len(searched.output["matches"]), 1)
            self.assertEqual(searched.output["matches"][0]["payload"]["app_name"], "Code")

    def test_activity_ingest_dry_run_does_not_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            ingested = ActivityIngestTool().execute(
                {"source": "manual", "text": "dry activity"},
                config,
            )
            searched = ActivitySearchTool().execute({"query": "dry activity"}, config)

            self.assertEqual(ingested.status, ActionStatus.SKIPPED)
            self.assertEqual(searched.output["matches"], [])

    def test_activity_policy_blocks_excluded_ingest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            ActivityPolicyStore(activity_policy_path(config)).save({"excluded_apps": ["SecretApp"], "retention_days": 30})

            result = ActivityIngestTool().execute(
                {"source": "accessibility", "text": "private work", "app_name": "SecretApp"},
                config,
            )
            searched = ActivitySearchTool().execute({"query": "private work"}, config)

            self.assertEqual(result.status, ActionStatus.BLOCKED)
            self.assertTrue(result.output["blocked_by_policy"])
            self.assertEqual(searched.output["matches"], [])

    def test_activity_search_and_memory_tools_filter_policy_excluded_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            store = EventStore(config.memory_db_path)
            store.append(
                "activity_event",
                {"source": "browser", "text": "visible project note", "app_name": "Code", "url": "https://example.com"},
            )
            store.append(
                "activity_event",
                {"source": "browser", "text": "hidden banking note", "app_name": "Browser", "url": "https://bank.example.com"},
            )
            ActivityPolicyStore(activity_policy_path(config)).save({"excluded_url_domains": ["bank.example.com"], "retention_days": 30})

            activity = ActivitySearchTool().execute({"query": "note", "limit": 10}, config)
            memory = MemorySearchTool().execute({"query": "note", "limit": 10}, config)
            summary = MemorySummaryTool().execute({"period": "recent", "query": "note", "limit": 10}, config)

            self.assertEqual([event["payload"]["text"] for event in activity.output["matches"]], ["visible project note"])
            self.assertEqual([event["payload"]["text"] for event in memory.output["matches"]], ["visible project note"])
            self.assertEqual(summary.output["total_events"], 1)
            self.assertIn("activity_event", summary.output["event_counts"])

    def test_activity_policy_update_dry_run_previews_without_saving(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            result = ActivityPolicyUpdateTool().execute(
                {"retention_days": 7, "excluded_apps": ["Mail"], "reason": "privacy"},
                config,
            )
            loaded = ActivityPolicyTool().execute({}, config)

            self.assertEqual(result.status, ActionStatus.SKIPPED)
            self.assertTrue(result.output["policy_not_saved"])
            self.assertEqual(result.output["policy"]["retention_days"], 7)
            self.assertEqual(loaded.output["policy"]["retention_days"], 30)

    def test_activity_prune_deletes_only_old_activity_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            store = EventStore(config.memory_db_path)
            old_at = datetime.now(timezone.utc) - timedelta(days=40)
            store.append("activity_event", {"source": "manual", "text": "old activity"}, created_at=old_at)
            store.append("activity_event", {"source": "manual", "text": "fresh activity"})
            store.append("user_memory", {"kind": "fact", "text": "old memory"}, created_at=old_at)

            pruned = ActivityPruneTool().execute({"older_than_days": 30, "reason": "retention"}, config)
            events = store.search("activity", limit=10)
            memories = store.search("old memory", limit=10)

            self.assertEqual(pruned.status, ActionStatus.SUCCEEDED)
            self.assertEqual(pruned.output["deleted_count"], 1)
            self.assertEqual([event["payload"]["text"] for event in events], ["fresh activity"])
            self.assertEqual(len(memories), 1)


if __name__ == "__main__":
    unittest.main()
