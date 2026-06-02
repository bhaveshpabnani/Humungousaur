from __future__ import annotations

import json
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.interaction import HarnessResult, InteractionHarness, Stimulus
from humungousaur.orchestrator import AgentOrchestrator
from humungousaur.schemas import AgentRunResult


def transcript_from_activation(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    transcript = str(payload.get("transcript", "")).strip()
    if transcript:
        return transcript

    transcript_path = payload.get("transcript_path")
    if transcript_path:
        candidate = Path(transcript_path)
        if candidate.exists():
            return candidate.read_text(encoding="utf-8").strip()

    raise ValueError(f"No transcript found in activation file: {path}")


def run_activation(path: Path, config: AgentConfig) -> AgentRunResult:
    transcript = transcript_from_activation(path)
    return AgentOrchestrator(config).run(transcript)


def handle_activation(
    path: Path,
    config: AgentConfig,
    response_mode: str = "voice_prepare",
    approve_high_risk: bool = False,
) -> HarnessResult:
    transcript = transcript_from_activation(path)
    metadata = _activation_metadata(path)
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
