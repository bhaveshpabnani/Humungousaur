from __future__ import annotations

import base64
import json
import mimetypes
import platform
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema
from humungousaur.tools.voice.providers import (
    SpeechProviderError,
    classify_provider_error,
    deepgram_transcribe_file,
    elevenlabs_synthesize_to_file,
    local_whisper_status,
    local_whisper_transcribe_file,
    play_audio_file,
    windows_sapi_synthesize_to_file,
)


VOICE_RESPONSE_MAX_CHARS = 20_000
VOICE_SPEAK_MAX_CHARS = 4_000
VOICE_TRANSCRIBE_PROVIDERS = {"deepgram", "local-whisper"}
VOICE_PREPARE_PROVIDERS = {"artifact", "elevenlabs", "system"}
VOICE_SPEAK_PROVIDERS = {"system", "elevenlabs"}


class VoiceProviderStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="voice_provider_status",
            description="Inspect configured speech-to-text and text-to-speech provider readiness without exposing API keys.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(),
            capability_group="voice",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        del tool_input
        import os

        payload = {
            "stt": {
                "deepgram": {
                    "configured": bool(_secret(config, "DEEPGRAM_API_KEY")),
                    "base_url": os.environ.get("DEEPGRAM_BASE_URL", "https://api.deepgram.com"),
                    "model_env_configured": bool(_secret(config, "DEEPGRAM_MODEL")),
                },
                "local-whisper": local_whisper_status(),
            },
            "tts": {
                "elevenlabs": {
                    "configured": bool(_elevenlabs_secret(config)),
                    "voice_id_configured": bool(config.secret_value("ELEVENLABS_VOICE_ID") or os.environ.get("ELEVENLABS_VOICE_ID")),
                    "base_url": os.environ.get("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io"),
                    "model_env_configured": bool(_secret(config, "ELEVENLABS_MODEL_ID")),
                },
                "system": {
                    "configured": platform.system().lower() == "windows",
                    "provider": "windows_sapi" if platform.system().lower() == "windows" else "unsupported",
                },
            },
            "preferred_tts_provider": _env_tts_provider(),
            "data_dir": str(config.normalized().data_dir),
        }
        ready = []
        if payload["stt"]["deepgram"]["configured"]:
            ready.append("deepgram_stt")
        if payload["stt"]["local-whisper"]["configured"]:
            ready.append("local_whisper_stt")
        if payload["tts"]["elevenlabs"]["configured"]:
            ready.append("elevenlabs_tts")
        if payload["tts"]["system"]["configured"]:
            ready.append("system_tts")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Voice providers ready: {', '.join(ready) if ready else 'none'}",
            payload,
        )


class VoiceTranscribeTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="voice_transcribe",
            description=(
                "Transcribe a local audio file through a configured speech-to-text provider. "
                "Use this for voice-wakeup recordings or other explicit audio stimuli."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "audio_path": {"type": "string", "description": "Path to a local audio file inside an allowed read root."},
                    "provider": {"type": "string", "enum": sorted(VOICE_TRANSCRIBE_PROVIDERS), "description": "Speech-to-text provider."},
                    "model": {"type": "string", "description": "Optional provider model override."},
                    "language": {"type": "string", "description": "Optional spoken language hint."},
                    "smart_format": {"type": "boolean", "description": "Ask the provider to normalize punctuation, numbers, and formatting."},
                    "mime_type": {"type": "string", "description": "Optional audio MIME type override."},
                    "reason": {"type": "string", "description": "Why the audio is being transcribed."},
                },
                required=["audio_path", "reason"],
            ),
            capability_group="voice",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        import os

        provider = str(tool_input.get("provider") or os.environ.get("HUMUNGOUSAUR_STT_PROVIDER") or os.environ.get("VOICE_STT_PROVIDER") or "local-whisper").strip().lower()
        if provider not in VOICE_TRANSCRIBE_PROVIDERS:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unsupported STT provider: {provider}")
        audio_path, error = _resolve_read_path(config, str(tool_input.get("audio_path", "")))
        if error:
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, error, error=error)
        assert audio_path is not None
        output = {
            "provider": provider,
            "audio_path": str(audio_path),
            "mime_type": str(tool_input.get("mime_type") or mimetypes.guess_type(str(audio_path))[0] or "application/octet-stream"),
            "reason": str(tool_input.get("reason", "")).strip(),
        }
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would transcribe audio through the configured STT provider.",
                {**output, "transcription_not_requested": True},
            )
        try:
            if provider == "deepgram":
                transcription = deepgram_transcribe_file(
                    audio_path,
                    api_key=_secret(config, "DEEPGRAM_API_KEY"),
                    model=str(tool_input.get("model") or config.secret_value("DEEPGRAM_MODEL") or ""),
                    language=str(tool_input.get("language") or ""),
                    smart_format=bool(tool_input.get("smart_format", True)),
                    mime_type=str(tool_input.get("mime_type") or ""),
                    timeout_seconds=float(config.model_timeout_seconds or 60.0),
                )
            else:
                transcription = local_whisper_transcribe_file(
                    audio_path,
                    model=str(tool_input.get("model") or ""),
                    language=str(tool_input.get("language") or ""),
                    timeout_seconds=float(config.model_timeout_seconds or 120.0),
                )
        except SpeechProviderError as exc:
            output["provider_error"] = classify_provider_error(str(exc))
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Speech-to-text provider failed.", output, str(exc))
        payload = {**output, **transcription.as_dict(), "transcript_length": len(transcription.transcript)}
        if not transcription.transcript:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Speech-to-text provider returned no transcript.",
                payload,
            )
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Transcribed audio through {provider}.",
            payload,
        )


class VoiceResponsePrepareTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="voice_response_prepare",
            description=(
                "Prepare a local spoken-response artifact for text-to-speech playback without speaking it immediately. "
                "Use when the agent should respond by voice or a UI should pick up speech output."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "text": {"type": "string", "description": "Response text to prepare for speech."},
                    "channel": {"type": "string", "enum": ["voice", "notification", "transcript"], "description": "Intended response channel."},
                    "reason": {"type": "string", "description": "Why a spoken response should be prepared."},
                    "run_id": {"type": "string", "description": "Optional agent run id this spoken response belongs to."},
                    "stimulus_id": {"type": "string", "description": "Optional stimulus id this spoken response belongs to."},
                    "tts_provider": {"type": "string", "enum": sorted(VOICE_PREPARE_PROVIDERS), "description": "Optional speech artifact provider."},
                    "fallback_tts_provider": {
                        "type": "string",
                        "enum": ["artifact", "system"],
                        "description": "Optional fallback provider if the requested cloud TTS provider fails.",
                    },
                    "rate": {"type": "integer", "minimum": -10, "maximum": 10, "description": "Windows SAPI speech rate for system synthesis."},
                    "volume": {"type": "integer", "minimum": 0, "maximum": 100, "description": "Windows SAPI speech volume for system synthesis."},
                    "voice_id": {"type": "string", "description": "ElevenLabs voice id. Can also be set with ELEVENLABS_VOICE_ID."},
                    "model": {"type": "string", "description": "Optional ElevenLabs model id."},
                    "output_format": {"type": "string", "description": "Optional ElevenLabs output format."},
                    "allow_voice_lookup": {"type": "boolean", "description": "Allow ElevenLabs to choose the first account voice if voice_id is not configured."},
                },
                required=["text", "reason"],
            ),
            capability_group="voice",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        text = _bounded_text(str(tool_input.get("text", "")), VOICE_RESPONSE_MAX_CHARS)
        if not text.strip():
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Voice response text is required.")
        channel = str(tool_input.get("channel", "voice")).strip().lower() or "voice"
        if channel not in {"voice", "notification", "transcript"}:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Unsupported voice response channel.", error="Unsupported voice response channel.")
        provider = _voice_prepare_provider(tool_input)
        fallback_provider = _voice_prepare_fallback_provider(tool_input, provider)
        payload = {
            "response_id": f"voice-response-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "channel": channel,
            "text": text,
            "text_length": len(text),
            "reason": str(tool_input.get("reason", "")).strip(),
            "run_id": str(tool_input.get("run_id", "")).strip(),
            "stimulus_id": str(tool_input.get("stimulus_id", "")).strip(),
            "source": "voice_response_prepare",
            "tts_provider": provider,
        }
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would prepare a local spoken-response artifact.",
                {**payload, "artifact_not_written": True, "speech_not_synthesized": provider in {"elevenlabs", "system"}},
            )
        if provider == "elevenlabs":
            try:
                synthesis = elevenlabs_synthesize_to_file(
                    text,
                    _voice_audio_dir(config),
                    response_id=payload["response_id"],
                    api_key=_elevenlabs_secret(config),
                    voice_id=str(tool_input.get("voice_id") or config.secret_value("ELEVENLABS_VOICE_ID") or ""),
                    model=str(tool_input.get("model") or config.secret_value("ELEVENLABS_MODEL_ID") or ""),
                    output_format=str(tool_input.get("output_format") or ""),
                    allow_voice_lookup=bool(tool_input.get("allow_voice_lookup", False)),
                    timeout_seconds=float(config.model_timeout_seconds or 60.0),
                )
            except SpeechProviderError as exc:
                payload["provider_error"] = classify_provider_error(str(exc))
                if fallback_provider == "system":
                    try:
                        synthesis = windows_sapi_synthesize_to_file(
                            text,
                            _voice_audio_dir(config),
                            response_id=payload["response_id"],
                            rate=max(-10, min(int(tool_input.get("rate") or 0), 10)),
                            volume=max(0, min(int(tool_input.get("volume") or 100), 100)),
                            timeout_seconds=float(config.model_timeout_seconds or 60.0),
                        )
                    except SpeechProviderError as fallback_exc:
                        payload["fallback_provider_error"] = classify_provider_error(str(fallback_exc))
                        return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Text-to-speech provider and fallback failed.", payload, str(fallback_exc))
                    payload["audio"] = synthesis.as_dict()
                    payload["primary_tts_provider"] = provider
                    payload["tts_provider"] = "system"
                    payload["fallback_tts_provider"] = "system"
                elif fallback_provider == "artifact":
                    payload["primary_tts_provider"] = provider
                    payload["tts_provider"] = "artifact"
                    payload["fallback_tts_provider"] = "artifact"
                else:
                    return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Text-to-speech provider failed.", payload, str(exc))
            else:
                payload["audio"] = synthesis.as_dict()
        if provider == "system":
            try:
                synthesis = windows_sapi_synthesize_to_file(
                    text,
                    _voice_audio_dir(config),
                    response_id=payload["response_id"],
                    rate=max(-10, min(int(tool_input.get("rate") or 0), 10)),
                    volume=max(0, min(int(tool_input.get("volume") or 100), 100)),
                    timeout_seconds=float(config.model_timeout_seconds or 60.0),
                )
            except SpeechProviderError as exc:
                payload["provider_error"] = classify_provider_error(str(exc))
                return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "System text-to-speech provider failed.", payload, str(exc))
            payload["audio"] = synthesis.as_dict()
        path = _voice_response_path(config, payload["response_id"])
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        payload["path"] = str(path)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            "Prepared local spoken-response artifact.",
            payload,
        )


class VoiceSpeakTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="voice_speak",
            description=(
                "Speak text to the user through the local OS text-to-speech engine. "
                "On Windows this uses SAPI.SpVoice; other platforms currently return unsupported."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "text": {"type": "string", "description": "Text to speak aloud."},
                    "rate": {"type": "integer", "minimum": -10, "maximum": 10, "description": "SAPI speech rate on Windows."},
                    "volume": {"type": "integer", "minimum": 0, "maximum": 100, "description": "SAPI speech volume on Windows."},
                    "reason": {"type": "string", "description": "Why the agent should speak aloud now."},
                    "provider": {"type": "string", "enum": sorted(VOICE_SPEAK_PROVIDERS), "description": "Text-to-speech playback provider."},
                    "voice_id": {"type": "string", "description": "ElevenLabs voice id. Can also be set with ELEVENLABS_VOICE_ID."},
                    "model": {"type": "string", "description": "Optional ElevenLabs model id."},
                    "output_format": {"type": "string", "description": "Optional ElevenLabs output format."},
                    "allow_voice_lookup": {"type": "boolean", "description": "Allow ElevenLabs to choose the first account voice if voice_id is not configured."},
                    "playback": {"type": "boolean", "description": "Whether to play synthesized provider audio immediately."},
                },
                required=["text", "reason"],
            ),
            capability_group="voice",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        text = _bounded_text(str(tool_input.get("text", "")), VOICE_SPEAK_MAX_CHARS)
        if not text.strip():
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Voice speech text is required.")
        provider = _voice_speak_provider(tool_input)
        rate = max(-10, min(int(tool_input.get("rate") or 0), 10))
        volume = max(0, min(int(tool_input.get("volume") or 100), 100))
        reason = str(tool_input.get("reason", "")).strip()
        output = {"text_length": len(text), "rate": rate, "volume": volume, "reason": reason, "provider": provider}
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would speak text through the configured TTS provider.",
                {**output, "speech_not_played": True},
            )
        if provider == "elevenlabs":
            response_id = f"voice-speak-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
            try:
                synthesis = elevenlabs_synthesize_to_file(
                    text,
                    _voice_audio_dir(config),
                    response_id=response_id,
                    api_key=_elevenlabs_secret(config),
                    voice_id=str(tool_input.get("voice_id") or config.secret_value("ELEVENLABS_VOICE_ID") or ""),
                    model=str(tool_input.get("model") or config.secret_value("ELEVENLABS_MODEL_ID") or ""),
                    output_format=str(tool_input.get("output_format") or ""),
                    allow_voice_lookup=bool(tool_input.get("allow_voice_lookup", False)),
                    timeout_seconds=float(config.model_timeout_seconds or 60.0),
                )
            except SpeechProviderError as exc:
                output["provider_error"] = classify_provider_error(str(exc))
                return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Text-to-speech provider failed.", output, str(exc))
            payload = {**output, "response_id": response_id, "audio": synthesis.as_dict()}
            if not bool(tool_input.get("playback", True)):
                return ToolResult(
                    self.name,
                    ActionStatus.SUCCEEDED,
                    self.risk_level,
                    "Synthesized speech through ElevenLabs without local playback.",
                    {**payload, "speech_played": False},
                )
            playback = play_audio_file(synthesis.audio_path, timeout_seconds=float(config.model_timeout_seconds or 60.0))
            payload["playback"] = playback
            if playback.get("status") != "ok":
                return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Synthesized speech, but local playback failed.", payload, playback.get("error"))
            return ToolResult(
                self.name,
                ActionStatus.SUCCEEDED,
                self.risk_level,
                "Synthesized and played speech through ElevenLabs.",
                {**payload, "speech_played": True},
            )
        if platform.system().lower() != "windows":
            return ToolResult(
                self.name,
                ActionStatus.FAILED,
                self.risk_level,
                "Local OS speech is currently implemented for Windows only.",
                output,
                "Local OS speech is currently implemented for Windows only.",
            )
        result = _run_powershell_tts(_sapi_speak_script(text=text, rate=rate, volume=volume))
        if result.get("status") != "ok":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Local OS speech failed.", {**output, **result}, result.get("error"))
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            "Spoke response through the local OS TTS engine.",
            {**output, "source": "windows_sapi"},
        )


class VoiceResponsesTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="voice_responses",
            description="List recent local spoken-response artifacts prepared for TTS or notification playback.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="voice",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = max(1, min(int(tool_input.get("limit") or 10), 50))
        responses = list_voice_responses(config, limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(responses)} local spoken-response artifact(s).",
            {"responses": responses, "image_bytes_served": False},
        )


def list_voice_responses(config: AgentConfig, limit: int = 20) -> list[dict[str, Any]]:
    directory = _voice_responses_dir(config)
    if not directory.exists():
        return []
    responses: list[dict[str, Any]] = []
    for path in sorted(directory.glob("voice-response-*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        responses.append(
            {
                "response_id": payload.get("response_id", path.stem),
                "created_at": payload.get("created_at", ""),
                "channel": payload.get("channel", ""),
                "text_preview": str(payload.get("text", ""))[:240],
                "text_length": int(payload.get("text_length") or len(str(payload.get("text", "")))),
                "run_id": payload.get("run_id", ""),
                "stimulus_id": payload.get("stimulus_id", ""),
                "tts_provider": payload.get("tts_provider", "artifact"),
                "audio": payload.get("audio", {}),
                "path": str(path),
            }
        )
        if len(responses) >= max(1, min(limit, 50)):
            break
    return responses


def default_voice_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        VoiceProviderStatusTool(),
        VoiceTranscribeTool(),
        VoiceResponsePrepareTool(),
        VoiceSpeakTool(),
        VoiceResponsesTool(),
    ]
    return {tool.name: tool for tool in tools}


def _voice_responses_dir(config: AgentConfig) -> Path:
    path = config.data_dir / "voice_responses"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _voice_audio_dir(config: AgentConfig) -> Path:
    path = _voice_responses_dir(config) / "audio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _voice_response_path(config: AgentConfig, response_id: str) -> Path:
    safe_name = "".join(char for char in response_id if char.isalnum() or char in {"-", "_"})
    if not safe_name:
        raise ValueError("Voice response id is invalid.")
    return _voice_responses_dir(config) / f"{safe_name}.json"


def _bounded_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def _voice_prepare_provider(tool_input: dict[str, Any]) -> str:
    provider = str(tool_input.get("tts_provider") or tool_input.get("provider") or _env_tts_provider() or "artifact").strip().lower()
    return provider if provider in VOICE_PREPARE_PROVIDERS else "artifact"


def _voice_prepare_fallback_provider(tool_input: dict[str, Any], primary_provider: str) -> str:
    provider = str(tool_input.get("fallback_tts_provider") or "").strip().lower()
    if provider not in {"artifact", "system"} or provider == primary_provider:
        return ""
    return provider


def _voice_speak_provider(tool_input: dict[str, Any]) -> str:
    provider = str(tool_input.get("provider") or tool_input.get("tts_provider") or _env_tts_provider() or "system").strip().lower()
    return provider if provider in VOICE_SPEAK_PROVIDERS else "system"


def _env_tts_provider() -> str:
    import os

    provider = os.environ.get("HUMUNGOUSAUR_TTS_PROVIDER") or os.environ.get("VOICE_TTS_PROVIDER") or ""
    return provider.strip().lower()


def _secret(config: AgentConfig, name: str) -> str | None:
    import os

    return config.normalized().secret_value(name) or os.environ.get(name)


def _elevenlabs_secret(config: AgentConfig) -> str | None:
    import os

    normalized = config.normalized()
    for name in ("ELEVENLABS_API_KEY", "ELEVEN_LABS_API_KEY", "ELEVAN_LABS_API_KEY", "ELEVANLABS_API_KEY"):
        value = normalized.secret_value(name) or os.environ.get(name)
        if value:
            return value
    return None


def _resolve_read_path(config: AgentConfig, raw_path: str) -> tuple[Path | None, str | None]:
    if not raw_path.strip():
        return None, "Audio path is required."
    normalized = config.normalized()
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = normalized.workspace / candidate
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        return None, f"Audio path is invalid: {exc}"
    roots = (*normalized.allowed_read_roots, normalized.data_dir)
    if not any(_path_inside(resolved, root) for root in roots):
        return None, "Audio path is outside the configured read roots."
    if not resolved.exists() or not resolved.is_file():
        return None, f"Audio file does not exist: {resolved}"
    return resolved, None


def _path_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _run_powershell_tts(script: str) -> dict[str, str]:
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                encoded,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
    if completed.returncode != 0:
        return {"status": "failed", "error": (completed.stderr or completed.stdout or "PowerShell TTS action failed.").strip()}
    return {"status": "ok", "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}


def _sapi_speak_script(text: str, rate: int, volume: int) -> str:
    return f"""
$ErrorActionPreference = "Stop"
$voice = New-Object -ComObject SAPI.SpVoice
$voice.Rate = {rate}
$voice.Volume = {volume}
[void]$voice.Speak({json.dumps(text)})
"""
