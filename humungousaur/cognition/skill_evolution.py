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
    SkillEvolutionRecord,
    SkillEvolutionStatus,
    SkillLifecycleStatus,
    SkillRecord,
    new_id,
    utc_now,
)
from .skills import SkillStore


COGNITION_PROMPT_RESOURCE = "resources/prompts/cognition.yaml"


@dataclass(slots=True)
class SkillUpdateProposal:
    skill_id: str
    name: str
    purpose: str
    when_to_use: str
    tools: list[str]
    verification_steps: list[str]
    failure_modes: list[str]
    confidence: float
    evidence_refs: list[str]


@dataclass(slots=True)
class SkillRetireProposal:
    skill_id: str
    reason: str
    evidence_refs: list[str]


@dataclass(slots=True)
class SkillCreateProposal:
    name: str
    purpose: str
    when_to_use: str
    tools: list[str]
    verification_steps: list[str]
    failure_modes: list[str]
    confidence: float
    evidence_refs: list[str]


@dataclass(slots=True)
class SkillEvolutionProposal:
    status: SkillEvolutionStatus
    purpose: str
    summary: str
    update_skills: list[SkillUpdateProposal]
    retire_skills: list[SkillRetireProposal]
    create_skills: list[SkillCreateProposal]
    retain_skill_ids: list[str]
    evidence_refs: list[str]
    confidence: float


class SkillEvolutionStore:
    """Durable records of model-led reusable skill review decisions."""

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
                CREATE TABLE IF NOT EXISTS cognitive_skill_evolutions (
                    evolution_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    updated_skill_ids TEXT NOT NULL,
                    retired_skill_ids TEXT NOT NULL,
                    created_skill_ids TEXT NOT NULL,
                    retained_skill_ids TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cognitive_skill_evolutions_created_at ON cognitive_skill_evolutions(created_at)")
            connection.commit()

    def append(self, record: SkillEvolutionRecord) -> SkillEvolutionRecord:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO cognitive_skill_evolutions
                (evolution_id, status, purpose, summary, updated_skill_ids, retired_skill_ids, created_skill_ids, retained_skill_ids, evidence_refs, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.evolution_id,
                    record.status.value,
                    record.purpose,
                    record.summary,
                    json.dumps(record.updated_skill_ids, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.retired_skill_ids, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.created_skill_ids, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.retained_skill_ids, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.evidence_refs, ensure_ascii=False, sort_keys=True),
                    record.confidence,
                    record.created_at,
                ),
            )
            connection.commit()
        return record

    def recent(self, limit: int = 20) -> list[SkillEvolutionRecord]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT evolution_id, status, purpose, summary, updated_skill_ids, retired_skill_ids, created_skill_ids, retained_skill_ids, evidence_refs, confidence, created_at
                FROM cognitive_skill_evolutions
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: sqlite3.Row) -> SkillEvolutionRecord:
        return SkillEvolutionRecord(
            evolution_id=row["evolution_id"],
            status=SkillEvolutionStatus(row["status"]),
            purpose=row["purpose"],
            summary=row["summary"],
            updated_skill_ids=json.loads(row["updated_skill_ids"]),
            retired_skill_ids=json.loads(row["retired_skill_ids"]),
            created_skill_ids=json.loads(row["created_skill_ids"]),
            retained_skill_ids=json.loads(row["retained_skill_ids"]),
            evidence_refs=json.loads(row["evidence_refs"]),
            confidence=float(row["confidence"]),
            created_at=row["created_at"],
        )


class SkillEvolutionProvider(ABC):
    @abstractmethod
    def propose(
        self,
        *,
        snapshot: CognitiveSnapshot,
        purpose: str,
        max_updates: int,
        max_new_skills: int,
    ) -> SkillEvolutionProposal:
        raise NotImplementedError


class EvidenceSkillEvolutionProvider(SkillEvolutionProvider):
    """Offline fallback that never rewrites reusable skills semantically."""

    def propose(
        self,
        *,
        snapshot: CognitiveSnapshot,
        purpose: str,
        max_updates: int,
        max_new_skills: int,
    ) -> SkillEvolutionProposal:
        del max_updates, max_new_skills
        return SkillEvolutionProposal(
            status=SkillEvolutionStatus.SKIPPED,
            purpose=purpose,
            summary="No model skill evolution provider was available; reusable skill review was skipped without semantic updates.",
            update_skills=[],
            retire_skills=[],
            create_skills=[],
            retain_skill_ids=[],
            evidence_refs=_snapshot_refs(snapshot),
            confidence=0.0,
        )


class ModelSkillEvolutionProvider(SkillEvolutionProvider):
    """Schema-driven provider for reviewing and improving reusable skills."""

    def __init__(self, model_client: ModelClient, fallback: SkillEvolutionProvider | None = None) -> None:
        self.model_client = model_client
        self.fallback = fallback or EvidenceSkillEvolutionProvider()

    def propose(
        self,
        *,
        snapshot: CognitiveSnapshot,
        purpose: str,
        max_updates: int,
        max_new_skills: int,
    ) -> SkillEvolutionProposal:
        prompt = self._build_prompt(snapshot=snapshot, purpose=purpose, max_updates=max_updates, max_new_skills=max_new_skills)
        try:
            raw = self.model_client.complete_json(prompt, _skill_evolution_schema(max_updates=max_updates, max_new_skills=max_new_skills))
            return _parse_model_skill_evolution(raw, purpose=purpose)
        except (ModelClientError, ValueError, KeyError, json.JSONDecodeError):
            return self.fallback.propose(snapshot=snapshot, purpose=purpose, max_updates=max_updates, max_new_skills=max_new_skills)

    def _build_prompt(self, *, snapshot: CognitiveSnapshot, purpose: str, max_updates: int, max_new_skills: int) -> str:
        payload = {
            "purpose": purpose,
            "limits": {"max_updates": max_updates, "max_new_skills": max_new_skills},
            "snapshot": {
                "focus": asdict(snapshot.focus),
                "active_goals": [asdict(goal) for goal in snapshot.active_goals[:8]],
                "active_tasks": [asdict(task) for task in snapshot.active_tasks[:16]],
                "skills": [_skill_for_model(skill) for skill in snapshot.skills[:50]],
                "learning": [asdict(record) for record in snapshot.learning[:16]],
                "consolidations": [asdict(record) for record in snapshot.consolidations[:16]],
                "curations": [asdict(record) for record in snapshot.curations[:12]],
                "skill_evolutions": [asdict(record) for record in snapshot.skill_evolutions[:12]],
                "recoveries": [asdict(record) for record in snapshot.recoveries[:12]],
                "briefings": [asdict(record) for record in snapshot.briefings[:8]],
                "knowledge": [asdict(record) for record in snapshot.knowledge[:12]],
                "persona": asdict(snapshot.persona),
                "specialists": [asdict(record) for record in snapshot.specialists[:8]],
            },
        }
        return render_prompt_template(
            "skill_evolution",
            resource=COGNITION_PROMPT_RESOURCE,
            skill_evolution_input=json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")),
        )


class SkillEvolutionEngine:
    """Applies model-led skill updates through exact active-skill operations."""

    def __init__(self, store: SkillEvolutionStore, skills: SkillStore, provider: SkillEvolutionProvider | None = None) -> None:
        self.store = store
        self.skills = skills
        self.provider = provider or EvidenceSkillEvolutionProvider()

    def evolve(
        self,
        *,
        snapshot: CognitiveSnapshot,
        purpose: str = "skill_review",
        max_updates: int = 5,
        max_new_skills: int = 3,
    ) -> SkillEvolutionRecord:
        try:
            proposal = self.provider.propose(
                snapshot=snapshot,
                purpose=_clean(purpose, limit=120) or "skill_review",
                max_updates=max(0, min(int(max_updates), 20)),
                max_new_skills=max(0, min(int(max_new_skills), 10)),
            )
            record = self._apply_proposal(proposal, snapshot=snapshot)
        except Exception as exc:  # pragma: no cover - defensive runtime boundary
            record = SkillEvolutionRecord(
                evolution_id=new_id("skill_evolution"),
                status=SkillEvolutionStatus.FAILED,
                purpose=_clean(purpose, limit=120) or "skill_review",
                summary=redact_secrets(f"Skill evolution failed: {exc}")[:1_000],
                confidence=0.0,
                created_at=utc_now(),
            )
        return self.store.append(record)

    def _apply_proposal(self, proposal: SkillEvolutionProposal, *, snapshot: CognitiveSnapshot) -> SkillEvolutionRecord:
        active_ids = {skill.skill_id for skill in snapshot.skills if skill.status == SkillLifecycleStatus.ACTIVE}
        known_ids = {skill.skill_id for skill in self.skills.list(limit=200, include_retired=True)}
        base_refs = _merge_refs(proposal.evidence_refs, _snapshot_refs(snapshot))
        if proposal.status != SkillEvolutionStatus.RECORDED:
            return SkillEvolutionRecord(
                evolution_id=new_id("skill_evolution"),
                status=SkillEvolutionStatus.SKIPPED,
                purpose=_clean(proposal.purpose, limit=120) or "skill_review",
                summary=_clean(proposal.summary, limit=1_500) or "Skill evolution skipped.",
                evidence_refs=base_refs[:30],
                confidence=_confidence(proposal.confidence),
                created_at=utc_now(),
            )
        updated_ids: list[str] = []
        retired_ids: list[str] = []
        created_ids: list[str] = []
        retained_ids: list[str] = []
        touched_ids: set[str] = set()
        for item in proposal.update_skills:
            if item.skill_id not in active_ids or item.skill_id in touched_ids:
                continue
            updated = self.skills.update_exact(
                item.skill_id,
                name=item.name,
                purpose=item.purpose,
                when_to_use=item.when_to_use,
                tools=item.tools,
                verification_steps=item.verification_steps,
                failure_modes=item.failure_modes,
                evidence_refs=_merge_refs(base_refs, item.evidence_refs),
                confidence=item.confidence,
            )
            if updated is not None:
                touched_ids.add(updated.skill_id)
                updated_ids.append(updated.skill_id)
        for item in proposal.retire_skills:
            if item.skill_id not in active_ids or item.skill_id in touched_ids:
                continue
            retired = self.skills.retire(item.skill_id, reason=item.reason, evidence_refs=_merge_refs(base_refs, item.evidence_refs))
            if retired is not None:
                touched_ids.add(retired.skill_id)
                retired_ids.append(retired.skill_id)
        for item in proposal.create_skills:
            if not item.name or not item.purpose or not item.when_to_use:
                continue
            skill = self.skills.upsert(
                name=item.name,
                purpose=item.purpose,
                when_to_use=item.when_to_use,
                tools=item.tools,
                verification_steps=item.verification_steps,
                failure_modes=item.failure_modes,
                evidence_refs=_merge_refs(base_refs, item.evidence_refs),
                confidence=item.confidence,
            )
            if skill.skill_id in known_ids:
                if skill.skill_id not in updated_ids:
                    updated_ids.append(skill.skill_id)
            else:
                known_ids.add(skill.skill_id)
                created_ids.append(skill.skill_id)
        for skill_id in proposal.retain_skill_ids:
            if skill_id in active_ids and skill_id not in touched_ids and skill_id not in retained_ids:
                retained_ids.append(skill_id)
        status = proposal.status
        if status == SkillEvolutionStatus.RECORDED and not (updated_ids or retired_ids or created_ids or retained_ids):
            status = SkillEvolutionStatus.SKIPPED
        return SkillEvolutionRecord(
            evolution_id=new_id("skill_evolution"),
            status=status,
            purpose=_clean(proposal.purpose, limit=120) or "skill_review",
            summary=_clean(proposal.summary, limit=1_500) or "Skill evolution completed.",
            updated_skill_ids=updated_ids,
            retired_skill_ids=retired_ids,
            created_skill_ids=created_ids,
            retained_skill_ids=retained_ids[:20],
            evidence_refs=base_refs[:30],
            confidence=_confidence(proposal.confidence),
            created_at=utc_now(),
        )


def _skill_evolution_schema(*, max_updates: int, max_new_skills: int) -> dict[str, Any]:
    skill_shape = {
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "purpose", "when_to_use", "tools", "verification_steps", "failure_modes", "confidence", "evidence_refs"],
        "properties": {
            "name": {"type": "string"},
            "purpose": {"type": "string"},
            "when_to_use": {"type": "string"},
            "tools": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
            "verification_steps": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
            "failure_modes": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
        },
    }
    update_shape = dict(skill_shape)
    update_shape["required"] = ["skill_id", *skill_shape["required"]]
    update_shape["properties"] = {"skill_id": {"type": "string"}, **skill_shape["properties"]}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "summary", "update_skills", "retire_skills", "create_skills", "retain_skill_ids", "evidence_refs", "confidence"],
        "properties": {
            "status": {"type": "string", "enum": [SkillEvolutionStatus.RECORDED.value, SkillEvolutionStatus.SKIPPED.value]},
            "summary": {"type": "string"},
            "update_skills": {
                "type": "array",
                "maxItems": max(0, min(max_updates, 20)),
                "items": update_shape,
            },
            "retire_skills": {
                "type": "array",
                "maxItems": max(0, min(max_updates, 20)),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["skill_id", "reason", "evidence_refs"],
                    "properties": {
                        "skill_id": {"type": "string"},
                        "reason": {"type": "string"},
                        "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                    },
                },
            },
            "create_skills": {
                "type": "array",
                "maxItems": max(0, min(max_new_skills, 10)),
                "items": skill_shape,
            },
            "retain_skill_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
            "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
    }


def _parse_model_skill_evolution(raw: str, *, purpose: str) -> SkillEvolutionProposal:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Skill evolution output must be a JSON object.")
    return SkillEvolutionProposal(
        status=SkillEvolutionStatus(str(payload["status"])),
        purpose=purpose,
        summary=redact_secrets(_clean(payload.get("summary"), limit=1_500)),
        update_skills=[_parse_update(item) for item in _dict_items(payload.get("update_skills"))],
        retire_skills=[_parse_retire(item) for item in _dict_items(payload.get("retire_skills"))],
        create_skills=[_parse_create(item) for item in _dict_items(payload.get("create_skills"))],
        retain_skill_ids=_string_list(payload.get("retain_skill_ids"), limit=200),
        evidence_refs=[redact_secrets(item) for item in _string_list(payload.get("evidence_refs"), limit=500)],
        confidence=_confidence(payload.get("confidence")),
    )


def _parse_update(item: dict[str, Any]) -> SkillUpdateProposal:
    return SkillUpdateProposal(
        skill_id=_clean(item.get("skill_id"), limit=200),
        name=redact_secrets(_clean(item.get("name"), limit=120)),
        purpose=redact_secrets(_clean(item.get("purpose"), limit=1_000)),
        when_to_use=redact_secrets(_clean(item.get("when_to_use"), limit=1_000)),
        tools=_string_list(item.get("tools"), limit=120),
        verification_steps=[redact_secrets(value) for value in _string_list(item.get("verification_steps"), limit=300)],
        failure_modes=[redact_secrets(value) for value in _string_list(item.get("failure_modes"), limit=300)],
        confidence=_confidence(item.get("confidence")),
        evidence_refs=[redact_secrets(value) for value in _string_list(item.get("evidence_refs"), limit=500)],
    )


def _parse_retire(item: dict[str, Any]) -> SkillRetireProposal:
    return SkillRetireProposal(
        skill_id=_clean(item.get("skill_id"), limit=200),
        reason=redact_secrets(_clean(item.get("reason"), limit=1_000)),
        evidence_refs=[redact_secrets(value) for value in _string_list(item.get("evidence_refs"), limit=500)],
    )


def _parse_create(item: dict[str, Any]) -> SkillCreateProposal:
    return SkillCreateProposal(
        name=redact_secrets(_clean(item.get("name"), limit=120)),
        purpose=redact_secrets(_clean(item.get("purpose"), limit=1_000)),
        when_to_use=redact_secrets(_clean(item.get("when_to_use"), limit=1_000)),
        tools=_string_list(item.get("tools"), limit=120),
        verification_steps=[redact_secrets(value) for value in _string_list(item.get("verification_steps"), limit=300)],
        failure_modes=[redact_secrets(value) for value in _string_list(item.get("failure_modes"), limit=300)],
        confidence=_confidence(item.get("confidence")),
        evidence_refs=[redact_secrets(value) for value in _string_list(item.get("evidence_refs"), limit=500)],
    )


def _skill_for_model(skill: SkillRecord) -> dict[str, Any]:
    payload = asdict(skill)
    for key in ["name", "purpose", "when_to_use", "retirement_reason"]:
        payload[key] = redact_secrets(str(payload.get(key, "")))
    payload["verification_steps"] = [redact_secrets(str(item)) for item in payload.get("verification_steps", [])]
    payload["failure_modes"] = [redact_secrets(str(item)) for item in payload.get("failure_modes", [])]
    payload["evidence_refs"] = [redact_secrets(str(item)) for item in payload.get("evidence_refs", [])]
    return payload


def _snapshot_refs(snapshot: CognitiveSnapshot) -> list[str]:
    refs: list[str] = []
    if snapshot.focus.active_goal_id:
        refs.append(f"goal:{snapshot.focus.active_goal_id}")
    if snapshot.focus.active_task_id:
        refs.append(f"task:{snapshot.focus.active_task_id}")
    refs.extend(f"goal:{record.goal_id}" for record in snapshot.active_goals[:8])
    refs.extend(f"task:{record.task_id}" for record in snapshot.active_tasks[:16])
    refs.extend(f"skill:{record.skill_id}" for record in snapshot.skills[:50])
    refs.extend(f"learning:{record.learning_id}" for record in snapshot.learning[:16])
    refs.extend(f"consolidation:{record.consolidation_id}" for record in snapshot.consolidations[:16])
    refs.extend(f"curation:{record.curation_id}" for record in snapshot.curations[:12])
    refs.extend(f"skill_evolution:{record.evolution_id}" for record in snapshot.skill_evolutions[:12])
    refs.extend(f"recovery:{record.recovery_id}" for record in snapshot.recoveries[:12])
    refs.extend(f"briefing:{record.briefing_id}" for record in snapshot.briefings[:8])
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


def _dict_items(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


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
