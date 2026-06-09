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

from .models import (
    CognitiveSnapshot,
    EnvironmentKind,
    EnvironmentRecord,
    EnvironmentReviewRecord,
    EnvironmentReviewStatus,
    new_id,
    utc_now,
)


COGNITION_PROMPT_RESOURCE = "resources/prompts/cognition.yaml"


@dataclass(slots=True)
class EnvironmentReviewProposal:
    status: EnvironmentReviewStatus
    purpose: str
    summary: str
    new_records: list[dict[str, Any]]
    updates: list[dict[str, Any]]
    archive_environment_ids: list[str]
    retained_environment_ids: list[str]
    evidence_refs: list[str]
    confidence: float


class EnvironmentStore:
    """Durable model of the assistant's operating environment."""

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
                CREATE TABLE IF NOT EXISTS cognitive_environment (
                    environment_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    source TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    archived_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cognitive_environment_kind ON cognitive_environment(kind, archived_at)")
            connection.commit()

    def create(
        self,
        *,
        kind: EnvironmentKind | str,
        title: str,
        summary: str,
        source: str = "",
        evidence_refs: list[str] | None = None,
        confidence: float = 0.5,
    ) -> EnvironmentRecord:
        now = utc_now()
        record = EnvironmentRecord(
            environment_id=new_id("environment"),
            kind=_environment_kind(kind),
            title=redact_secrets(_clean(title, limit=300)),
            summary=redact_secrets(_clean(summary, limit=2_000)),
            source=_clean(source, limit=120),
            evidence_refs=_string_list(evidence_refs, limit=500),
            confidence=_confidence(confidence),
            created_at=now,
            updated_at=now,
        )
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO cognitive_environment
                (environment_id, kind, title, summary, source, evidence_refs, confidence, archived_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.environment_id,
                    record.kind.value,
                    record.title,
                    record.summary,
                    record.source,
                    json.dumps(record.evidence_refs, ensure_ascii=False, sort_keys=True),
                    record.confidence,
                    record.archived_at,
                    record.created_at,
                    record.updated_at,
                ),
            )
            connection.commit()
        return record

    def update(
        self,
        environment_id: str,
        *,
        kind: EnvironmentKind | str | None = None,
        title: str | None = None,
        summary: str | None = None,
        evidence_refs: list[str] | None = None,
        confidence: float | None = None,
    ) -> EnvironmentRecord | None:
        record = self.get(environment_id, include_archived=True)
        if record is None:
            return None
        now = utc_now()
        next_kind = _environment_kind(kind) if kind is not None else record.kind
        next_title = redact_secrets(_clean(title, limit=300)) if title is not None else record.title
        next_summary = redact_secrets(_clean(summary, limit=2_000)) if summary is not None else record.summary
        next_refs = _merge_refs(record.evidence_refs, _string_list(evidence_refs, limit=500))
        next_confidence = _confidence(confidence) if confidence is not None else record.confidence
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE cognitive_environment
                SET kind = ?, title = ?, summary = ?, evidence_refs = ?, confidence = ?, updated_at = ?
                WHERE environment_id = ?
                """,
                (
                    next_kind.value,
                    next_title or record.title,
                    next_summary or record.summary,
                    json.dumps(next_refs, ensure_ascii=False, sort_keys=True),
                    next_confidence,
                    now,
                    record.environment_id,
                ),
            )
            connection.commit()
        return self.get(record.environment_id, include_archived=True)

    def archive(self, environment_id: str, reason: str = "") -> EnvironmentRecord | None:
        record = self.get(environment_id, include_archived=True)
        if record is None:
            return None
        refs = list(record.evidence_refs)
        if reason:
            refs.append(f"archive_reason:{_clean(reason, limit=300)}")
        now = utc_now()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE cognitive_environment
                SET evidence_refs = ?, archived_at = ?, updated_at = ?
                WHERE environment_id = ?
                """,
                (json.dumps(_merge_refs([], refs), ensure_ascii=False, sort_keys=True), now, now, record.environment_id),
            )
            connection.commit()
        return self.get(record.environment_id, include_archived=True)

    def get(self, environment_id: str, *, include_archived: bool = False) -> EnvironmentRecord | None:
        archived_clause = "" if include_archived else "AND archived_at = ''"
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                f"""
                SELECT environment_id, kind, title, summary, source, evidence_refs, confidence, archived_at, created_at, updated_at
                FROM cognitive_environment
                WHERE environment_id = ? {archived_clause}
                """,
                (_clean(environment_id, limit=200),),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def list(self, limit: int = 20, include_archived: bool = False) -> list[EnvironmentRecord]:
        where = "" if include_archived else "WHERE archived_at = ''"
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT environment_id, kind, title, summary, source, evidence_refs, confidence, archived_at, created_at, updated_at
                FROM cognitive_environment
                {where}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: sqlite3.Row) -> EnvironmentRecord:
        return EnvironmentRecord(
            environment_id=row["environment_id"],
            kind=_environment_kind(row["kind"]),
            title=row["title"],
            summary=row["summary"],
            source=row["source"],
            evidence_refs=json.loads(row["evidence_refs"]),
            confidence=float(row["confidence"]),
            archived_at=row["archived_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class EnvironmentReviewStore:
    """Durable audit records for environment model review passes."""

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
                CREATE TABLE IF NOT EXISTS cognitive_environment_reviews (
                    review_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_environment_ids TEXT NOT NULL,
                    updated_environment_ids TEXT NOT NULL,
                    archived_environment_ids TEXT NOT NULL,
                    retained_environment_ids TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cognitive_environment_reviews_created_at ON cognitive_environment_reviews(created_at)")
            connection.commit()

    def append(self, record: EnvironmentReviewRecord) -> EnvironmentReviewRecord:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO cognitive_environment_reviews
                (review_id, status, purpose, summary, created_environment_ids, updated_environment_ids, archived_environment_ids, retained_environment_ids, evidence_refs, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.review_id,
                    record.status.value,
                    record.purpose,
                    record.summary,
                    json.dumps(record.created_environment_ids, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.updated_environment_ids, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.archived_environment_ids, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.retained_environment_ids, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.evidence_refs, ensure_ascii=False, sort_keys=True),
                    record.confidence,
                    record.created_at,
                ),
            )
            connection.commit()
        return record

    def recent(self, limit: int = 20) -> list[EnvironmentReviewRecord]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT review_id, status, purpose, summary, created_environment_ids, updated_environment_ids, archived_environment_ids, retained_environment_ids, evidence_refs, confidence, created_at
                FROM cognitive_environment_reviews
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: sqlite3.Row) -> EnvironmentReviewRecord:
        return EnvironmentReviewRecord(
            review_id=row["review_id"],
            status=EnvironmentReviewStatus(row["status"]),
            purpose=row["purpose"],
            summary=row["summary"],
            created_environment_ids=json.loads(row["created_environment_ids"]),
            updated_environment_ids=json.loads(row["updated_environment_ids"]),
            archived_environment_ids=json.loads(row["archived_environment_ids"]),
            retained_environment_ids=json.loads(row["retained_environment_ids"]),
            evidence_refs=json.loads(row["evidence_refs"]),
            confidence=float(row["confidence"]),
            created_at=row["created_at"],
        )


class EnvironmentReviewProvider(ABC):
    @abstractmethod
    def propose(
        self,
        *,
        snapshot: CognitiveSnapshot,
        purpose: str,
        max_new_records: int,
        max_updates: int,
    ) -> EnvironmentReviewProposal:
        raise NotImplementedError


class EvidenceEnvironmentReviewProvider(EnvironmentReviewProvider):
    """Offline fallback that does not infer environment facts."""

    def propose(
        self,
        *,
        snapshot: CognitiveSnapshot,
        purpose: str,
        max_new_records: int,
        max_updates: int,
    ) -> EnvironmentReviewProposal:
        return EnvironmentReviewProposal(
            status=EnvironmentReviewStatus.SKIPPED,
            purpose=purpose,
            summary="No model environment-review provider was available; environment model updates were skipped without inferred workspace, system, browser, app, constraint, resource, risk, opportunity, or signal facts.",
            new_records=[],
            updates=[],
            archive_environment_ids=[],
            retained_environment_ids=[],
            evidence_refs=_snapshot_refs(snapshot),
            confidence=0.0,
        )


class ModelEnvironmentReviewProvider(EnvironmentReviewProvider):
    """Schema-driven provider for durable environment/world-context modeling."""

    def __init__(self, model_client: ModelClient, fallback: EnvironmentReviewProvider | None = None) -> None:
        self.model_client = model_client
        self.fallback = fallback or EvidenceEnvironmentReviewProvider()

    def propose(
        self,
        *,
        snapshot: CognitiveSnapshot,
        purpose: str,
        max_new_records: int,
        max_updates: int,
    ) -> EnvironmentReviewProposal:
        prompt = self._build_prompt(snapshot=snapshot, purpose=purpose, max_new_records=max_new_records, max_updates=max_updates)
        try:
            raw = self.model_client.complete_json(prompt, _environment_review_schema())
            return _parse_model_environment_review(raw, purpose=purpose)
        except (ModelClientError, ValueError, KeyError, json.JSONDecodeError):
            return self.fallback.propose(
                snapshot=snapshot,
                purpose=purpose,
                max_new_records=max_new_records,
                max_updates=max_updates,
            )

    def _build_prompt(
        self,
        *,
        snapshot: CognitiveSnapshot,
        purpose: str,
        max_new_records: int,
        max_updates: int,
    ) -> str:
        payload = {
            "purpose": purpose,
            "max_new_records": max_new_records,
            "max_updates": max_updates,
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
                "interaction_reviews": [asdict(record) for record in snapshot.interaction_reviews[:12]],
                "commitments": [asdict(record) for record in snapshot.commitments[:20]],
                "commitment_reviews": [asdict(record) for record in snapshot.commitment_reviews[:12]],
                "environment": [asdict(record) for record in snapshot.environment[:20]],
                "environment_reviews": [asdict(record) for record in snapshot.environment_reviews[:12]],
                "recoveries": [asdict(record) for record in snapshot.recoveries[:12]],
                "briefings": [asdict(record) for record in snapshot.briefings[:8]],
                "wakeups": [asdict(record) for record in snapshot.wakeups[:8]],
                "skills": [asdict(record) for record in snapshot.skills[:12]],
                "specialists": [asdict(record) for record in snapshot.specialists[:8]],
            },
        }
        return render_prompt_template(
            "environment_review",
            resource=COGNITION_PROMPT_RESOURCE,
            environment_review_input=json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")),
        )


class EnvironmentReviewEngine:
    """Applies model-led environment proposals to exact durable records."""

    def __init__(
        self,
        review_store: EnvironmentReviewStore,
        environment_store: EnvironmentStore,
        provider: EnvironmentReviewProvider | None = None,
    ) -> None:
        self.review_store = review_store
        self.environment_store = environment_store
        self.provider = provider or EvidenceEnvironmentReviewProvider()

    def review(
        self,
        *,
        snapshot: CognitiveSnapshot,
        purpose: str = "environment_review",
        max_new_records: int = 5,
        max_updates: int = 10,
    ) -> EnvironmentReviewRecord:
        cleaned_purpose = _clean(purpose, limit=120) or "environment_review"
        max_new_records = max(0, min(max_new_records, 20))
        max_updates = max(0, min(max_updates, 40))
        try:
            proposal = self.provider.propose(
                snapshot=snapshot,
                purpose=cleaned_purpose,
                max_new_records=max_new_records,
                max_updates=max_updates,
            )
            record = self._apply_proposal(
                proposal,
                snapshot=snapshot,
                max_new_records=max_new_records,
                max_updates=max_updates,
            )
        except Exception as exc:  # pragma: no cover - defensive runtime boundary
            record = EnvironmentReviewRecord(
                review_id=new_id("environment_review"),
                status=EnvironmentReviewStatus.FAILED,
                purpose=cleaned_purpose,
                summary=redact_secrets(f"Environment review failed: {exc}")[:1_000],
                created_at=utc_now(),
            )
        return self.review_store.append(record)

    def _apply_proposal(
        self,
        proposal: EnvironmentReviewProposal,
        *,
        snapshot: CognitiveSnapshot,
        max_new_records: int,
        max_updates: int,
    ) -> EnvironmentReviewRecord:
        if proposal.status != EnvironmentReviewStatus.RECORDED:
            return EnvironmentReviewRecord(
                review_id=new_id("environment_review"),
                status=EnvironmentReviewStatus.SKIPPED,
                purpose=_clean(proposal.purpose, limit=120) or "environment_review",
                summary=_clean(proposal.summary, limit=1_500) or "Environment review skipped.",
                evidence_refs=_merge_refs(proposal.evidence_refs, _snapshot_refs(snapshot))[:30],
                confidence=_confidence(proposal.confidence),
                created_at=utc_now(),
            )
        active_ids = {record.environment_id for record in snapshot.environment}
        created: list[str] = []
        updated: list[str] = []
        archived: list[str] = []
        retained: list[str] = []
        for item in proposal.new_records[:max_new_records]:
            if not isinstance(item, dict):
                continue
            title = redact_secrets(_clean(item.get("title"), limit=300))
            summary = redact_secrets(_clean(item.get("summary"), limit=2_000))
            if not title or not summary:
                continue
            record = self.environment_store.create(
                kind=_environment_kind(item.get("kind")),
                title=title,
                summary=summary,
                source=_clean(item.get("source"), limit=120) or "environment_review",
                evidence_refs=_merge_refs(_string_list(item.get("evidence_refs"), limit=500), proposal.evidence_refs),
                confidence=_confidence(item.get("confidence")),
            )
            created.append(record.environment_id)
        for item in proposal.updates[:max_updates]:
            if not isinstance(item, dict):
                continue
            environment_id = _clean(item.get("environment_id"), limit=200)
            if environment_id not in active_ids:
                continue
            record = self.environment_store.update(
                environment_id,
                kind=_optional_kind(item.get("kind")),
                title=_optional_clean(item.get("title"), limit=300),
                summary=_optional_clean(item.get("summary"), limit=2_000),
                evidence_refs=_merge_refs(_string_list(item.get("evidence_refs"), limit=500), proposal.evidence_refs),
                confidence=_optional_confidence(item.get("confidence")),
            )
            if record is not None:
                updated.append(record.environment_id)
        for environment_id in proposal.archive_environment_ids[:max_updates]:
            cleaned_id = _clean(environment_id, limit=200)
            if cleaned_id not in active_ids:
                continue
            record = self.environment_store.archive(cleaned_id, reason=proposal.summary)
            if record is not None:
                archived.append(record.environment_id)
        for environment_id in proposal.retained_environment_ids[:max_updates]:
            cleaned_id = _clean(environment_id, limit=200)
            if cleaned_id in active_ids and cleaned_id not in retained:
                retained.append(cleaned_id)
        status = EnvironmentReviewStatus.RECORDED
        if not (created or updated or archived or retained):
            status = EnvironmentReviewStatus.SKIPPED
        return EnvironmentReviewRecord(
            review_id=new_id("environment_review"),
            status=status,
            purpose=_clean(proposal.purpose, limit=120) or "environment_review",
            summary=_clean(proposal.summary, limit=1_500) or "Environment review recorded.",
            created_environment_ids=created[:30],
            updated_environment_ids=_merge_refs([], updated)[:30],
            archived_environment_ids=_merge_refs([], archived)[:30],
            retained_environment_ids=retained[:30],
            evidence_refs=_merge_refs(proposal.evidence_refs, _snapshot_refs(snapshot))[:30],
            confidence=_confidence(proposal.confidence),
            created_at=utc_now(),
        )


def _environment_review_schema() -> dict[str, Any]:
    kinds = [item.value for item in EnvironmentKind]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "status",
            "summary",
            "new_records",
            "updates",
            "archive_environment_ids",
            "retained_environment_ids",
            "evidence_refs",
            "confidence",
        ],
        "properties": {
            "status": {"type": "string", "enum": [EnvironmentReviewStatus.RECORDED.value, EnvironmentReviewStatus.SKIPPED.value]},
            "summary": {"type": "string"},
            "new_records": {
                "type": "array",
                "maxItems": 20,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["kind", "title", "summary", "source", "evidence_refs", "confidence"],
                    "properties": {
                        "kind": {"type": "string", "enum": kinds},
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                        "source": {"type": "string"},
                        "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                },
            },
            "updates": {
                "type": "array",
                "maxItems": 40,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["environment_id", "kind", "title", "summary", "evidence_refs", "confidence"],
                    "properties": {
                        "environment_id": {"type": "string"},
                        "kind": {"type": "string", "enum": kinds},
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                        "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                },
            },
            "archive_environment_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 40},
            "retained_environment_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 40},
            "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
    }


def _parse_model_environment_review(raw: str, *, purpose: str) -> EnvironmentReviewProposal:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Environment-review output must be a JSON object.")
    return EnvironmentReviewProposal(
        status=EnvironmentReviewStatus(str(payload["status"])),
        purpose=purpose,
        summary=redact_secrets(_clean(payload.get("summary"), limit=1_500)),
        new_records=_dict_list(payload.get("new_records")),
        updates=_dict_list(payload.get("updates")),
        archive_environment_ids=[redact_secrets(item) for item in _string_list(payload.get("archive_environment_ids"), limit=500)],
        retained_environment_ids=[redact_secrets(item) for item in _string_list(payload.get("retained_environment_ids"), limit=500)],
        evidence_refs=[redact_secrets(item) for item in _string_list(payload.get("evidence_refs"), limit=500)],
        confidence=_confidence(payload.get("confidence")),
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
    refs.extend(f"interaction_review:{record.review_id}" for record in snapshot.interaction_reviews[:12])
    refs.extend(f"commitment:{record.commitment_id}" for record in snapshot.commitments[:20])
    refs.extend(f"commitment_review:{record.review_id}" for record in snapshot.commitment_reviews[:12])
    refs.extend(f"environment:{record.environment_id}" for record in snapshot.environment[:20])
    refs.extend(f"environment_review:{record.review_id}" for record in snapshot.environment_reviews[:12])
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


def _dict_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)][:50]


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


def _optional_clean(value: object, *, limit: int) -> str | None:
    cleaned = _clean(value, limit=limit)
    return cleaned or None


def _confidence(value: object) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return 0.5


def _optional_confidence(value: object) -> float | None:
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return None


def _environment_kind(value: EnvironmentKind | str | object) -> EnvironmentKind:
    try:
        return value if isinstance(value, EnvironmentKind) else EnvironmentKind(str(value or EnvironmentKind.SIGNAL.value))
    except ValueError:
        return EnvironmentKind.SIGNAL


def _optional_kind(value: object) -> EnvironmentKind | None:
    cleaned = _clean(value, limit=50)
    if not cleaned:
        return None
    return _environment_kind(cleaned)
