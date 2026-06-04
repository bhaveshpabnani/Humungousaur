from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from humungousaur.config import AgentConfig
from humungousaur.env import load_workspace_environment
from humungousaur.integrations.channels import handle_channel_inbound
from humungousaur.interaction import InteractionHarness
from humungousaur.orchestrator import AgentOrchestrator
from humungousaur.planning.model_factory import build_model_client
from humungousaur.schemas import ActionStatus
from humungousaur.tools import default_tools
from humungousaur.tools.channel_tools import ChannelCatalogTool
from humungousaur.tools.skill_tools import AgentSkillCatalogTool
from humungousaur.tools.voice_tools import VoiceProviderStatusTool, VoiceSpeakTool, VoiceTranscribeTool


def main() -> int:
    parser = argparse.ArgumentParser(description="Humungousaur end-to-end smoke checks")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--data-dir", type=Path, default=Path("artifacts/smoke"))
    parser.add_argument("--live-groq", action="store_true", help="Call Groq through the OpenAI-compatible model client")
    parser.add_argument("--live-groq-agent", action="store_true", help="Run a simple model-planned agent task through Groq")
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
        "channel_catalog",
        "channel_message_prepare",
        "agent_skill_catalog",
        "agent_skill_import",
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

    harness = InteractionHarness(config)
    user_result = harness.handle('system_status {}')
    record("local", "stimulus_user_text", user_result.run is not None and user_result.run.results[0].status == ActionStatus.SUCCEEDED, _compact_harness(user_result))

    voice_result = harness.handle({"source": "voice_transcript", "text": "system_status {}"}, response_mode="voice_prepare")
    record("local", "stimulus_voice_transcript", voice_result.voice_result is not None, _compact_harness(voice_result))

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

    if args.live_groq:
        try:
            groq_config = AgentConfig(workspace=workspace, data_dir=args.data_dir, planner_provider="model", model_provider="groq").normalized()
            client = build_model_client(groq_config)
            raw = client.complete_json(
                "Return JSON confirming the smoke test is alive.",
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["ok", "summary"],
                    "properties": {"ok": {"type": "boolean"}, "summary": {"type": "string"}},
                },
            )
            parsed = json.loads(raw)
            ok = (
                bool(parsed.get("ok"))
                or bool(parsed.get("verification"))
                or str(parsed.get("result", "")).strip().lower() in {"ok", "success", "succeeded"}
                or str(parsed.get("status", "")).strip().lower() in {"ok", "alive", "success", "succeeded"}
            )
            record("live", "groq_model_client", ok, parsed)
        except Exception as exc:
            record("live", "groq_model_client", False, {"error": str(exc)})

    if args.live_groq_agent:
        try:
            groq_agent_config = AgentConfig(workspace=workspace, data_dir=args.data_dir, planner_provider="model", model_provider="groq").normalized()
            result = AgentOrchestrator(groq_agent_config).run("Check local system status using the available system status tool.")
            action_results = [item for item in result.results if item.tool_name != "write_note"]
            ok = bool(action_results) and all(item.status != ActionStatus.FAILED for item in action_results)
            record("live", "groq_agent_run", ok, {"run_id": result.run_id, "response": result.final_response[:500], "statuses": [item.status.value for item in result.results]})
        except Exception as exc:
            record("live", "groq_agent_run", False, {"error": str(exc)})

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
    if spoken.status != ActionStatus.SUCCEEDED:
        return {"ok": False, "stage": "tts", "status": spoken.status.value, "summary": spoken.summary, "error": spoken.error}
    audio_path = str(spoken.output.get("audio", {}).get("audio_path") or "")
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
        "tts": {"status": spoken.status.value, "audio_path": audio_path},
        "stt": {"status": transcribed.status.value, "summary": transcribed.summary, "transcript": transcribed.output.get("transcript", ""), "error": transcribed.error},
    }


def _compact_harness(result) -> dict[str, object]:
    return {
        "decision": asdict(result.decision),
        "run_id": result.run.run_id if result.run else "",
        "result_statuses": [item.status.value for item in result.run.results] if result.run else [],
        "voice_response_id": (result.voice_result or {}).get("response_id", ""),
    }


if __name__ == "__main__":
    sys.exit(main())
