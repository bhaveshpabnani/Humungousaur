from __future__ import annotations

import json
from typing import Any

from humungousaur.planning.model_clients import ModelClient, ModelClientError, redact_secrets
from humungousaur.planning.prompt_templates import render_prompt_template
from humungousaur.planning.structured import load_json_object

from .activity_guides import ActivityGuide
from .models import ActiveAgentDecision, ActiveAgentRoute, Confidence, ReflexPosture, new_id
from .redaction import safe_compact_mapping


COGNITION_PROMPT_RESOURCE = "resources/prompts/cognition.yaml"


class ReflexInterpreter:
    """Small model-led interpreter for active-agent reflex and triage decisions."""

    def __init__(self, model_client: ModelClient | None = None) -> None:
        self.model_client = model_client

    def interpret(
        self,
        *,
        route: ActiveAgentRoute,
        event: dict[str, Any],
        context_window: dict[str, Any],
        task_contexts: list[dict[str, Any]],
        muted_scopes: list[dict[str, Any]],
        activity_guides: list[ActivityGuide],
        policy: dict[str, Any],
        active_episodes: list[dict[str, Any]] | None = None,
        active_episode_events: list[dict[str, Any]] | None = None,
        corrections: list[dict[str, Any]] | None = None,
        deep_dive_requests: list[dict[str, Any]] | None = None,
    ) -> ActiveAgentDecision:
        if self.model_client is None:
            return _safe_no_model_decision(route)
        prompt = _build_prompt(
            route=route,
            event=event,
            context_window=context_window,
            task_contexts=task_contexts,
            muted_scopes=muted_scopes,
            active_episodes=active_episodes or [],
            active_episode_events=active_episode_events or [],
            corrections=corrections or [],
            deep_dive_requests=deep_dive_requests or [],
            activity_guides=activity_guides,
            policy=policy,
        )
        try:
            raw = self.model_client.complete_json(prompt, reflex_decision_schema())
            payload = load_json_object(raw, label="Reflex decision")
            return parse_reflex_decision(payload, route=route, model_status="model")
        except (ModelClientError, ValueError, KeyError, json.JSONDecodeError):
            return _safe_no_model_decision(route)


def reflex_decision_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "posture",
            "confidence",
            "should_interrupt_user",
            "user_visible_text",
            "agent_stimulus",
            "reason",
            "task_context_updates",
            "memory_updates",
            "safety_notes",
            "deep_dive_request",
        ],
        "properties": {
            "posture": {"type": "string", "enum": [item.value for item in ReflexPosture]},
            "confidence": {"type": "string", "enum": [item.value for item in Confidence]},
            "should_interrupt_user": {"type": "boolean"},
            "user_visible_text": {"type": "string"},
            "agent_stimulus": {"type": "string"},
            "reason": {"type": "string"},
            "task_context_updates": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "memory_updates": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "safety_notes": {"type": "array", "items": {"type": "string"}},
            "episode_update": {
                "anyOf": [
                    {"type": "null"},
                    {
                        "type": "object",
                        "additionalProperties": True,
                        "required": ["action", "confidence", "status", "hypothesis", "summary", "reason"],
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": [
                                    "observe_only",
                                    "start_episode",
                                    "continue_episode",
                                    "resume_episode",
                                    "split_episode",
                                    "pause_episode",
                                    "complete_episode",
                                    "abandon_episode",
                                ],
                            },
                            "episode_id": {"type": "string"},
                            "confidence": {"type": "string", "enum": [item.value for item in Confidence]},
                            "status": {"type": "string"},
                            "hypothesis": {"type": "string"},
                            "summary": {"type": "string"},
                            "primary_entities": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
                            "supporting_entities": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
                            "task_context_id": {"type": "string"},
                            "correction_refs": {"type": "array", "items": {"type": "string"}},
                            "deep_dive_refs": {"type": "array", "items": {"type": "string"}},
                            "evidence_refs": {"type": "array", "items": {"type": "string"}},
                            "reason": {"type": "string"},
                        },
                    },
                ]
            },
            "deep_dive_request": {
                "anyOf": [
                    {"type": "null"},
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["episode_id", "purpose", "source", "requested_access", "privacy_tier", "requires_user_approval"],
                        "properties": {
                            "episode_id": {"type": "string"},
                            "purpose": {"type": "string"},
                            "source": {"type": "string"},
                            "requested_access": {"type": "string"},
                            "privacy_tier": {"type": "string"},
                            "requires_user_approval": {"type": "boolean"},
                        },
                    },
                ]
            },
        },
    }


def parse_reflex_decision(payload: dict[str, Any], *, route: ActiveAgentRoute, model_status: str) -> ActiveAgentDecision:
    posture = ReflexPosture(str(payload["posture"]))
    confidence = Confidence(str(payload["confidence"]))
    should_interrupt = bool(payload["should_interrupt_user"])
    user_visible_text = redact_secrets(str(payload.get("user_visible_text") or ""))[:1_000]
    agent_stimulus = redact_secrets(str(payload.get("agent_stimulus") or ""))[:2_000]
    if posture in {ReflexPosture.STAY_SILENT, ReflexPosture.REMEMBER, ReflexPosture.SUMMARIZE, ReflexPosture.PREPARE}:
        should_interrupt = False
        if posture != ReflexPosture.PREPARE:
            user_visible_text = ""
    if posture in {ReflexPosture.WAKE_MAIN_AGENT, ReflexPosture.ASK_USER} and not agent_stimulus and not user_visible_text:
        posture = ReflexPosture.REMEMBER
        should_interrupt = False
    return ActiveAgentDecision(
        decision_id=new_id("reflex"),
        route_id=route.route_id,
        event_sequence=route.event_sequence,
        posture=posture,
        confidence=confidence,
        should_interrupt_user=should_interrupt,
        user_visible_text=user_visible_text,
        agent_stimulus=agent_stimulus,
        reason=redact_secrets(str(payload.get("reason") or "Model-led reflex decision."))[:1_000],
        task_context_updates=_safe_dicts(payload.get("task_context_updates")),
        memory_updates=_safe_dicts(payload.get("memory_updates")),
        safety_notes=[redact_secrets(str(item))[:400] for item in _list(payload.get("safety_notes"))],
        deep_dive_request=_safe_dict(payload.get("deep_dive_request")),
        episode_update=_safe_dict(payload.get("episode_update")),
        model_status=model_status,
        raw_output=_safe_dict(payload) or {},
    )


def _build_prompt(
    *,
    route: ActiveAgentRoute,
    event: dict[str, Any],
    context_window: dict[str, Any],
    task_contexts: list[dict[str, Any]],
    muted_scopes: list[dict[str, Any]],
    activity_guides: list[ActivityGuide],
    policy: dict[str, Any],
    active_episodes: list[dict[str, Any]],
    active_episode_events: list[dict[str, Any]],
    corrections: list[dict[str, Any]],
    deep_dive_requests: list[dict[str, Any]],
) -> str:
    payload = {
        "route": {
            "route_class": route.route_class.value,
            "reason": route.reason,
            "collector": route.collector,
            "source": route.source,
            "stimulus_type": route.stimulus_type,
            "privacy_tier": route.privacy_tier,
        },
        "event": _compact_event(event),
        "recent_context": context_window,
        "task_contexts": task_contexts[:8],
        "muted_scopes": muted_scopes[:8],
        "active_episodes": [_compact_record(item) for item in active_episodes[:6]],
        "active_episode_events": [_compact_record(item) for item in active_episode_events[:12]],
        "recent_corrections": [_compact_record(item) for item in corrections[:8]],
        "deep_dive_requests": [_compact_record(item) for item in deep_dive_requests[:8]],
        "policy": policy,
        "activity_guides": [guide.prompt_payload for guide in activity_guides],
    }
    return render_prompt_template(
        "reflex_interpretation",
        resource=COGNITION_PROMPT_RESOURCE,
        reflex_input=json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")),
    )


def _compact_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "sequence": int(event.get("sequence") or 0),
        "event_id": str(event.get("event_id") or ""),
        "collector": str(event.get("collector") or ""),
        "source": str(event.get("source") or ""),
        "stimulus_type": str(event.get("stimulus_type") or ""),
        "privacy_tier": str(event.get("privacy_tier") or ""),
        "occurred_at": str(event.get("occurred_at") or ""),
        "text": str(event.get("text") or "")[:500],
        "metadata": safe_compact_mapping(event.get("metadata")),
        "payload": safe_compact_mapping(event.get("payload")),
        "redaction": safe_compact_mapping(event.get("redaction")),
    }


def _compact_record(record: dict[str, Any]) -> dict[str, Any]:
    compact = safe_compact_mapping(record)
    for key, value in list(compact.items()):
        if isinstance(value, str):
            compact[key] = redact_secrets(" ".join(value.split()))[:500]
    return compact


def _safe_no_model_decision(route: ActiveAgentRoute) -> ActiveAgentDecision:
    return ActiveAgentDecision(
        decision_id=new_id("reflex"),
        route_id=route.route_id,
        event_sequence=route.event_sequence,
        posture=ReflexPosture.STAY_SILENT,
        confidence=Confidence.LOW,
        should_interrupt_user=False,
        reason="Reflex model unavailable; preserved event state without semantic inference.",
        safety_notes=["No model-led activity interpretation was performed."],
        model_status="unavailable",
    )


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in _list(value) if isinstance(item, dict)][:20]


def _safe_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in (_safe_dict(item) for item in _list(value) if isinstance(item, dict)) if item][:20]


def _safe_dict(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return _drop_redacted_fields(safe_compact_mapping(value))


def _drop_redacted_fields(value: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        if item == "[redacted]":
            continue
        if isinstance(item, dict):
            nested = _drop_redacted_fields(item)
            if nested:
                cleaned[key] = nested
            continue
        if isinstance(item, list):
            nested_list = [_drop_redacted_fields(child) if isinstance(child, dict) else child for child in item]
            nested_list = [child for child in nested_list if child not in ("[redacted]", {}, [])]
            if nested_list:
                cleaned[key] = nested_list
            continue
        cleaned[key] = item
    return cleaned
