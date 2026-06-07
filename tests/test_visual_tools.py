import json
import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.visual_tools import (
    DiagramArtifactCreateTool,
    DiagramArtifactInspectTool,
    ExcalidrawDiagramCreateTool,
    InfographicPlanCreateTool,
    InfographicPlanInspectTool,
)


class VisualToolTests(unittest.TestCase):
    def test_diagram_artifact_create_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = DiagramArtifactCreateTool().execute(
                {
                    "filename": "agent-flow.md",
                    "title": "Agent Flow",
                    "diagram_type": "sequence",
                    "status": "current",
                    "nodes": [
                        {"id": "user", "label": "User", "kind": "stimulus"},
                        {"id": "agent", "label": "Agent", "kind": "reasoning"},
                    ],
                    "edges": [{"from": "user", "to": "agent", "label": "asks", "evidence": "fixture"}],
                    "evidence_refs": ["tests fixture"],
                    "unknowns": ["No live runtime involved."],
                    "reason": "Verify native diagram artifacts.",
                },
                config,
            )
            inspected = DiagramArtifactInspectTool().execute({"path": created.output["path"]}, config)
            mermaid = Path(created.output["mermaid_path"]).read_text(encoding="utf-8")

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["node_count"], 2)
        self.assertEqual(created.output["edge_count"], 1)
        self.assertIn("sequenceDiagram", mermaid)
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["status"], "current")
        self.assertEqual(inspected.output["evidence_ref_count"], 1)

    def test_excalidraw_diagram_create_writes_compatible_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = ExcalidrawDiagramCreateTool().execute(
                {
                    "filename": "agent-flow.excalidraw",
                    "title": "Agent Flow Sketch",
                    "nodes": [
                        {"id": "stimulus", "label": "Stimulus", "x": 40, "y": 60},
                        {"id": "planner", "label": "Planner", "x": 340, "y": 60},
                    ],
                    "edges": [{"from": "stimulus", "to": "planner", "label": "routes"}],
                    "status": "draft",
                    "evidence_refs": ["synthetic fixture"],
                    "reason": "Verify native Excalidraw export.",
                },
                config,
            )
            payload = json.loads(Path(created.output["path"]).read_text(encoding="utf-8"))

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(payload["type"], "excalidraw")
        self.assertEqual(payload["humungousaur_metadata"]["status"], "draft")
        self.assertGreaterEqual(created.output["element_count"], 5)

    def test_infographic_plan_create_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = InfographicPlanCreateTool().execute(
                {
                    "filename": "growth-plan.md",
                    "title": "Growth Snapshot",
                    "audience": "Product leadership",
                    "key_message": "Activation improved across the synthetic smoke fixture.",
                    "status": "ready_for_review",
                    "metrics": [{"label": "Activation", "value": "42", "unit": "%", "source": "fixture", "notes": "synthetic"}],
                    "sections": [{"title": "Why it matters", "body": "Shows the hierarchy and source-backed metric."}],
                    "visual_marks": ["large number", "bar comparison"],
                    "accessibility_notes": ["Do not encode status by color alone."],
                    "source_refs": ["tests fixture"],
                    "reason": "Verify native infographic artifact.",
                },
                config,
            )
            inspected = InfographicPlanInspectTool().execute({"path": created.output["path"]}, config)

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["metric_count"], 1)
        self.assertEqual(created.output["section_count"], 1)
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["status"], "ready_for_review")
        self.assertEqual(inspected.output["accessibility_note_count"], 1)

    def test_infographic_requires_key_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = InfographicPlanCreateTool().execute({"title": "Missing message", "reason": "Verify validation."}, config)

        self.assertEqual(result.status, ActionStatus.FAILED)
        self.assertIn("key_message", result.summary)


if __name__ == "__main__":
    unittest.main()
