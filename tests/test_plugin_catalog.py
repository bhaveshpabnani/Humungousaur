import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.plugin_tools import PluginCatalogTool, PluginSetupPlanTool, load_plugin_catalog


class PluginCatalogTests(unittest.TestCase):
    def test_builtin_plugin_catalog_lists_humungousaur_owned_capabilities(self) -> None:
        plugins = load_plugin_catalog()
        ids = {plugin["plugin_id"] for plugin in plugins}

        self.assertIn("channels.whatsapp", ids)
        self.assertIn("channels.slack", ids)
        self.assertIn("voice.deepgram", ids)
        self.assertIn("browser.playwright", ids)
        self.assertTrue(all(plugin.get("owned_by") == "humungousaur" for plugin in plugins))

    def test_plugin_catalog_tool_filters_by_kind_and_plugin_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            channels = PluginCatalogTool().execute({"kind": "channel", "include_contracts": False}, config)
            slack = PluginCatalogTool().execute({"plugin_id": "channels.slack"}, config)

        self.assertEqual(channels.status, ActionStatus.SUCCEEDED)
        self.assertIn("channels.slack", {plugin["plugin_id"] for plugin in channels.output["plugins"]})
        self.assertNotIn("contracts", channels.output["plugins"][0])
        self.assertEqual(slack.output["plugins"][0]["runtime_adapter"], "humungousaur.channel_adapters.slack")

    def test_plugin_setup_plan_reports_missing_env_without_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            plan = PluginSetupPlanTool().execute({"plugin_id": "channels.slack"}, config)

        self.assertEqual(plan.status, ActionStatus.SUCCEEDED)
        self.assertIn("SLACK_BOT_TOKEN", plan.output["setup_status"]["missing_env"])
        self.assertFalse(plan.output["setup_status"]["ready"])
        self.assertNotIn("xoxb", str(plan.output))


if __name__ == "__main__":
    unittest.main()
