#!/usr/bin/env python3
"""Smoke-test the shared desktop API runtime used by Windows and macOS apps."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from humungousaur.api import create_api_server
from humungousaur.config import AgentConfig

ROOT = Path(__file__).resolve().parents[1]


def project_version() -> str:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(metadata["project"]["version"])


class DesktopRuntimeSmoke:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.errors: list[str] = []

    def ok(self, message: str) -> None:
        self.passed.append(message)

    def fail(self, message: str) -> None:
        self.errors.append(message)

    def require(self, condition: bool, message: str, detail: Any = None) -> None:
        if condition:
            self.ok(message)
            return
        suffix = f": {detail}" if detail is not None else ""
        self.fail(f"{message}{suffix}")

    def summary(self) -> int:
        for message in self.passed:
            print(f"PASS {message}")
        for message in self.errors:
            print(f"FAIL {message}")
        print(f"\nDesktop runtime smoke: {len(self.passed)} passed, {len(self.errors)} failures")
        return 1 if self.errors else 0


class RunningAPI:
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


def api_get(base_url: str, path: str) -> Any:
    with urllib.request.urlopen(base_url + path, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def api_post(base_url: str, path: str, payload: dict[str, Any]) -> Any:
    request = urllib.request.Request(
        base_url + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def api_post_error(base_url: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        base_url + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=20)
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "payload": json.loads(exc.read().decode("utf-8"))}
    return {"status": 0, "payload": {}}


def main() -> int:
    smoke = DesktopRuntimeSmoke()
    version = project_version()
    with tempfile.TemporaryDirectory(prefix="humungousaur-desktop-runtime-") as temp_dir:
        workspace = Path(temp_dir)
        (workspace / "README.md").write_text("# Desktop Runtime Smoke\n\nShared app API contract.", encoding="utf-8")
        config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

        with RunningAPI(config) as base_url:
            health = api_get(base_url, "/health")
            smoke.require(health.get("status") == "ok", "health endpoint reports ok", health)

            system_status = api_get(base_url, "/system/status")
            smoke.require(system_status.get("workspace") == str(workspace.resolve()), "system status reports desktop workspace")

            updates = api_get(base_url, "/updates/latest?offline=1&platform=macos")
            smoke.require(updates.get("current_version") == version, "update endpoint reports installed app version", updates)
            smoke.require(updates.get("latest_tag") == f"v{version}", "update endpoint exposes release tag", updates)
            smoke.require(
                str(updates.get("platform_download_url", "")).endswith("/Humungousaur-macOS.pkg"),
                "update endpoint exposes platform download URL",
                updates.get("platform_download_url"),
            )

            tools = api_get(base_url, "/tools")
            group_names = {group.get("name") for group in tools.get("groups", [])}
            tool_names = {tool.get("name") for tool in tools.get("tools", [])}
            smoke.require(tools.get("tool_count", 0) > 100, "tool catalog exposes full native tool surface", tools.get("tool_count"))
            smoke.require({"channels", "voice", "browser", "os"}.issubset(group_names), "tool catalog includes desktop capability groups", sorted(group_names))
            smoke.require({"read_file", "channel_message_prepare", "voice_provider_status"}.issubset(tool_names), "tool catalog includes desktop-used tools")

            channels = api_get(base_url, "/channels")
            channel_ids = {channel.get("channel_id") for channel in channels}
            smoke.require({"slack", "telegram", "discord", "whatsapp"}.issubset(channel_ids), "channel catalog exposes primary desktop channels", sorted(channel_ids))

            slack_requirements = api_get(base_url, "/channels/requirements?channel_id=slack")
            smoke.require("SLACK_BOT_TOKEN" in slack_requirements.get("setup", {}).get("required_secrets", []), "channel requirements expose Slack bot token setup")

            saved_setup = api_post(
                base_url,
                "/channels/setup",
                {
                    "channel_id": "slack",
                    "enabled": True,
                    "listen_enabled": False,
                    "secret_refs": {"bot_token": "SLACK_BOT_TOKEN"},
                    "secret_configured": {"bot_token": True},
                    "conversation_defaults": {"conversation_id": "C-DESKTOP", "conversation_type": "dm"},
                    "allowlist": ["U-DESKTOP"],
                    "group_allowlist": [],
                    "notes": "Desktop runtime smoke setup.",
                },
            )
            smoke.require(saved_setup.get("setup", {}).get("enabled") is True, "channel setup save works through desktop API")

            runtime_payload = {
                "channel_id": "slack",
                "planner": "explicit",
                "runtime_secrets": {"SLACK_BOT_TOKEN": "xoxb-desktop-runtime"},
            }
            channel_status = api_post(base_url, "/channels/status", runtime_payload)
            missing_send_env = channel_status.get("channels", [{}])[0].get("missing_send_env", [])
            smoke.require(missing_send_env == [], "runtime secrets hydrate channel setup without leaking values", missing_send_env)
            smoke.require("xoxb-desktop-runtime" not in json.dumps(channel_status), "channel status does not echo runtime secrets")

            channel_doctor = api_post(base_url, "/channels/doctor", runtime_payload)
            smoke.require(channel_doctor.get("overall_status") in {"ok", "ready", "needs_setup"}, "channel doctor responds through desktop API", channel_doctor.get("overall_status"))

            channel_smoke = api_post(
                base_url,
                "/channels/smoke",
                {**runtime_payload, "prepare_messages": True, "dry_run_sends": True},
            )
            smoke.require(channel_smoke.get("channel_count") == 1, "channel integration smoke scopes to requested channel")
            smoke.require(channel_smoke.get("live_send_performed") is False, "channel integration smoke avoids live sends by default")
            smoke.require(channel_smoke.get("channels", [{}])[0].get("prepared_outbox_ready") is True, "channel integration smoke prepares outbox evidence")

            listener_status = api_post(base_url, "/channels/listeners", runtime_payload)
            smoke.require(listener_status.get("listeners", [{}])[0].get("channel_id") == "slack", "channel listener status responds through desktop API")
            listener_tick = api_post(base_url, "/channels/listeners/tick", {**runtime_payload, "limit": 1, "prepare_replies": True})
            smoke.require(listener_tick.get("processed_count") == 0, "channel listener tick is safe when no live events are present")

            prepared_message = api_post(
                base_url,
                "/channels/message/prepare",
                {
                    "channel_id": "slack",
                    "conversation_id": "C-DESKTOP",
                    "text": "Prepared from desktop runtime smoke.",
                    "reason": "Verify desktop message preparation.",
                    "metadata": {"source": "desktop_runtime_smoke"},
                },
            )
            smoke.require(prepared_message.get("message", {}).get("status") == "prepared_not_sent", "channel message prepare writes non-sending outbox item")
            outbox = api_get(base_url, "/channels/outbox")
            smoke.require(any(item.get("channel_id") == "slack" for item in outbox.get("messages", [])), "channel outbox is readable by desktop apps")

            send_without_approval = api_post_error(
                base_url,
                "/channels/message/send",
                {
                    "channel_id": "slack",
                    "conversation_id": "C-DESKTOP",
                    "text": "This must not send.",
                    "reason": "Verify desktop send approval gate.",
                },
            )
            smoke.require(send_without_approval.get("status") == 403, "channel sends remain approval-gated")

            dry_send = api_post(
                base_url,
                "/channels/message/send",
                {
                    "channel_id": "slack",
                    "conversation_id": "C-DESKTOP",
                    "text": "Dry-run desktop send.",
                    "reason": "Verify approved dry-run desktop send.",
                    "approve_high_risk": True,
                    "dry_run": True,
                },
            )
            smoke.require(dry_send.get("message", {}).get("status") == "dry_run_not_sent", "approved dry-run channel send does not contact provider")

            voice_status = api_post(
                base_url,
                "/voice/status",
                {"runtime_secrets": {"DEEPGRAM_API_KEY": "dg-desktop", "ELEVENLABS_API_KEY": "el-desktop"}},
            )
            smoke.require(voice_status.get("stt", {}).get("deepgram", {}).get("configured") is True, "voice status accepts app-provided Deepgram secret")
            smoke.require(voice_status.get("tts", {}).get("elevenlabs", {}).get("configured") is True, "voice status accepts app-provided ElevenLabs secret")
            smoke.require("dg-desktop" not in json.dumps(voice_status) and "el-desktop" not in json.dumps(voice_status), "voice status does not echo runtime secrets")

            stimulus = api_post(
                base_url,
                "/stimuli",
                {
                    "source": "user_text",
                    "text": 'read_file {"path":"README.md"}',
                    "response_mode": "silent",
                    "planner": "explicit",
                    "metadata": {"source": "desktop_runtime_smoke"},
                },
            )
            run = stimulus.get("run") or {}
            run_id = run.get("run_id", "")
            smoke.require(stimulus.get("decision", {}).get("decision") == "respond", "stimulus endpoint accepts desktop chat request")
            smoke.require("Desktop Runtime Smoke" in run.get("final_response", ""), "stimulus endpoint executes explicit desktop request")
            smoke.require(bool(run_id), "stimulus endpoint records a run id")

            runs = api_get(base_url, "/runs?limit=10")
            smoke.require(any(item.get("run_id") == run_id for item in runs), "runs list exposes desktop-submitted run")
            timeline = api_get(base_url, f"/runs/{run_id}/timeline?limit=50")
            smoke.require(isinstance(timeline, list), "run timeline is readable by desktop apps")
            approvals = api_get(base_url, "/approvals?status=pending&limit=10")
            smoke.require(isinstance(approvals, list), "pending approvals endpoint is readable by desktop apps")

            autonomous_status = api_get(base_url, "/autonomous/status?limit=5")
            smoke.require("scheduled_wakeups" in autonomous_status, "autonomy status endpoint responds through desktop API")
            autonomous_cycle = api_post(
                base_url,
                "/autonomous/cycles",
                {"planner": "explicit", "max_cycles": 1, "idle_sleep_seconds": 0, "stop_after_idle_cycles": 1, "allow_initiative": False},
            )
            smoke.require(autonomous_cycle.get("stopped_reason") in {"idle", "max_cycles"}, "bounded autonomy cycle endpoint is safe and responsive")

            collectors_status = api_get(base_url, "/collectors/status?limit=5")
            smoke.require("active_window" in collectors_status.get("profile", {}).get("collectors", {}), "collector status exposes desktop stimulus collectors")
            collectors_config = api_post(
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
                    "watch_paths": [str(workspace)],
                    "max_events_per_tick": 1,
                },
            )
            smoke.require(collectors_config.get("profile", {}).get("enabled") is True, "collector configuration persists through desktop API")
            api_post(base_url, "/collectors/tick", {"force": True})
            (workspace / "desktop-context.md").write_text("Desktop app context changed.", encoding="utf-8")
            collectors_tick = api_post(base_url, "/collectors/tick", {"force": True})
            smoke.require("collected" in collectors_tick and "skipped" in collectors_tick, "collector tick endpoint runs safely for desktop API")
            smoke.require(
                bool(collectors_tick.get("semantic_events")),
                "collector tick emits semantic events for desktop UI context",
                collectors_tick,
            )
            events_status = api_get(base_url, "/events/status?limit=5")
            smoke.require(events_status.get("current_context_exists") is True, "events status exposes generated current context")
            smoke.require(
                any(event.get("payload", {}).get("event_type") == "project_files_changed" for event in events_status.get("semantic_events", [])),
                "events status exposes compact project file semantic event",
                events_status.get("semantic_events", []),
            )
            rebuilt_context = api_post(base_url, "/events/rebuild-context", {"limit": 5})
            smoke.require("current_context_path" in rebuilt_context, "events rebuild endpoint refreshes context artifacts")

    return smoke.summary()


if __name__ == "__main__":
    sys.exit(main())
