import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from humungousaur.config import AgentConfig
from humungousaur.interaction import InteractionHarness, Stimulus, decide_interaction, normalize_stimulus
from humungousaur.planning.model_clients import StaticModelClient
from humungousaur.schemas import ActionStatus
from humungousaur.tools.voice_tools import VoiceResponsePrepareTool, VoiceSpeakTool, VoiceResponsesTool, list_voice_responses


class InteractionHarnessTests(unittest.TestCase):
    def test_direct_user_stimulus_runs_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Harness Demo\n\nA local assistant runtime.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

            result = InteractionHarness(config).handle('read_file {"path":"README.md"}')

        self.assertEqual(result.decision.decision, "respond")
        self.assertIsNotNone(result.run)
        self.assertIn("README.md", result.run.final_response)

    def test_passive_activity_without_task_is_recorded_but_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts", planner_provider="explicit").normalized()

            result = InteractionHarness(config).handle({"source": "activity", "text": "User browsed project notes."})

        self.assertEqual(result.decision.decision, "observe")
        self.assertFalse(result.decision.should_run_agent)
        self.assertIsNone(result.run)
        self.assertIsNotNone(result.recorded_event_id)

    def test_passive_activity_with_structured_action_metadata_runs_agent_silently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Passive Demo\n\nA local assistant runtime.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

            result = InteractionHarness(config).handle(
                {"source": "activity", "text": 'read_file {"path":"README.md"}', "metadata": {"requires_response": True}},
                response_mode="silent",
            )

        self.assertEqual(result.decision.decision, "analyze")
        self.assertEqual(result.decision.response_mode, "silent")
        self.assertIsNotNone(result.run)

    def test_harness_uses_model_led_cognitive_decision_for_passive_stimulus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Model Harness\n\nA local assistant runtime.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="model").normalized()
            cognitive_response = json.dumps(
                {
                    "action": "analyze",
                    "request": 'read_file {"path":"README.md"}',
                    "response_mode": "silent",
                    "reason": "Model judged the passive event relevant to active work.",
                    "should_run_agent": True,
                    "should_record_event": True,
                    "memory_action": "remember",
                    "focus_goal_id": "",
                    "create_goal_title": "Inspect passive activity",
                    "create_task_title": "Read referenced README",
                    "stay_warm": False,
                    "next_wakeup_seconds": None,
                }
            )
            planner_response = json.dumps(
                {
                    "steps": [
                        {
                            "tool_name": "read_file",
                            "tool_input": {"path": "README.md"},
                            "reason": "Read the referenced file.",
                        }
                    ]
                }
            )

            with (
                patch("humungousaur.cognition.recorder.build_model_client", return_value=StaticModelClient(cognitive_response)),
                patch("humungousaur.orchestrator.build_model_client", return_value=StaticModelClient(planner_response)),
            ):
                result = InteractionHarness(config).handle({"source": "activity", "text": "User paused on README."})

        self.assertEqual(result.decision.decision, "analyze")
        self.assertEqual(result.decision.reason, "Model judged the passive event relevant to active work.")
        self.assertTrue(result.decision.should_run_agent)
        self.assertIsNotNone(result.run)
        self.assertIn("README.md", result.run.final_response)

    def test_voice_stimulus_prepares_spoken_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Voice Harness\n\nA local assistant runtime.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

            result = InteractionHarness(config).handle(
                Stimulus(text='read_file {"path":"README.md"}', source="voice_transcript"),
                response_mode="voice_prepare",
            )
            listed = list_voice_responses(config)

            self.assertEqual(result.decision.response_mode, "voice_prepare")
            self.assertIsNotNone(result.voice_result)
            self.assertIn("response_id", result.voice_result)
            self.assertEqual(len(listed), 1)

    def test_decision_helpers_normalize_and_ignore_empty_input(self) -> None:
        stimulus = normalize_stimulus({"source": "unknown", "text": ""})
        decision = decide_interaction(stimulus)

        self.assertEqual(stimulus.source, "activity")
        self.assertEqual(decision.decision, "ignore")
        self.assertFalse(decision.should_record_activity)


class VoiceToolTests(unittest.TestCase):
    def test_voice_response_prepare_writes_local_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = VoiceResponsePrepareTool().execute({"text": "Hello there", "reason": "test"}, config)
            listed = VoiceResponsesTool().execute({"limit": 5}, config)

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertTrue(Path(result.output["path"]).exists())
            self.assertEqual(len(listed.output["responses"]), 1)

    def test_voice_speak_dry_run_does_not_play_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            result = VoiceSpeakTool().execute({"text": "Hello", "reason": "test"}, config)

        self.assertEqual(result.status, ActionStatus.SKIPPED)
        self.assertTrue(result.output["speech_not_played"])


if __name__ == "__main__":
    unittest.main()
