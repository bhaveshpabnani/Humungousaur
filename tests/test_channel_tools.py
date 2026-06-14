import hashlib
import hmac
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime
from humungousaur.integrations.channel_listeners import channel_listener_status, process_channel_webhook
from humungousaur.integrations.channels import channel_setup_status, handle_channel_inbound
from humungousaur.schemas import ActionStatus
from humungousaur.tools.channel_tools import (
    ChannelActionPrepareTool,
    ChannelCatalogTool,
    ChannelDoctorTool,
    ChannelIntegrationSmokeTool,
    ChannelManifestTool,
    ChannelPairingPrepareTool,
    ChannelListenerStatusTool,
    ChannelMessagePrepareTool,
    ChannelOutboxTool,
    ChannelRoutingPolicyPrepareTool,
    ChannelSetupSaveTool,
    ChannelSetupStatusTool,
    ChannelTroubleshootingGuideTool,
    ChannelWebhookIngestTool,
)
from humungousaur.tools import default_tools


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

    def test_channel_action_prepare_writes_reaction_and_thread_actions_without_sending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            reaction = ChannelActionPrepareTool().execute(
                {
                    "channel_id": "slack",
                    "conversation_id": "C123",
                    "action_type": "reaction_add",
                    "target_message_id": "1712023032.1234",
                    "metadata": {"emoji": "white_check_mark"},
                    "reason": "Acknowledge a reviewed message.",
                },
                config,
            )
            thread = ChannelActionPrepareTool().execute(
                {
                    "channel_id": "discord",
                    "conversation_id": "990001",
                    "action_type": "thread_reply",
                    "target_message_id": "m-123",
                    "text": "Draft thread reply; not sent.",
                    "reason": "Prepare a thread reply action.",
                },
                config,
            )
            outbox = ChannelOutboxTool().execute({"limit": 10}, config)
            reaction_path_exists = Path(reaction.output["action"]["path"]).exists()

        self.assertEqual(reaction.status, ActionStatus.SUCCEEDED)
        self.assertEqual(reaction.output["action"]["status"], "prepared_not_sent")
        self.assertTrue(reaction.output["action"]["requires_approval"])
        self.assertEqual(reaction.output["action"]["action_type"], "reaction_add")
        self.assertEqual(thread.status, ActionStatus.SUCCEEDED)
        self.assertEqual(thread.output["action"]["action_type"], "thread_reply")
        self.assertTrue(reaction_path_exists)
        self.assertTrue(any(item["item_type"] == "action" and item["action_type"] == "reaction_add" for item in outbox.output["messages"]))

    def test_channel_action_prepare_blocks_unsupported_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = ChannelActionPrepareTool().execute(
                {
                    "channel_id": "whatsapp",
                    "conversation_id": "+15555550100",
                    "action_type": "thread_reply",
                    "target_message_id": "wamid-1",
                    "text": "WhatsApp does not expose native thread replies.",
                    "reason": "Verify unsupported action handling.",
                },
                config,
            )

        self.assertEqual(result.status, ActionStatus.FAILED)
        self.assertIn("not supported", result.summary)

    def test_channel_action_tool_is_in_global_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            tools = default_tools(config)

        self.assertIn("channel_action_prepare", tools)
        self.assertEqual(tools["channel_action_prepare"].capability_group, "channels")
        self.assertIn("channel_integration_smoke", tools)
        self.assertEqual(tools["channel_integration_smoke"].capability_group, "channels")

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

    def test_channel_status_and_listener_use_runtime_secrets_without_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                runtime_secrets={"TELEGRAM_BOT_TOKEN": "tg-runtime"},
            ).normalized()
            ChannelSetupSaveTool().execute(
                {
                    "channel_id": "telegram",
                    "enabled": True,
                    "listen_enabled": False,
                    "conversation_defaults": {"conversation_id": "42", "conversation_type": "dm"},
                },
                config,
            )

            with patch.dict("os.environ", {}, clear=True):
                status = channel_setup_status(config, channel_id="telegram")
                listener = channel_listener_status(config, channel_id="telegram")

        self.assertEqual(status["channels"][0]["missing_send_env"], [])
        self.assertTrue(status["channels"][0]["ready_for_send"])
        self.assertTrue(status["channels"][0]["enabled"])
        self.assertFalse(status["channels"][0]["listen_enabled"])
        self.assertFalse(status["channels"][0]["ready_for_inbound"])
        self.assertFalse(listener["listeners"][0]["listen_enabled"])
        self.assertFalse(listener["listeners"][0]["polling_available"])

    def test_channel_setup_status_uses_connector_credentials_without_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            ConnectorRuntime(config).configure_client("telegram", client_id="telegram-bot", client_secret="tg-connector-token")

            with patch.dict("os.environ", {}, clear=True):
                status = channel_setup_status(config, channel_id="telegram")

        channel = status["channels"][0]
        self.assertEqual(channel["missing_send_env"], [])
        self.assertEqual(channel["credential_source"], "connector")
        self.assertEqual(channel["connector_provider_id"], "telegram")
        self.assertTrue(channel["connector_readiness"]["connection_ready"])
        self.assertTrue(channel["ready_for_send"])

    def test_channel_listener_status_uses_connector_credentials_without_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            ConnectorRuntime(config).configure_client("telegram", client_id="telegram-bot", client_secret="tg-connector-token")
            ChannelSetupSaveTool().execute(
                {
                    "channel_id": "telegram",
                    "enabled": True,
                    "listen_enabled": True,
                    "conversation_defaults": {"conversation_id": "42", "conversation_type": "dm"},
                },
                config,
            )

            with patch.dict("os.environ", {}, clear=True):
                listener = channel_listener_status(config, channel_id="telegram")["listeners"][0]

        self.assertEqual(listener["missing_env"], [])
        self.assertEqual(listener["credential_source"], "connector")
        self.assertTrue(listener["polling_available"])
        self.assertTrue(listener["ready"])

    def test_channel_integration_smoke_reports_runtime_secret_readiness_without_live_send(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                runtime_secrets={"TELEGRAM_BOT_TOKEN": "tg-runtime"},
            ).normalized()
            ChannelSetupSaveTool().execute(
                {
                    "channel_id": "telegram",
                    "enabled": True,
                    "conversation_defaults": {"conversation_id": "42", "conversation_type": "dm"},
                    "secret_refs": {"bot_token": "TELEGRAM_BOT_TOKEN"},
                    "secret_configured": {"bot_token": True},
                },
                config,
            )

            with patch.dict("os.environ", {}, clear=True):
                result = ChannelIntegrationSmokeTool().execute(
                    {"channel_ids": ["telegram"], "reason": "Verify channel smoke."},
                    config,
                )
                outbox = ChannelOutboxTool().execute({"limit": 10}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertEqual(result.output["channel_count"], 1)
        self.assertEqual(result.output["channels"][0]["readiness"], "ready")
        self.assertTrue(result.output["channels"][0]["prepared_outbox_ready"])
        self.assertTrue(result.output["channels"][0]["dry_run_send_ready"])
        self.assertTrue(result.output["channels"][0]["direct_send_ready"])
        self.assertTrue(result.output["channels"][0]["listener_ready"])
        self.assertFalse(result.output["live_send_performed"])
        self.assertGreaterEqual(len(outbox.output["messages"]), 2)

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

    def test_channel_listener_status_reflects_enabled_channels_and_webhook_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts", planner_provider="explicit").normalized()
            ChannelSetupSaveTool().execute(
                {
                    "channel_id": "slack",
                    "enabled": True,
                    "conversation_defaults": {"conversation_id": "C123", "conversation_type": "channel"},
                    "secret_refs": {"bot_token": "SLACK_BOT_TOKEN", "signing_secret": "SLACK_SIGNING_SECRET"},
                },
                config,
            )

            status = channel_listener_status(config, channel_id="slack")
            tool_status = ChannelListenerStatusTool().execute({"channel_id": "slack"}, config)

        listener = status["listeners"][0]
        self.assertTrue(listener["enabled"])
        self.assertEqual(listener["channel_id"], "slack")
        self.assertEqual(listener["webhook_path"], "/channels/webhook/slack")
        self.assertIn("slack_events_webhook", listener["listener_mode"])
        self.assertEqual(tool_status.status, ActionStatus.SUCCEEDED)
        self.assertEqual(tool_status.output["listeners"][0]["channel_id"], "slack")

    def test_channel_webhook_ingest_normalizes_slack_event_and_prepares_reply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Slack Listener\n\nNative ingress.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

            result = process_channel_webhook(
                config,
                channel_id="slack",
                payload={
                    "event_id": "Ev1",
                    "event": {
                        "type": "message",
                        "channel": "C123",
                        "channel_type": "im",
                        "user": "U123",
                        "text": 'read_file {"path":"README.md"}',
                        "client_msg_id": "m-1",
                    },
                },
            )
            outbox = ChannelOutboxTool().execute({"limit": 5}, config)
            tool_result = ChannelWebhookIngestTool().execute(
                {
                    "channel_id": "telegram",
                    "payload": {
                        "update_id": 10,
                        "message": {
                            "message_id": 20,
                            "chat": {"id": "42", "type": "private"},
                            "from": {"id": "7", "is_bot": False},
                            "text": "hello",
                        },
                    },
                    "reason": "test webhook ingestion",
                },
                config,
            )

        self.assertTrue(result["accepted"])
        self.assertEqual(result["message_count"], 1)
        self.assertIsNotNone(result["results"][0]["prepared_reply"])
        self.assertEqual(outbox.output["messages"][0]["channel_id"], "slack")
        self.assertEqual(tool_result.status, ActionStatus.SUCCEEDED)
        self.assertEqual(tool_result.output["message_count"], 1)

    def test_slack_webhook_signature_is_verified_when_secret_is_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, patch.dict(os.environ, {"SLACK_SIGNING_SECRET": "signing-secret"}, clear=False):
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Slack Signature\n", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()
            payload = {
                "event_id": "EvSigned",
                "event": {
                    "type": "message",
                    "channel": "C123",
                    "channel_type": "im",
                    "user": "U123",
                    "text": "hello",
                    "client_msg_id": "m-signed",
                },
            }
            raw_body = json.dumps(payload, separators=(",", ":"))
            timestamp = str(int(time.time()))
            signature = "v0=" + hmac.new(
                b"signing-secret",
                f"v0:{timestamp}:{raw_body}".encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            result = process_channel_webhook(
                config,
                channel_id="slack",
                payload=payload,
                headers={"X-Slack-Request-Timestamp": timestamp, "X-Slack-Signature": signature},
                raw_body=raw_body,
            )

            with self.assertRaises(ValueError):
                process_channel_webhook(
                    config,
                    channel_id="slack",
                    payload=payload,
                    headers={"X-Slack-Request-Timestamp": timestamp, "X-Slack-Signature": "v0=bad"},
                    raw_body=raw_body,
                )

        self.assertTrue(result["accepted"])
        self.assertEqual(result["message_count"], 1)

    def test_native_channel_catalog_includes_remaining_channel_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            catalog = ChannelCatalogTool().execute({}, config)
            clickclack = ChannelManifestTool().execute({"channel_id": "clickclack"}, config)
            qa = ChannelManifestTool().execute({"channel_id": "qa_channel"}, config)

        ids = {item["channel_id"] for item in catalog.output["channels"]}
        expected = {
            "line",
            "irc",
            "nextcloud_talk",
            "nostr",
            "synology_chat",
            "tlon",
            "twitch",
            "zalo",
            "zalo_personal",
            "clickclack",
            "qa_channel",
            "googlechat",
        }
        self.assertTrue(expected.issubset(ids))
        self.assertEqual(clickclack.status, ActionStatus.SUCCEEDED)
        self.assertEqual(clickclack.output["channel"]["setup_kind"], "clickclack_bridge")
        self.assertTrue(clickclack.output["channel"]["policies"]["ambient_room_events_supported"])
        self.assertEqual(qa.output["channel"]["setup_kind"], "local_test_harness")
        self.assertEqual(qa.output["channel"]["plugin_status"], "implemented")

    def test_native_channel_routing_pairing_and_troubleshooting_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            policy = ChannelRoutingPolicyPrepareTool().execute(
                {
                    "channel_id": "clickclack",
                    "access_groups": ["core"],
                    "broadcast_groups": ["announcements"],
                    "group_routes": [{"from": "room-a", "to": "room-b"}],
                    "location_events_enabled": True,
                    "ambient_room_events_enabled": True,
                    "pairing_required": True,
                    "troubleshooting_notes": ["Bridge must be local or trusted."],
                    "reason": "native routing smoke.",
                },
                config,
            )
            pairing = ChannelPairingPrepareTool().execute(
                {
                    "channel_id": "qa_channel",
                    "conversation_id": "fixture-room",
                    "pairing_kind": "group",
                    "identity_hint": "qa-fixture",
                    "reason": "Prepare deterministic pairing.",
                },
                config,
            )
            guide = ChannelTroubleshootingGuideTool().execute({"channel_id": "clickclack"}, config)
            prepared = ChannelMessagePrepareTool().execute(
                {"channel_id": "qa_channel", "conversation_id": "fixture-room", "text": "hello", "reason": "QA outbox."},
                config,
            )
            smoke = ChannelIntegrationSmokeTool().execute(
                {"channel_ids": ["clickclack", "qa_channel"], "reason": "native channel smoke."},
                config,
            )
            policy_path_exists = Path(policy.output["policy"]["path"]).exists()
            pairing_path_exists = Path(pairing.output["pairing"]["path"]).exists()

        self.assertEqual(policy.status, ActionStatus.SUCCEEDED)
        self.assertTrue(policy_path_exists)
        self.assertEqual(policy.output["policy"]["broadcast_groups"], ["announcements"])
        self.assertTrue(policy.output["policy"]["location_events_enabled"])
        self.assertEqual(pairing.status, ActionStatus.SUCCEEDED)
        self.assertTrue(pairing_path_exists)
        self.assertEqual(pairing.output["pairing"]["status"], "prepared_not_paired")
        self.assertEqual(guide.status, ActionStatus.SUCCEEDED)
        self.assertIn("CLICKCLACK_BRIDGE_TOKEN", guide.output["guide"]["required_secrets"])
        self.assertEqual(prepared.status, ActionStatus.SUCCEEDED)
        self.assertEqual(prepared.output["message"]["channel_id"], "qa_channel")
        self.assertEqual(smoke.status, ActionStatus.SUCCEEDED)
        self.assertEqual(smoke.output["channel_count"], 2)
        self.assertTrue(any(item["channel_id"] == "qa_channel" for item in smoke.output["channels"]))


if __name__ == "__main__":
    unittest.main()
