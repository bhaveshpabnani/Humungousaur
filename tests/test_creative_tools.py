import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools import default_tools
from humungousaur.tools.creative_tools import (
    CreativeBriefCreateTool,
    CreativeBriefInspectTool,
    CreativeRevisionPacketCreateTool,
    CreativeRevisionPacketInspectTool,
    SongStructureCreateTool,
    SongStructureInspectTool,
)


class CreativeToolTests(unittest.TestCase):
    def test_creative_brief_create_and_inspect_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = CreativeBriefCreateTool().execute(
                {
                    "filename": "scene-brief.md",
                    "title": "Rain Station Scene",
                    "creative_type": "scene",
                    "genre": "quiet speculative fiction",
                    "theme": "choosing repair over escape",
                    "audience": "adult readers",
                    "mood": "tender and tense",
                    "constraints": ["No direct imitation of named authors."],
                    "forbidden_elements": ["copyrighted characters"],
                    "beats": [{"label": "Arrival", "purpose": "Set the station", "notes": "Rain reveals old signage."}],
                    "motifs": ["warm light", "delayed train"],
                    "voice_notes": ["precise sensory detail"],
                    "source_refs": ["test fixture"],
                    "reason": "Verify native creative brief artifact.",
                },
                config,
            )
            inspected = CreativeBriefInspectTool().execute({"path": created.output["path"]}, config)

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["beat_count"], 1)
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["forbidden_element_count"], 1)
        self.assertIn("Do not copy protected works", inspected.output["preview"])

    def test_song_structure_create_and_inspect_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = SongStructureCreateTool().execute(
                {
                    "filename": "song-structure.md",
                    "title": "Window Light",
                    "genre": "indie pop",
                    "mood": "hopeful",
                    "tempo_bpm": 104,
                    "hook_concept": "A small light becoming a signal.",
                    "sections": [
                        {"name": "Verse 1", "role": "setup", "length": "8 bars", "notes": "Concrete image, no borrowed lyric."},
                        {"name": "Chorus", "role": "hook", "length": "8 bars", "notes": "Lift melody concept only."},
                    ],
                    "originality_constraints": ["No living-artist imitation."],
                    "production_notes": ["Clean drums, soft synth bass."],
                    "reason": "Verify native song structure artifact.",
                },
                config,
            )
            inspected = SongStructureInspectTool().execute({"path": created.output["path"]}, config)

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["section_count"], 2)
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["production_note_count"], 1)
        self.assertIn("Audio generation status: not_generated", inspected.output["preview"])

    def test_creative_revision_packet_create_and_inspect_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = CreativeRevisionPacketCreateTool().execute(
                {
                    "filename": "revision.md",
                    "title": "Scene Revision",
                    "source_draft": "The train arrived late, and Mira watched the station lights blink awake.",
                    "revision_goals": ["Make the image more specific."],
                    "protected_elements": ["Mira", "late train"],
                    "change_notes": ["Keep the sentence compact."],
                    "variants": [{"label": "sensory", "body": "The late train sighed in, and Mira counted each amber station light as it woke."}],
                    "reason": "Verify native creative revision packet.",
                },
                config,
            )
            inspected = CreativeRevisionPacketInspectTool().execute({"path": created.output["path"]}, config)

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["variant_count"], 1)
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["protected_element_count"], 2)

    def test_creative_tools_are_in_global_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            tools = default_tools(config)

        self.assertIn("creative_brief_create", tools)
        self.assertIn("song_structure_create", tools)
        self.assertIn("creative_revision_packet_create", tools)
        self.assertEqual(tools["creative_brief_create"].capability_group, "creative")


if __name__ == "__main__":
    unittest.main()
