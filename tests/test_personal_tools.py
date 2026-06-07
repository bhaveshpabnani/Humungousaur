import json
import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.personal_tools import ContactNoteCreateTool, ContactNoteInspectTool, DailyPlanCreateTool, DailyPlanInspectTool


class PersonalToolTests(unittest.TestCase):
    def test_contact_note_create_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = ContactNoteCreateTool().execute(
                {
                    "filename": "ada.md",
                    "person_name": "Ada Lovelace",
                    "role": "Collaborator",
                    "organization": "Example Labs",
                    "preferred_channel": "email",
                    "facts": [{"fact": "Prefers concise technical summaries.", "evidence": "User-provided note", "confidence": "high"}],
                    "preferences": [{"preference": "Likes agendas before calls.", "evidence": "Meeting note"}],
                    "followups": [{"title": "Send agenda", "due": "tomorrow", "reason": "Upcoming call", "evidence": "User request"}],
                    "sensitivity": "medium",
                    "source_refs": ["fixture"],
                    "reason": "Verify native contact note artifact.",
                },
                config,
            )
            inspected = ContactNoteInspectTool().execute({"path": created.output["path"]}, config)
            metadata = json.loads(Path(created.output["metadata_path"]).read_text(encoding="utf-8"))

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["fact_count"], 1)
        self.assertEqual(created.output["followup_count"], 1)
        self.assertEqual(created.output["memory_status"], "prepared_not_memorized")
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["sensitivity"], "medium")
        self.assertIn("durable memory requires", metadata["memory_boundary"])

    def test_daily_plan_create_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = DailyPlanCreateTool().execute(
                {
                    "filename": "today.md",
                    "title": "Today Plan",
                    "date": "2026-06-07",
                    "time_window": "afternoon",
                    "energy": "medium",
                    "evidence_refs": ["cognitive_state fixture"],
                    "must_do": [{"title": "Run tests", "priority": "high", "evidence": "active goal", "reason": "Verify changes"}],
                    "time_blocks": [{"time": "14:00", "focus": "Focused implementation", "notes": "Avoid multitasking"}],
                    "reminder_drafts": [{"title": "Review next slice", "when": "tomorrow", "reason": "Continue skill hardening"}],
                    "summary": "One focused implementation block with a review reminder draft.",
                    "reason": "Verify native daily plan artifact.",
                },
                config,
            )
            inspected = DailyPlanInspectTool().execute({"path": created.output["path"]}, config)

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["must_do_count"], 1)
        self.assertEqual(created.output["reminder_draft_count"], 1)
        self.assertEqual(created.output["plan_status"], "prepared_not_scheduled")
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["time_block_count"], 1)

    def test_contact_note_requires_person_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = ContactNoteCreateTool().execute({"reason": "Verify validation."}, config)

        self.assertEqual(result.status, ActionStatus.FAILED)
        self.assertIn("Person name", result.summary)


if __name__ == "__main__":
    unittest.main()
