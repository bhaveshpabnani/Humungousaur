from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

from humungousaur.config import AgentConfig
from humungousaur.cognition import CognitiveRecorder
from humungousaur.cognition.models import CognitiveDecision
from humungousaur.memory.event_store import EventStore
from humungousaur.orchestrator import AgentOrchestrator
from humungousaur.schemas import AgentRunResult
from humungousaur.tools.voice_tools import VoiceResponsePrepareTool, VoiceSpeakTool


STIMULUS_SOURCES = {
    "user_text",
    "voice_transcript",
    "activity",
    "accessibility",
    "screen_ocr",
    "audio_transcript",
    "browser",
    "system",
}
HARNESS_DECISIONS = {"respond", "analyze", "observe", "ignore", "monitor"}
RESPONSE_MODES = {"text", "voice_prepare", "voice_speak", "silent"}
ACTION_INTENTS = {"task", "question", "request", "respond", "analyze", "act"}


@dataclass(slots=True)
class Stimulus:
    text: str
    source: str = "user_text"
    metadata: dict[str, Any] = field(default_factory=dict)
    stimulus_id: str = field(default_factory=lambda: f"stimulus-{uuid.uuid4().hex[:12]}")
    occurred_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(slots=True)
class HarnessDecision:
    decision: str
    request: str
    response_mode: str
    reason: str
    should_run_agent: bool
    should_record_activity: bool
    should_prepare_voice: bool
    should_speak: bool


@dataclass(slots=True)
class HarnessResult:
    stimulus: Stimulus
    decision: HarnessDecision
    run: AgentRunResult | None = None
    voice_result: dict[str, Any] | None = None
    recorded_event_id: str | None = None


class InteractionHarness:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config.normalized()
        self.memory = EventStore(self.config.memory_db_path)

    def handle(
        self,
        stimulus: Stimulus | dict[str, Any] | str,
        *,
        response_mode: str | None = None,
        approve_high_risk: bool = False,
    ) -> HarnessResult:
        normalized = normalize_stimulus(stimulus)
        cognitive = CognitiveRecorder(self.config)
        cognitive_event, cognitive_decision, cognitive_goal_id, cognitive_task_id = cognitive.begin_stimulus(
            source=normalized.source,
            text=normalized.text,
            metadata=normalized.metadata,
            response_mode=response_mode,
            event_id=normalized.stimulus_id,
        )
        decision = harness_decision_from_cognitive(cognitive_decision, normalized)
        recorded_event_id = self._record_stimulus(normalized, decision) if decision.should_record_activity else None
        run: AgentRunResult | None = None
        voice_result: dict[str, Any] | None = None
        if decision.should_run_agent:
            run = AgentOrchestrator(self.config).run(decision.request, approve_high_risk=approve_high_risk)
            if decision.should_prepare_voice or decision.should_speak:
                voice_result = self._emit_voice_response(
                    text=run.final_response,
                    stimulus_id=normalized.stimulus_id,
                    run_id=run.run_id,
                    speak=decision.should_speak,
                )
        cognitive.finish_stimulus(
            event_id=cognitive_event.event_id,
            decision=cognitive_decision,
            goal_id=cognitive_goal_id,
            task_id=cognitive_task_id,
            run=run,
            voice_result=voice_result,
        )
        result = HarnessResult(
            stimulus=normalized,
            decision=decision,
            run=run,
            voice_result=voice_result,
            recorded_event_id=recorded_event_id,
        )
        self.memory.append(
            "interaction_result",
            {
                "stimulus_id": normalized.stimulus_id,
                "source": normalized.source,
                "decision": decision.decision,
                "response_mode": decision.response_mode,
                "run_id": run.run_id if run is not None else "",
                "voice_response_id": (voice_result or {}).get("response_id", ""),
                "recorded_event_id": recorded_event_id or "",
            },
        )
        return result

    def _record_stimulus(self, stimulus: Stimulus, decision: HarnessDecision) -> str:
        return self.memory.append(
            "interaction_stimulus",
            {
                "stimulus_id": stimulus.stimulus_id,
                "source": stimulus.source,
                "text": stimulus.text,
                "metadata": stimulus.metadata,
                "occurred_at": stimulus.occurred_at,
                "decision": decision.decision,
                "decision_reason": decision.reason,
            },
        )

    def _emit_voice_response(self, text: str, stimulus_id: str, run_id: str, speak: bool) -> dict[str, Any]:
        prepared = VoiceResponsePrepareTool().execute(
            {
                "text": text,
                "channel": "voice",
                "reason": "Agent harness prepared a spoken response.",
                "stimulus_id": stimulus_id,
                "run_id": run_id,
            },
            self.config,
        )
        output = dict(prepared.output)
        output["prepare_status"] = prepared.status.value
        if speak:
            spoken = VoiceSpeakTool().execute(
                {"text": text, "reason": "Agent harness is responding aloud to the user."},
                self.config,
            )
            output["speak_status"] = spoken.status.value
            output["speak_summary"] = spoken.summary
            if spoken.error:
                output["speak_error"] = spoken.error
        return output


def normalize_stimulus(stimulus: Stimulus | dict[str, Any] | str) -> Stimulus:
    if isinstance(stimulus, Stimulus):
        return stimulus
    if isinstance(stimulus, str):
        return Stimulus(text=stimulus)
    if not isinstance(stimulus, dict):
        raise TypeError("Stimulus must be a Stimulus, string, or object.")
    source = str(stimulus.get("source", "user_text")).strip() or "user_text"
    if source not in STIMULUS_SOURCES:
        source = "activity"
    text = str(stimulus.get("text", "")).strip()
    metadata = stimulus.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    stimulus_id = str(stimulus.get("stimulus_id", "")).strip() or f"stimulus-{uuid.uuid4().hex[:12]}"
    occurred_at = str(stimulus.get("occurred_at", "")).strip() or datetime.now(timezone.utc).isoformat()
    return Stimulus(text=text, source=source, metadata=metadata, stimulus_id=stimulus_id, occurred_at=occurred_at)


def decide_interaction(stimulus: Stimulus, response_mode: str | None = None) -> HarnessDecision:
    """Explicit fallback helper for compatibility; InteractionHarness uses CognitiveRecorder decisions."""

    mode = (response_mode or str(stimulus.metadata.get("response_mode", "")) or _default_response_mode(stimulus)).strip().lower()
    if mode not in RESPONSE_MODES:
        mode = _default_response_mode(stimulus)
    text = stimulus.text.strip()
    if not text:
        return HarnessDecision(
            decision="ignore",
            request="",
            response_mode="silent",
            reason="Empty stimulus.",
            should_run_agent=False,
            should_record_activity=False,
            should_prepare_voice=False,
            should_speak=False,
        )
    if stimulus.source in {"user_text", "voice_transcript"}:
        decision = "respond"
        should_run = True
        reason = "Direct user stimulus."
    elif _metadata_requests_action(stimulus):
        decision = "analyze" if mode == "silent" else "respond"
        should_run = True
        reason = "Passive stimulus carried structured action metadata."
    elif stimulus.source in {"activity", "accessibility", "screen_ocr", "audio_transcript", "browser"}:
        decision = "observe"
        should_run = False
        reason = "Passive activity recorded for context; no explicit request detected."
    else:
        decision = "ignore"
        should_run = False
        reason = "Stimulus did not require action."
    return HarnessDecision(
        decision=decision,
        request=text if should_run else "",
        response_mode=mode if should_run else "silent",
        reason=reason,
        should_run_agent=should_run,
        should_record_activity=stimulus.source not in {"user_text"},
        should_prepare_voice=should_run and mode in {"voice_prepare", "voice_speak"},
        should_speak=should_run and mode == "voice_speak",
    )


def harness_decision_from_cognitive(decision: CognitiveDecision, stimulus: Stimulus) -> HarnessDecision:
    should_run = bool(decision.should_run_agent)
    mode = _normalized_response_mode(decision.response_mode, stimulus) if should_run else "silent"
    request = decision.request.strip() if should_run else ""
    if should_run and not request:
        request = stimulus.text.strip()
    return HarnessDecision(
        decision=decision.action.value if decision.action.value in HARNESS_DECISIONS else "observe",
        request=request,
        response_mode=mode,
        reason=decision.reason,
        should_run_agent=should_run,
        should_record_activity=bool(decision.should_record_event),
        should_prepare_voice=should_run and mode in {"voice_prepare", "voice_speak"},
        should_speak=should_run and mode == "voice_speak",
    )


def harness_result_to_dict(result: HarnessResult) -> dict[str, Any]:
    payload = {
        "stimulus": asdict(result.stimulus),
        "decision": asdict(result.decision),
        "recorded_event_id": result.recorded_event_id,
        "voice_result": result.voice_result,
    }
    if result.run is not None:
        payload["run"] = asdict(result.run)
    else:
        payload["run"] = None
    return payload


def _default_response_mode(stimulus: Stimulus) -> str:
    if stimulus.source == "voice_transcript":
        return "voice_prepare"
    return "text"


def _normalized_response_mode(response_mode: str, stimulus: Stimulus) -> str:
    mode = str(response_mode or "").strip().lower()
    return mode if mode in RESPONSE_MODES else _default_response_mode(stimulus)


def _metadata_requests_action(stimulus: Stimulus) -> bool:
    metadata = stimulus.metadata
    if metadata.get("should_run_agent") is True or metadata.get("requires_response") is True:
        return True
    intent = str(metadata.get("intent", "")).strip().lower()
    return intent in ACTION_INTENTS
