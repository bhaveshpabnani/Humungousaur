from __future__ import annotations

import base64
import json
import platform
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


VOICE_RESPONSE_MAX_CHARS = 20_000
VOICE_SPEAK_MAX_CHARS = 4_000


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
        }
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would prepare a local spoken-response artifact.",
                {**payload, "artifact_not_written": True},
            )
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
                },
                required=["text", "reason"],
            ),
            capability_group="voice",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        text = _bounded_text(str(tool_input.get("text", "")), VOICE_SPEAK_MAX_CHARS)
        if not text.strip():
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Voice speech text is required.")
        rate = max(-10, min(int(tool_input.get("rate") or 0), 10))
        volume = max(0, min(int(tool_input.get("volume") or 100), 100))
        reason = str(tool_input.get("reason", "")).strip()
        output = {"text_length": len(text), "rate": rate, "volume": volume, "reason": reason}
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would speak text through the local OS TTS engine.",
                {**output, "speech_not_played": True},
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
                "path": str(path),
            }
        )
        if len(responses) >= max(1, min(limit, 50)):
            break
    return responses


def default_voice_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        VoiceResponsePrepareTool(),
        VoiceSpeakTool(),
        VoiceResponsesTool(),
    ]
    return {tool.name: tool for tool in tools}


def _voice_responses_dir(config: AgentConfig) -> Path:
    path = config.data_dir / "voice_responses"
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
