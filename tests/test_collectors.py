import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import humungousaur.collectors.manager as collector_manager
import humungousaur.collectors.lifecycle as lifecycle_collectors
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
        self.assertEqual(status["profile"]["privacy_mode"], "privacy_first")
        self.assertFalse(status["profile"]["rich_capture_opt_in"]["clipboard"])
        self.assertIn("audio_activity", status["capabilities"]["collectors"])
        self.assertIn("input_device", status["capabilities"]["collectors"])
        self.assertIn("browser_lifecycle", status["capabilities"]["collectors"])

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

    def test_file_burst_coalesces_into_attention_batch_for_llm(self) -> None:
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
                    "submit_to_harness": True,
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
                    "max_events_per_tick": 5,
                },
            )

            result = run_collector_tick(config, force=True)
            memory = EventStore(config.memory_db_path).tail(limit=20)
            context_exists = Path(result.current_context["current_context_path"]).exists()

        self.assertEqual(len(result.collected), 2)
        self.assertEqual(len(result.attention_batches), 1)
        self.assertEqual(len(result.submitted), 1)
        self.assertEqual(result.submitted[0]["collector"], "attention_batch")
        self.assertEqual(result.attention_batches[0]["collector_counts"]["filesystem"], 2)
        self.assertIn("Filesystem changes: 2 file(s)", result.attention_batches[0]["text"])
        self.assertEqual(len([event for event in memory if event["event_type"] == "attention_batch"]), 1)
        self.assertEqual(result.semantic_events[0]["event_type"], "project_files_changed")
        self.assertEqual(result.action_candidates[0]["action_type"], "update_context")
        self.assertTrue(context_exists)

    def test_rich_capture_collector_requires_explicit_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": False,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": True,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                    },
                },
            )

            with patch.object(collector_manager, "_clipboard_text", return_value="very secret clipboard"):
                result = run_collector_tick(config, force=True)

        self.assertEqual(result.collected, [])
        self.assertTrue(any(item["reason"] == "rich capture collector is not opted in" for item in result.skipped))

    def test_clipboard_attention_batch_omits_clipboard_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": True,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                    },
                    "rich_capture_opt_in": {"clipboard": True},
                },
            )

            with patch.object(collector_manager, "_clipboard_text", return_value="super secret clipboard"):
                result = run_collector_tick(config, force=True)

        self.assertEqual(len(result.attention_batches), 1)
        batch = result.attention_batches[0]
        self.assertIn("Clipboard changed", batch["text"])
        self.assertNotIn("super secret", batch["text"])
        self.assertNotIn("super secret", str(batch["events"]))

    def test_ambient_voice_activity_does_not_submit_to_llm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": True,
                    },
                    "rich_capture_opt_in": {"audio_activity": True},
                },
            )

            with patch.object(collector_manager, "_audio_rms_sample", return_value={"rms": 0.2, "sample_rate": 16000, "sample_seconds": 1.5}):
                result = run_collector_tick(config, force=True)

        self.assertEqual(len(result.collected), 1)
        self.assertEqual(result.attention_batches, [])
        self.assertEqual(result.submitted, [])

    def test_collector_rate_limit_caps_event_floods(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            watched = root / "watched"
            workspace.mkdir()
            watched.mkdir()
            for index in range(3):
                (watched / f"{index}.txt").write_text(str(index), encoding="utf-8")
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
                    "max_file_events": 3,
                    "collector_rate_limits_per_minute": {"filesystem": 1},
                },
            )

            result = run_collector_tick(config)

        self.assertEqual(len(result.collected), 1)
        self.assertEqual(len([item for item in result.skipped if "minute budget exceeded" in item["reason"]]), 2)

    def test_input_device_collector_reads_native_bridge_spool_without_text_logging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            spool_dir = config.data_dir / "collector_spool"
            spool_dir.mkdir(parents=True)
            (spool_dir / "input_device.jsonl").write_text(
                '{"event_id":"mouse-forward-1","stimulus_type":"mouse_forward","metadata":{"button":"forward"},"payload":{"button":4}}\n',
                encoding="utf-8",
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
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "input_device": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(len(result.collected), 1)
        self.assertEqual(result.collected[0]["collector"], "input_device")
        self.assertEqual(result.collected[0]["stimulus_type"], "mouse_forward")
        self.assertNotIn("typed", str(result.collected[0]).lower())

    def test_app_lifecycle_collector_detects_opened_process_after_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
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
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "app_lifecycle": True,
                    },
                },
            )

            with patch.object(lifecycle_collectors, "_process_names", side_effect=[{"Finder"}, {"Finder", "Xcode"}]):
                baseline = run_collector_tick(config, force=True)
                opened = run_collector_tick(config, force=True)

        self.assertEqual(baseline.collected, [])
        self.assertEqual(len(opened.collected), 1)
        self.assertEqual(opened.collected[0]["collector"], "app_lifecycle")
        self.assertEqual(opened.collected[0]["stimulus_type"], "app_opened")
        self.assertEqual(opened.collected[0]["metadata"]["app_name"], "Xcode")


if __name__ == "__main__":
    unittest.main()
