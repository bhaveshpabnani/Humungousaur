from __future__ import annotations

import json
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.interaction import HarnessResult, InteractionHarness, Stimulus
from humungousaur.orchestrator import AgentOrchestrator
from humungousaur.schemas import ActionStatus, AgentRunResult
from humungousaur.tools.voice_tools import VoiceTranscribeTool


def transcript_from_activation(path: Path, config: AgentConfig | None = None) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    transcript = str(payload.get("transcript", "")).strip()
    if transcript:
        return transcript

    transcript_path = payload.get("transcript_path")
    if transcript_path:
        candidate = Path(transcript_path)
        if candidate.exists():
            return candidate.read_text(encoding="utf-8").strip()

    audio_path = _activation_audio_path(path, payload)
    if audio_path is not None and config is not None:
        result = VoiceTranscribeTool().execute(
            {
                "audio_path": str(audio_path),
                "provider": str(payload.get("stt_provider") or "deepgram"),
                "model": str(payload.get("stt_model") or ""),
                "language": str(payload.get("language") or ""),
                "smart_format": bool(payload.get("smart_format", True)),
                "mime_type": str(payload.get("mime_type") or ""),
                "reason": "Transcribe voice-wakeup activation audio.",
            },
            config,
        )
        if result.status == ActionStatus.SUCCEEDED:
            return str(result.output.get("transcript", "")).strip()
        raise ValueError(f"Activation audio transcription failed: {result.summary} {result.error or ''}".strip())

    raise ValueError(f"No transcript found in activation file: {path}")


def run_activation(path: Path, config: AgentConfig) -> AgentRunResult:
    transcript = transcript_from_activation(path, config)
    return AgentOrchestrator(config).run(transcript)


def handle_activation(
    path: Path,
    config: AgentConfig,
    response_mode: str = "voice_prepare",
    approve_high_risk: bool = False,
    stt_provider: str = "",
    tts_provider: str = "",
    voice_id: str = "",
    tts_model: str = "",
) -> HarnessResult:
    transcript = transcript_from_activation(path, config)
    metadata = _activation_metadata(path)
    if stt_provider:
        metadata["stt_provider"] = stt_provider
    if tts_provider:
        metadata["tts_provider"] = tts_provider
    if voice_id:
        metadata["voice_id"] = voice_id
    if tts_model:
        metadata["tts_model"] = tts_model
    stimulus = Stimulus(
        text=transcript,
        source="voice_transcript",
        metadata={**metadata, "activation_path": str(path), "response_mode": response_mode},
    )
    return InteractionHarness(config).handle(stimulus, response_mode=response_mode, approve_high_risk=approve_high_risk)


def _activation_metadata(path: Path) -> dict[str, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {key: str(value) for key, value in payload.items() if key != "transcript"}


def _activation_audio_path(activation_path: Path, payload: object) -> Path | None:
    if not isinstance(payload, dict):
        return None
    for key in ("audio_path", "recording_path", "wav_path", "audio_file"):
        raw = str(payload.get(key) or "").strip()
        if not raw:
            continue
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = activation_path.parent / candidate
        return candidate
    return None
