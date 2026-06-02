import json
import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.integrations.voice_wakeup import handle_activation, transcript_from_activation, run_activation


class VoiceIntegrationTests(unittest.TestCase):
    def test_transcript_from_activation_reads_inline_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            activation = Path(tmp_dir) / "activation.json"
            activation.write_text(json.dumps({"transcript": "summarize this project"}), encoding="utf-8")

            self.assertEqual(transcript_from_activation(activation), "summarize this project")

    def test_run_activation_routes_transcript_to_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Voice Demo\n\nA local assistant runtime.", encoding="utf-8")
            activation = workspace / "activation.json"
            activation.write_text(json.dumps({"transcript": 'read_file {"path":"README.md"}'}), encoding="utf-8")

            result = run_activation(
                activation,
                AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit"),
            )

            self.assertIn("README.md", result.final_response)

    def test_handle_activation_uses_interaction_harness_and_voice_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Voice Harness Demo\n\nA local assistant runtime.", encoding="utf-8")
            activation = workspace / "activation.json"
            activation.write_text(json.dumps({"transcript": 'read_file {"path":"README.md"}'}), encoding="utf-8")

            result = handle_activation(
                activation,
                AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit"),
                response_mode="voice_prepare",
            )

            self.assertEqual(result.decision.response_mode, "voice_prepare")
            self.assertIsNotNone(result.run)
            self.assertIsNotNone(result.voice_result)
            self.assertIn("README.md", result.run.final_response)


if __name__ == "__main__":
    unittest.main()
