import json
import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.research_tools import (
    CitationBibliographyCreateTool,
    CitationBibliographyInspectTool,
    LiteratureSetCreateTool,
    LiteratureSetInspectTool,
)


class ResearchToolTests(unittest.TestCase):
    def test_citation_bibliography_create_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = CitationBibliographyCreateTool().execute(
                {
                    "filename": "refs.md",
                    "title": "Research References",
                    "target_style": "mixed",
                    "entries": [
                        {
                            "type": "article",
                            "title": "Attention Is All You Need",
                            "authors": ["Vaswani, Ashish", "Shazeer, Noam"],
                            "year": "2017",
                            "venue": "NeurIPS",
                            "url": "https://example.com/attention",
                            "source_refs": ["provided metadata"],
                            "verified_fields": ["title", "authors", "year"],
                            "uncertain_fields": ["url"],
                        }
                    ],
                    "reason": "Verify native bibliography artifact creation.",
                },
                config,
            )
            inspected = CitationBibliographyInspectTool().execute({"path": created.output["path"]}, config)
            metadata = json.loads(Path(created.output["metadata_path"]).read_text(encoding="utf-8"))
            bibtex_exists = Path(created.output["bibtex_path"]).exists()

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["entry_count"], 1)
        self.assertEqual(created.output["uncertain_entry_count"], 1)
        self.assertTrue(bibtex_exists)
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertIn("Attention Is All You Need", inspected.output["preview"])
        self.assertIn("@article", metadata["entries"][0]["bibtex"])

    def test_literature_set_create_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = LiteratureSetCreateTool().execute(
                {
                    "filename": "lit.md",
                    "title": "Agent Tool Use Literature",
                    "research_question": "How do agents verify tool-using workflows?",
                    "inclusion_criteria": ["Tool-use evidence is explicit."],
                    "papers": [
                        {
                            "paper_id": "p1",
                            "title": "Toolformer",
                            "authors": ["Schick, Timo"],
                            "year": 2023,
                            "venue": "NeurIPS",
                            "relevance": "Shows language models learning tool-use behavior.",
                            "evidence_level": "abstract",
                            "themes": ["tool use"],
                            "source_refs": ["https://example.com/toolformer"],
                        }
                    ],
                    "themes": [{"name": "Tool use", "summary": "Models coordinate external calls.", "paper_ids": ["p1"]}],
                    "gaps": ["Need more local verification work."],
                    "limitations": ["Synthetic smoke metadata."],
                    "reason": "Verify native literature set artifact creation.",
                },
                config,
            )
            inspected = LiteratureSetInspectTool().execute({"path": created.output["path"]}, config)

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["paper_count"], 1)
        self.assertEqual(created.output["theme_count"], 1)
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["gap_count"], 1)
        self.assertIn("Toolformer", inspected.output["preview"])

    def test_bibliography_create_requires_title_per_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = CitationBibliographyCreateTool().execute(
                {"title": "Bad refs", "entries": [{"authors": ["Unknown"]}], "reason": "Verify validation."},
                config,
            )

        self.assertEqual(result.status, ActionStatus.FAILED)
        self.assertIn("requires a title", result.summary)


if __name__ == "__main__":
    unittest.main()
