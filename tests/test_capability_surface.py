import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.capability_tools import CapabilitySurfaceTool, ToolDescribeTool, ToolSearchTool, build_capability_surface


class CapabilitySurfaceTests(unittest.TestCase):
    def test_capability_surface_unifies_tools_skills_plugins_and_channels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            skill_dir = workspace / "skills" / "voice-loop"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: voice-loop\ndescription: Handle voice wakeup, STT, agent work, and TTS response.\n---\n# Voice Loop\n",
                encoding="utf-8",
            )
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = CapabilitySurfaceTool().execute({"include_records": True}, config)
            surface = result.output

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertGreater(surface["counts"]["tools"], 100)
        self.assertGreaterEqual(surface["counts"]["workspace_skills"], 1)
        self.assertIn("channels.whatsapp", {plugin["plugin_id"] for plugin in surface["plugins"]})
        self.assertIn("whatsapp", {channel["channel_id"] for channel in surface["channels"]})
        self.assertIn("voice", {group["name"] for group in surface["tool_groups"]})
        self.assertIn("capabilities", {group["name"] for group in surface["tool_groups"]})
        self.assertEqual(surface["integrity"]["missing_plugin_declared_tools"], [])
        self.assertIn("large_catalog_search", {item["surface_id"] for item in surface["surfaces"]})
        self.assertTrue(surface["policy_boundary"]["model_led_routing"])

    def test_tool_search_and_describe_return_exact_catalog_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            voice = ToolSearchTool().execute({"query": "voice response", "limit": 10}, config)
            slack = ToolDescribeTool().execute({"record_id": "plugin:channels.slack"}, config)
            spoken = ToolDescribeTool().execute({"record_id": "tool:voice_speak", "include_tool_schema": True}, config)

        self.assertEqual(voice.status, ActionStatus.SUCCEEDED)
        self.assertIn("tool:voice_response_prepare", {match["record_id"] for match in voice.output["matches"]})
        self.assertIn("plugin:voice.elevenlabs", {match["record_id"] for match in voice.output["matches"]})
        self.assertEqual(slack.status, ActionStatus.SUCCEEDED)
        self.assertEqual(slack.output["record"]["kind"], "plugin")
        self.assertIn("channel_message_send", slack.output["record"]["tools"])
        self.assertEqual(spoken.status, ActionStatus.SUCCEEDED)
        self.assertEqual(spoken.output["record"]["kind"], "tool")
        self.assertIn("input_schema", spoken.output["record"])
        self.assertEqual(spoken.output["record"]["input_schema"]["required"], ["text", "reason"])

    def test_build_capability_surface_reports_contract_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            surface = build_capability_surface(config)

        self.assertEqual(surface["integrity"]["missing_plugin_declared_tools"], [])


if __name__ == "__main__":
    unittest.main()
