import tempfile
import unittest
from pathlib import Path

from humungousaur.collectors import (
    collector_status,
    run_collector_tick,
    save_collector_profile,
)
from humungousaur.config import AgentConfig
from humungousaur.memory.event_store import EventStore
from humungousaur.tools.activity.implementation import ActivityPolicyStore, activity_policy_path


class CollectorTests(unittest.TestCase):
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
        self.assertIn("audio_activity", status["capabilities"]["collectors"])

    def test_filesystem_collector_records_and_dedupes_events(self) -> None:
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

            first = run_collector_tick(config)
            second = run_collector_tick(config)
            events = [event for event in EventStore(config.memory_db_path).tail(limit=10) if event["event_type"] == "collector_stimulus"]

        self.assertEqual(len(first.collected), 1)
        self.assertEqual(len(second.collected), 0)
        self.assertTrue(any(item["reason"] == "duplicate" for item in second.skipped))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["stimulus_type"], "file_changed")

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

            first = run_collector_tick(config)
            second = run_collector_tick(config)
            events = [event for event in EventStore(config.memory_db_path).tail(limit=10) if event["event_type"] == "collector_stimulus"]

        self.assertEqual(len(first.collected), 2)
        self.assertEqual(len(second.collected), 0)
        self.assertEqual(len([item for item in second.skipped if item["reason"] == "duplicate"]), 2)
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

            result = run_collector_tick(config)

        paths = [item["payload"]["relative_path"] for item in result.collected]
        self.assertEqual(paths, [str(watched / "public.txt")])

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

            result = run_collector_tick(config)
            events = [event for event in EventStore(config.memory_db_path).tail(limit=10) if event["event_type"] == "collector_stimulus"]

        self.assertEqual(result.collected, [])
        self.assertTrue(any("source disabled" in item["reason"] for item in result.skipped))
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
