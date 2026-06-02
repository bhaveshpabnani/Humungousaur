import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.interaction import InteractionHarness, Stimulus, decide_interaction, normalize_stimulus
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
                {"source": "activity", "text": 'read_file {"path":"README.md"}', "metadata": {"intent": "task"}},
                response_mode="silent",
            )

        self.assertEqual(result.decision.decision, "analyze")
        self.assertEqual(result.decision.response_mode, "silent")
        self.assertIsNotNone(result.run)

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
