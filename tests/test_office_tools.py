import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools import default_tools
from humungousaur.tools.office import (
    DocxDocumentCreateTool,
    DocxDocumentInspectTool,
    PptxDeckCreateTool,
    PptxDeckInspectTool,
)


class OfficeToolTests(unittest.TestCase):
    def test_docx_document_create_and_inspect_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = DocxDocumentCreateTool().execute(
                {
                    "filename": "office-smoke.docx",
                    "title": "Humungousaur Office Smoke",
                    "reason": "Smoke test DOCX artifact creation.",
                    "sections": [
                        {
                            "heading": "Summary",
                            "paragraphs": ["This document was created by a native Humungousaur DOCX tool."],
                            "bullets": ["No upstream script import", "Local artifact only"],
                            "tables": [{"rows": [["Capability", "Status"], ["DOCX", "Created"]]}],
                        }
                    ],
                },
                config,
            )
            inspected = DocxDocumentInspectTool().execute({"path": created.output["path"], "sample_paragraphs": 10}, config)

            self.assertEqual(created.status, ActionStatus.SUCCEEDED)
            self.assertTrue(Path(created.output["path"]).exists())
            self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
            self.assertGreaterEqual(inspected.output["paragraph_count"], 4)
            self.assertEqual(inspected.output["table_count"], 1)
            self.assertIn("Humungousaur Office Smoke", inspected.output["text_preview"])

    def test_pptx_deck_create_and_inspect_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = PptxDeckCreateTool().execute(
                {
                    "filename": "office-smoke.pptx",
                    "title": "Humungousaur Deck Smoke",
                    "reason": "Smoke test PPTX artifact creation.",
                    "slides": [
                        {"title": "Capability", "bullets": ["Native PPTX tool", "Inspectable slide text"]},
                        {"title": "Verification", "bullets": ["Artifact exists", "Slide count matches"]},
                    ],
                },
                config,
            )
            inspected = PptxDeckInspectTool().execute({"path": created.output["path"], "sample_slides": 5}, config)

            self.assertEqual(created.status, ActionStatus.SUCCEEDED)
            self.assertTrue(Path(created.output["path"]).exists())
            self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
            self.assertEqual(inspected.output["slide_count"], 3)
            self.assertEqual(inspected.output["slides"][0]["title"], "Humungousaur Deck Smoke")
            self.assertIn("Capability", [slide["title"] for slide in inspected.output["slides"]])

    def test_office_tools_are_in_global_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            tools = default_tools(config)

        self.assertIn("docx_document_create", tools)
        self.assertIn("docx_document_inspect", tools)
        self.assertIn("pptx_deck_create", tools)
        self.assertIn("pptx_deck_inspect", tools)
        self.assertEqual(tools["docx_document_create"].capability_group, "office")


if __name__ == "__main__":
    unittest.main()
