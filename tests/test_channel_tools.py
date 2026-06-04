import json
import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.integrations.channels import channel_setup_status, handle_channel_inbound
from humungousaur.schemas import ActionStatus
from humungousaur.tools.channel_tools import (
    ChannelCatalogTool,
    ChannelDoctorTool,
    ChannelManifestTool,
    ChannelMessagePrepareTool,
    ChannelOutboxTool,
    ChannelSetupSaveTool,
    ChannelSetupStatusTool,
)


class ChannelToolTests(unittest.TestCase):
    def test_channel_catalog_includes_humungousaur_chat_surfaces(self) -> None:
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
        self.assertEqual(slack.output["channel"]["setup_kind"], "slack_app_credentials")
        self.assertEqual(whatsapp.output["channel"]["setup_kind"], "whatsapp_account")
        self.assertEqual(slack.output["channel"]["setup"]["auth_type"], "slack_app")
        self.assertTrue(slack.output["channel"]["policies"]["ambient_room_events_supported"])
        self.assertTrue(slack.output["channel"]["delivery"]["official_send"]["implemented"])

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
            self.assertEqual(prepared.output["message"]["media"][0]["kind"], "image")
            self.assertEqual(prepared.output["message"]["media"][0]["url"], "https://example.com/image.png")
            self.assertTrue(Path(prepared.output["message"]["path"]).exists())
            self.assertEqual(len(outbox.output["messages"]), 1)

    def test_channel_setup_save_status_and_doctor_report_missing_env_without_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            saved = ChannelSetupSaveTool().execute(
                {
                    "channel_id": "slack",
                    "enabled": True,
                    "conversation_defaults": {"conversation_id": "C123", "conversation_type": "channel"},
                    "secret_refs": {"bot_token": "SLACK_BOT_TOKEN"},
                    "secret_configured": {"bot_token": False},
                    "allowlist": ["U123"],
                    "notes": "test setup",
                },
                config,
            )
            status = ChannelSetupStatusTool().execute({"channel_id": "slack"}, config)
            doctor = ChannelDoctorTool().execute({"channel_id": "slack"}, config)

        self.assertEqual(saved.status, ActionStatus.SUCCEEDED)
        self.assertEqual(saved.output["setup"]["secret_refs"], {"bot_token": "SLACK_BOT_TOKEN"})
        self.assertNotIn("xoxb", json.dumps(saved.output))
        self.assertFalse(status.output["channels"][0]["ready_for_send"])
        self.assertIn("SLACK_BOT_TOKEN", status.output["channels"][0]["missing_send_env"])
        self.assertEqual(doctor.output["overall_status"], "needs_setup")

    def test_channel_setup_status_function_uses_catalog_setup_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            status = channel_setup_status(config, channel_id="telegram")

        self.assertEqual(status["channels"][0]["setup"]["auth_type"], "bot_token")
        self.assertIn("TELEGRAM_BOT_TOKEN", status["channels"][0]["missing_send_env"])

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

    def test_channel_inbound_ignores_bot_authored_messages_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts", planner_provider="explicit").normalized()

            result = handle_channel_inbound(
                {
                    "channel_id": "discord",
                    "conversation_id": "C123",
                    "conversation_type": "server_channel",
                    "sender_id": "bot-a",
                    "sender_is_bot": True,
                    "text": "hello from another bot",
                    "requires_response": True,
                },
                config,
            )

        self.assertTrue(result["ignored"])
        self.assertEqual(result["ignore_reason"], "bot_authored_message_blocked")
        self.assertIsNone(result["prepared_reply"])
        self.assertIsNone(result["harness"])

    def test_ambient_channel_message_records_context_without_prepared_reply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

            result = handle_channel_inbound(
                {
                    "channel_id": "slack",
                    "conversation_id": "C123",
                    "conversation_type": "channel",
                    "sender_id": "U123",
                    "text": "quiet room context",
                    "requires_response": False,
                    "mentioned": False,
                    "ambient": True,
                    "prepare_reply": True,
                },
                config,
            )

        self.assertFalse(result["ignored"])
        self.assertTrue(result["policy"]["ambient"])
        self.assertTrue(result["stimulus"]["metadata"]["ambient"])
        self.assertIsNone(result["prepared_reply"])
        self.assertEqual(result["harness"]["decision"]["decision"], "observe")


if __name__ == "__main__":
    unittest.main()
