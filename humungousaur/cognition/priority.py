from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from humungousaur.planning.model_clients import ModelClient, ModelClientError, redact_secrets
from humungousaur.planning.prompt_templates import render_prompt_template

from .models import CognitiveSnapshot, PriorityReviewRecord, PriorityReviewStatus, new_id, utc_now


COGNITION_PROMPT_RESOURCE = "resources/prompts/cognition.yaml"


@dataclass(slots=True)
class PriorityReviewProposal:
    status: PriorityReviewStatus
    purpose: str
    summary: str
    focus_recommendation: str
    ranked_goal_ids: list[str]
    ranked_task_ids: list[str]
    ranked_commitment_ids: list[str]
    next_actions: list[str]
    deferred_items: list[str]
    escalation_items: list[str]
    evidence_refs: list[str]
    confidence: float


class PriorityReviewStore:
    """Durable model-led priority and initiative reviews."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cognitive_priority_reviews (
                    review_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    focus_recommendation TEXT NOT NULL,
                    ranked_goal_ids TEXT NOT NULL,
                    ranked_task_ids TEXT NOT NULL,
                    ranked_commitment_ids TEXT NOT NULL,
                    next_actions TEXT NOT NULL,
                    deferred_items TEXT NOT NULL,
                    escalation_items TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cognitive_priority_reviews_created_at ON cognitive_priority_reviews(created_at)")
            connection.commit()

    def append(self, record: PriorityReviewRecord) -> PriorityReviewRecord:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO cognitive_priority_reviews
                (review_id, status, purpose, summary, focus_recommendation, ranked_goal_ids, ranked_task_ids, ranked_commitment_ids, next_actions, deferred_items, escalation_items, evidence_refs, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.review_id,
                    record.status.value,
                    record.purpose,
                    record.summary,
                    record.focus_recommendation,
                    json.dumps(record.ranked_goal_ids, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.ranked_task_ids, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.ranked_commitment_ids, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.next_actions, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.deferred_items, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.escalation_items, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.evidence_refs, ensure_ascii=False, sort_keys=True),
                    record.confidence,
                    record.created_at,
                ),
            )
            connection.commit()
        return record

    def recent(self, limit: int = 20) -> list[PriorityReviewRecord]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT review_id, status, purpose, summary, focus_recommendation, ranked_goal_ids, ranked_task_ids, ranked_commitment_ids, next_actions, deferred_items, escalation_items, evidence_refs, confidence, created_at
                FROM cognitive_priority_reviews
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: sqlite3.Row) -> PriorityReviewRecord:
        return PriorityReviewRecord(
            review_id=row["review_id"],
            status=PriorityReviewStatus(row["status"]),
            purpose=row["purpose"],
            summary=row["summary"],
            focus_recommendation=row["focus_recommendation"],
            ranked_goal_ids=json.loads(row["ranked_goal_ids"]),
            ranked_task_ids=json.loads(row["ranked_task_ids"]),
            ranked_commitment_ids=json.loads(row["ranked_commitment_ids"]),
            next_actions=json.loads(row["next_actions"]),
            deferred_items=json.loads(row["deferred_items"]),
            escalation_items=json.loads(row["escalation_items"]),
            evidence_refs=json.loads(row["evidence_refs"]),
            confidence=float(row["confidence"]),
            created_at=row["created_at"],
        )


class PriorityReviewProvider(ABC):
    @abstractmethod
    def propose(self, *, snapshot: CognitiveSnapshot, purpose: str) -> PriorityReviewProposal:
        raise NotImplementedError


class EvidencePriorityReviewProvider(PriorityReviewProvider):
    """Offline fallback that does not infer priorities or initiative."""

    def propose(self, *, snapshot: CognitiveSnapshot, purpose: str) -> PriorityReviewProposal:
        return PriorityReviewProposal(
            status=PriorityReviewStatus.SKIPPED,
            purpose=purpose,
            summary="No model priority-review provider was available; priority arbitration was skipped without inferred urgency, importance, or initiative.",
            focus_recommendation="",
            ranked_goal_ids=[],
            ranked_task_ids=[],
            ranked_commitment_ids=[],
            next_actions=[],
            deferred_items=[],
            escalation_items=[],
            evidence_refs=_snapshot_refs(snapshot),
            confidence=0.0,
        )


class ModelPriorityReviewProvider(PriorityReviewProvider):
    """Schema-driven provider for priority, focus, and initiative review."""

    def __init__(self, model_client: ModelClient, fallback: PriorityReviewProvider | None = None) -> None:
        self.model_client = model_client
        self.fallback = fallback or EvidencePriorityReviewProvider()

    def propose(self, *, snapshot: CognitiveSnapshot, purpose: str) -> PriorityReviewProposal:
        prompt = self._build_prompt(snapshot=snapshot, purpose=purpose)
        try:
            raw = self.model_client.complete_json(prompt, _priority_review_schema())
            return _parse_model_priority_review(raw, purpose=purpose, snapshot=snapshot)
        except (ModelClientError, ValueError, KeyError, json.JSONDecodeError):
            return self.fallback.propose(snapshot=snapshot, purpose=purpose)

    def _build_prompt(self, *, snapshot: CognitiveSnapshot, purpose: str) -> str:
        payload = {
            "purpose": purpose,
            "snapshot": {
                "focus": asdict(snapshot.focus),
                "active_goals": [asdict(record) for record in snapshot.active_goals[:12]],
                "active_tasks": [asdict(record) for record in snapshot.active_tasks[:24]],
                "persona": asdict(snapshot.persona),
                "knowledge": [asdict(record) for record in snapshot.knowledge[:16]],
                "learning": [asdict(record) for record in snapshot.learning[:16]],
                "consolidations": [asdict(record) for record in snapshot.consolidations[:12]],
                "curations": [asdict(record) for record in snapshot.curations[:12]],
                "skill_evolutions": [asdict(record) for record in snapshot.skill_evolutions[:12]],
                "persona_evolutions": [asdict(record) for record in snapshot.persona_evolutions[:12]],
                "self_reviews": [asdict(record) for record in snapshot.self_reviews[:12]],
                "interaction_reviews": [asdict(record) for record in snapshot.interaction_reviews[:12]],
                "commitments": [asdict(record) for record in snapshot.commitments[:20]],
                "commitment_reviews": [asdict(record) for record in snapshot.commitment_reviews[:12]],
                "environment": [asdict(record) for record in snapshot.environment[:20]],
                "environment_reviews": [asdict(record) for record in snapshot.environment_reviews[:12]],
                "priority_reviews": [asdict(record) for record in snapshot.priority_reviews[:12]],
                "recoveries": [asdict(record) for record in snapshot.recoveries[:12]],
                "briefings": [asdict(record) for record in snapshot.briefings[:8]],
                "wakeups": [asdict(record) for record in snapshot.wakeups[:8]],
                "skills": [asdict(record) for record in snapshot.skills[:12]],
                "specialists": [asdict(record) for record in snapshot.specialists[:8]],
            },
        }
        return render_prompt_template(
            "priority_review",
            resource=COGNITION_PROMPT_RESOURCE,
            priority_review_input=json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")),
        )


class PriorityReviewEngine:
    """Persists model-led priority, focus, and initiative reviews."""

    def __init__(self, store: PriorityReviewStore, provider: PriorityReviewProvider | None = None) -> None:
        self.store = store
        self.provider = provider or EvidencePriorityReviewProvider()

    def review(self, *, snapshot: CognitiveSnapshot, purpose: str = "priority_review") -> PriorityReviewRecord:
        cleaned_purpose = _clean(purpose, limit=120) or "priority_review"
        try:
            proposal = self.provider.propose(snapshot=snapshot, purpose=cleaned_purpose)
            record = self._proposal_to_record(proposal, snapshot=snapshot)
        except Exception as exc:  # pragma: no cover - defensive runtime boundary
            record = PriorityReviewRecord(
                review_id=new_id("priority_review"),
                status=PriorityReviewStatus.FAILED,
                purpose=cleaned_purpose,
                summary=redact_secrets(f"Priority review failed: {exc}")[:1_000],
                created_at=utc_now(),
            )
        return self.store.append(record)

    def _proposal_to_record(self, proposal: PriorityReviewProposal, *, snapshot: CognitiveSnapshot) -> PriorityReviewRecord:
        status = proposal.status
        if status == PriorityReviewStatus.GENERATED and not proposal.summary:
            status = PriorityReviewStatus.SKIPPED
        valid_goals = {record.goal_id for record in snapshot.active_goals}
        valid_tasks = {record.task_id for record in snapshot.active_tasks}
        valid_commitments = {record.commitment_id for record in snapshot.commitments}
        return PriorityReviewRecord(
            review_id=new_id("priority_review"),
            status=status,
            purpose=_clean(proposal.purpose, limit=120) or "priority_review",
            summary=_clean(proposal.summary, limit=1_500) or "Priority review skipped.",
            focus_recommendation=redact_secrets(_clean(proposal.focus_recommendation, limit=800)),
            ranked_goal_ids=[item for item in _string_list(proposal.ranked_goal_ids, limit=200) if item in valid_goals][:20],
            ranked_task_ids=[item for item in _string_list(proposal.ranked_task_ids, limit=200) if item in valid_tasks][:30],
            ranked_commitment_ids=[item for item in _string_list(proposal.ranked_commitment_ids, limit=200) if item in valid_commitments][:30],
            next_actions=[redact_secrets(item) for item in _string_list(proposal.next_actions, limit=500)][:12],
            deferred_items=[redact_secrets(item) for item in _string_list(proposal.deferred_items, limit=500)][:12],
            escalation_items=[redact_secrets(item) for item in _string_list(proposal.escalation_items, limit=500)][:12],
            evidence_refs=_merge_refs(proposal.evidence_refs, _snapshot_refs(snapshot))[:30],
            confidence=_confidence(proposal.confidence),
            created_at=utc_now(),
        )


def _priority_review_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "status",
            "summary",
            "focus_recommendation",
            "ranked_goal_ids",
            "ranked_task_ids",
            "ranked_commitment_ids",
            "next_actions",
            "deferred_items",
            "escalation_items",
            "evidence_refs",
            "confidence",
        ],
        "properties": {
            "status": {"type": "string", "enum": [PriorityReviewStatus.GENERATED.value, PriorityReviewStatus.SKIPPED.value]},
            "summary": {"type": "string"},
            "focus_recommendation": {"type": "string"},
            "ranked_goal_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
            "ranked_task_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
            "ranked_commitment_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
            "next_actions": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
            "deferred_items": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
            "escalation_items": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
            "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
    }


def _parse_model_priority_review(raw: str, *, purpose: str, snapshot: CognitiveSnapshot) -> PriorityReviewProposal:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Priority-review output must be a JSON object.")
    return PriorityReviewProposal(
        status=PriorityReviewStatus(str(payload["status"])),
        purpose=purpose,
        summary=redact_secrets(_clean(payload.get("summary"), limit=1_500)),
        focus_recommendation=redact_secrets(_clean(payload.get("focus_recommendation"), limit=800)),
        ranked_goal_ids=_string_list(payload.get("ranked_goal_ids"), limit=200),
        ranked_task_ids=_string_list(payload.get("ranked_task_ids"), limit=200),
        ranked_commitment_ids=_string_list(payload.get("ranked_commitment_ids"), limit=200),
        next_actions=[redact_secrets(item) for item in _string_list(payload.get("next_actions"), limit=500)],
        deferred_items=[redact_secrets(item) for item in _string_list(payload.get("deferred_items"), limit=500)],
        escalation_items=[redact_secrets(item) for item in _string_list(payload.get("escalation_items"), limit=500)],
        evidence_refs=[redact_secrets(item) for item in _string_list(payload.get("evidence_refs"), limit=500)],
        confidence=_confidence(payload.get("confidence")),
    )


def _snapshot_refs(snapshot: CognitiveSnapshot) -> list[str]:
    refs: list[str] = []
    if snapshot.focus.active_goal_id:
        refs.append(f"goal:{snapshot.focus.active_goal_id}")
    if snapshot.focus.active_task_id:
        refs.append(f"task:{snapshot.focus.active_task_id}")
    refs.extend(f"goal:{record.goal_id}" for record in snapshot.active_goals[:12])
    refs.extend(f"task:{record.task_id}" for record in snapshot.active_tasks[:24])
    refs.extend(f"knowledge:{record.knowledge_id}" for record in snapshot.knowledge[:16])
    refs.extend(f"learning:{record.learning_id}" for record in snapshot.learning[:16])
    refs.extend(f"consolidation:{record.consolidation_id}" for record in snapshot.consolidations[:12])
    refs.extend(f"curation:{record.curation_id}" for record in snapshot.curations[:12])
    refs.extend(f"skill_evolution:{record.evolution_id}" for record in snapshot.skill_evolutions[:12])
    refs.extend(f"persona_evolution:{record.evolution_id}" for record in snapshot.persona_evolutions[:12])
    refs.extend(f"self_review:{record.review_id}" for record in snapshot.self_reviews[:12])
    refs.extend(f"interaction_review:{record.review_id}" for record in snapshot.interaction_reviews[:12])
    refs.extend(f"commitment:{record.commitment_id}" for record in snapshot.commitments[:20])
    refs.extend(f"commitment_review:{record.review_id}" for record in snapshot.commitment_reviews[:12])
    refs.extend(f"environment:{record.environment_id}" for record in snapshot.environment[:20])
    refs.extend(f"environment_review:{record.review_id}" for record in snapshot.environment_reviews[:12])
    refs.extend(f"priority_review:{record.review_id}" for record in snapshot.priority_reviews[:12])
    refs.extend(f"recovery:{record.recovery_id}" for record in snapshot.recoveries[:12])
    refs.extend(f"briefing:{record.briefing_id}" for record in snapshot.briefings[:8])
    refs.extend(f"wakeup:{record.wakeup_id}" for record in snapshot.wakeups[:8])
    refs.extend(f"skill:{record.skill_id}" for record in snapshot.skills[:12])
    refs.extend(f"specialist:{record.specialist_id}" for record in snapshot.specialists[:8])
    return _merge_refs([], refs)


def _merge_refs(base: list[str], extra: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for item in [*base, *extra]:
        cleaned = _clean(item, limit=500)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            merged.append(cleaned)
    return merged[:50]


def _string_list(value: object, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        cleaned = _clean(item, limit=limit)
        if cleaned:
            items.append(cleaned)
    return items[:50]


def _clean(value: object, *, limit: int = 1_000) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _confidence(value: object) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return 0.5
