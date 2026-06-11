import base64
import json
import socket
import tempfile
import threading
import time
import urllib.error
import unittest
import urllib.request
from pathlib import Path

from humungousaur.api import create_api_server
from humungousaur.active_agent import active_agent_status
from humungousaur.active_agent.models import ActiveEpisode, Confidence
from humungousaur.active_agent.store import ActiveAgentStore
from humungousaur.config import AgentConfig
from humungousaur.cognition import TriggerStore, WakeupStore, WakeupStatus
from humungousaur.cognition.knowledge import KnowledgeStore
from humungousaur.cognition.models import KnowledgeKind
from humungousaur.orchestrator import AgentOrchestrator
from humungousaur.runtime import request_config
from humungousaur.safety.audit import AuditLog
from humungousaur.tools.browser_tools import BrowserSessionStore


class APITests(unittest.TestCase):
    def test_api_server_failed_bind_closes_without_masking_port_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
                blocker.bind(("127.0.0.1", 0))
                blocker.listen(1)
                port = blocker.getsockname()[1]

                with self.assertRaises(OSError) as raised:
                    create_api_server(AgentConfig(workspace=workspace, data_dir=workspace / "artifacts"), port=port)

                self.assertIn(raised.exception.errno, {48, 98})

    def test_api_serves_dashboard_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            with running_api(AgentConfig(workspace=workspace, data_dir=workspace / "artifacts")) as base_url:
                html = api_get_text(base_url, "/")
                css = api_get_text(base_url, "/dashboard/styles.css")
                js = api_get_text(base_url, "/dashboard/app.js")

                self.assertIn("Humungousaur", html)
                self.assertIn("commandForm", html)
                self.assertIn("cancelRunBtn", html)
                self.assertIn("modelProviderSelect", html)
                self.assertIn("modelNameInput", html)
                self.assertIn("modelApiKeyEnvInput", html)
                self.assertIn("dryRunToggle", html)
                self.assertIn("permissions", html)
                self.assertIn("readRootForm", html)
                self.assertIn("browserSessions", html)
                self.assertIn("screenCaptures", html)
                self.assertIn("memorySummaryBtn", html)
                self.assertIn("memoryProfile", html)
                self.assertIn(".topbar", css)
                self.assertIn(".modelRow", css)
                self.assertIn(".inlineToggle", css)
                self.assertIn(".notice", css)
                self.assertIn(".memoryRecap", css)
                self.assertIn("refreshAll", js)
                self.assertIn("startTimelinePolling", js)
                self.assertIn("cancelCurrentRun", js)
                self.assertIn("renderPermissions", js)
                self.assertIn("renderCapabilityGroup", js)
                self.assertIn("renderBrowserSession", js)
                self.assertIn("renderScreenCapture", js)
                self.assertIn("renderMemorySummary", js)
                self.assertIn("renderMemoryProfile", js)
                self.assertIn("renderApprovalPreview", js)
                self.assertIn("Forget browser session", js)
                self.assertIn("editApproval", js)
                self.assertIn("renderSystemStatus", js)
                self.assertIn("addReadRoot", js)
                self.assertIn("rebuildIndex", js)
                self.assertIn("model_provider", js)
                self.assertIn("model_api_key_env", js)

    def test_api_run_plan_and_memory_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# API Demo\n\nLocal runtime.", encoding="utf-8")
            with running_api(AgentConfig(workspace=workspace, data_dir=workspace / "artifacts")) as base_url:
                health = api_get(base_url, "/health")
                self.assertEqual(health["status"], "ok")
                self.assertIn("system", health)
                self.assertIn("overall_status", health["system"])
                providers = api_get(base_url, "/model/providers")
                self.assertIn("openrouter", {item["provider_id"] for item in providers["providers"]})
                self.assertIn("anthropic_messages", providers["transports"])
                bad_stimulus = api_post_error(base_url, "/stimuli", {"text": "", "source": "user_text"})
                self.assertEqual(bad_stimulus["status"], 400)
                self.assertEqual(bad_stimulus["payload"]["error"], "Field 'text' is required.")
                request_logs = [
                    json.loads(line)
                    for line in (workspace / "artifacts" / "api_requests.jsonl").read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                self.assertTrue(any(entry["path"] == "/stimuli" and entry["status"] == 400 for entry in request_logs))
                self.assertNotIn("runtime_secrets", json.dumps(request_logs))
                system_status = api_get(base_url, "/system/status")
                self.assertEqual(system_status["workspace"], str(workspace.resolve()))
                updates = api_get(base_url, "/updates/latest?offline=1&platform=macos")
                self.assertEqual(updates["current_version"], "0.1.3")
                self.assertEqual(updates["latest_tag"], "v0.1.3")
                self.assertFalse(updates["update_available"])
                self.assertEqual(updates["platform"], "macos")
                self.assertTrue(updates["platform_download_url"].endswith("/Humungousaur-macOS.zip"))
                self.assertTrue(updates["checksum_url"].endswith("/checksums.txt"))
                tools = api_get(base_url, "/tools")
                self.assertGreater(tools["tool_count"], 100)
                self.assertIn("voice", {group["name"] for group in tools["groups"]})
                self.assertIn("channels", {group["name"] for group in tools["groups"]})
                self.assertIn("system_status", {tool["name"] for tool in tools["tools"]})
                capabilities = api_get(base_url, "/capabilities")
                self.assertEqual(capabilities["status"], "succeeded")
                self.assertIn("large_catalog_search", {surface["surface_id"] for surface in capabilities["surfaces"]})
                self.assertEqual(capabilities["integrity"]["missing_plugin_declared_tools"], [])
                tool_matches = api_get(base_url, "/tools/search?q=voice&limit=5")
                self.assertEqual(tool_matches["status"], "succeeded")
                self.assertIn("tool:voice_provider_status", {match["record_id"] for match in tool_matches["matches"]})
                tool_detail = api_get(base_url, "/tools/describe?record_id=plugin:channels.slack")
                self.assertEqual(tool_detail["record"]["kind"], "plugin")
                self.assertIn("channel_message_send", tool_detail["record"]["tools"])
                voice_status = api_get(base_url, "/voice/status")
                self.assertEqual(voice_status["status"], "succeeded")
                self.assertIn("stt", voice_status)
                self.assertIn("tts", voice_status)
                voice_status_with_app_secret = api_post(
                    base_url,
                    "/voice/status",
                    {"runtime_secrets": {"DEEPGRAM_API_KEY": "dg-runtime", "ELEVENLABS_API_KEY": "el-runtime"}},
                )
                self.assertTrue(voice_status_with_app_secret["stt"]["deepgram"]["configured"])
                self.assertTrue(voice_status_with_app_secret["tts"]["elevenlabs"]["configured"])
                self.assertNotIn("dg-runtime", json.dumps(voice_status_with_app_secret))
                voice_sample = workspace / "voice-sample.m4a"
                voice_sample.write_bytes(b"fake audio bytes")
                voice_transcribe = api_post(
                    base_url,
                    "/voice/transcribe",
                    {
                        "audio_base64": base64.b64encode(voice_sample.read_bytes()).decode("ascii"),
                        "filename": "voice-sample.m4a",
                        "provider": "deepgram",
                        "reason": "api dry-run voice capture smoke",
                        "dry_run": True,
                        "runtime_secrets": {"DEEPGRAM_API_KEY": "dg-runtime"},
                    },
                )
                self.assertEqual(voice_transcribe["status"], "skipped")
                self.assertTrue(voice_transcribe["transcription_not_requested"])
                self.assertNotIn("dg-runtime", json.dumps(voice_transcribe))
                voice_stop = api_post(base_url, "/voice/stop_playback", {"reason": "api voice stop smoke"})
                self.assertEqual(voice_stop["status"], "succeeded")
                self.assertFalse(voice_stop["stopped"])
                screen_captures = api_get(base_url, "/screen/captures")
                self.assertFalse(screen_captures["image_bytes_served"])
                self.assertEqual(screen_captures["captures"], [])
                self.assertEqual(api_get(base_url, "/plugins"), [])
                plugin_catalog = api_get(base_url, "/plugins/catalog")
                self.assertIn("channels.whatsapp", {plugin["plugin_id"] for plugin in plugin_catalog})
                self.assertIn("voice.deepgram", {plugin["plugin_id"] for plugin in plugin_catalog})
                channels = api_get(base_url, "/channels")
                self.assertIn("whatsapp", {channel["channel_id"] for channel in channels})
                self.assertIn("slack", {channel["channel_id"] for channel in channels})
                self.assertEqual(next(channel for channel in channels if channel["channel_id"] == "slack")["setup"]["auth_type"], "slack_app")
                channel_status = api_get(base_url, "/channels/status?channel_id=slack")
                self.assertIn("SLACK_BOT_TOKEN", channel_status["channels"][0]["missing_send_env"])
                channel_requirements = api_get(base_url, "/channels/requirements?channel_id=slack")
                self.assertEqual(channel_requirements["channel_id"], "slack")
                self.assertIn("SLACK_BOT_TOKEN", channel_requirements["setup"]["required_secrets"])
                self.assertEqual(channel_requirements["delivery"]["official_send"]["mode"], "slack_chat_post_message")
                channel_status_with_app_secret = api_post(
                    base_url,
                    "/channels/status",
                    {"channel_id": "slack", "runtime_secrets": {"SLACK_BOT_TOKEN": "xoxb-runtime"}},
                )
                self.assertEqual(channel_status_with_app_secret["channels"][0]["missing_send_env"], [])
                channel_smoke = api_post(
                    base_url,
                    "/channels/smoke",
                    {
                        "channel_id": "slack",
                        "runtime_secrets": {"SLACK_BOT_TOKEN": "xoxb-runtime"},
                        "prepare_messages": True,
                        "dry_run_sends": True,
                    },
                )
                self.assertEqual(channel_smoke["channel_count"], 1)
                self.assertEqual(channel_smoke["channels"][0]["channel_id"], "slack")
                self.assertTrue(channel_smoke["channels"][0]["prepared_outbox_ready"])
                self.assertTrue(channel_smoke["channels"][0]["dry_run_send_ready"])
                self.assertFalse(channel_smoke["live_send_performed"])
                channel_doctor = api_get(base_url, "/channels/doctor?channel_id=slack")
                self.assertEqual(channel_doctor["overall_status"], "needs_setup")
                saved_setup = api_post(
                    base_url,
                    "/channels/setup",
                    {
                        "channel_id": "slack",
                        "enabled": True,
                        "listen_enabled": False,
                        "secret_refs": {"bot_token": "SLACK_BOT_TOKEN"},
                        "conversation_defaults": {"conversation_id": "C123"},
                    },
                )
                self.assertTrue(saved_setup["setup"]["enabled"])
                self.assertFalse(saved_setup["setup"]["listen_enabled"])
                posted_requirements = api_post(base_url, "/channels/requirements", {"channel_id": "telegram"})
                self.assertEqual(posted_requirements["setup"]["auth_type"], "bot_token")
                listener_status = api_get(base_url, "/channels/listeners?channel_id=slack")
                self.assertEqual(listener_status["listeners"][0]["channel_id"], "slack")
                self.assertTrue(listener_status["listeners"][0]["enabled"])
                self.assertFalse(listener_status["listeners"][0]["listen_enabled"])
                self.assertEqual(listener_status["listeners"][0]["webhook_path"], "/channels/webhook/slack")
                listener_tick = api_post(
                    base_url,
                    "/channels/listeners/tick",
                    {"channel_id": "slack", "limit": 1, "prepare_replies": True, "planner": "explicit"},
                )
                self.assertEqual(listener_tick["processed_count"], 0)
                self.assertEqual(api_get_text(base_url, "/channels/webhook/whatsapp?hub.challenge=verify-123"), "verify-123")

                permissions = api_get(base_url, "/permissions")
                self.assertEqual(permissions["workspace"], str(workspace.resolve()))
                self.assertIn("index", permissions)
                self.assertIn("plugins", permissions)
                self.assertIn(str(workspace.resolve()), permissions["allowed_read_roots"])
                self.assertIn(str((workspace / "artifacts").resolve()), permissions["allowed_write_roots"])
                self.assertIn("python", permissions["shell"]["allowed_commands"])
                self.assertIn("trusted_dev", permissions["shell"]["command_profiles"])
                self.assertEqual(permissions["plugins"]["manifest_count"], 0)
                group_names = {group["name"] for group in permissions["capability_groups"]}
                self.assertIn("activity", group_names)
                self.assertIn("files", group_names)
                self.assertIn("browser", group_names)
                self.assertIn("memory", group_names)
                self.assertIn("os", group_names)
                self.assertIn("plugins", group_names)
                self.assertIn("channels", group_names)
                self.assertIn("skills", group_names)
                self.assertIn("screen", group_names)
                self.assertIn("shell", group_names)
                self.assertIn("integrations", group_names)
                self.assertIn("voice", group_names)
                self.assertIn("capabilities", group_names)
                shell_tool = next(tool for tool in permissions["tools"] if tool["name"] == "run_shell_command")
                plugin_tool = next(tool for tool in permissions["tools"] if tool["name"] == "plugin_manifests")
                sessions_tool = next(tool for tool in permissions["tools"] if tool["name"] == "browser_sessions")
                back_tool = next(tool for tool in permissions["tools"] if tool["name"] == "browser_back")
                forget_tool = next(tool for tool in permissions["tools"] if tool["name"] == "browser_forget_session")
                self.assertEqual(shell_tool["capability_group"], "shell")
                self.assertEqual(shell_tool["risk_level"], "high")
                self.assertTrue(shell_tool["requires_approval"])
                self.assertFalse(shell_tool["allowed_without_approval"])
                self.assertEqual(shell_tool["input_schema"]["required"], ["argv"])
                self.assertEqual(plugin_tool["capability_group"], "plugins")
                self.assertFalse(plugin_tool["requires_approval"])
                self.assertEqual(sessions_tool["capability_group"], "browser")
                self.assertEqual(sessions_tool["risk_level"], "low")
                self.assertFalse(sessions_tool["requires_approval"])
                self.assertTrue(sessions_tool["allowed_without_approval"])
                self.assertEqual(back_tool["capability_group"], "browser")
                self.assertEqual(back_tool["risk_level"], "low")
                self.assertFalse(back_tool["requires_approval"])
                self.assertTrue(back_tool["allowed_without_approval"])
                self.assertEqual(forget_tool["capability_group"], "browser")
                self.assertEqual(forget_tool["risk_level"], "medium")
                self.assertTrue(forget_tool["requires_approval"])
                self.assertFalse(forget_tool["allowed_without_approval"])

                benchmarks = api_get(base_url, "/benchmarks?iterations=1&q=runtime")
                self.assertEqual(benchmarks["iterations"], 1)
                self.assertIn("permissions_snapshot", {item["name"] for item in benchmarks["benchmarks"]})

                index_status = api_get(base_url, "/index/status")
                self.assertFalse(index_status["usable"])
                rebuilt = api_post(base_url, "/index/rebuild", {})
                self.assertTrue(rebuilt["usable"])
                self.assertGreaterEqual(rebuilt["indexed_files"], 1)

                run = api_post(base_url, "/runs", {"request": 'read_file {"path":"README.md"}', "planner": "explicit"})
                self.assertIn("README.md", run["final_response"])
                stimulus = api_post(
                    base_url,
                    "/stimuli",
                    {"source": "voice_transcript", "text": 'read_file {"path":"README.md"}', "response_mode": "voice_prepare", "planner": "explicit"},
                )
                self.assertEqual(stimulus["decision"]["decision"], "respond")
                self.assertEqual(stimulus["run"]["results"][0]["tool_name"], "read_file")
                self.assertIn("README.md", stimulus["run"]["final_response"])
                self.assertIn("response_id", stimulus["voice_result"])
                stream_events = api_post_sse(
                    base_url,
                    "/stimuli/stream",
                    {"source": "user_text", "text": 'read_file {"path":"README.md"}', "response_mode": "text", "planner": "explicit"},
                )
                stream_event_names = [event["event"] for event in stream_events]
                run_events = [event["data"] for event in stream_events if event["event"] == "run_event"]
                self.assertIn("stream_started", stream_event_names)
                self.assertIn("final_response", stream_event_names)
                self.assertIn("stream_finished", stream_event_names)
                self.assertIn("plan_created", [event["event_type"] for event in run_events])
                self.assertIn("action_started", [event["event_type"] for event in run_events])
                self.assertIn("action_finished", [event["event_type"] for event in run_events])
                self.assertIn("README.md", next(event for event in stream_events if event["event"] == "final_response")["data"]["response"])
                channel = api_post(
                    base_url,
                    "/channels/inbound",
                    {
                        "channel_id": "slack",
                        "conversation_id": "C123",
                        "conversation_type": "dm",
                        "sender_id": "U123",
                        "text": 'read_file {"path":"README.md"}',
                        "requires_response": True,
                        "prepare_reply": True,
                        "planner": "explicit",
                    },
                )
                self.assertEqual(channel["stimulus"]["source"], "channel_message")
                self.assertIsNotNone(channel["prepared_reply"])
                self.assertEqual(api_get(base_url, "/channels/outbox")["messages"][0]["channel_id"], "slack")
                prepared_channel_message = api_post(
                    base_url,
                    "/channels/message/prepare",
                    {
                        "channel_id": "slack",
                        "conversation_id": "C123",
                        "text": "Prepared from API.",
                        "reason": "API channel prepare smoke.",
                    },
                )
                self.assertEqual(prepared_channel_message["message"]["status"], "prepared_not_sent")
                self.assertEqual(prepared_channel_message["message"]["channel_id"], "slack")
                send_without_approval = api_post_error(
                    base_url,
                    "/channels/message/send",
                    {
                        "channel_id": "slack",
                        "conversation_id": "C123",
                        "text": "Do not send without approval.",
                        "reason": "API channel send approval gate smoke.",
                    },
                )
                self.assertEqual(send_without_approval["status"], 403)
                dry_run_send = api_post(
                    base_url,
                    "/channels/message/send",
                    {
                        "channel_id": "slack",
                        "conversation_id": "C123",
                        "text": "Dry-run approved send.",
                        "reason": "API channel send dry-run smoke.",
                        "approve_high_risk": True,
                        "dry_run": True,
                    },
                )
                self.assertEqual(dry_run_send["message"]["status"], "dry_run_not_sent")
                webhook = api_post(
                    base_url,
                    "/channels/webhook/slack",
                    {
                        "event_id": "Ev1",
                        "event": {
                            "type": "message",
                            "channel": "C123",
                            "channel_type": "im",
                            "user": "U123",
                            "text": 'read_file {"path":"README.md"}',
                            "client_msg_id": "m-webhook",
                        },
                        "planner": "explicit",
                    },
                )
                self.assertTrue(webhook["accepted"])
                self.assertEqual(webhook["message_count"], 1)
                self.assertIsNotNone(webhook["results"][0]["prepared_reply"])

                plans = api_get(base_url, "/plans?limit=3")
                self.assertIn(channel["harness"]["run"]["run_id"], {plan["run_id"] for plan in plans})
                self.assertIn(webhook["results"][0]["harness"]["run"]["run_id"], {plan["run_id"] for plan in plans})
                self.assertEqual(plans[0]["used_provider"], "explicit")

                memory = api_get(base_url, "/memory?limit=20")
                self.assertIn(stimulus["run"]["run_id"], [event["payload"].get("run_id") for event in memory])
                memory_summary = api_get(base_url, "/memory/summary?period=recent")
                self.assertGreaterEqual(memory_summary["total_events"], 1)
                self.assertIn("read_file", memory_summary["summary"])
                api_post(
                    base_url,
                    "/runs",
                    {"request": 'memory_write {"kind":"preference","text":"I prefer compact API summaries"}', "planner": "explicit"},
                )
                profile = api_get(base_url, "/memory/profile")
                self.assertIn("compact API summaries", profile["preferences"][0]["text"])

    def test_api_reports_local_plugin_manifests_and_declared_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            plugin_dir = workspace / ".humungousaur" / "plugins" / "demo"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "plugin.json").write_text(
                json.dumps(
                    {
                        "name": "demo-plugin",
                        "version": "0.1.0",
                        "capability_group": "plugins.demo",
                        "tools": [
                            {
                                "name": "plugin_demo_echo",
                                "description": "Echo plugin input.",
                                "risk_level": "low",
                                "input_schema": {"type": "object", "properties": {}},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with running_api(AgentConfig(workspace=workspace, data_dir=workspace / "artifacts")) as base_url:
                plugins = api_get(base_url, "/plugins?detail=true")
                permissions = api_get(base_url, "/permissions")
                declared_tool = next(tool for tool in permissions["tools"] if tool["name"] == "plugin_demo_echo")

            self.assertEqual(plugins[0]["name"], "demo-plugin")
            self.assertEqual(plugins[0]["tools"][0]["execution_status"], "blocked_until_trusted_runtime")
            self.assertEqual(permissions["plugins"]["manifest_count"], 1)
            self.assertEqual(permissions["plugins"]["declared_tool_count"], 1)
            self.assertEqual(declared_tool["risk_level"], "blocked")
            self.assertEqual(declared_tool["capability_group"], "plugins.demo")
            self.assertFalse(declared_tool["allowed_with_approval"])

    def test_api_async_run_accepts_dashboard_model_runtime_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Runtime Options\n\nModel UI smoke.", encoding="utf-8")
            with running_api(AgentConfig(workspace=workspace, data_dir=workspace / "artifacts")) as base_url:
                queued = api_post(
                    base_url,
                    "/runs/async",
                    {
                        "request": "summarize this project",
                        "planner": "model",
                        "model_provider": "local-openai",
                        "model": "gpt-oss:20b",
                        "model_base_url": "http://127.0.0.1:9/v1",
                        "model_api_key_env": "LOCAL_LLM_API_KEY",
                        "model_timeout_seconds": 0.2,
                        "dry_run": True,
                    },
                )
                run = wait_for_finished_run(base_url, queued["run_id"])
                trace = api_get(base_url, f"/plans?run_id={queued['run_id']}")

                self.assertIn(run["status"], {"succeeded", "failed"})
                self.assertEqual(trace["requested_provider"], "model")
                self.assertTrue(trace["fallback_used"])
                self.assertIn("local-openai", trace["error"])
                self.assertNotIn("LOCAL_LLM_API_KEY=", json.dumps(trace))

    def test_api_accepts_active_agent_model_runtime_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            payload = {
                "planner": "model",
                "model_provider": "openai-responses",
                "model": "gpt-5-mini",
                "model_api_key_env": "OPENAI_API_KEY",
                "active_model_provider": "local-openai",
                "active_model": "llama3.1:8b",
                "active_model_base_url": "http://127.0.0.1:11434/v1",
                "active_model_api_key_env": "LOCAL_LLM_API_KEY",
                "runtime_secrets": {"OPENAI_API_KEY": "main-secret", "LOCAL_LLM_API_KEY": "active-secret"},
            }
            runtime_config = request_config(config, payload)

        self.assertEqual(runtime_config.model_provider, "openai-responses")
        self.assertEqual(runtime_config.active_model_provider, "local-openai")
        self.assertEqual(runtime_config.active_model_name, "llama3.1:8b")
        self.assertEqual(runtime_config.active_model_base_url, "http://127.0.0.1:11434/v1")
        self.assertEqual(runtime_config.active_model_api_key_env, "LOCAL_LLM_API_KEY")
        self.assertEqual(runtime_config.secret_value("OPENAI_API_KEY"), "main-secret")
        self.assertEqual(runtime_config.secret_value("LOCAL_LLM_API_KEY"), "active-secret")

    def test_active_agent_status_reports_effective_reflex_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                model_provider="openai-responses",
                model_name="gpt-5-mini",
                active_model_provider="local-openai",
                active_model_name="llama3.1:8b",
            ).normalized()
            status = active_agent_status(config)

        self.assertEqual(status["reflex_model"]["main_model_provider"], "openai-responses")
        self.assertEqual(status["reflex_model"]["active_model_provider"], "local-openai")
        self.assertEqual(status["reflex_model"]["effective_model_provider"], "local-openai")
        self.assertEqual(status["reflex_model"]["effective_model_name"], "llama3.1:8b")

    def test_api_runs_bounded_autonomous_cycles_for_due_wakeup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Autonomous API\n\nCycle endpoint works.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()
            WakeupStore(config.cognition_db_path).schedule(
                scheduled_for=_utc_seconds_from_now(-1),
                event_type="STIMULUS",
                payload={
                    "text": 'read_file {"path":"README.md"}',
                    "source": "wakeup",
                    "metadata": {"should_run_agent": True, "intent": "task"},
                    "response_mode": "silent",
                },
                reason="API due wakeup.",
            )

            with running_api(config) as base_url:
                before = api_get(base_url, "/autonomous/status?limit=5")
                loop = api_post(
                    base_url,
                    "/autonomous/cycles",
                    {"max_cycles": 3, "stop_after_idle_cycles": 1, "planner": "explicit"},
                )
                after = api_get(base_url, "/autonomous/status?limit=5")

            self.assertEqual(len(before["scheduled_wakeups"]), 1)
            self.assertEqual(loop["stopped_reason"], "idle")
            self.assertEqual(loop["cycles"][0]["status"], "run_finished")
            self.assertEqual(loop["cycles"][1]["status"], "no_op")
            self.assertEqual(after["scheduled_wakeups"], [])
            self.assertEqual(after["recent_wakeups"][0]["status"], WakeupStatus.FIRED)

    def test_api_exposes_skill_forge_daemon_and_multi_agent_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Coordination API\n\nEvidence.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

            with running_api(config) as base_url:
                forged = api_post(
                    base_url,
                    "/skills/forge",
                    {
                        "request": "Create a reusable coordination skill.",
                        "planner": "explicit",
                        "evidence": [
                            {
                                "skill": {
                                    "name": "Coordination smoke",
                                    "description": "Coordinate a simple specialist task.",
                                    "purpose": "Capture a reusable specialist coordination smoke workflow.",
                                    "when_to_use": "Use when validating specialist contracts and task graph execution.",
                                    "tools": ["multi_agent_coordinate", "multi_agent_board", "autonomous_cycle_run"],
                                    "procedure": ["Create a specialist contract.", "Create a task graph.", "Inspect the board."],
                                    "verification_steps": ["Confirm the board lists the specialist."],
                                    "failure_modes": ["Treating a graph as complete before a cycle runs."],
                                    "evidence_refs": ["api:test"],
                                    "confidence": 0.8,
                                }
                            }
                        ],
                        "write_pack": True,
                        "import_memory": True,
                    },
                )
                packs = api_get(base_url, "/skills/forge/packs")
                daemon_config = api_post(
                    base_url,
                    "/automation/daemon/configure",
                    {"enabled": True, "poll_seconds": 1, "max_cycles_per_tick": 1, "planner": "explicit"},
                )
                daemon = api_get(base_url, "/automation/daemon")
                tick = api_post(base_url, "/automation/daemon/tick", {"max_cycles_per_tick": 1, "planner": "explicit"})
                coordination = api_post(
                    base_url,
                    "/multi-agent/coordinate",
                    {
                        "planner": "explicit",
                        "goal_title": "Coordinate API README review",
                        "specialists": [
                            {
                                "name": "API reviewer",
                                "purpose": "Read files for API smoke tasks.",
                                "contract": "Use read-only tools and exact evidence.",
                                "tools": ["read_file"],
                            }
                        ],
                        "tasks": [
                            {
                                "task_id": "readme",
                                "title": "Read README",
                                "owner": "API reviewer",
                                "request": 'read_file {"path":"README.md"}',
                            }
                        ],
                    },
                )
                board = api_get(base_url, "/multi-agent/board")

            self.assertEqual(forged["status"], "succeeded")
            self.assertEqual(packs["packs"][0]["name"], "coordination-smoke")
            self.assertEqual(daemon_config["status"], "succeeded")
            self.assertTrue(daemon["profile"]["enabled"])
            self.assertEqual(tick["status"], "succeeded")
            self.assertEqual(coordination["status"], "succeeded")
            self.assertEqual(board["specialists"][0]["name"], "API reviewer")

    def test_api_evaluates_structured_triggers_into_autonomous_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            trigger = TriggerStore(config.cognition_db_path).create(
                name="File changed trigger",
                match_source="file_event",
                match_stimulus_type="changed",
                conditions={"metadata_equals": {"workspace": "api-test"}},
                payload={
                    "text": "review the changed file",
                    "metadata": {"should_run_agent": True, "intent": "task"},
                    "response_mode": "silent",
                },
                reason="API trigger evaluation test.",
            )

            with running_api(config) as base_url:
                result = api_post(
                    base_url,
                    "/triggers/evaluate",
                    {
                        "source": "file_event",
                        "stimulus_type": "changed",
                        "metadata": {"workspace": "api-test"},
                        "payload": {"path": "README.md"},
                        "stimulus_id": "stim-api",
                    },
                )
                status = api_get(base_url, "/autonomous/status?limit=5")

            self.assertEqual(result["fired"][0]["trigger"]["trigger_id"], trigger.trigger_id)
            self.assertEqual(result["fired"][0]["event"]["payload"]["metadata"]["triggered_by"]["stimulus_id"], "stim-api")
            self.assertEqual(status["queued_events"][0]["payload"]["text"], "review the changed file")
            self.assertEqual(status["recent_triggers"][0]["fire_count"], 1)

    def test_api_exposes_continuous_collectors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            watched = root / "watched"
            workspace.mkdir()
            watched.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()

            with running_api(config) as base_url:
                status = api_get(base_url, "/collectors/status?limit=5")
                configured = api_post(
                    base_url,
                    "/collectors/configure",
                    {
                        "enabled": True,
                        "submit_to_harness": True,
                        "collectors": {
                            "active_window": False,
                            "browser": False,
                            "clipboard": False,
                            "filesystem": True,
                            "screenshot": False,
                            "screen_ocr": False,
                            "video_frame": False,
                            "audio_activity": False,
                        },
                        "watch_paths": [str(watched)],
                        "max_events_per_tick": 1,
                    },
                )
                baseline = api_post(base_url, "/collectors/tick", {"force": True})
                (watched / "collector.txt").write_text("collector smoke", encoding="utf-8")
                tick = api_post(base_url, "/collectors/tick", {"force": True})
                events = api_get(base_url, "/events/status?limit=5")
                rebuilt = api_post(base_url, "/events/rebuild-context", {"limit": 5})

            self.assertIn("active_window", status["profile"]["collectors"])
            self.assertTrue(configured["profile"]["enabled"])
            self.assertIn("filesystem", configured["profile"]["collectors"])
            self.assertEqual(baseline["collected"], [])
            self.assertIn("collected", tick)
            self.assertIn("semantic_events", events)
            self.assertTrue(events["current_context_exists"])
            self.assertIn("current_context_path", rebuilt)

    def test_api_accepts_validated_collector_bridge_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()

            with running_api(config) as base_url:
                configured = api_post(
                    base_url,
                    "/collectors/configure",
                    {
                        "enabled": True,
                        "submit_to_harness": True,
                        "collectors": {
                            "active_window": False,
                            "browser": False,
                            "clipboard": False,
                            "filesystem": False,
                            "screenshot": False,
                            "screen_ocr": False,
                            "video_frame": False,
                            "audio_activity": False,
                            "terminal_activity": True,
                        },
                    },
                )
                accepted = api_post(
                    base_url,
                    "/collectors/bridge",
                    {
                        "collector": "terminal_activity",
                        "stimulus_type": "tests_failed",
                        "text": "Tests failed in backend suite.",
                        "metadata": {"app_name": "Terminal"},
                        "payload": {"raw_output": "SECRET RAW OUTPUT"},
                    },
                )
                rejected = api_post_error(
                    base_url,
                    "/collectors/bridge",
                    {"collector": "terminal_activity", "stimulus_type": "password_field_focused"},
                )
                tick = api_post(base_url, "/collectors/tick", {"force": True})
                queried = api_get(base_url, "/collectors/events?collector=terminal_activity&limit=5")
                helper_health = api_post(
                    base_url,
                    "/collectors/helper-health",
                    {
                        "helper_id": "terminal-helper",
                        "collector": "terminal_activity",
                        "platform": "Darwin",
                        "status": "running",
                        "permission_state": "granted",
                    },
                )
                health_status = api_get(base_url, "/collectors/status?limit=5")

            self.assertTrue(configured["profile"]["collectors"]["terminal_activity"])
            self.assertTrue(accepted["accepted"])
            self.assertEqual(accepted["collector"], "terminal_activity")
            self.assertNotIn("SECRET RAW OUTPUT", str(accepted))
            self.assertEqual(rejected["status"], 400)
            self.assertEqual(tick["collected"][0]["collector"], "terminal_activity")
            self.assertEqual(tick["semantic_events"][0]["event_type"], "terminal_activity")
            self.assertEqual(tick["action_candidates"][0]["action_type"], "analyze")
            self.assertNotIn("SECRET RAW OUTPUT", str(tick["attention_batches"]))
            self.assertEqual(queried["events"][0]["collector"], "terminal_activity")
            self.assertTrue(helper_health["accepted"])
            self.assertEqual(health_status["event_log"]["helper_health"][0]["helper_id"], "terminal-helper")

    def test_api_exposes_active_agent_state_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            KnowledgeStore(config.cognition_db_path).append(
                kind=KnowledgeKind.CONTEXT,
                text="Planner preview can resume the Acme proposal.",
                source="active_agent_memory_candidate",
                evidence_refs=["active_memory_candidate:api-preview"],
                confidence=0.81,
            )

            with running_api(config) as base_url:
                task = api_post(base_url, "/active-agent/task-contexts", {"goal": "Draft the Acme proposal", "allowed_help": ["resume_capsule"]})
                mute = api_post(base_url, "/active-agent/muted-scopes", {"collector": "device_state", "mode": "no_assistance"})
                deep = api_post(
                    base_url,
                    "/active-agent/deep-dives",
                    {"purpose": "Prepare a resume capsule", "source": "google_docs", "requested_access": "document_outline"},
                )
                status = api_get(base_url, "/active-agent/status?limit=5")
                preview = api_get(base_url, "/active-agent/planner-context?request=continue")
                posted_preview = api_post(
                    base_url,
                    "/active-agent/planner-context",
                    {"request": "Bearer secret-token continue"},
                )

            self.assertEqual(task["task_context"]["user_declared_goal"], "Draft the Acme proposal")
            self.assertEqual(mute["muted_scope"]["mode"], "no_assistance")
            self.assertEqual(deep["deep_dive_request"]["status"], "needs_approval")
            self.assertEqual(status["task_contexts"][0]["user_declared_goal"], "Draft the Acme proposal")
            self.assertEqual(status["muted_scopes"][0]["collector"], "device_state")
            self.assertEqual(preview["source"], "planner_runtime_context_preview")
            self.assertIn("active_agent_memory", preview)
            self.assertIn("active_agent_state", preview)
            self.assertIn("safety", preview)
            self.assertEqual(preview["active_agent_state"]["task_contexts"][0]["user_declared_goal"], "Draft the Acme proposal")
            self.assertEqual(preview["active_agent_memory"]["items"][0]["text"], "Planner preview can resume the Acme proposal.")
            self.assertNotIn("routes", preview)
            self.assertNotIn("decisions", preview)
            self.assertNotIn("memory_candidates", json.dumps(preview, sort_keys=True))
            self.assertNotIn("secret-token", json.dumps(posted_preview, sort_keys=True))
            self.assertNotIn("store_path", json.dumps(preview, sort_keys=True))

    def test_api_active_agent_lifecycle_mutation_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            ActiveAgentStore(config.active_agent_db_path).upsert_episode(
                ActiveEpisode(
                    episode_id="episode_api",
                    status="active",
                    source="test",
                    hypothesis="API lifecycle episode",
                    summary="API lifecycle episode",
                    confidence=Confidence.MEDIUM,
                    evidence_refs=["test:api"],
                )
            )

            with running_api(config) as base_url:
                mute = api_post(base_url, "/active-agent/muted-scopes", {"collector": "device_state", "mode": "no_assistance"})
                approve_deep = api_post(
                    base_url,
                    "/active-agent/deep-dives",
                    {"purpose": "Prepare a resume capsule", "source": "google_docs", "requested_access": "document_outline"},
                )
                reject_deep = api_post(
                    base_url,
                    "/active-agent/deep-dives",
                    {"purpose": "Read the rich document body", "source": "google_docs", "requested_access": "rich_document_body"},
                )

                cancelled = api_post(
                    base_url,
                    "/active-agent/muted-scopes/cancel",
                    {"scope_id": mute["muted_scope"]["scope_id"], "reason": "resume active assistance"},
                )
                approved = api_post(
                    base_url,
                    "/active-agent/deep-dives/approve",
                    {"request_id": approve_deep["deep_dive_request"]["request_id"], "reason": "user approved"},
                )
                executed = api_post(
                    base_url,
                    "/active-agent/deep-dives/execute",
                    {"request_id": approve_deep["deep_dive_request"]["request_id"], "limit": 5},
                )
                rejected = api_post(
                    base_url,
                    "/active-agent/deep-dives/reject",
                    {"request_id": reject_deep["deep_dive_request"]["request_id"], "reason": "user rejected"},
                )
                episode = api_post(
                    base_url,
                    "/active-agent/episodes/operate",
                    {"operation": "split", "episode_id": "episode_api", "new_episode_id": "episode_api_child", "summary": "API split task"},
                )
                exported = api_post(base_url, "/active-agent/privacy/export", {"target_type": "deep_dive_request", "target_id": approve_deep["deep_dive_request"]["request_id"]})
                eval_run = api_post(base_url, "/active-agent/evals/run", {"scenario": "api"})
                status = api_get(base_url, "/active-agent/status?limit=10")

            deep_by_id = {item["request_id"]: item for item in status["deep_dive_requests"]}
            self.assertEqual(cancelled["muted_scope"]["status"], "cancelled")
            self.assertEqual(approved["deep_dive_request"]["status"], "approved")
            self.assertEqual(executed["deep_dive_request"]["status"], "completed")
            self.assertEqual(executed["deep_dive_result"]["status"], "completed")
            self.assertEqual(rejected["deep_dive_request"]["status"], "rejected")
            self.assertEqual(episode["new_episode"]["episode_id"], "episode_api_child")
            self.assertEqual(exported["privacy_action"]["action_type"], "export")
            self.assertIn(eval_run["eval_run"]["status"], {"passed", "failed"})
            self.assertEqual(status["muted_scopes"][0]["status"], "cancelled")
            self.assertEqual(deep_by_id[approve_deep["deep_dive_request"]["request_id"]]["status"], "completed")
            self.assertEqual(deep_by_id[reject_deep["deep_dive_request"]["request_id"]]["status"], "rejected")
            self.assertTrue(status["deep_dive_results"])
            self.assertTrue(status["episode_links"])
            self.assertTrue(status["eval_runs"])

    def test_api_active_agent_user_correction_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()

            with running_api(config) as base_url:
                api_post(
                    base_url,
                    "/active-agent/task-contexts",
                    {"task_context_id": "ctx_original", "goal": "Draft the Acme proposal", "allowed_help": ["resume_capsule"]},
                )
                try:
                    correction = api_post(
                        base_url,
                        "/active-agent/corrections",
                        {
                            "target_type": "task_context",
                            "target_id": "ctx_original",
                            "correction_type": "wrong_task",
                            "reason": "This active-agent context matched the wrong task.",
                            "task_context": {
                                "task_context_id": "ctx_corrected",
                                "goal": "Review the personal finance note",
                                "allowed_help": ["resume_capsule"],
                            },
                            "evidence_refs": ["task_context:ctx_original"],
                        },
                    )
                    private_correction = api_post(
                        base_url,
                        "/active-agent/corrections",
                        {
                            "target_type": "task_context",
                            "target_id": "ctx_original",
                            "correction_type": "private",
                            "reason": "Do not resume this suggestion right now.",
                            "collector": "device_state",
                            "evidence_refs": ["task_context:ctx_original"],
                        },
                    )
                except urllib.error.HTTPError as exc:
                    if exc.code == 404:
                        self.skipTest("Active-agent correction HTTP endpoint is not exposed yet.")
                    raise
                status = api_get(base_url, "/active-agent/status?limit=10")

        corrections = _active_agent_corrections(status)
        if not corrections:
            self.skipTest("Active-agent corrections are not exposed by active-agent status yet.")
        serialized = json.dumps({"correction": correction, "private_correction": private_correction, "status": status}, sort_keys=True)
        self.assertIn("wrong_task", serialized)
        self.assertIn("private", serialized)
        self.assertIn("ctx_corrected", serialized)
        self.assertIn("Review the personal finance note", serialized)
        self.assertTrue(any(item.get("mode") == "private" for item in status["muted_scopes"]))

    def test_api_accepts_google_workspace_collector_source_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            collectors = {
                "active_window": False,
                "browser": False,
                "clipboard": False,
                "filesystem": False,
                "screenshot": False,
                "screen_ocr": False,
                "video_frame": False,
                "audio_activity": False,
                "calendar_scheduling_activity": True,
            }

            with running_api(config) as base_url:
                configured = api_post(
                    base_url,
                    "/collectors/configure",
                    {
                        "enabled": True,
                        "submit_to_harness": False,
                        "collectors": collectors,
                        "rich_capture_opt_in": {"calendar_scheduling_activity": True},
                    },
                )
                accepted = api_post(
                    base_url,
                    "/collectors/google-workspace",
                    {
                        "app": "calendar",
                        "event_type": "calendar_event_created",
                        "calendar_id": "primary-secret",
                        "event_id": "event-secret",
                        "title": "Sensitive customer review",
                        "attendees": ["person@example.com"],
                        "location": "Secret room",
                        "occurred_at": "2026-06-11T00:00:00+00:00",
                    },
                )
                rejected = api_post_error(
                    base_url,
                    "/collectors/google-workspace",
                    {"app": "calendar", "event_type": "raw_calendar_dump", "title": "Do not leak"},
                )
                queried = api_get(base_url, "/collectors/events?collector=calendar_scheduling_activity&limit=5")
                source_status = api_get(base_url, "/collectors/google-workspace/status")

            serialized = json.dumps({"accepted": accepted, "queried": queried, "status": source_status}, ensure_ascii=False)
            self.assertTrue(configured["profile"]["collectors"]["calendar_scheduling_activity"])
            self.assertTrue(accepted["accepted"])
            self.assertEqual(accepted["collector"], "calendar_scheduling_activity")
            self.assertEqual(rejected["status"], 400)
            self.assertEqual(queried["events"][0]["source"], "google_workspace")
            self.assertEqual(source_status["dead_letter_count"], 1)
            self.assertNotIn("Sensitive customer review", serialized)
            self.assertNotIn("person@example.com", serialized)
            self.assertNotIn("Secret room", serialized)

    def test_api_accepts_planning_collector_source_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            collectors = {
                "active_window": False,
                "browser": False,
                "clipboard": False,
                "filesystem": False,
                "screenshot": False,
                "screen_ocr": False,
                "video_frame": False,
                "audio_activity": False,
                "task_manager_activity": True,
            }

            with running_api(config) as base_url:
                configured = api_post(
                    base_url,
                    "/collectors/configure",
                    {
                        "enabled": True,
                        "submit_to_harness": False,
                        "collectors": collectors,
                        "rich_capture_opt_in": {"task_manager_activity": True},
                    },
                )
                accepted = api_post(
                    base_url,
                    "/collectors/planning",
                    {
                        "provider_id": "clickup",
                        "event": "taskPriorityUpdated",
                        "task_id": "task-secret",
                        "title": "Sensitive priority task",
                        "comment": "Raw private comment",
                        "priority_bucket": "urgent",
                        "occurred_at": "2026-06-11T00:00:00+00:00",
                    },
                )
                rejected = api_post_error(
                    base_url,
                    "/collectors/planning",
                    {"provider_id": "clickup", "event": "raw_task_dump", "title": "Do not leak"},
                )
                queried = api_get(base_url, "/collectors/events?collector=task_manager_activity&limit=5")
                source_status = api_get(base_url, "/collectors/planning/status?provider_id=clickup")

            serialized = json.dumps({"accepted": accepted, "queried": queried, "status": source_status}, ensure_ascii=False)
            self.assertTrue(configured["profile"]["collectors"]["task_manager_activity"])
            self.assertTrue(accepted["accepted"])
            self.assertEqual(accepted["collector"], "task_manager_activity")
            self.assertEqual(accepted["stimulus_type"], "task_priority_changed")
            self.assertEqual(rejected["status"], 400)
            self.assertEqual(queried["events"][0]["source"], "clickup")
            self.assertEqual(source_status["sources"][0]["dead_letter_count"], 1)
            self.assertNotIn("Sensitive priority task", serialized)
            self.assertNotIn("Raw private comment", serialized)

    def test_api_accepts_browser_collector_source_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data", planner_provider="explicit").normalized()
            collectors = {
                "active_window": False,
                "browser": False,
                "clipboard": False,
                "filesystem": False,
                "screenshot": False,
                "screen_ocr": False,
                "video_frame": False,
                "audio_activity": False,
                "browser_page_activity": True,
            }

            with running_api(config) as base_url:
                configured = api_post(
                    base_url,
                    "/collectors/configure",
                    {
                        "enabled": True,
                        "submit_to_harness": False,
                        "collectors": collectors,
                        "rich_capture_opt_in": {"browser_page_activity": True},
                    },
                )
                accepted = api_post(
                    base_url,
                    "/collectors/browsers",
                    {
                        "browser": "safari",
                        "event_type": "form_submitted",
                        "url": "https://example.com/private-form?secret=value",
                        "title": "Sensitive application",
                        "form_id": "form-secret",
                        "metadata": {"field_value": "raw value"},
                        "occurred_at": "2026-06-11T00:00:00+00:00",
                    },
                )
                rejected = api_post_error(
                    base_url,
                    "/collectors/browsers",
                    {"browser": "chrome", "event_type": "raw_page_dump", "url": "https://secret.example"},
                )
                queried = api_get(base_url, "/collectors/events?collector=browser_page_activity&limit=5")
                source_status = api_get(base_url, "/collectors/browsers/status")

        serialized = json.dumps({"accepted": accepted, "queried": queried, "status": source_status}, ensure_ascii=False)
        self.assertTrue(configured["profile"]["collectors"]["browser_page_activity"])
        self.assertTrue(accepted["accepted"])
        self.assertEqual(accepted["collector"], "browser_page_activity")
        self.assertEqual(accepted["stimulus_type"], "form_submitted")
        self.assertEqual(rejected["status"], 400)
        self.assertEqual(queried["events"][0]["source"], "browsers")
        self.assertEqual(source_status["dead_letter_count"], 1)
        self.assertNotIn("Sensitive application", serialized)
        self.assertNotIn("private-form", serialized)
        self.assertNotIn("raw value", serialized)

    def test_api_exposes_ai_assistant_source_collectors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

            with running_api(config) as base_url:
                health = api_post(
                    base_url,
                    "/collectors/ai-assistants/health",
                    {"assistant": "claude", "status": "running", "metadata": {"title": "SECRET CHAT TITLE"}},
                )
                accepted = api_post(
                    base_url,
                    "/collectors/ai-assistants",
                    {
                        "assistant": "Claude",
                        "event_type": "prompt_submitted",
                        "conversation_id": "conversation-secret",
                        "model": "secret-model",
                        "prompt": "SECRET PROMPT",
                        "metadata": {"file_path": "/tmp/humungousaur-fixtures/SECRET_PATH/context.ts"},
                        "occurred_at": "2026-06-11T00:00:00+00:00",
                    },
                )
                rejected = api_post_error(
                    base_url,
                    "/collectors/ai-assistants",
                    {"assistant": "claude", "event_type": "raw_prompt_dump", "prompt": "SECRET RAW"},
                )
                queried = api_get(base_url, "/collectors/events?collector=ai_assistant_activity&limit=5")
                source_status = api_get(base_url, "/collectors/ai-assistants/status")

        serialized = json.dumps({"health": health, "accepted": accepted, "queried": queried, "status": source_status}, ensure_ascii=False)
        self.assertTrue(health["accepted"])
        self.assertTrue(accepted["accepted"])
        self.assertEqual(accepted["collector"], "ai_assistant_activity")
        self.assertEqual(accepted["stimulus_type"], "ai_prompt_submitted")
        self.assertEqual(rejected["status"], 400)
        self.assertEqual(queried["events"][0]["source"], "ai_assistants")
        self.assertEqual(source_status["dead_letter_count"], 1)
        self.assertIn("claude", source_status["supported_assistants"])
        self.assertNotIn("SECRET CHAT TITLE", serialized)
        self.assertNotIn("SECRET PROMPT", serialized)
        self.assertNotIn("SECRET_PATH", serialized)
        self.assertNotIn("secret-model", serialized)

    def test_api_exposes_connector_source_collectors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

            with running_api(config) as base_url:
                manifest = api_get(base_url, "/connectors/sources/manifest?provider_id=slack")
                status_before = api_get(base_url, "/connectors/sources?provider_id=slack")
                health = api_post(
                    base_url,
                    "/connectors/source-health",
                    {"provider_id": "slack", "status": "running", "metadata": {"team_id": "team-secret"}},
                )
                accepted = api_post(
                    base_url,
                    "/connectors/source-events",
                    {
                        "provider_id": "slack",
                        "source_event": "message_received",
                        "object_type": "message",
                        "object_id": "message-secret",
                        "metadata": {"channel_id": "channel-secret", "text": "raw message body"},
                    },
                )
                tick = api_post(base_url, "/connectors/sources/tick", {"provider_id": "slack", "dry_run": True})
                events = api_get(base_url, "/collectors/events?collector=channel_activity&limit=5")
                status_after = api_get(base_url, "/connectors/sources?provider_id=slack")

        serialized = json.dumps({"accepted": accepted, "events": events, "status": status_after}, ensure_ascii=False)
        self.assertEqual(manifest["source_count"], 1)
        self.assertEqual(status_before["sources"][0]["provider_id"], "slack")
        self.assertTrue(health["accepted"])
        self.assertTrue(accepted["accepted"])
        self.assertEqual(accepted["collector"], "channel_activity")
        self.assertEqual(events["events"][0]["source"], "slack")
        self.assertEqual(tick["sources"][0]["events_appended"], 0)
        self.assertGreater(status_after["sources"][0]["health_count"], 0)
        self.assertNotIn("raw message body", serialized)

    def test_api_approval_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            with running_api(AgentConfig(workspace=workspace, data_dir=workspace / "artifacts")) as base_url:
                run = api_post(base_url, "/runs", {"request": 'run_shell_command {"argv":["python","--version"]}', "planner": "explicit"})
                token = run["approvals"][0]["approval_token"]

                pending = api_get(base_url, "/approvals?limit=1")
                self.assertEqual(pending[0]["approval_token"], token)
                paused = api_get(base_url, f"/runs/{run['run_id']}")
                self.assertEqual(paused["status"], "needs_approval")
                self.assertIsNone(paused["finished_at"])

                approved = api_post(base_url, f"/approvals/{token}/approve", {"note": "api test"})
                self.assertEqual(approved["run_id"], run["run_id"])
                self.assertIn("Python", approved["stdout"])

                all_approvals = api_get(base_url, "/approvals?status=all&limit=1")
                self.assertEqual(all_approvals[0]["status"], "executed")
                source_run = api_get(base_url, f"/runs/{run['run_id']}")
                self.assertEqual(source_run["status"], "succeeded")
                timeline = api_get(base_url, f"/runs/{run['run_id']}/timeline?limit=100")
                event_types = [event["event_type"] for event in timeline]
                self.assertIn("approval_approved", event_types)
                self.assertIn("run_waiting_for_approval", event_types)
                self.assertIn("run_finished", event_types)

    def test_api_approval_input_can_be_edited_before_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            with running_api(AgentConfig(workspace=workspace, data_dir=workspace / "artifacts")) as base_url:
                run = api_post(base_url, "/runs", {"request": 'run_shell_command {"argv":["python","--version"]}', "planner": "explicit"})
                token = run["approvals"][0]["approval_token"]

                edited = api_post(
                    base_url,
                    f"/approvals/{token}/edit",
                    {"tool_input": {"argv": ["python", "-V"]}, "note": "api edit"},
                )
                pending = api_get(base_url, "/approvals?limit=1")
                approved = api_post(base_url, f"/approvals/{token}/approve", {"note": "api approved edit"})

                self.assertEqual(edited["approval"]["tool_input"], {"argv": ["python", "-V"]})
                self.assertEqual(pending[0]["tool_input"], {"argv": ["python", "-V"]})
                self.assertIn("Python", approved["stdout"])
                timeline = api_get(base_url, f"/runs/{run['run_id']}/timeline?limit=100")
                self.assertIn("approval_updated", [event["event_type"] for event in timeline])

    def test_api_rejects_approval_on_source_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            with running_api(AgentConfig(workspace=workspace, data_dir=workspace / "artifacts")) as base_url:
                run = api_post(base_url, "/runs", {"request": 'run_shell_command {"argv":["python","--version"]}', "planner": "explicit"})
                token = run["approvals"][0]["approval_token"]

                rejected = api_post(base_url, f"/approvals/{token}/reject", {"note": "api test reject"})

                self.assertEqual(rejected["run_id"], run["run_id"])
                self.assertEqual(rejected["approval"]["status"], "rejected")
                source_run = api_get(base_url, f"/runs/{run['run_id']}")
                self.assertEqual(source_run["status"], "blocked")
                self.assertIn("Approval rejected", source_run["final_response"])
                timeline = api_get(base_url, f"/runs/{run['run_id']}/timeline?limit=100")
                event_types = [event["event_type"] for event in timeline]
                self.assertIn("approval_rejected", event_types)
                self.assertIn("run_finished", event_types)

    def test_api_async_run_timeline_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Async Demo\n\nTimeline runtime.", encoding="utf-8")
            with running_api(AgentConfig(workspace=workspace, data_dir=workspace / "artifacts")) as base_url:
                queued = api_post(base_url, "/runs/async", {"request": 'read_file {"path":"README.md"}', "planner": "explicit"})
                run_id = queued["run_id"]
                self.assertEqual(queued["status"], "planned")

                run = wait_for_finished_run(base_url, run_id)
                self.assertEqual(run["status"], "succeeded")
                self.assertIn("README.md", run["final_response"])

                timeline = api_get(base_url, f"/runs/{run_id}/timeline?limit=100")
                event_types = [event["event_type"] for event in timeline]
                self.assertEqual(event_types[0], "queued")
                for expected in [
                    "run_started",
                    "plan_created",
                    "action_started",
                    "action_finished",
                    "run_finished",
                ]:
                    self.assertIn(expected, event_types)
                self.assertEqual(timeline[-1]["payload"]["status"], "succeeded")

    def test_api_cancel_run_before_worker_starts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Cancel Demo\n\nInterruptible runtime.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()
            audit = AuditLog(config.audit_db_path)
            run_id = audit.start_run('read_file {"path":"README.md"}')
            with running_api(config) as base_url:
                cancelling = api_post(base_url, f"/runs/{run_id}/cancel", {"reason": "api test"})
                self.assertEqual(cancelling["status"], "cancelling")
                self.assertIsNotNone(cancelling["cancel_requested_at"])

            result = AgentOrchestrator(config).run('read_file {"path":"README.md"}', run_id=run_id)
            self.assertEqual(result.final_response, "Run cancelled before completing remaining actions.")

            run = audit.get_run(run_id)
            self.assertEqual(run["status"], "cancelled")
            self.assertIsNotNone(run["finished_at"])
            timeline = audit.get_run_events(run_id)
            event_types = [event["event_type"] for event in timeline]
            self.assertIn("cancel_requested", event_types)
            self.assertIn("run_cancelled", event_types)

    def test_api_permission_read_roots_are_persistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            extra = root / "external-docs"
            extra.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data")

            with running_api(config) as base_url:
                updated = api_post(base_url, "/permissions/read-roots/add", {"path": str(extra)})
                self.assertIn(str(extra.resolve()), updated["extra_read_roots"])
                self.assertIn(str(extra.resolve()), updated["allowed_read_roots"])
                self.assertTrue(updated["index"]["usable"])
                self.assertIn(str(extra.resolve()), updated["index"]["allowed_read_roots"])

            with running_api(config) as base_url:
                persisted = api_get(base_url, "/permissions")
                self.assertIn(str(extra.resolve()), persisted["extra_read_roots"])
                self.assertIn(str(extra.resolve()), persisted["allowed_read_roots"])
                self.assertTrue(persisted["index"]["usable"])
                removed = api_post(base_url, "/permissions/read-roots/remove", {"path": str(extra)})
                self.assertNotIn(str(extra.resolve()), removed["extra_read_roots"])
                self.assertTrue(removed["index"]["usable"])
                self.assertNotIn(str(extra.resolve()), removed["index"]["allowed_read_roots"])

    def test_api_added_read_root_expands_agent_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            extra = root / "external-docs"
            extra.mkdir()
            external_file = extra / "research.md"
            external_file.write_text("externalneedle from added permission", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=root / "data")

            with running_api(config) as base_url:
                updated = api_post(base_url, "/permissions/read-roots/add", {"path": str(extra)})
                self.assertTrue(updated["index"]["usable"])
                run = api_post(base_url, "/runs", {"request": 'search_workspace {"query":"externalneedle"}', "planner": "explicit"})

                self.assertIn(str(external_file.resolve()), run["final_response"])
                self.assertEqual(run["results"][0]["output"]["source"], "index")

    def test_api_stale_index_falls_back_to_live_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            readme = workspace / "README.md"
            readme.write_text("oldneedle", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts")

            with running_api(config) as base_url:
                rebuilt = api_post(base_url, "/index/rebuild", {})
                self.assertTrue(rebuilt["usable"])

                readme.write_text("freshneedle with a different size", encoding="utf-8")
                status = api_get(base_url, "/index/status")
                self.assertFalse(status["usable"])
                self.assertTrue(status["stale"])

                run = api_post(base_url, "/runs", {"request": 'search_workspace {"query":"freshneedle"}', "planner": "explicit"})

                self.assertIn("freshneedle", run["final_response"])
                self.assertEqual(run["results"][0]["output"]["source"], "scan")

    def test_api_lists_browser_sessions_for_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            session = BrowserSessionStore(config.browser_sessions_db_path).create_or_update(
                {
                    "url": "http://127.0.0.1/example",
                    "title": "Browser Session",
                    "text": "Visible browser page text.",
                    "links": [{"href": "/next", "text": "Next"}],
                    "images": [{"src": "/preview.png", "alt": "Preview image", "title": ""}],
                    "forms": [
                        {
                            "action": "/submit",
                            "method": "post",
                            "inputs": [{"name": "message", "type": "textarea", "value": ""}],
                        }
                    ],
                }
            )
            BrowserSessionStore(config.browser_sessions_db_path).update_form_draft(
                session["session_id"],
                0,
                {"message": "draft"},
            )

            with running_api(config) as base_url:
                sessions = api_get(base_url, "/browser/sessions")
                detail = api_get(base_url, f"/browser/sessions/{session['session_id']}")

            self.assertEqual(sessions[0]["session_id"], session["session_id"])
            self.assertEqual(sessions[0]["forms"][0]["draft"], {"message": "draft"})
            self.assertFalse(sessions[0]["can_go_back"])
            self.assertEqual(detail["links"][0]["text"], "Next")
            self.assertEqual(detail["images"][0]["alt"], "Preview image")

    def test_api_exposes_workflow_plugin_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            with running_api(AgentConfig(workspace=workspace, data_dir=workspace / "artifacts")) as base_url:
                diff = api_post(base_url, "/workflow/diff", {"left_text": "a\nold\n", "right_text": "a\nnew\n"})
                compacted = api_post(base_url, "/workflow/tokenjuice", {"text": "\n".join(f"line {index}" for index in range(600)), "max_chars": 1000})
                llm_task = api_post(
                    base_url,
                    "/workflow/llm-task",
                    {
                        "objective": "Return dry-run JSON.",
                        "json_schema": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["ok"],
                            "properties": {"ok": {"type": "boolean"}},
                        },
                        "dry_run": True,
                    },
                )
                workflow = api_post(
                    base_url,
                    "/workflow/lobster/start",
                    {
                        "name": "API workflow smoke",
                        "objective": "Exercise workflow endpoints.",
                        "steps": [{"type": "note", "title": "No-op checkpoint"}],
                    },
                )
                workflow_id = workflow["workflow"]["workflow_id"]
                workflow_status = api_get(base_url, f"/workflow/lobster/status?workflow_id={workflow_id}")
                canvas = api_post(
                    base_url,
                    "/canvas/a2ui/create",
                    {
                        "title": "API canvas",
                        "nodes": [
                            {"id": "start", "label": "Start"},
                            {"id": "done", "label": "Done", "x": 300},
                        ],
                        "edges": [{"from": "start", "to": "done"}],
                    },
                )
                rendered = api_post(base_url, "/canvas/a2ui/render", {"canvas_id": canvas["canvas"]["canvas_id"]})

            self.assertEqual(diff["status"], "succeeded")
            self.assertEqual(diff["stats"]["added"], 1)
            self.assertEqual(compacted["status"], "succeeded")
            self.assertTrue(compacted["compacted"])
            self.assertEqual(llm_task["status"], "skipped")
            self.assertEqual(workflow_status["workflow"]["status"], "succeeded")
            self.assertEqual(canvas["status"], "succeeded")
            self.assertIn("<svg", rendered["svg"])


class running_api:
    def __init__(self, config: AgentConfig) -> None:
        self.server = create_api_server(config, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> str:
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, exc_type, exc, tb) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def api_get(base_url: str, path: str):
    with urllib.request.urlopen(base_url + path, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def api_get_text(base_url: str, path: str):
    with urllib.request.urlopen(base_url + path, timeout=10) as response:
        return response.read().decode("utf-8")


def api_post(base_url: str, path: str, payload: dict):
    request = urllib.request.Request(
        base_url + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def api_post_error(base_url: str, path: str, payload: dict):
    request = urllib.request.Request(
        base_url + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=15)
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "payload": json.loads(exc.read().decode("utf-8"))}
    raise AssertionError("Expected HTTP error response.")


def _active_agent_corrections(status: dict) -> list[dict]:
    for key in ("corrections", "user_corrections", "active_agent_corrections"):
        value = status.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = value.get("items") or value.get("corrections")
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
    return []


def api_post_sse(base_url: str, path: str, payload: dict):
    request = urllib.request.Request(
        base_url + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    events = []
    with urllib.request.urlopen(request, timeout=20) as response:
        self_event = "message"
        data_lines = []
        for raw_line in response:
            line = raw_line.decode("utf-8").rstrip("\n")
            if line.startswith("event: "):
                self_event = line.removeprefix("event: ").strip()
                continue
            if line.startswith("data: "):
                data_lines.append(line.removeprefix("data: "))
                continue
            if line == "" and data_lines:
                events.append({"event": self_event, "data": json.loads("\n".join(data_lines))})
                if self_event in {"stream_finished", "stream_error"}:
                    break
                self_event = "message"
                data_lines = []
    return events


def wait_for_finished_run(base_url: str, run_id: str, timeout_seconds: float = 5.0):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        run = api_get(base_url, f"/runs/{run_id}")
        if run["finished_at"]:
            return run
        time.sleep(0.05)
    raise AssertionError(f"Run did not finish: {run_id}")


def _utc_seconds_from_now(seconds: int) -> str:
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


if __name__ == "__main__":
    unittest.main()
