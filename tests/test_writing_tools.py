import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools import default_tools
from humungousaur.tools.writing import (
    MeetingFollowupPacketCreateTool,
    WritingDraftCreateTool,
    WritingDraftInspectTool,
)


class WritingToolTests(unittest.TestCase):
    def test_writing_draft_create_and_inspect_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = WritingDraftCreateTool().execute(
                {
                    "filename": "status-update.md",
                    "draft_type": "status_update",
                    "title": "Weekly Project Update",
                    "audience": "Engineering team",
                    "tone": "clear and concise",
                    "body": "Done: native skill smoke coverage improved.\nNext: continue capability hardening.",
                    "variants": [{"label": "short", "body": "Skill smoke coverage improved; next is more hardening."}],
                    "must_keep_facts": ["Draft is not sent."],
                    "source_refs": ["tests/test_writing_tools.py"],
                    "approval_required": True,
                    "reason": "Smoke test writing draft creation.",
                },
                config,
            )
            inspected = WritingDraftInspectTool().execute({"path": created.output["path"]}, config)

            self.assertEqual(created.status, ActionStatus.SUCCEEDED)
            self.assertTrue(Path(created.output["path"]).exists())
            self.assertEqual(created.output["send_status"], "not_sent")
            self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
            self.assertEqual(inspected.output["draft_type"], "status_update")
            self.assertEqual(inspected.output["variant_count"], 1)
            self.assertIn("Weekly Project Update", inspected.output["preview"])

    def test_meeting_followup_packet_create_records_unsent_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = MeetingFollowupPacketCreateTool().execute(
                {
                    "filename": "planning-followup.md",
                    "meeting_title": "Planning Sync",
                    "summary": "The team agreed to verify skill coverage and continue native tool work.",
                    "action_items": [{"task": "Run skill smoke", "owner": "Humungousaur", "due": "today", "evidence": "meeting notes"}],
                    "draft_messages": [{"channel_id": "slack", "conversation_id": "D123", "text": "I will post the verified smoke results after approval."}],
                    "reminders": [{"title": "Review smoke results", "scheduled_for": "2026-06-08T09:00:00Z", "reason": "Follow-up"}],
                    "open_questions": ["Which skill cluster is next?"],
                    "source_refs": ["Planning Sync notes"],
                    "reason": "Smoke test meeting follow-up packet.",
                },
                config,
            )

            self.assertEqual(created.status, ActionStatus.SUCCEEDED)
            self.assertTrue(Path(created.output["path"]).exists())
            self.assertEqual(created.output["send_status"], "not_sent")
            self.assertEqual(created.output["action_item_count"], 1)
            self.assertEqual(created.output["draft_message_count"], 1)
            self.assertIn("Status: not_sent", Path(created.output["path"]).read_text(encoding="utf-8"))

    def test_writing_tools_are_in_global_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            tools = default_tools(config)

        self.assertIn("writing_draft_create", tools)
        self.assertIn("writing_draft_inspect", tools)
        self.assertIn("meeting_followup_packet_create", tools)
        self.assertEqual(tools["writing_draft_create"].capability_group, "writing")


if __name__ == "__main__":
    unittest.main()
