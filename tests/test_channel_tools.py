import json
import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.integrations.channels import handle_channel_inbound
from humungousaur.schemas import ActionStatus
from humungousaur.tools.channel_tools import ChannelCatalogTool, ChannelManifestTool, ChannelMessagePrepareTool, ChannelOutboxTool


class ChannelToolTests(unittest.TestCase):
    def test_channel_catalog_includes_openclaw_style_chat_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            catalog = ChannelCatalogTool().execute({}, config)
            slack = ChannelManifestTool().execute({"channel_id": "slack"}, config)
            whatsapp = ChannelManifestTool().execute({"channel_id": "whatsapp"}, config)

        ids = {item["channel_id"] for item in catalog.output["channels"]}
        self.assertEqual(catalog.status, ActionStatus.SUCCEEDED)
        self.assertIn("slack", ids)
        self.assertIn("whatsapp", ids)
        self.assertIn("telegram", ids)
        self.assertEqual(slack.output["channel"]["setup"], "slack_app_credentials")
        self.assertEqual(whatsapp.output["channel"]["setup"], "qr_pairing")

    def test_channel_message_prepare_writes_outbox_without_sending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            prepared = ChannelMessagePrepareTool().execute(
                {
                    "channel_id": "telegram",
                    "conversation_id": "chat-1",
                    "text": "Here is an image: ![alt](https://example.com/image.png)",
                    "reason": "test",
                },
                config,
            )
            outbox = ChannelOutboxTool().execute({"limit": 5}, config)

            self.assertEqual(prepared.status, ActionStatus.SUCCEEDED)
            self.assertEqual(prepared.output["message"]["status"], "prepared_not_sent")
            self.assertTrue(prepared.output["message"]["rendering_hints"]["markdown_image_media_conversion"])
            self.assertTrue(Path(prepared.output["message"]["path"]).exists())
            self.assertEqual(len(outbox.output["messages"]), 1)

    def test_channel_inbound_routes_to_interaction_harness_and_prepares_reply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Channel Demo\n\nA local assistant runtime.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

            result = handle_channel_inbound(
                {
                    "channel_id": "slack",
                    "conversation_id": "C123",
                    "conversation_type": "dm",
                    "sender_id": "U123",
                    "text": 'read_file {"path":"README.md"}',
                    "requires_response": True,
                    "message_id": "m-1",
                    "prepare_reply": True,
                },
                config,
            )

        self.assertEqual(result["stimulus"]["source"], "channel_message")
        self.assertEqual(result["harness"]["decision"]["decision"], "respond")
        self.assertIsNotNone(result["prepared_reply"])
        self.assertEqual(result["prepared_reply"]["channel_id"], "slack")
        self.assertIn("README.md", json.dumps(result["harness"]))


if __name__ == "__main__":
    unittest.main()
