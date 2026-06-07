import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.orchestrator import AgentOrchestrator
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools import default_tools
from humungousaur.tools.productivity import (
    EmailDraftPrepareTool,
    GmailDraftPrepareTool,
    XlsxWorkbookCreateTool,
    XlsxWorkbookInspectTool,
)


class ProductivityToolTests(unittest.TestCase):
    def test_gmail_draft_prepare_writes_approval_ready_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = GmailDraftPrepareTool().execute(
                {
                    "to": ["person@example.com"],
                    "subject": "Follow-up from Humungousaur",
                    "body": "Hi there,\n\nHere is the requested follow-up.\n\nBest,\nHumungousaur",
                    "tone": "warm and concise",
                    "reason": "Smoke test Gmail drafting.",
                },
                config,
            )

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertEqual(result.tool_name, "gmail_draft_prepare")
            self.assertEqual(result.output["draft"]["send_status"], "not_sent")
            self.assertTrue(result.output["draft"]["approval_required_for_send"])
            self.assertTrue(Path(result.output["path"]).exists())
            self.assertTrue(Path(result.output["body_path"]).exists())
            self.assertIn("gog", result.output["draft"]["gmail_command_preview"])

    def test_email_draft_prepare_rejects_invalid_recipient(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = EmailDraftPrepareTool().execute(
                {"to": ["missing-at-symbol"], "subject": "Bad", "body": "Nope", "reason": "validation smoke"},
                config,
            )

            self.assertEqual(result.status, ActionStatus.FAILED)
            self.assertIn("missing-at-symbol", result.output["invalid_addresses"])

    def test_xlsx_workbook_create_and_inspect_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = XlsxWorkbookCreateTool().execute(
                {
                    "filename": "skill-smoke.xlsx",
                    "reason": "Smoke test workbook operations.",
                    "sheets": [
                        {
                            "name": "Summary",
                            "rows": [["Metric", "Value"], ["Revenue", 1200], ["Cost", 700], ["Profit", None]],
                            "formulas": [{"cell": "B4", "formula": "=B2-B3"}],
                            "freeze_panes": "A2",
                            "widths": {"A": 18, "B": 12},
                        }
                    ],
                },
                config,
            )
            inspected = XlsxWorkbookInspectTool().execute({"path": created.output["path"], "sample_rows": 5}, config)

            self.assertEqual(created.status, ActionStatus.SUCCEEDED)
            self.assertTrue(Path(created.output["path"]).exists())
            self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
            self.assertEqual(inspected.output["sheets"][0]["name"], "Summary")
            self.assertEqual(inspected.output["sheets"][0]["max_row"], 4)
            self.assertIn({"cell": "B4", "formula": "=B2-B3"}, inspected.output["sheets"][0]["formulas"])

    def test_xlsx_create_accepts_formula_cell_objects_and_inspects_by_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = XlsxWorkbookCreateTool().execute(
                {
                    "filename": "formula-object.xlsx",
                    "reason": "Formula object smoke.",
                    "sheets": [
                        {
                            "name": "Summary",
                            "rows": [["Metric", "Value"], ["Revenue", 100], ["Cost", 40], ["Profit", {"formula": "=B2-B3"}]],
                        }
                    ],
                },
                config,
            )
            inspected = XlsxWorkbookInspectTool().execute({"path": "formula-object.xlsx", "sample_rows": 5}, config)

            self.assertEqual(created.status, ActionStatus.SUCCEEDED)
            self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
            self.assertIn({"cell": "B4", "formula": "=B2-B3"}, inspected.output["sheets"][0]["formulas"])

    def test_productivity_tools_are_in_global_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            tools = default_tools(config)

            self.assertIn("gmail_draft_prepare", tools)
            self.assertIn("email_draft_prepare", tools)
            self.assertIn("xlsx_workbook_create", tools)
            self.assertIn("xlsx_workbook_inspect", tools)
            self.assertEqual(tools["gmail_draft_prepare"].capability_group, "productivity")

    def test_productivity_final_response_preserves_exact_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts", planner_provider="explicit").normalized()
            path = str(config.data_dir / "email_drafts" / "gmail-draft.json")
            body_path = str(config.data_dir / "email_drafts" / "gmail-draft.txt")
            result = ToolResult(
                "gmail_draft_prepare",
                ActionStatus.SUCCEEDED,
                RiskLevel.MEDIUM,
                "Prepared gmail draft artifact.",
                {
                    "draft": {"to": ["person@example.com"], "subject": "Exact Path", "send_status": "not_sent"},
                    "path": path,
                    "body_path": body_path,
                },
            )

            response = AgentOrchestrator(config)._compose_response("prepare gmail draft", [result])

            self.assertIn(path, response)
            self.assertIn(body_path, response)
            self.assertIn("not sent", response)


if __name__ == "__main__":
    unittest.main()
