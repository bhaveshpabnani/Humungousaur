import json
import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.content_tools import TranscriptSummaryCreateTool, TranscriptSummaryInspectTool


class ContentToolTests(unittest.TestCase):
    def test_transcript_summary_create_and_inspect_inline_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            created = TranscriptSummaryCreateTool().execute(
                {
                    "filename": "demo-summary.md",
                    "title": "Demo Video",
                    "source_type": "youtube",
                    "source_url": "https://example.com/watch?v=demo",
                    "transcript": "[00:01] Welcome to the demo.\n00:42 The team decides to ship the transcript tool.",
                    "transcript_provider": "provided",
                    "summary": "The demo introduces the native transcript summary tool and captures the shipping decision.",
                    "key_points": ["Native transcript artifacts preserve provenance."],
                    "decisions": ["Ship transcript summary create and inspect tools."],
                    "action_items": [{"task": "Add skill smoke coverage", "owner": "Humungousaur", "due": "today", "evidence": "00:42"}],
                    "open_questions": ["Which content skill should be hardened next?"],
                    "limitations": ["Transcript is a short fixture."],
                    "reason": "Verify native transcript summary artifact creation.",
                },
                config,
            )
            inspected = TranscriptSummaryInspectTool().execute({"path": created.output.get("path", "")}, config)
            metadata = json.loads(Path(created.output["metadata_path"]).read_text(encoding="utf-8"))

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["segment_count"], 2)
        self.assertEqual(created.output["action_item_count"], 1)
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["source_type"], "youtube")
        self.assertEqual(inspected.output["segment_count"], 2)
        self.assertIn("shipping decision", inspected.output["preview"])
        self.assertEqual(metadata["timestamp_segments"][1]["timestamp"], "00:42")

    def test_transcript_summary_create_reads_allowed_transcript_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            transcript = workspace / "meeting.txt"
            transcript.write_text("00:00 Kickoff\n00:10 Decision: use native content tools.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            created = TranscriptSummaryCreateTool().execute(
                {
                    "title": "Meeting Transcript",
                    "source_type": "meeting",
                    "transcript_path": "meeting.txt",
                    "summary": "The meeting records a decision to use native content tools.",
                    "reason": "Verify transcript file input.",
                },
                config,
            )

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["transcript_source"], str(transcript.resolve()))

    def test_transcript_summary_blocks_outside_transcript_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            workspace.mkdir()
            outside = Path(tmp_dir) / "outside.txt"
            outside.write_text("secret transcript", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = TranscriptSummaryCreateTool().execute(
                {
                    "title": "Blocked Transcript",
                    "transcript_path": str(outside),
                    "summary": "Should not be created.",
                    "reason": "Verify allowed roots.",
                },
                config,
            )

        self.assertEqual(result.status, ActionStatus.FAILED)
        self.assertIn("outside allowed roots", result.summary)


if __name__ == "__main__":
    unittest.main()
