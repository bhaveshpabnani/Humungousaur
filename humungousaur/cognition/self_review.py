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

from .models import CognitiveSnapshot, SelfReviewRecord, SelfReviewStatus, new_id, utc_now


COGNITION_PROMPT_RESOURCE = "resources/prompts/cognition.yaml"
AUTONOMY_POSTURES = {"pause", "ask_user", "observe", "continue", "delegate", "recover", "normal"}


@dataclass(slots=True)
class SelfReviewProposal:
    status: SelfReviewStatus
    purpose: str
    summary: str
    autonomy_posture: str
    confidence: float
    uncertainty: float
    risks: list[str]
    open_questions: list[str]
    recommended_actions: list[str]
    should_ask_user: bool
    evidence_refs: list[str]


class SelfReviewStore:
    """Durable metacognitive self-review records."""

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
                CREATE TABLE IF NOT EXISTS cognitive_self_reviews (
                    review_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    autonomy_posture TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    uncertainty REAL NOT NULL,
                    risks TEXT NOT NULL,
                    open_questions TEXT NOT NULL,
                    recommended_actions TEXT NOT NULL,
                    should_ask_user INTEGER NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cognitive_self_reviews_created_at ON cognitive_self_reviews(created_at)")
            connection.commit()

    def append(self, record: SelfReviewRecord) -> SelfReviewRecord:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO cognitive_self_reviews
                (review_id, status, purpose, summary, autonomy_posture, confidence, uncertainty, risks, open_questions, recommended_actions, should_ask_user, evidence_refs, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.review_id,
                    record.status.value,
                    record.purpose,
                    record.summary,
                    record.autonomy_posture,
                    record.confidence,
                    record.uncertainty,
                    json.dumps(record.risks, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.open_questions, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.recommended_actions, ensure_ascii=False, sort_keys=True),
                    int(record.should_ask_user),
                    json.dumps(record.evidence_refs, ensure_ascii=False, sort_keys=True),
                    record.created_at,
                ),
            )
            connection.commit()
        return record

    def recent(self, limit: int = 20) -> list[SelfReviewRecord]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT review_id, status, purpose, summary, autonomy_posture, confidence, uncertainty, risks, open_questions, recommended_actions, should_ask_user, evidence_refs, created_at
                FROM cognitive_self_reviews
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: sqlite3.Row) -> SelfReviewRecord:
        return SelfReviewRecord(
            review_id=row["review_id"],
            status=SelfReviewStatus(row["status"]),
            purpose=row["purpose"],
            summary=row["summary"],
            autonomy_posture=row["autonomy_posture"],
            confidence=float(row["confidence"]),
            uncertainty=float(row["uncertainty"]),
            risks=json.loads(row["risks"]),
            open_questions=json.loads(row["open_questions"]),
            recommended_actions=json.loads(row["recommended_actions"]),
            should_ask_user=bool(row["should_ask_user"]),
            evidence_refs=json.loads(row["evidence_refs"]),
            created_at=row["created_at"],
        )


class SelfReviewProvider(ABC):
    @abstractmethod
    def propose(self, *, snapshot: CognitiveSnapshot, purpose: str) -> SelfReviewProposal:
        raise NotImplementedError


class EvidenceSelfReviewProvider(SelfReviewProvider):
    """Offline fallback that does not infer cognitive state or confidence."""

    def propose(self, *, snapshot: CognitiveSnapshot, purpose: str) -> SelfReviewProposal:
        return SelfReviewProposal(
            status=SelfReviewStatus.SKIPPED,
            purpose=purpose,
            summary="No model self-review provider was available; metacognitive review was skipped without inferred confidence or autonomy judgment.",
            autonomy_posture="normal",
            confidence=0.0,
            uncertainty=0.0,
            risks=[],
            open_questions=[],
            recommended_actions=[],
            should_ask_user=False,
            evidence_refs=_snapshot_refs(snapshot),
        )


class ModelSelfReviewProvider(SelfReviewProvider):
    """Schema-driven provider for metacognitive self-monitoring."""

    def __init__(self, model_client: ModelClient, fallback: SelfReviewProvider | None = None) -> None:
        self.model_client = model_client
        self.fallback = fallback or EvidenceSelfReviewProvider()

    def propose(self, *, snapshot: CognitiveSnapshot, purpose: str) -> SelfReviewProposal:
        prompt = self._build_prompt(snapshot=snapshot, purpose=purpose)
        try:
            raw = self.model_client.complete_json(prompt, _self_review_schema())
            return _parse_model_self_review(raw, purpose=purpose)
        except (ModelClientError, ValueError, KeyError, json.JSONDecodeError):
            return self.fallback.propose(snapshot=snapshot, purpose=purpose)

    def _build_prompt(self, *, snapshot: CognitiveSnapshot, purpose: str) -> str:
        payload = {
            "purpose": purpose,
            "snapshot": {
                "focus": asdict(snapshot.focus),
                "active_goals": [asdict(record) for record in snapshot.active_goals[:8]],
                "active_tasks": [asdict(record) for record in snapshot.active_tasks[:16]],
                "persona": asdict(snapshot.persona),
                "knowledge": [asdict(record) for record in snapshot.knowledge[:16]],
                "learning": [asdict(record) for record in snapshot.learning[:16]],
                "consolidations": [asdict(record) for record in snapshot.consolidations[:12]],
                "curations": [asdict(record) for record in snapshot.curations[:12]],
                "skill_evolutions": [asdict(record) for record in snapshot.skill_evolutions[:12]],
                "persona_evolutions": [asdict(record) for record in snapshot.persona_evolutions[:12]],
                "self_reviews": [asdict(record) for record in snapshot.self_reviews[:12]],
                "recoveries": [asdict(record) for record in snapshot.recoveries[:12]],
                "briefings": [asdict(record) for record in snapshot.briefings[:8]],
                "wakeups": [asdict(record) for record in snapshot.wakeups[:8]],
                "skills": [asdict(record) for record in snapshot.skills[:12]],
                "specialists": [asdict(record) for record in snapshot.specialists[:8]],
            },
        }
        return render_prompt_template(
            "self_review",
            resource=COGNITION_PROMPT_RESOURCE,
            self_review_input=json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")),
        )


class SelfReviewEngine:
    """Persists model-led metacognitive self-review records."""

    def __init__(self, store: SelfReviewStore, provider: SelfReviewProvider | None = None) -> None:
        self.store = store
        self.provider = provider or EvidenceSelfReviewProvider()

    def review(self, *, snapshot: CognitiveSnapshot, purpose: str = "self_review") -> SelfReviewRecord:
        try:
            proposal = self.provider.propose(snapshot=snapshot, purpose=_clean(purpose, limit=120) or "self_review")
            record = self._proposal_to_record(proposal, snapshot=snapshot)
        except Exception as exc:  # pragma: no cover - defensive runtime boundary
            record = SelfReviewRecord(
                review_id=new_id("self_review"),
                status=SelfReviewStatus.FAILED,
                purpose=_clean(purpose, limit=120) or "self_review",
                summary=redact_secrets(f"Self-review failed: {exc}")[:1_000],
                created_at=utc_now(),
            )
        return self.store.append(record)

    def _proposal_to_record(self, proposal: SelfReviewProposal, *, snapshot: CognitiveSnapshot) -> SelfReviewRecord:
        base_refs = _merge_refs(proposal.evidence_refs, _snapshot_refs(snapshot))
        status = proposal.status
        if status == SelfReviewStatus.GENERATED and not proposal.summary:
            status = SelfReviewStatus.SKIPPED
        return SelfReviewRecord(
            review_id=new_id("self_review"),
            status=status,
            purpose=_clean(proposal.purpose, limit=120) or "self_review",
            summary=_clean(proposal.summary, limit=1_500) or "Metacognitive self-review skipped.",
            autonomy_posture=_autonomy_posture(proposal.autonomy_posture),
            confidence=_confidence(proposal.confidence),
            uncertainty=_confidence(proposal.uncertainty),
            risks=[redact_secrets(item) for item in _string_list(proposal.risks, limit=500)][:10],
            open_questions=[redact_secrets(item) for item in _string_list(proposal.open_questions, limit=500)][:10],
            recommended_actions=[redact_secrets(item) for item in _string_list(proposal.recommended_actions, limit=500)][:10],
            should_ask_user=bool(proposal.should_ask_user),
            evidence_refs=base_refs[:30],
            created_at=utc_now(),
        )


def _self_review_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "status",
            "summary",
            "autonomy_posture",
            "confidence",
            "uncertainty",
            "risks",
            "open_questions",
            "recommended_actions",
            "should_ask_user",
            "evidence_refs",
        ],
        "properties": {
            "status": {"type": "string", "enum": [SelfReviewStatus.GENERATED.value, SelfReviewStatus.SKIPPED.value]},
            "summary": {"type": "string"},
            "autonomy_posture": {"type": "string", "enum": sorted(AUTONOMY_POSTURES)},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "uncertainty": {"type": "number", "minimum": 0, "maximum": 1},
            "risks": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
            "open_questions": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
            "recommended_actions": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
            "should_ask_user": {"type": "boolean"},
            "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
        },
    }


def _parse_model_self_review(raw: str, *, purpose: str) -> SelfReviewProposal:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Self-review output must be a JSON object.")
    return SelfReviewProposal(
        status=SelfReviewStatus(str(payload["status"])),
        purpose=purpose,
        summary=redact_secrets(_clean(payload.get("summary"), limit=1_500)),
        autonomy_posture=_autonomy_posture(payload.get("autonomy_posture")),
        confidence=_confidence(payload.get("confidence")),
        uncertainty=_confidence(payload.get("uncertainty")),
        risks=[redact_secrets(item) for item in _string_list(payload.get("risks"), limit=500)],
        open_questions=[redact_secrets(item) for item in _string_list(payload.get("open_questions"), limit=500)],
        recommended_actions=[redact_secrets(item) for item in _string_list(payload.get("recommended_actions"), limit=500)],
        should_ask_user=bool(payload.get("should_ask_user", False)),
        evidence_refs=[redact_secrets(item) for item in _string_list(payload.get("evidence_refs"), limit=500)],
    )


def _snapshot_refs(snapshot: CognitiveSnapshot) -> list[str]:
    refs: list[str] = []
    if snapshot.focus.active_goal_id:
        refs.append(f"goal:{snapshot.focus.active_goal_id}")
    if snapshot.focus.active_task_id:
        refs.append(f"task:{snapshot.focus.active_task_id}")
    refs.extend(f"goal:{record.goal_id}" for record in snapshot.active_goals[:8])
    refs.extend(f"task:{record.task_id}" for record in snapshot.active_tasks[:16])
    refs.extend(f"knowledge:{record.knowledge_id}" for record in snapshot.knowledge[:16])
    refs.extend(f"learning:{record.learning_id}" for record in snapshot.learning[:16])
    refs.extend(f"consolidation:{record.consolidation_id}" for record in snapshot.consolidations[:12])
    refs.extend(f"curation:{record.curation_id}" for record in snapshot.curations[:12])
    refs.extend(f"skill_evolution:{record.evolution_id}" for record in snapshot.skill_evolutions[:12])
    refs.extend(f"persona_evolution:{record.evolution_id}" for record in snapshot.persona_evolutions[:12])
    refs.extend(f"self_review:{record.review_id}" for record in snapshot.self_reviews[:12])
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


def _autonomy_posture(value: object) -> str:
    posture = str(value or "normal").strip().lower()
    return posture if posture in AUTONOMY_POSTURES else "normal"
