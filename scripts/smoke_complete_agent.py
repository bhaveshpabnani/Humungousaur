from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, replace
from functools import partial
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from humungousaur.config import AgentConfig
from humungousaur.env import load_workspace_environment
from humungousaur.executor import Executor
from humungousaur.integrations.channels import handle_channel_inbound
from humungousaur.integrations.voice_wakeup import handle_activation
from humungousaur.interaction import InteractionHarness
from humungousaur.orchestrator import AgentOrchestrator
from humungousaur.safety.policy import PolicyEngine
from humungousaur.schemas import ActionStatus, PlannedStep, ToolResult
from humungousaur.tools import default_tools
from humungousaur.tools.browser import LIVE_BROWSER_MANAGER
from humungousaur.tools.os_tools import save_ui_observation
from humungousaur.tools.workflow_tools import LlmTaskJsonTool


PASS_STATUSES = {ActionStatus.SUCCEEDED}
SAFE_PASS_STATUSES = {ActionStatus.SUCCEEDED, ActionStatus.SKIPPED, ActionStatus.NEEDS_APPROVAL}


def main() -> int:
    parser = argparse.ArgumentParser(description="Comprehensive Humungousaur end-to-end smoke runner")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--data-dir", type=Path, default=Path("artifacts/complete-smoke"))
    parser.add_argument("--live-groq", action="store_true", help="Use Groq for live model-led planner/tool JSON checks")
    parser.add_argument("--live-openai", action="store_true", help="Use OpenAI for live model-led planner/tool JSON checks")
    parser.add_argument("--live-voice", action="store_true", help="Use ElevenLabs TTS plus Deepgram STT for activation audio")
    parser.add_argument("--voice-id", default="", help="Optional ElevenLabs voice id")
    parser.add_argument("--live-browser", action="store_true", help="Launch Playwright headless browser if installed")
    parser.add_argument("--real-screen", action="store_true", help="Capture an actual screenshot artifact after policy approval")
    args = parser.parse_args()

    workspace = args.workspace.expanduser().resolve()
    load_workspace_environment(workspace)
    config = AgentConfig(workspace=workspace, data_dir=args.data_dir, planner_provider="explicit").normalized()
    tools = default_tools(config)
    executor = Executor(tools, PolicyEngine())
    results: dict[str, Any] = {
        "workspace": str(config.workspace),
        "data_dir": str(config.data_dir),
        "sections": [],
    }
    failed = False

    def record(section: str, name: str, ok: bool, payload: Any) -> None:
        nonlocal failed
        results["sections"].append({"section": section, "name": name, "ok": ok, "payload": _jsonable(payload)})
        if not ok:
            failed = True

    required_tools = {
        "voice_provider_status",
        "voice_transcribe",
        "voice_response_prepare",
        "voice_speak",
        "system_status",
        "read_file",
        "write_note",
        "browser_open",
        "browser_observe",
        "browser_type",
        "browser_submit_form",
        "browser_live_status",
        "os_active_window",
        "os_windows",
        "os_observe_ui",
        "os_click_element",
        "os_type_text",
        "os_send_keys",
        "os_click_coordinates",
        "open_app",
        "os_launch_app",
        "screenshot_capture",
        "cognitive_state",
        "automation_daemon_tick",
        "multi_agent_coordinate",
        "diff_render",
        "llm_task_json",
        "tokenjuice_compact",
        "canvas_a2ui_create",
    }
    record("registry", "required_tool_surface", required_tools.issubset(tools), {"missing": sorted(required_tools - set(tools)), "tool_count": len(tools)})

    record_tool(record, "voice", "voice_provider_status", tools["voice_provider_status"].execute({}, config))
    _run_core_agent_and_stimuli(record, config)
    _run_voice_wakeup_inline(record, config)
    if args.live_voice:
        model_provider = "groq" if args.live_groq else "openai-responses" if args.live_openai else "auto"
        _run_live_voice_audio_activation(record, config, voice_id=args.voice_id, model_provider=model_provider)
    if args.live_groq:
        _run_live_model(record, workspace, args.data_dir, "groq")
    if args.live_openai:
        _run_live_model(record, workspace, args.data_dir, "openai-responses")

    with local_web_app() as url:
        _run_static_browser(record, config, executor, url)
        if args.live_browser:
            _run_live_browser(record, config, executor, url)
        else:
            live_status = tools["browser_live_status"].execute({}, config)
            record_tool(record, "browser_live", "browser_live_status_probe", live_status)

    _run_os_and_screen(record, config, executor, real_screen=args.real_screen)
    _run_cognition(record, config)
    _run_workflow_tools(record, config)

    config.data_dir.mkdir(parents=True, exist_ok=True)
    result_path = config.data_dir / "complete-smoke-results.json"
    result_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    failed_sections = [
        {"section": item["section"], "name": item["name"], "payload": item["payload"]}
        for item in results["sections"]
        if not item["ok"]
    ]
    print(
        json.dumps(
            {
                "ok": not failed,
                "result_path": str(result_path),
                "section_count": len(results["sections"]),
                "failed_count": len(failed_sections),
                "failed": failed_sections,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 1 if failed else 0


def record_tool(record, section: str, name: str, result: ToolResult, allow_skipped: bool = False) -> None:
    statuses = SAFE_PASS_STATUSES if allow_skipped else PASS_STATUSES
    record(
        section,
        name,
        result.status in statuses,
        {"status": result.status.value, "summary": result.summary, "error": result.error, "output": result.output},
    )


def _run_core_agent_and_stimuli(record, config: AgentConfig) -> None:
    readme = config.data_dir / "fixtures" / "complete-smoke-readme.md"
    readme.parent.mkdir(parents=True, exist_ok=True)
    readme.write_text("# Complete Smoke\n\nHumungousaur complete smoke fixture.\n", encoding="utf-8")
    read_path = readme.relative_to(config.workspace).as_posix()
    run = AgentOrchestrator(config).run(f'read_file {{"path":"{read_path}"}}')
    record("agent", "explicit_agent_read_file", bool(run.results and run.results[0].status == ActionStatus.SUCCEEDED), _compact_run(run))

    harness = InteractionHarness(config)
    text = harness.handle('system_status {}', response_mode="text")
    voice = harness.handle({"source": "voice_transcript", "text": "system_status {}"}, response_mode="voice_prepare")
    activity = harness.handle({"source": "activity", "text": "system_status {}", "metadata": {"requires_response": True}}, response_mode="silent")
    channel = handle_channel_inbound(
        {
            "channel_id": "slack",
            "conversation_id": "C-complete-smoke",
            "conversation_type": "dm",
            "sender_id": "U-complete-smoke",
            "text": "system_status {}",
            "requires_response": True,
            "prepare_reply": True,
        },
        config,
    )
    record("stimuli", "user_text_stimulus", text.run is not None and _run_ok(text.run), _compact_harness(text))
    record("stimuli", "voice_transcript_stimulus", voice.run is not None and voice.voice_result is not None, _compact_harness(voice))
    record("stimuli", "activity_stimulus", activity.run is not None and _run_ok(activity.run), _compact_harness(activity))
    record("stimuli", "channel_message_stimulus", channel.get("prepared_reply") is not None, {"decision": channel["harness"]["decision"], "reply": channel.get("prepared_reply")})


def _run_voice_wakeup_inline(record, config: AgentConfig) -> None:
    activation = config.data_dir / "complete-smoke-activation-inline.json"
    activation.parent.mkdir(parents=True, exist_ok=True)
    activation.write_text(json.dumps({"transcript": "system_status {}"}, ensure_ascii=False), encoding="utf-8")
    result = handle_activation(activation, config, response_mode="voice_prepare")
    record("voice_wakeup", "activation_inline_transcript_to_voice_response", result.run is not None and result.voice_result is not None, _compact_harness(result))


def _run_live_voice_audio_activation(record, config: AgentConfig, *, voice_id: str, model_provider: str) -> None:
    tools = default_tools(config)
    tts = tools["voice_speak"].execute(
        {
            "text": "Check local system status using the available system status tool.",
            "reason": "Generate voice-wakeup activation audio for complete smoke.",
            "provider": "elevenlabs",
            "voice_id": voice_id,
            "allow_voice_lookup": not bool(voice_id),
            "playback": False,
        },
        config,
    )
    if tts.status != ActionStatus.SUCCEEDED:
        fallback = tools["voice_response_prepare"].execute(
            {
                "text": "Check local system status using the available system status tool.",
                "reason": "Fallback local Windows SAPI activation audio for complete smoke.",
                "tts_provider": "system",
            },
            config,
        )
        provider_error = tts.output.get("provider_error", {}) if isinstance(tts.output, dict) else {}
        provider_blocked = provider_error.get("category") in {"provider_account", "provider_entitlement", "provider_quota"}
        record(
            "voice_live",
            "elevenlabs_activation_audio",
            provider_blocked,
            {
                "status": tts.status.value,
                "summary": tts.summary,
                "error": tts.error,
                "output": tts.output,
                "accepted_as_provider_block": provider_blocked,
            },
        )
        record_tool(record, "voice_live", "system_tts_fallback_activation_audio", fallback)
        if fallback.status != ActionStatus.SUCCEEDED:
            return
        audio_path = fallback.output.get("audio", {}).get("audio_path", "")
    else:
        record_tool(record, "voice_live", "elevenlabs_activation_audio", tts)
        audio_path = tts.output.get("audio", {}).get("audio_path", "")

    stt = tools["voice_transcribe"].execute(
        {"audio_path": str(audio_path), "provider": "deepgram", "reason": "Transcribe generated activation audio."},
        config,
    )
    record_tool(record, "voice_live", "deepgram_activation_stt", stt, allow_skipped=False)
    if stt.status != ActionStatus.SUCCEEDED:
        return

    activation = config.data_dir / "complete-smoke-activation-audio.json"
    activation.write_text(json.dumps({"audio_path": str(audio_path), "stt_provider": "deepgram"}, ensure_ascii=False), encoding="utf-8")
    run_config = replace(config, planner_provider="model", model_provider=model_provider).normalized()
    result = handle_activation(
        activation,
        run_config,
        response_mode="voice_prepare",
        tts_provider="elevenlabs",
        fallback_tts_provider="system",
        voice_id=voice_id,
    )
    voice_ready = bool(
        result.run is not None
        and _run_ok(result.run)
        and result.voice_result is not None
        and result.voice_result.get("prepare_status") == "succeeded"
    )
    record("voice_live", "audio_activation_stt_agent_voice_response", voice_ready, _compact_harness(result))


def _run_live_model(record, workspace: Path, data_dir: Path, provider: str) -> None:
    model_config = AgentConfig(workspace=workspace, data_dir=data_dir, planner_provider="model", model_provider=provider).normalized()
    try:
        run = AgentOrchestrator(model_config).run("Check local system status using the available system status tool.")
        record("model", f"{provider}_agent_tool_selection", _run_ok(run), _compact_run(run))
    except Exception as exc:
        record("model", f"{provider}_agent_tool_selection", False, {"error": str(exc)})
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["ok", "summary"],
        "properties": {"ok": {"type": "boolean"}, "summary": {"type": "string"}},
    }
    result = LlmTaskJsonTool().execute({"objective": "Confirm complete smoke JSON task readiness.", "json_schema": schema}, model_config)
    record_tool(record, "model", f"{provider}_llm_task_json", result)


def _run_static_browser(record, config: AgentConfig, executor: Executor, url: str) -> None:
    tools = default_tools(config)
    opened = tools["browser_open"].execute({"url": url}, config)
    record_tool(record, "browser_static", "browser_open", opened)
    if opened.status != ActionStatus.SUCCEEDED:
        return
    session_id = opened.output["session_id"]
    observe = tools["browser_observe"].execute({"session_id": session_id, "include_text": True}, config)
    extract = tools["browser_extract"].execute({"session_id": session_id, "query": "Humungousaur", "include_links": True}, config)
    clicked = tools["browser_click_element"].execute({"session_id": session_id, "element_id": "link:0"}, config)
    back = tools["browser_back"].execute({"session_id": session_id}, config)
    typed = tools["browser_type"].execute({"session_id": session_id, "element_id": "form:0:field:q", "text": "complete smoke", "clear": True}, config)
    gated = executor.execute(PlannedStep("browser_submit_form", {"session_id": session_id, "form_index": 0}, "complete smoke submit"), config)
    submitted = executor.execute(PlannedStep("browser_submit_form", {"session_id": session_id, "form_index": 0}, "complete smoke submit"), config, approved=True)
    record_tool(record, "browser_static", "browser_observe", observe)
    record_tool(record, "browser_static", "browser_extract", extract)
    record_tool(record, "browser_static", "browser_click_element", clicked)
    record_tool(record, "browser_static", "browser_back", back)
    record_tool(record, "browser_static", "browser_type_form_draft", typed)
    record_tool(record, "browser_static", "browser_submit_policy_gate", gated, allow_skipped=True)
    record_tool(record, "browser_static", "browser_submit_approved", submitted)


def _run_live_browser(record, config: AgentConfig, executor: Executor, url: str) -> None:
    tools = default_tools(config)
    status = tools["browser_live_status"].execute({}, config)
    record_tool(record, "browser_live", "browser_live_status", status)
    if not status.output.get("available"):
        record("browser_live", "browser_live_backend_available", False, status.output)
        return
    opened = tools["browser_live_open"].execute({"url": url, "headless": True, "viewport_width": 900, "viewport_height": 700}, config)
    record_tool(record, "browser_live", "browser_live_open", opened)
    if opened.status != ActionStatus.SUCCEEDED:
        return
    live_session_id = opened.output["live_session_id"]
    try:
        observe = tools["browser_live_observe"].execute({"live_session_id": live_session_id, "include_text": True, "max_elements": 50}, config)
        input_element = next((item for item in observe.output.get("interactive_elements", []) if item.get("name") == "q"), {})
        element_id = input_element.get("element_id", "")
        typed = executor.execute(
            PlannedStep(
                "browser_live_type",
                {"live_session_id": live_session_id, "element_id": element_id, "text": "live smoke", "reason": "Complete live browser typing smoke."},
                "complete live browser type",
            ),
            config,
            approved=True,
        )
        key = executor.execute(
            PlannedStep(
                "browser_live_press_key",
                {"live_session_id": live_session_id, "element_id": element_id, "shortcut": "Enter", "reason": "Complete live browser keyboard smoke."},
                "complete live browser key",
            ),
            config,
            approved=True,
        )
        screenshot = executor.execute(
            PlannedStep(
                "browser_live_screenshot",
                {"live_session_id": live_session_id, "reason": "Complete live browser screenshot smoke."},
                "complete live browser screenshot",
            ),
            config,
            approved=True,
        )
        record_tool(record, "browser_live", "browser_live_observe", observe)
        record_tool(record, "browser_live", "browser_live_type_approved", typed)
        record_tool(record, "browser_live", "browser_live_press_key_approved", key)
        record_tool(record, "browser_live", "browser_live_screenshot_approved", screenshot)
    finally:
        close = executor.execute(PlannedStep("browser_live_close", {"live_session_id": live_session_id, "reason": "Complete smoke cleanup."}, "close live browser"), config, approved=True)
        record_tool(record, "browser_live", "browser_live_close", close)


def _run_os_and_screen(record, config: AgentConfig, executor: Executor, *, real_screen: bool) -> None:
    tools = default_tools(config)
    dry_config = replace(config, dry_run=True).normalized()
    observation = save_ui_observation(
        dry_config,
        {
            "supported": True,
            "active_window": {"title": "Synthetic complete smoke window", "window_handle": 1234},
            "elements": [
                {
                    "element_id": "uia:1",
                    "name": "Synthetic Button",
                    "control_type": "Button",
                    "bounds": {"left": 10, "top": 10, "right": 110, "bottom": 50, "width": 100, "height": 40},
                    "metadata": {},
                }
            ],
            "source": "complete_smoke_synthetic_observation",
        },
    )
    observation_id = observation["observation_id"]
    record_tool(record, "os_metadata", "os_active_window", tools["os_active_window"].execute({}, config))
    record_tool(record, "os_metadata", "os_windows", tools["os_windows"].execute({"limit": 10}, config), allow_skipped=True)
    record_tool(record, "os_metadata", "os_cursor", tools["os_cursor"].execute({}, config), allow_skipped=True)
    record_tool(record, "os_metadata", "os_apps", tools["os_apps"].execute({"query": "calc", "limit": 5}, config), allow_skipped=True)
    record_tool(record, "os_metadata", "os_virtual_desktops", tools["os_virtual_desktops"].execute({"limit": 5}, config), allow_skipped=True)

    dry_steps = {
        "os_observe_ui_dry_run": ("os_observe_ui", {"max_elements": 5, "reason": "Complete smoke dry-run UI observation."}),
        "os_click_element_dry_run": ("os_click_element", {"observation_id": observation_id, "element_id": "uia:1", "reason": "Complete smoke dry-run click."}),
        "os_type_text_dry_run": ("os_type_text", {"observation_id": observation_id, "element_id": "uia:1", "text": "hello", "reason": "Complete smoke dry-run typing."}),
        "os_scroll_element_dry_run": ("os_scroll_element", {"observation_id": observation_id, "element_id": "uia:1", "direction": "down", "reason": "Complete smoke dry-run scroll."}),
        "os_send_keys_dry_run": ("os_send_keys", {"shortcut": "Ctrl+S", "reason": "Complete smoke dry-run keyboard shortcut."}),
        "os_click_coordinates_dry_run": ("os_click_coordinates", {"x": 20, "y": 20, "reason": "Complete smoke dry-run mouse coordinate click."}),
        "os_uia_pattern_action_dry_run": ("os_uia_pattern_action", {"observation_id": observation_id, "element_id": "uia:1", "action": "invoke", "reason": "Complete smoke dry-run UIA action."}),
        "os_window_state_dry_run": ("os_window_state", {"window_id": "window:1234", "action": "restore", "reason": "Complete smoke dry-run window state."}),
        "open_app_dry_run": ("open_app", {"app_id": "calculator"}),
        "os_launch_app_dry_run": ("os_launch_app", {"app": "Calculator", "reason": "Complete smoke dry-run app launch."}),
        "os_clipboard_read_dry_run": ("os_clipboard_read", {"reason": "Complete smoke dry-run clipboard read."}),
        "os_clipboard_write_dry_run": ("os_clipboard_write", {"text": "complete smoke", "reason": "Complete smoke dry-run clipboard write."}),
    }
    for name, (tool_name, payload) in dry_steps.items():
        result = executor.execute(PlannedStep(tool_name, payload, name), dry_config, approved=True)
        record_tool(record, "os_actions", name, result, allow_skipped=True)

    screen_config = config if real_screen else dry_config
    screenshot = executor.execute(
        PlannedStep("screenshot_capture", {"reason": "Complete smoke screen capture check."}, "complete screen capture"),
        screen_config,
        approved=True,
    )
    record_tool(record, "screen", "screenshot_capture" + ("_real" if real_screen else "_dry_run"), screenshot, allow_skipped=not real_screen)
    record_tool(record, "screen", "screen_captures", tools["screen_captures"].execute({"limit": 5}, config))


def _run_cognition(record, config: AgentConfig) -> None:
    tools = default_tools(config)
    record_tool(record, "cognition", "cognitive_state", tools["cognitive_state"].execute({}, config))
    goal = tools["cognitive_goal_create"].execute(
        {"title": "Complete smoke goal", "description": "Exercise cognition goal storage.", "status": "active"},
        config,
    )
    record_tool(record, "cognition", "cognitive_goal_create", goal)
    daemon_config = tools["automation_daemon_configure"].execute(
        {"enabled": True, "poll_seconds": 1, "max_cycles_per_tick": 1, "stop_after_idle_cycles": 1},
        config,
    )
    daemon_tick = tools["automation_daemon_tick"].execute({"max_cycles_per_tick": 1}, config)
    multi = tools["multi_agent_coordinate"].execute(
        {
            "goal_title": "Complete smoke multi-agent",
            "specialists": [{"name": "Smoke specialist", "purpose": "Inspect smoke status.", "contract": "Use low-risk tools.", "tools": ["system_status"]}],
            "tasks": [{"task_id": "status", "title": "Inspect system", "owner": "Smoke specialist", "request": "system_status {}"}],
        },
        config,
    )
    board = tools["multi_agent_board"].execute({}, config)
    record_tool(record, "cognition", "automation_daemon_configure", daemon_config)
    record_tool(record, "cognition", "automation_daemon_tick", daemon_tick, allow_skipped=True)
    record_tool(record, "cognition", "multi_agent_coordinate", multi)
    record_tool(record, "cognition", "multi_agent_board", board)


def _run_workflow_tools(record, config: AgentConfig) -> None:
    tools = default_tools(config)
    diff = tools["diff_render"].execute({"left_text": "a\nold\n", "right_text": "a\nnew\n"}, config)
    compact = tools["tokenjuice_compact"].execute({"text": "\n".join(f"line {index}" for index in range(500)), "max_chars": 1000}, config)
    canvas = tools["canvas_a2ui_create"].execute(
        {
            "title": "Complete smoke flow",
            "nodes": [{"id": "wake", "label": "Wakeup"}, {"id": "agent", "label": "Agent", "x": 280}],
            "edges": [{"from": "wake", "to": "agent"}],
        },
        config,
    )
    record_tool(record, "workflow", "diff_render", diff)
    record_tool(record, "workflow", "tokenjuice_compact", compact)
    record_tool(record, "workflow", "canvas_a2ui_create", canvas)


@contextmanager
def local_web_app():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        (root / "index.html").write_text(
            """
<!doctype html>
<html><head><title>Humungousaur Smoke</title></head>
<body>
<h1>Humungousaur Browser Smoke</h1>
<p>Humungousaur can inspect, type, submit, navigate, and screenshot this page.</p>
<a href="/details.html">Details</a>
<form method="get" action="/submitted.html">
  <input name="q" placeholder="query">
  <button type="submit">Submit</button>
</form>
</body></html>
""",
            encoding="utf-8",
        )
        (root / "details.html").write_text("<html><head><title>Details</title></head><body><p>Details page.</p></body></html>", encoding="utf-8")
        (root / "submitted.html").write_text("<html><head><title>Submitted</title></head><body><p>Submitted smoke form.</p></body></html>", encoding="utf-8")

        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(root)))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            yield f"http://{host}:{port}/index.html"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            for session_id in list(LIVE_BROWSER_MANAGER.sessions):
                try:
                    LIVE_BROWSER_MANAGER.close(session_id)
                except Exception:
                    pass


def _compact_harness(result) -> dict[str, Any]:
    return {
        "decision": asdict(result.decision),
        "run": _compact_run(result.run) if result.run is not None else None,
        "voice_response": result.voice_result,
    }


def _compact_run(run) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "final_response": run.final_response[:700],
        "results": [{"tool_name": item.tool_name, "status": item.status.value, "summary": item.summary, "error": item.error} for item in run.results],
        "approval_count": len(run.approvals),
    }


def _run_ok(run) -> bool:
    real_results = [item for item in run.results if item.tool_name != "write_note"]
    if not real_results:
        return False
    if "I could not create a valid tool plan" in run.final_response:
        return False
    return all(item.status not in {ActionStatus.FAILED, ActionStatus.BLOCKED} for item in real_results)


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        return str(value)


if __name__ == "__main__":
    sys.exit(main())
