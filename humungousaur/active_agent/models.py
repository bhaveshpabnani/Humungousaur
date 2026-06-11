from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


class RouteClass(str, Enum):
    REFLEX = "reflex"
    TRIAGE = "triage"
    CONTEXT = "context"
    MUTED = "muted"
    BLOCKED = "blocked"
    DEEP_DIVE = "deep_dive"


class ReflexPosture(str, Enum):
    STAY_SILENT = "stay_silent"
    REMEMBER = "remember"
    SUMMARIZE = "summarize"
    PREPARE = "prepare"
    ASK_USER = "ask_user"
    WAKE_MAIN_AGENT = "wake_main_agent"
    REQUEST_DEEP_DIVE = "request_deep_dive"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MutedScopeMode(str, Enum):
    NO_ASSISTANCE = "no_assistance"
    NOT_NOW = "not_now"
    DO_NOT_TRACK = "do_not_track"
    PRIVATE = "private"


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ActiveAgentRoute:
    route_id: str
    event_sequence: int
    event_id: str
    collector: str
    source: str
    stimulus_type: str
    privacy_tier: str
    route_class: RouteClass
    reason: str
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class TaskContext:
    task_context_id: str
    status: str = "active"
    source: str = "inferred"
    user_declared_goal: str = ""
    episode_id: str = ""
    primary_entities: list[dict[str, Any]] = field(default_factory=list)
    supporting_entities: list[dict[str, Any]] = field(default_factory=list)
    assistant_mode: str = "metadata_first"
    allowed_help: list[str] = field(default_factory=list)
    privacy_mode: str = "metadata_first"
    summary: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class ActiveEpisode:
    episode_id: str
    status: str = "active"
    source: str = "model"
    hypothesis: str = ""
    summary: str = ""
    confidence: Confidence = Confidence.LOW
    primary_entities: list[dict[str, Any]] = field(default_factory=list)
    supporting_entities: list[dict[str, Any]] = field(default_factory=list)
    task_context_id: str = ""
    correction_refs: list[str] = field(default_factory=list)
    deep_dive_refs: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    last_event_sequence: int = 0
    event_count: int = 0
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class MutedScope:
    scope_id: str
    mode: MutedScopeMode
    scope_type: str
    status: str = "active"
    entity_refs: list[str] = field(default_factory=list)
    collector: str = ""
    source: str = ""
    stimulus_type: str = ""
    expires_at: str = ""
    do_not_interrupt: bool = True
    do_not_deep_dive: bool = True
    do_not_send_to_llm: bool = True
    do_not_store: bool = False
    reason: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class DeepDiveRequest:
    request_id: str
    episode_id: str
    requested_by: str
    purpose: str
    source: str
    requested_access: str
    privacy_tier: str = "rich_capture"
    requires_user_approval: bool = True
    status: str = "needs_approval"
    evidence_refs: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class DeepDiveResult:
    result_id: str
    request_id: str
    episode_id: str = ""
    status: str = "completed"
    executor: str = "local_context"
    summary: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    safety_notes: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class ActiveAgentDecision:
    decision_id: str
    route_id: str
    event_sequence: int
    posture: ReflexPosture
    confidence: Confidence
    should_interrupt_user: bool
    user_visible_text: str = ""
    agent_stimulus: str = ""
    reason: str = ""
    task_context_updates: list[dict[str, Any]] = field(default_factory=list)
    memory_updates: list[dict[str, Any]] = field(default_factory=list)
    safety_notes: list[str] = field(default_factory=list)
    deep_dive_request: dict[str, Any] | None = None
    episode_update: dict[str, Any] | None = None
    model_status: str = "model"
    raw_output: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class ActiveAgentActivation:
    activation_id: str
    decision_id: str
    route_id: str
    event_sequence: int
    posture: ReflexPosture
    status: str
    response_mode: str
    stimulus_id: str
    user_visible_text: str = ""
    agent_stimulus: str = ""
    reason: str = ""
    should_interrupt_user: bool = False
    allowed_actions: list[str] = field(default_factory=list)
    forbidden_actions: list[str] = field(default_factory=list)
    harness_result: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class ActivationResponse:
    response_id: str
    activation_id: str
    response_type: str
    text: str = ""
    action_taken: str = ""
    task_context_id: str = ""
    muted_scope_id: str = ""
    harness_result: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class ActiveAgentMemoryCandidate:
    candidate_id: str
    decision_id: str
    route_id: str
    event_sequence: int
    kind: str
    summary: str
    importance: str = "normal"
    status: str = "candidate"
    payload: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class ActiveAgentStatus:
    routes: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    activations: list[dict[str, Any]]
    memory_candidates: list[dict[str, Any]]
    episodes: list[dict[str, Any]]
    episode_events: list[dict[str, Any]]
    task_contexts: list[dict[str, Any]]
    muted_scopes: list[dict[str, Any]]
    deep_dive_requests: list[dict[str, Any]]
    deep_dive_results: list[dict[str, Any]] = field(default_factory=list)
    activation_responses: list[dict[str, Any]] = field(default_factory=list)
    episode_links: list[dict[str, Any]] = field(default_factory=list)
    privacy_actions: list[dict[str, Any]] = field(default_factory=list)
    eval_runs: list[dict[str, Any]] = field(default_factory=list)
    context_window: dict[str, Any] = field(default_factory=dict)
    context_windows: list[dict[str, Any]] = field(default_factory=list)
    context_boundaries: list[dict[str, Any]] = field(default_factory=list)
    resume_capsules: list[dict[str, Any]] = field(default_factory=list)
    explanations: list[dict[str, Any]] = field(default_factory=list)
    corrections: list[dict[str, Any]] = field(default_factory=list)
