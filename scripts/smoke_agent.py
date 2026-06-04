from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from humungousaur.config import AgentConfig
from humungousaur.env import load_workspace_environment
from humungousaur.integrations.channels import handle_channel_inbound
from humungousaur.integrations.voice_wakeup import handle_activation
from humungousaur.interaction import InteractionHarness
from humungousaur.orchestrator import AgentOrchestrator
from humungousaur.planning.model_factory import build_model_client
from humungousaur.schemas import ActionStatus
from humungousaur.tools import default_tools
from humungousaur.tools.capability_tools import CapabilitySurfaceTool, ToolDescribeTool, ToolSearchTool
from humungousaur.tools.channel_tools import ChannelCatalogTool
from humungousaur.tools.skill_tools import AgentSkillCatalogTool
from humungousaur.tools.voice_tools import VoiceProviderStatusTool, VoiceResponsePrepareTool, VoiceSpeakTool, VoiceTranscribeTool


def main() -> int:
    parser = argparse.ArgumentParser(description="Humungousaur end-to-end smoke checks")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--data-dir", type=Path, default=Path("artifacts/smoke"))
    parser.add_argument("--live-groq", action="store_true", help="Call Groq through the OpenAI-compatible model client")
    parser.add_argument("--live-groq-agent", action="store_true", help="Run a simple model-planned agent task through Groq")
    parser.add_argument("--live-openai", action="store_true", help="Call OpenAI through the configured OpenAI model client")
    parser.add_argument("--live-openai-agent", action="store_true", help="Run a simple model-planned agent task through OpenAI")
    parser.add_argument("--live-voice", action="store_true", help="Call ElevenLabs TTS and Deepgram STT")
    parser.add_argument("--voice-id", default="", help="Optional ElevenLabs voice id")
    parser.add_argument("--no-voice-lookup", action="store_true", help="Require explicit ELEVENLABS_VOICE_ID or --voice-id")
    args = parser.parse_args()

    workspace = args.workspace.expanduser().resolve()
    load_workspace_environment(workspace)
    config = AgentConfig(workspace=workspace, data_dir=args.data_dir, planner_provider="explicit").normalized()
    summary: dict[str, object] = {"local": [], "live": [], "workspace": str(config.workspace), "data_dir": str(config.data_dir)}
    failed = False

    def record(section: str, name: str, ok: bool, payload: object) -> None:
        nonlocal failed
        summary[section].append({"name": name, "ok": ok, "payload": payload})
        if not ok:
            failed = True

    tools = default_tools(config)
    required_tools = {
        "voice_provider_status",
        "voice_transcribe",
        "voice_response_prepare",
        "voice_speak",
        "capability_surface",
        "tool_search",
        "tool_describe",
        "channel_catalog",
        "channel_message_prepare",
        "agent_skill_catalog",
        "agent_skill_import",
        "screenpipe_search",
        "system_status",
    }
    record("local", "tool_registry", required_tools.issubset(tools), {"missing": sorted(required_tools - set(tools)), "tool_count": len(tools)})

    voice_status = VoiceProviderStatusTool().execute({}, config)
    record("local", "voice_provider_status", voice_status.status == ActionStatus.SUCCEEDED, voice_status.output)

    channels = ChannelCatalogTool().execute({}, config)
    channel_ids = {item["channel_id"] for item in channels.output.get("channels", [])}
    record("local", "channel_catalog", {"whatsapp", "slack", "telegram", "webchat"}.issubset(channel_ids), {"channel_count": len(channel_ids)})

    skills = AgentSkillCatalogTool().execute({"source": "workspace"}, config)
    record("local", "workspace_skills", skills.status == ActionStatus.SUCCEEDED and len(skills.output["workspace_skills"]) >= 1, {"skill_count": len(skills.output["workspace_skills"])})

    capability_surface = CapabilitySurfaceTool().execute({"include_records": False}, config)
    record(
        "local",
        "capability_surface",
        capability_surface.status == ActionStatus.SUCCEEDED and not capability_surface.output["integrity"]["missing_plugin_declared_tools"],
        {
            "tool_count": capability_surface.output["counts"]["tools"],
            "surface_count": len(capability_surface.output["surfaces"]),
            "missing_plugin_declared_tools": capability_surface.output["integrity"]["missing_plugin_declared_tools"],
        },
    )
    tool_search = ToolSearchTool().execute({"query": "voice response", "limit": 10}, config)
    record(
        "local",
        "tool_search",
        tool_search.status == ActionStatus.SUCCEEDED and any(match["record_id"] == "tool:voice_response_prepare" for match in tool_search.output["matches"]),
        {"matches": [match["record_id"] for match in tool_search.output["matches"][:8]]},
    )
    tool_describe = ToolDescribeTool().execute({"record_id": "plugin:channels.slack"}, config)
    record(
        "local",
        "tool_describe",
        tool_describe.status == ActionStatus.SUCCEEDED and "channel_message_send" in tool_describe.output["record"].get("tools", []),
        {"record_id": "plugin:channels.slack", "status": tool_describe.status.value},
    )

    harness = InteractionHarness(config)
    user_result = harness.handle('system_status {}')
    record("local", "stimulus_user_text", user_result.run is not None and user_result.run.results[0].status == ActionStatus.SUCCEEDED, _compact_harness(user_result))

    voice_result = harness.handle({"source": "voice_transcript", "text": "system_status {}"}, response_mode="voice_prepare")
    record("local", "stimulus_voice_transcript", voice_result.voice_result is not None, _compact_harness(voice_result))

    activation_path = config.data_dir / "activation-smoke.json"
    activation_path.parent.mkdir(parents=True, exist_ok=True)
    activation_path.write_text(json.dumps({"transcript": "system_status {}"}, ensure_ascii=False), encoding="utf-8")
    activation_result = handle_activation(activation_path, config, response_mode="voice_prepare")
    record(
        "local",
        "voice_wakeup_activation",
        activation_result.run is not None and activation_result.voice_result is not None,
        _compact_harness(activation_result),
    )

    activity_result = harness.handle(
        {"source": "activity", "text": "system_status {}", "metadata": {"requires_response": True}},
        response_mode="silent",
    )
    record("local", "stimulus_activity_metadata", activity_result.run is not None, _compact_harness(activity_result))

    channel_result = handle_channel_inbound(
        {
            "channel_id": "slack",
            "conversation_id": "C-smoke",
            "conversation_type": "dm",
            "sender_id": "U-smoke",
            "text": "system_status {}",
            "requires_response": True,
            "prepare_reply": True,
        },
        config,
    )
    record("local", "stimulus_channel_message", channel_result["prepared_reply"] is not None, {"decision": channel_result["harness"]["decision"], "reply_id": (channel_result["prepared_reply"] or {}).get("message_id", "")})

    if args.live_openai:
        record("live", "openai_model_client", *_live_model_client_smoke(workspace, args.data_dir, "openai-responses"))

    if args.live_openai_agent:
        record("live", "openai_agent_run", *_live_agent_smoke(workspace, args.data_dir, "openai-responses"))

    if args.live_groq:
        record("live", "groq_model_client", *_live_model_client_smoke(workspace, args.data_dir, "groq"))

    if args.live_groq_agent:
        record("live", "groq_agent_run", *_live_agent_smoke(workspace, args.data_dir, "groq"))

    if args.live_voice:
        voice_smoke = _live_voice_smoke(config, voice_id=args.voice_id, allow_voice_lookup=not args.no_voice_lookup)
        record("live", "elevenlabs_deepgram_voice_loop", voice_smoke.get("ok") is True, voice_smoke)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 1 if failed else 0


def _live_voice_smoke(config: AgentConfig, *, voice_id: str, allow_voice_lookup: bool) -> dict[str, object]:
    spoken = VoiceSpeakTool().execute(
        {
            "text": "Humungousaur live voice smoke test.",
            "reason": "Live smoke test for provider-backed voice response.",
            "provider": "elevenlabs",
            "voice_id": voice_id,
            "allow_voice_lookup": allow_voice_lookup,
            "playback": False,
        },
        config,
    )
    primary_tts = {
        "status": spoken.status.value,
        "summary": spoken.summary,
        "error": spoken.error or "",
        "provider_error": spoken.output.get("provider_error", {}),
        "audio_path": str(spoken.output.get("audio", {}).get("audio_path") or ""),
    }
    fallback_tts: dict[str, object] = {}
    audio_path = primary_tts["audio_path"]
    if spoken.status != ActionStatus.SUCCEEDED:
        fallback = VoiceResponsePrepareTool().execute(
            {
                "text": "Humungousaur live voice smoke test.",
                "reason": "Fallback local Windows SAPI synthesis for live Deepgram STT smoke.",
                "tts_provider": "system",
            },
            config,
        )
        fallback_tts = {
            "status": fallback.status.value,
            "summary": fallback.summary,
            "error": fallback.error or "",
            "provider_error": fallback.output.get("provider_error", {}),
            "audio_path": str(fallback.output.get("audio", {}).get("audio_path") or ""),
        }
        if fallback.status != ActionStatus.SUCCEEDED:
            return {"ok": False, "stage": "tts", "elevenlabs": primary_tts, "system_fallback": fallback_tts}
        audio_path = str(fallback_tts["audio_path"])
    transcribed = VoiceTranscribeTool().execute(
        {
            "audio_path": audio_path,
            "provider": "deepgram",
            "reason": "Transcribe the ElevenLabs voice smoke artifact.",
        },
        config,
    )
    return {
        "ok": transcribed.status in {ActionStatus.SUCCEEDED, ActionStatus.SKIPPED},
        "tts": {"primary_elevenlabs": primary_tts, "system_fallback": fallback_tts, "audio_path": audio_path},
        "stt": {"status": transcribed.status.value, "summary": transcribed.summary, "transcript": transcribed.output.get("transcript", ""), "error": transcribed.error},
    }


def _live_model_client_smoke(workspace: Path, data_dir: Path, provider: str) -> tuple[bool, dict[str, object]]:
    try:
        model_config = AgentConfig(workspace=workspace, data_dir=data_dir, planner_provider="model", model_provider=provider).normalized()
        client = build_model_client(model_config)
        raw = client.complete_json(
            "Return JSON confirming the Humungousaur live model smoke test is alive.",
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["ok", "summary"],
                "properties": {"ok": {"type": "boolean"}, "summary": {"type": "string"}},
            },
        )
        parsed = json.loads(raw)
        return _json_ok(parsed), parsed
    except Exception as exc:
        return False, {"error": str(exc)}


def _live_agent_smoke(workspace: Path, data_dir: Path, provider: str) -> tuple[bool, dict[str, object]]:
    try:
        agent_config = AgentConfig(workspace=workspace, data_dir=data_dir, planner_provider="model", model_provider=provider).normalized()
        result = AgentOrchestrator(agent_config).run("Check local system status using the available system status tool.")
        action_results = [item for item in result.results if item.tool_name != "write_note"]
        ok = bool(action_results) and all(item.status not in {ActionStatus.FAILED, ActionStatus.BLOCKED} for item in action_results)
        return ok, {"run_id": result.run_id, "response": result.final_response[:500], "statuses": [item.status.value for item in result.results]}
    except Exception as exc:
        return False, {"error": str(exc)}


def _json_ok(parsed: dict[str, object]) -> bool:
    return (
        bool(parsed.get("ok"))
        or bool(parsed.get("verification"))
        or bool(parsed.get("live_status"))
        or str(parsed.get("result", "")).strip().lower() in {"ok", "success", "succeeded"}
        or str(parsed.get("status", "")).strip().lower() in {"ok", "alive", "success", "succeeded"}
        or str(parsed.get("test_status", "")).strip().lower() in {"ok", "alive", "success", "succeeded", "passed"}
    )


def _compact_harness(result) -> dict[str, object]:
    return {
        "decision": asdict(result.decision),
        "run_id": result.run.run_id if result.run else "",
        "result_statuses": [item.status.value for item in result.run.results] if result.run else [],
        "voice_response_id": (result.voice_result or {}).get("response_id", ""),
    }


if __name__ == "__main__":
    sys.exit(main())
