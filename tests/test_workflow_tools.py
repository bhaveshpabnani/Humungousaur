import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from humungousaur.config import AgentConfig
from humungousaur.planning.model_clients import StaticModelClient
from humungousaur.schemas import ActionStatus
from humungousaur.tools import default_tools
from humungousaur.tools.workflow_tools import (
    CanvasA2uiCreateTool,
    CanvasA2uiRenderTool,
    DiffRenderTool,
    LlmTaskJsonTool,
    LobsterWorkflowApproveTool,
    LobsterWorkflowStartTool,
    LobsterWorkflowStatusTool,
    TokenjuiceCompactTool,
)


class WorkflowToolTests(unittest.TestCase):
    def test_default_registry_exposes_workflow_plugin_tools(self) -> None:
        tools = default_tools()

        for name in {
            "diff_render",
            "llm_task_json",
            "tokenjuice_compact",
            "lobster_workflow_start",
            "lobster_workflow_status",
            "lobster_workflow_approve",
            "canvas_a2ui_create",
            "canvas_a2ui_render",
        }:
            self.assertIn(name, tools)
            self.assertEqual(tools[name].capability_group, "workflow")

    def test_diff_render_compares_text_and_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            before = workspace / "before.txt"
            after = workspace / "after.txt"
            before.write_text("alpha\nold\n", encoding="utf-8")
            after.write_text("alpha\nnew\n", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            text_result = DiffRenderTool().execute(
                {"left_text": "one\n", "right_text": "two\n", "write_artifact": True},
                config,
            )
            file_result = DiffRenderTool().execute(
                {"left_path": "before.txt", "right_path": "after.txt"},
                config,
            )
            artifact_exists = Path(text_result.output["artifact_path"]).exists()

        self.assertEqual(text_result.status, ActionStatus.SUCCEEDED)
        self.assertTrue(text_result.output["changed"])
        self.assertTrue(artifact_exists)
        self.assertEqual(file_result.status, ActionStatus.SUCCEEDED)
        self.assertEqual(file_result.output["stats"]["added"], 1)
        self.assertIn("+new", file_result.output["unified_diff"])

    def test_llm_task_json_uses_model_and_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            schema = {
                "type": "object",
                "additionalProperties": False,
                "required": ["status", "steps", "confidence"],
                "properties": {
                    "status": {"type": "string"},
                    "steps": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                },
            }

            with patch(
                "humungousaur.tools.workflow.implementation.build_model_client",
                return_value=StaticModelClient(json.dumps({"status": "ok", "steps": ["read"], "confidence": 0.9})),
            ):
                result = LlmTaskJsonTool().execute({"objective": "Plan the next step.", "json_schema": schema}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertEqual(result.output["json"]["status"], "ok")
        self.assertEqual(result.output["json"]["steps"], ["read"])

    def test_tokenjuice_compact_mechanical_and_model_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            text = "\n".join(f"line {index}" for index in range(1000))

            result = TokenjuiceCompactTool().execute({"text": text, "max_chars": 1200}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertTrue(result.output["compacted"])
        self.assertLessEqual(len(result.output["compacted_text"]), 1200)
        self.assertEqual(len(result.output["sha256"]), 64)

    def test_lobster_workflow_pauses_and_resumes_approval_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            started = LobsterWorkflowStartTool().execute(
                {
                    "name": "Approval smoke",
                    "objective": "Write a note only after approval.",
                    "input_schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["ticket"],
                        "properties": {"ticket": {"type": "string"}},
                    },
                    "input": {"ticket": "T-1"},
                    "steps": [
                        {
                            "type": "tool",
                            "title": "Write note",
                            "tool_name": "write_note",
                            "tool_input": {"title": "approved", "content": "done"},
                            "requires_approval": True,
                        }
                    ],
                },
                config,
            )
            workflow = started.output["workflow"]
            token = workflow["steps"][0]["approval_token"]
            status = LobsterWorkflowStatusTool().execute({"workflow_id": workflow["workflow_id"]}, config)
            approved = LobsterWorkflowApproveTool().execute(
                {"workflow_id": workflow["workflow_id"], "approval_token": token, "decision": "approve", "note": "test approval"},
                config,
            )
            note_exists = (workspace / "artifacts" / "notes" / "approved.md").exists()

        self.assertEqual(started.status, ActionStatus.SUCCEEDED)
        self.assertEqual(workflow["status"], "needs_approval")
        self.assertEqual(status.output["workflow"]["typed_input"]["ticket"], "T-1")
        self.assertEqual(approved.output["workflow"]["status"], "succeeded")
        self.assertTrue(note_exists)

    def test_canvas_a2ui_create_and_render_svg_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = CanvasA2uiCreateTool().execute(
                {
                    "title": "Agent Flow",
                    "nodes": [
                        {"id": "stimulus", "label": "Stimulus", "x": 40, "y": 80, "kind": "input", "color": "#dcfce7"},
                        {"id": "agent", "label": "Agent", "x": 320, "y": 80, "kind": "reasoning", "color": "#dbeafe"},
                    ],
                    "edges": [{"from": "stimulus", "to": "agent", "label": "routes to"}],
                },
                config,
            )
            canvas_id = created.output["canvas"]["canvas_id"]
            rendered = CanvasA2uiRenderTool().execute({"canvas_id": canvas_id}, config)
            json_exists = Path(created.output["path"]).exists()
            svg_exists = Path(created.output["svg_path"]).exists()

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertTrue(json_exists)
        self.assertTrue(svg_exists)
        self.assertEqual(rendered.status, ActionStatus.SUCCEEDED)
        self.assertIn("<svg", rendered.output["svg"])


if __name__ == "__main__":
    unittest.main()
