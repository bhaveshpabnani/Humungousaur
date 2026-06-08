from __future__ import annotations

import unittest

from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema
from scripts.smoke_skills import _build_live_boundary_coverage, _build_live_smoke_plan, _build_skill_task_coverage


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

    def test_live_boundary_coverage_tracks_boundary_evidence_separately(self) -> None:
        tools = {
            "safe_tool": DummyTool("safe_tool"),
            "approval_tool": DummyTool("approval_tool", requires_approval=True, risk_level=RiskLevel.HIGH),
            "dry_run_tool": DummyTool("dry_run_tool", risk_level=RiskLevel.MEDIUM),
        }
        skills = [
            {
                "skill_id": "workspace:skills/safe/SKILL.md",
                "name": "safe",
                "native_tools": ["safe_tool"],
                "skill_refs": [],
                "missing": [],
            },
            {
                "skill_id": "workspace:skills/live/SKILL.md",
                "name": "live",
                "native_tools": ["approval_tool", "dry_run_tool"],
                "skill_refs": [],
                "missing": [],
            },
        ]
        sections = [
            {
                "section": "approval",
                "name": "approval_tool",
                "ok": True,
                "payload": {"tool_name": "approval_tool", "status": "succeeded", "summary": "Prepared approved packet."},
            },
            {
                "section": "approval",
                "name": "dry_run_tool",
                "ok": True,
                "payload": {"tool_name": "dry_run_tool", "status": "skipped", "summary": "Dry-run boundary."},
            },
        ]

        coverage = _build_live_boundary_coverage(skills, sections, tools)

        rows = {row["name"]: row for row in coverage["skills"]}
        self.assertEqual(rows["safe"]["live_boundary_state"], "no_boundary_tools")
        self.assertEqual(rows["live"]["live_boundary_state"], "boundary_evidence_present_live_not_proven")
        self.assertEqual(rows["live"]["missing_boundary_tools"], [])
        self.assertEqual(rows["live"]["dry_run_or_skipped_boundary_tools"], ["dry_run_tool"])
        self.assertEqual(coverage["summary"]["skills_with_boundary_tools_count"], 1)
        self.assertEqual(coverage["summary"]["skills_with_missing_boundary_evidence_count"], 0)
        self.assertEqual(coverage["summary"]["boundary_tools_seen_in_evidence_count"], 2)

        plan = _build_live_smoke_plan(coverage)
        self.assertEqual(plan["summary"]["planned_skill_count"], 1)
        self.assertEqual(plan["summary"]["planned_tool_count"], 2)
        self.assertIn("other_boundaries", plan["summary"]["highest_priority_domains"])
        self.assertEqual(plan["domains"][0]["dry_run_or_skipped_tools"], ["dry_run_tool"])
        self.assertTrue(plan["domains"][0]["next_smoke_steps"])


if __name__ == "__main__":
    unittest.main()
