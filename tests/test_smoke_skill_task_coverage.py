from __future__ import annotations

import unittest

from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema
from scripts.smoke_skills import _build_skill_task_coverage


class DummyTool(Tool):
    def __init__(self, name: str, *, requires_approval: bool = False, risk_level: RiskLevel = RiskLevel.LOW) -> None:
        super().__init__(
            name=name,
            description=f"Dummy {name}.",
            risk_level=risk_level,
            requires_approval=requires_approval,
            input_schema=object_input_schema(),
            capability_group="test",
        )

    def execute(self, tool_input, config):
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, "ok")


class SmokeSkillTaskCoverageTests(unittest.TestCase):
    def test_coverage_marks_direct_script_composition_and_pending_skills(self) -> None:
        tools = {
            "gmail_draft_prepare": DummyTool("gmail_draft_prepare", requires_approval=True, risk_level=RiskLevel.MEDIUM),
            "channel_message_prepare": DummyTool("channel_message_prepare"),
            "missing_task_tool": DummyTool("missing_task_tool"),
        }
        skills = [
            {
                "skill_id": "workspace:skills/email-operations/SKILL.md",
                "name": "email-operations",
                "description": "Draft email.",
                "relative_path": "skills/email-operations/SKILL.md",
                "script_count": 0,
                "tool_map": ["gmail_draft_prepare"],
                "native_tools": ["gmail_draft_prepare"],
                "skill_refs": [],
                "missing": [],
            },
            {
                "skill_id": "workspace:skills/wrapper/SKILL.md",
                "name": "wrapper",
                "description": "Compose email operations.",
                "relative_path": "skills/wrapper/SKILL.md",
                "script_count": 0,
                "tool_map": ["email-operations"],
                "native_tools": [],
                "skill_refs": ["email-operations"],
                "missing": [],
            },
            {
                "skill_id": "workspace:skills/scripted/SKILL.md",
                "name": "scripted",
                "description": "Run script.",
                "relative_path": "skills/scripted/SKILL.md",
                "script_count": 1,
                "tool_map": ["missing_task_tool"],
                "native_tools": ["missing_task_tool"],
                "skill_refs": [],
                "missing": [],
            },
            {
                "skill_id": "workspace:skills/pending/SKILL.md",
                "name": "pending",
                "description": "Needs smoke.",
                "relative_path": "skills/pending/SKILL.md",
                "script_count": 0,
                "tool_map": ["missing_task_tool"],
                "native_tools": ["missing_task_tool"],
                "skill_refs": [],
                "missing": [],
            },
        ]
        sections = [
            {
                "section": "productivity",
                "name": "gmail_draft_prepare",
                "ok": True,
                "payload": {"tool_name": "gmail_draft_prepare", "status": "succeeded", "summary": "Draft prepared."},
            },
            {
                "section": "skills",
                "name": "script_run:scripted-helper",
                "ok": True,
                "payload": {
                    "script_id": "workspace:skills/scripted/scripts/helper.py",
                    "skill_id": "workspace:skills/scripted/SKILL.md",
                    "status": "succeeded",
                    "summary": "Script ran.",
                },
            },
        ]

        coverage = _build_skill_task_coverage(
            skills,
            sections,
            tools,
            {"workspace:skills/scripted/scripts/helper.py": "workspace:skills/scripted/SKILL.md"},
        )

        rows = {row["name"]: row for row in coverage["skills"]}
        self.assertEqual(rows["email-operations"]["task_evidence_status"], "task_smoked")
        self.assertEqual(rows["wrapper"]["task_evidence_status"], "composition_smoked")
        self.assertEqual(rows["scripted"]["task_evidence_status"], "task_smoked")
        self.assertEqual(rows["pending"]["task_evidence_status"], "native_tool_pending_task_smoke")
        self.assertIn("gmail_draft_prepare", rows["email-operations"]["approval_or_external_boundary_tools"])
        self.assertEqual(coverage["summary"]["task_smoked_count"], 2)
        self.assertEqual(coverage["summary"]["composition_smoked_count"], 1)
        self.assertEqual(coverage["summary"]["pending_task_smoke_count"], 1)


if __name__ == "__main__":
    unittest.main()
