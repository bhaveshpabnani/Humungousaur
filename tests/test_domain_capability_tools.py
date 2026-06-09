import json
import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools import default_tools
from humungousaur.tools.domain_capabilities import NATIVE_DOMAIN_CAPABILITY_SPECS


class DomainCapabilityToolTests(unittest.TestCase):
    def test_default_tools_expose_all_domain_capability_specs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            tools = default_tools(config)

            missing = [spec["name"] for spec in NATIVE_DOMAIN_CAPABILITY_SPECS if spec["name"] not in tools]

        self.assertEqual(missing, [])
        self.assertGreaterEqual(len(NATIVE_DOMAIN_CAPABILITY_SPECS), 80)

    def test_creative_capability_tool_writes_asset_and_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            tools = default_tools(config)

            result = tools["pixel_art_create"].execute(
                {
                    "title": "Status Tile",
                    "items": [{"color": "#111111"}, {"color": "#22aaff"}],
                    "reason": "test pixel capability",
                },
                config,
            )

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertTrue(Path(result.output["markdown_path"]).is_file())
            self.assertTrue(Path(result.output["json_path"]).is_file())
            self.assertTrue(Path(result.output["svg_path"]).is_file())
            packet = json.loads(Path(result.output["json_path"]).read_text(encoding="utf-8"))
            self.assertEqual(packet["tool"], "pixel_art_create")
            self.assertEqual(packet["implementation_boundary"], "native_humungousaur_tool")

    def test_mlops_capability_tool_records_command_and_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            tools = default_tools(config)

            result = tools["vllm_server_prepare"].execute(
                {"title": "Serve local model", "target": "TinyLlama/TinyLlama-1.1B", "reason": "test vllm capability"},
                config,
            )

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        packet = result.output["packet"]
        self.assertEqual(packet["tool"], "vllm_server_prepare")
        self.assertIn("prepared_command", packet["params"])
        self.assertIn("runtime_readiness", packet["params"])

    def test_apple_live_tool_requires_approval_before_side_effect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            tools = default_tools(config)

            result = tools["apple_notes_create"].execute(
                {"title": "Private note", "content": "draft body", "reason": "test approval gate"},
                config,
            )

        self.assertEqual(result.status, ActionStatus.NEEDS_APPROVAL)
        self.assertTrue(result.output["packet"]["approval_required"])

    def test_productivity_capability_tool_tracks_missing_credentials_without_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            tools = default_tools(config)

            result = tools["shopify_operation_prepare"].execute(
                {"title": "Create product", "target": "demo-shop", "reason": "test shopify capability"},
                config,
            )

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertIn("SHOPIFY_ADMIN_TOKEN", result.output["readiness"]["missing_env"])
        self.assertNotIn("token", json.dumps(result.output["packet"]).lower().replace("shopify_admin_token", ""))


if __name__ == "__main__":
    unittest.main()
