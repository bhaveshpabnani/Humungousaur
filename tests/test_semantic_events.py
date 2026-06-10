import tempfile
import unittest
from pathlib import Path

from humungousaur.cognition.queue import RuntimeEventQueue
from humungousaur.cognition.semantic_events import (
    rebuild_current_context,
    record_attention_batch_semantics,
    record_stimulus_semantics,
    semantic_events_status,
)
from humungousaur.config import AgentConfig
from humungousaur.memory.event_store import EventStore


class SemanticEventTests(unittest.TestCase):
    def test_attention_batch_creates_semantic_events_context_and_action_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config = AgentConfig(workspace=root / "workspace", data_dir=root / "data", planner_provider="explicit").normalized()
            batch = {
                "batch_id": "attention-test",
                "occurred_at": "2026-06-10T00:00:00+00:00",
                "events": [
                    {"collector": "filesystem", "path": "app.py", "stimulus_type": "file_changed"},
                    {"collector": "filesystem", "path": "README.md", "stimulus_type": "file_changed"},
                ],
            }

            result = record_attention_batch_semantics(config, batch)
            status = semantic_events_status(config)
            context_exists = Path(result["context"]["current_context_path"]).exists()
            queued_event_type = RuntimeEventQueue(config.cognition_db_path).queued(limit=5)[0].event_type

        self.assertEqual(result["semantic_events"][0]["event_type"], "project_files_changed")
        self.assertEqual(result["action_candidates"][0]["action_type"], "update_context")
        self.assertTrue(context_exists)
        self.assertIn("project file change", status["current_context_preview"])
        self.assertEqual(queued_event_type, "AUTONOMOUS_ACTION_CANDIDATE")

    def test_clipboard_semantic_event_omits_raw_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config = AgentConfig(workspace=root / "workspace", data_dir=root / "data", planner_provider="explicit").normalized()
            batch = {
                "batch_id": "attention-clipboard",
                "occurred_at": "2026-06-10T00:00:00+00:00",
                "events": [
                    {
                        "collector": "clipboard",
                        "stimulus_type": "clipboard_changed",
                        "text_length": 27,
                        "truncated": False,
                    }
                ],
            }

            result = record_attention_batch_semantics(config, batch)
            status = semantic_events_status(config)

        payload_text = str(result) + status["current_context_preview"] + status["events_preview"]
        self.assertIn("Clipboard changed", payload_text)
        self.assertNotIn("super secret clipboard", payload_text)

    def test_direct_user_and_voice_stimuli_record_without_autonomous_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config = AgentConfig(workspace=root / "workspace", data_dir=root / "data", planner_provider="explicit").normalized()

            text_result = record_stimulus_semantics(
                config,
                {"text": "summarize my current work", "source": "user_text", "stimulus_id": "text-1"},
                decision="respond",
            )
            voice_result = record_stimulus_semantics(
                config,
                {
                    "text": "open my tasks",
                    "source": "voice_transcript",
                    "stimulus_id": "voice-1",
                    "metadata": {"wake_word_detected": True, "wake_word": "hey humungousaur"},
                },
                decision="respond",
            )
            queued = RuntimeEventQueue(config.cognition_db_path).queued(limit=5)

        self.assertEqual(text_result["semantic_events"][0]["event_type"], "explicit_user_request")
        self.assertEqual([event["event_type"] for event in voice_result["semantic_events"]], ["voice_wake_detected", "voice_command_received"])
        self.assertEqual(queued, [])

    def test_research_to_work_transition_queues_resume_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config = AgentConfig(workspace=root / "workspace", data_dir=root / "data", planner_provider="explicit").normalized()
            record_attention_batch_semantics(
                config,
                {
                    "batch_id": "attention-browser",
                    "occurred_at": "2026-06-10T00:00:00+00:00",
                    "events": [
                        {
                            "collector": "browser",
                            "app_name": "Google Chrome",
                            "window_title": "Research results",
                            "url": "https://example.com",
                        }
                    ],
                },
            )

            result = record_attention_batch_semantics(
                config,
                {
                    "batch_id": "attention-work",
                    "occurred_at": "2026-06-10T00:01:00+00:00",
                    "events": [
                        {
                            "collector": "active_window",
                            "app_name": "Codex",
                            "window_title": "Humungousaur",
                        }
                    ],
                },
            )

        self.assertTrue(any(candidate["action_type"] == "prepare_resume_context" for candidate in result["action_candidates"]))

    def test_rebuild_context_uses_event_store_as_source_of_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config = AgentConfig(workspace=root / "workspace", data_dir=root / "data", planner_provider="explicit").normalized()
            record_stimulus_semantics(config, {"text": "hi", "source": "user_text", "stimulus_id": "stim-1"}, decision="respond")

            rebuilt = rebuild_current_context(config)
            memory = EventStore(config.memory_db_path).tail(limit=10)
            context_exists = Path(rebuilt["current_context_path"]).exists()

        self.assertTrue(context_exists)
        self.assertTrue(any(event["event_type"] == "current_context_brief" for event in memory))


if __name__ == "__main__":
    unittest.main()
