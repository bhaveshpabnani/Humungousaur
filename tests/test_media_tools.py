import json
import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.media_tools import (
    MediaStoryboardCreateTool,
    MediaStoryboardInspectTool,
    SoundSpecCreateTool,
    SoundSpecInspectTool,
)


class MediaToolTests(unittest.TestCase):
    def test_sound_spec_create_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = SoundSpecCreateTool().execute(
                {
                    "filename": "launch-jingle.md",
                    "title": "Launch Jingle",
                    "sound_type": "song",
                    "intended_use": "Internal launch celebration",
                    "duration_seconds": 30,
                    "genre": "bright synth pop",
                    "mood": "optimistic",
                    "tempo_bpm": 118,
                    "instrumentation": ["soft drums", "pluck synth", "warm bass"],
                    "lyrics": "We shipped the thing, we kept it clean.",
                    "sections": [{"name": "Hook", "start": "00:00", "duration": "10s", "notes": "Start immediately with the motif."}],
                    "licensing_constraints": ["No living-artist imitation."],
                    "reason": "Verify native sound spec creation.",
                },
                config,
            )
            inspected = SoundSpecInspectTool().execute({"path": created.output["path"]}, config)
            metadata = json.loads(Path(created.output["metadata_path"]).read_text(encoding="utf-8"))

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["sound_type"], "song")
        self.assertEqual(created.output["section_count"], 1)
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["licensing_constraint_count"], 1)
        self.assertEqual(metadata["status"], "prepared_not_generated")

    def test_media_storyboard_create_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = MediaStoryboardCreateTool().execute(
                {
                    "filename": "slack-confetti.md",
                    "title": "Slack Confetti Reaction",
                    "media_type": "gif",
                    "audience": "Product team",
                    "intended_use": "Slack celebration draft",
                    "duration_seconds": 2.5,
                    "width": 480,
                    "height": 270,
                    "style": "clean geometric",
                    "palette": ["#1d3557", "#f1faee", "#e63946"],
                    "scenes": [
                        {"label": "Start", "description": "A calm checkmark appears.", "duration_seconds": 0.8, "motion": "fade in"},
                        {"label": "Burst", "description": "Confetti arcs outward.", "duration_seconds": 1.7, "motion": "radial burst", "text": "Done"},
                    ],
                    "accessibility_notes": ["Avoid flashing."],
                    "licensing_constraints": ["No copyrighted characters."],
                    "reason": "Verify native storyboard creation.",
                },
                config,
            )
            inspected = MediaStoryboardInspectTool().execute({"path": created.output["path"]}, config)
            svg_exists = Path(created.output["svg_path"]).exists()

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertTrue(svg_exists)
        self.assertEqual(created.output["scene_count"], 2)
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["media_type"], "gif")
        self.assertIn("Slack Confetti Reaction", inspected.output["preview"])

    def test_media_storyboard_requires_scene_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = MediaStoryboardCreateTool().execute(
                {"title": "Bad Storyboard", "media_type": "video", "scenes": [{"label": "Empty"}], "reason": "Verify validation."},
                config,
            )

        self.assertEqual(result.status, ActionStatus.FAILED)
        self.assertIn("requires a description", result.summary)


if __name__ == "__main__":
    unittest.main()
