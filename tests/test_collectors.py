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
        self.assertIn("browser_page_activity", status["capabilities"]["collectors"])
        self.assertIn("terminal_activity", status["capabilities"]["collectors"])
        self.assertIn("ide_activity", status["capabilities"]["collectors"])
        self.assertIn("accessibility_context", status["capabilities"]["collectors"])
        self.assertIn("notification_activity", status["capabilities"]["collectors"])
        self.assertIn("calendar_activity", status["capabilities"]["collectors"])
        self.assertIn("communication_activity", status["capabilities"]["collectors"])
        self.assertIn("security_context", status["capabilities"]["collectors"])

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

    def test_terminal_bridge_collector_batches_semantic_failure_without_raw_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            spool_dir = config.data_dir / "collector_spool"
            spool_dir.mkdir(parents=True)
            (spool_dir / "terminal_activity.jsonl").write_text(
                '{"event_id":"tests-failed-1","stimulus_type":"tests_failed","text":"Tests failed in backend suite.","metadata":{"app_name":"Terminal"},"payload":{"summary":"2 tests failed","raw_output":"SECRET RAW OUTPUT"}}\n',
                encoding="utf-8",
            )
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
                        "audio_activity": False,
                        "terminal_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(len(result.collected), 1)
        self.assertEqual(result.collected[0]["collector"], "terminal_activity")
        self.assertEqual(result.semantic_events[0]["event_type"], "terminal_activity")
        self.assertEqual(result.action_candidates[0]["action_type"], "analyze")
        self.assertIn("Terminal activity event", result.attention_batches[0]["text"])
        self.assertNotIn("SECRET RAW OUTPUT", str(result.attention_batches[0]))

    def test_calendar_bridge_collector_queues_briefing_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            spool_dir = config.data_dir / "collector_spool"
            spool_dir.mkdir(parents=True)
            (spool_dir / "calendar_activity.jsonl").write_text(
                '{"event_id":"meeting-starting-1","stimulus_type":"meeting_starting","text":"Meeting starting soon.","metadata":{"calendar_id":"work"}}\n',
                encoding="utf-8",
            )
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
                        "audio_activity": False,
                        "calendar_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(result.semantic_events[0]["event_type"], "calendar_activity")
        self.assertEqual(result.action_candidates[0]["action_type"], "prepare_briefing")
        self.assertIn("Calendar event", result.attention_batches[0]["text"])

    def test_security_bridge_collector_requires_rich_capture_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            spool_dir = config.data_dir / "collector_spool"
            spool_dir.mkdir(parents=True)
            (spool_dir / "security_context.jsonl").write_text(
                '{"event_id":"password-field-1","stimulus_type":"password_field_focused","text":"Password field focused."}\n',
                encoding="utf-8",
            )
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
                        "audio_activity": False,
                        "security_context": True,
                    },
                },
            )

            blocked = run_collector_tick(config, force=True)
            save_collector_profile(config, {"rich_capture_opt_in": {"security_context": True}})
            with (spool_dir / "security_context.jsonl").open("a", encoding="utf-8") as handle:
                handle.write('{"event_id":"private-mode-1","stimulus_type":"private_browsing_detected","text":"Private browsing detected."}\n')
            allowed = run_collector_tick(config, force=True)

        self.assertEqual(blocked.collected, [])
        self.assertTrue(any(item["reason"] == "rich capture collector is not opted in" for item in blocked.skipped))
        self.assertEqual(allowed.semantic_events[0]["event_type"], "security_context_changed")
        self.assertEqual(allowed.action_candidates[0]["action_type"], "suppress_collection")

    def test_bridge_activity_collectors_feed_compact_attention_batches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            spool_dir = config.data_dir / "collector_spool"
            spool_dir.mkdir(parents=True)
            (spool_dir / "terminal_activity.jsonl").write_text(
                '{"event_id":"terminal-fail-1","stimulus_type":"terminal_command_failed","text":"Terminal command failed: pytest exited 1.","metadata":{"app_name":"Terminal"},"payload":{"exit_code":1}}\n',
                encoding="utf-8",
            )
            (spool_dir / "browser_page_activity.jsonl").write_text(
                '{"event_id":"browser-error-1","stimulus_type":"console_error","text":"Browser console error observed.","metadata":{"app_name":"Chrome","url":"http://localhost:3000"},"payload":{"error_count":1}}\n',
                encoding="utf-8",
            )
            save_collector_profile(
                config,
                {
                    "enabled": True,
                    "submit_to_harness": True,
                    "batch_seconds": 1,
                    "llm_attention_interval_seconds": 1,
                    "collectors": {
                        "active_window": False,
                        "browser": False,
                        "clipboard": False,
                        "filesystem": False,
                        "screenshot": False,
                        "screen_ocr": False,
                        "video_frame": False,
                        "audio_activity": False,
                        "terminal_activity": True,
                        "browser_page_activity": True,
                    },
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual({event["collector"] for event in result.collected}, {"terminal_activity", "browser_page_activity"})
        self.assertEqual(len(result.attention_batches), 1)
        batch_text = result.attention_batches[0]["text"]
        self.assertIn("Terminal activity event(s): 1", batch_text)
        self.assertIn("Browser page activity event(s): 1", batch_text)
        self.assertIn("terminal_activity", {event["event_type"] for event in result.semantic_events})
        self.assertIn("browser_page_activity", {event["event_type"] for event in result.semantic_events})

    def test_productivity_bridge_collectors_generate_semantic_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            spool_dir = config.data_dir / "collector_spool"
            spool_dir.mkdir(parents=True)
            (spool_dir / "communication_activity.jsonl").write_text(
                '{"event_id":"mention-1","stimulus_type":"mention_received","text":"Mention received in Slack.","metadata":{"channel_id":"slack","conversation_id":"C123"},"payload":{"body":"SECRET MESSAGE BODY"}}\n',
                encoding="utf-8",
            )
            (spool_dir / "calendar_activity.jsonl").write_text(
                '{"event_id":"meeting-1","stimulus_type":"meeting_starting","text":"Meeting starting in 5 minutes.","metadata":{"app_name":"Calendar"},"payload":{"title":"Planning"}}\n',
                encoding="utf-8",
            )
            (spool_dir / "notification_activity.jsonl").write_text(
                '{"event_id":"alert-1","stimulus_type":"critical_alert_received","text":"Critical notification received.","metadata":{"app_name":"PagerDuty"},"payload":{"body":"SECRET ALERT BODY"}}\n',
                encoding="utf-8",
            )
            (spool_dir / "security_context.jsonl").write_text(
                '{"event_id":"security-1","stimulus_type":"private_browsing_detected","text":"Private browsing detected.","metadata":{"privacy_level":"sensitive"},"payload":{"url":"SECRET PRIVATE URL"}}\n',
                encoding="utf-8",
            )
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
                        "audio_activity": False,
                        "communication_activity": True,
                        "calendar_activity": True,
                        "notification_activity": True,
                        "security_context": True,
                    },
                    "rich_capture_opt_in": {"security_context": True},
                },
            )

            result = run_collector_tick(config, force=True)

        self.assertEqual(
            {event["collector"] for event in result.collected},
            {"communication_activity", "calendar_activity", "notification_activity", "security_context"},
        )
        batch = result.attention_batches[0]
        self.assertIn("Communication event(s): 1", batch["text"])
        self.assertIn("Calendar event(s): 1", batch["text"])
        self.assertIn("Notification event(s): 1", batch["text"])
        self.assertIn("Security context event(s): 1", batch["text"])
        self.assertNotIn("SECRET MESSAGE BODY", str(batch))
        self.assertNotIn("SECRET ALERT BODY", str(batch))
        self.assertNotIn("SECRET PRIVATE URL", str(batch))
        semantic_types = {event["event_type"] for event in result.semantic_events}
        self.assertIn("communication_activity", semantic_types)
        self.assertIn("calendar_activity", semantic_types)
        self.assertIn("notification_activity", semantic_types)
        self.assertIn("security_context_changed", semantic_types)
        action_types = {candidate["action_type"] for candidate in result.action_candidates}
        self.assertIn("review_message", action_types)
        self.assertIn("prepare_briefing", action_types)
        self.assertIn("review_attention", action_types)
        self.assertIn("suppress_collection", action_types)


if __name__ == "__main__":
    unittest.main()
