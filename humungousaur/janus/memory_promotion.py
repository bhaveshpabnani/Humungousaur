from __future__ import annotations

from dataclasses import asdict
from typing import Any

from humungousaur.cognition.knowledge import KnowledgeStore
from humungousaur.cognition.markdown_brain import refresh_cognitive_markdown
from humungousaur.cognition.models import KnowledgeKind
from humungousaur.cognition.recorder import CognitiveRecorder
from humungousaur.config import AgentConfig
from humungousaur.memory.event_store import EventStore
from humungousaur.planning.model_clients import redact_secrets

from .store import JanusStore


def promote_memory_candidate(
    config: AgentConfig,
    store: JanusStore,
    candidate_id: str,
    *,
    reason: str = "",
) -> dict[str, Any] | None:
    normalized = config.normalized()
    candidate = store.memory_candidate(candidate_id)
    if candidate is None:
        return None
    if candidate.get("status") in {"private", "rejected", "archived"}:
        return None

    knowledge_store = KnowledgeStore(normalized.cognition_db_path)
    existing_id = str(candidate.get("promoted_knowledge_id") or "")
    existing = knowledge_store.get(existing_id) if existing_id else None
    if existing is not None:
        return {
            "candidate": candidate,
            "knowledge": asdict(existing),
            "created": False,
            "reason": "already_promoted",
        }

    text = redact_secrets(_clean(candidate.get("summary"), limit=3_000))
    if not text:
        return None
    knowledge = knowledge_store.append(
        kind=_knowledge_kind(candidate.get("kind")),
        text=text,
        source="janus_memory_candidate",
        evidence_refs=_promotion_refs(candidate, reason=reason),
        confidence=_confidence(candidate),
    )
    promoted_candidate = store.mark_memory_candidate_promoted(candidate_id, knowledge_id=knowledge.knowledge_id) or candidate
    EventStore(normalized.memory_db_path).append(
        "janus_memory_promotion",
        {
            "candidate_id": candidate_id,
            "knowledge_id": knowledge.knowledge_id,
            "kind": knowledge.kind.value,
            "summary": text[:1_000],
            "reason": _clean(reason, limit=500),
            "evidence_refs": knowledge.evidence_refs,
            "privacy_note": "Promotion stores the candidate summary only; raw collector payloads are not included.",
        },
    )
    _refresh_markdown_best_effort(normalized)
    return {
        "candidate": promoted_candidate,
        "knowledge": asdict(knowledge),
        "created": True,
        "reason": "accepted",
    }


def retract_promoted_memory_candidate(
    config: AgentConfig,
    store: JanusStore,
    candidate_id: str,
    *,
    reason: str = "",
) -> dict[str, Any] | None:
    normalized = config.normalized()
    candidate = store.memory_candidate(candidate_id)
    if candidate is None:
        return None
    knowledge_id = str(candidate.get("promoted_knowledge_id") or "")
    if not knowledge_id:
        return None
    knowledge_store = KnowledgeStore(normalized.cognition_db_path)
    archived = knowledge_store.archive(knowledge_id, reason=_clean(reason or "janus correction", limit=300))
    if archived is None:
        return None
    EventStore(normalized.memory_db_path).append(
        "janus_memory_retraction",
        {
            "candidate_id": candidate_id,
            "knowledge_id": knowledge_id,
            "candidate_status": candidate.get("status", ""),
            "reason": _clean(reason, limit=500),
            "privacy_note": "Retraction records ids and status only; raw collector payloads are not included.",
        },
    )
    _refresh_markdown_best_effort(normalized)
    return {
        "candidate": candidate,
        "knowledge": asdict(archived),
        "reason": "retracted",
    }


def _promotion_refs(candidate: dict[str, Any], *, reason: str) -> list[str]:
    refs = [
        f"active_memory_candidate:{candidate.get('candidate_id', '')}",
        f"active_reflex_decision:{candidate.get('decision_id', '')}",
        f"active_route:{candidate.get('route_id', '')}",
    ]
    refs.extend(str(item) for item in candidate.get("evidence_refs", []) if str(item))
    cleaned_reason = _clean(reason, limit=300)
    if cleaned_reason:
        refs.append(f"user_correction:{cleaned_reason}")
    return _dedupe([_clean(item, limit=500) for item in refs if _clean(item, limit=500)])[:30]


def _knowledge_kind(value: object) -> KnowledgeKind:
    normalized = str(value or "").strip().lower()
    aliases = {
        "preference": KnowledgeKind.PREFERENCE,
        "user_preference": KnowledgeKind.PREFERENCE,
        "fact": KnowledgeKind.FACT,
        "stable_fact": KnowledgeKind.FACT,
        "procedure": KnowledgeKind.PROCEDURE,
        "workflow": KnowledgeKind.PROCEDURE,
        "project": KnowledgeKind.PROJECT,
        "lesson": KnowledgeKind.LESSON,
    }
    if normalized in aliases:
        return aliases[normalized]
    try:
        return KnowledgeKind(normalized)
    except ValueError:
        return KnowledgeKind.CONTEXT


def _confidence(candidate: dict[str, Any]) -> float:
    importance = str(candidate.get("importance") or "").strip().lower()
    if importance in {"high", "critical"}:
        return 0.85
    if importance in {"low", "minor"}:
        return 0.55
    return 0.7


def _refresh_markdown_best_effort(config: AgentConfig) -> None:
    try:
        recorder = CognitiveRecorder(config)
        refresh_cognitive_markdown(config, recorder.snapshot())
    except OSError:
        EventStore(config.memory_db_path).append(
            "cognitive_markdown_refresh_failed",
            {"source": "janus_memory_promotion", "reason": "filesystem_error"},
        )


def _clean(value: object, *, limit: int) -> str:
    return " ".join(str(value or "").strip().split())[: max(1, int(limit))]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output
