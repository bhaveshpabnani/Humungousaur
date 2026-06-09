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
from humungousaur.schemas import AgentRunResult

from .knowledge import KnowledgeStore
from .models import (
    ConsolidationRecord,
    ConsolidationStatus,
    KnowledgeKind,
    LearningRecord,
    ReflectionRecord,
    new_id,
    utc_now,
)
from .persona import PersonaStore
from .skills import SkillStore


COGNITION_PROMPT_RESOURCE = "resources/prompts/cognition.yaml"


@dataclass(slots=True)
class KnowledgeProposal:
    kind: KnowledgeKind
    text: str
    confidence: float = 0.5
    evidence_refs: list[str] | None = None


@dataclass(slots=True)
class SkillProposal:
    name: str
    purpose: str
    when_to_use: str
    tools: list[str] | None = None
    verification_steps: list[str] | None = None
    failure_modes: list[str] | None = None
    confidence: float = 0.5


@dataclass(slots=True)
class PersonaProposal:
    kind: str
    text: str


@dataclass(slots=True)
class ConsolidationProposal:
    status: ConsolidationStatus
    summary: str
    knowledge: list[KnowledgeProposal]
    skills: list[SkillProposal]
    persona: list[PersonaProposal]


class ConsolidationStore:
    """Durable record of experience-to-memory consolidation attempts."""

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
                CREATE TABLE IF NOT EXISTS cognitive_consolidations (
                    consolidation_id TEXT PRIMARY KEY,
                    goal_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    reflection_id TEXT NOT NULL,
                    learning_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    knowledge_ids TEXT NOT NULL,
                    skill_ids TEXT NOT NULL,
                    persona_updates TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_cognitive_consolidations_task ON cognitive_consolidations(task_id, created_at)"
            )
            connection.commit()

    def append(self, record: ConsolidationRecord) -> ConsolidationRecord:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO cognitive_consolidations
                (consolidation_id, goal_id, task_id, run_id, reflection_id, learning_id, status, summary, knowledge_ids, skill_ids, persona_updates, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.consolidation_id,
                    record.goal_id,
                    record.task_id,
                    record.run_id,
                    record.reflection_id,
                    record.learning_id,
                    record.status.value,
                    record.summary,
                    json.dumps(record.knowledge_ids, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.skill_ids, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.persona_updates, ensure_ascii=False, sort_keys=True),
                    record.created_at,
                ),
            )
            connection.commit()
        return record

    def recent(self, limit: int = 20) -> list[ConsolidationRecord]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT consolidation_id, goal_id, task_id, run_id, reflection_id, learning_id, status, summary, knowledge_ids, skill_ids, persona_updates, created_at
                FROM cognitive_consolidations
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def for_task(self, task_id: str, limit: int = 10) -> list[ConsolidationRecord]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT consolidation_id, goal_id, task_id, run_id, reflection_id, learning_id, status, summary, knowledge_ids, skill_ids, persona_updates, created_at
                FROM cognitive_consolidations
                WHERE task_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (task_id, max(1, min(limit, 100))),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: sqlite3.Row) -> ConsolidationRecord:
        return ConsolidationRecord(
            consolidation_id=row["consolidation_id"],
            goal_id=row["goal_id"],
            task_id=row["task_id"],
            run_id=row["run_id"],
            reflection_id=row["reflection_id"],
            learning_id=row["learning_id"],
            status=ConsolidationStatus(row["status"]),
            summary=row["summary"],
            knowledge_ids=json.loads(row["knowledge_ids"]),
            skill_ids=json.loads(row["skill_ids"]),
            persona_updates=json.loads(row["persona_updates"]),
            created_at=row["created_at"],
        )


class ConsolidationProvider(ABC):
    @abstractmethod
    def propose(
        self,
        *,
        run: AgentRunResult,
        reflection: ReflectionRecord,
        learning: LearningRecord,
    ) -> ConsolidationProposal:
        raise NotImplementedError


class EvidenceConsolidationProvider(ConsolidationProvider):
    """Offline fallback that does not infer durable memories from language."""

    def propose(
        self,
        *,
        run: AgentRunResult,
        reflection: ReflectionRecord,
        learning: LearningRecord,
    ) -> ConsolidationProposal:
        del run, reflection, learning
        return ConsolidationProposal(
            status=ConsolidationStatus.SKIPPED,
            summary="No model consolidation provider was available; reflection-linked learning was recorded only.",
            knowledge=[],
            skills=[],
            persona=[],
        )


class ModelConsolidationProvider(ConsolidationProvider):
    """Schema-driven provider for turning evidence into durable memory updates."""

    def __init__(self, model_client: ModelClient, fallback: ConsolidationProvider | None = None) -> None:
        self.model_client = model_client
        self.fallback = fallback or EvidenceConsolidationProvider()

    def propose(
        self,
        *,
        run: AgentRunResult,
        reflection: ReflectionRecord,
        learning: LearningRecord,
    ) -> ConsolidationProposal:
        prompt = self._build_prompt(run=run, reflection=reflection, learning=learning)
        try:
            raw = self.model_client.complete_json(prompt, _consolidation_schema())
            return _parse_model_proposal(raw)
        except (ModelClientError, ValueError, KeyError, json.JSONDecodeError):
            return self.fallback.propose(run=run, reflection=reflection, learning=learning)

    def _build_prompt(self, *, run: AgentRunResult, reflection: ReflectionRecord, learning: LearningRecord) -> str:
        payload = {
            "run": _run_for_model(run),
            "reflection": asdict(reflection),
            "learning": asdict(learning),
            "allowed_outputs": {
                "knowledge_kinds": [kind.value for kind in KnowledgeKind],
                "persona_kinds": ["preference", "fact"],
            },
        }
        return render_prompt_template(
            "memory_consolidation",
            resource=COGNITION_PROMPT_RESOURCE,
            consolidation_input=json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")),
        )


class ConsolidationEngine:
    """Writes model-approved consolidation proposals through durable stores."""

    def __init__(
        self,
        store: ConsolidationStore,
        knowledge: KnowledgeStore,
        skills: SkillStore,
        persona: PersonaStore,
        provider: ConsolidationProvider | None = None,
    ) -> None:
        self.store = store
        self.knowledge = knowledge
        self.skills = skills
        self.persona = persona
        self.provider = provider or EvidenceConsolidationProvider()

    def consolidate_task(
        self,
        *,
        run: AgentRunResult,
        reflection: ReflectionRecord,
        learning: LearningRecord,
    ) -> ConsolidationRecord:
        try:
            proposal = self.provider.propose(run=run, reflection=reflection, learning=learning)
            record = self._apply_proposal(proposal, run=run, reflection=reflection, learning=learning)
        except Exception as exc:  # pragma: no cover - defensive boundary for autonomous runtime continuity
            record = ConsolidationRecord(
                consolidation_id=new_id("consolidation"),
                goal_id=reflection.goal_id,
                task_id=reflection.task_id,
                run_id=run.run_id,
                reflection_id=reflection.reflection_id,
                learning_id=learning.learning_id,
                status=ConsolidationStatus.FAILED,
                summary=redact_secrets(f"Consolidation failed: {exc}")[:1_000],
                created_at=utc_now(),
            )
        return self.store.append(record)

    def _apply_proposal(
        self,
        proposal: ConsolidationProposal,
        *,
        run: AgentRunResult,
        reflection: ReflectionRecord,
        learning: LearningRecord,
    ) -> ConsolidationRecord:
        knowledge_ids: list[str] = []
        skill_ids: list[str] = []
        persona_updates: list[str] = []
        if proposal.status == ConsolidationStatus.RECORDED:
            base_refs = _base_evidence_refs(run, reflection, learning)
            for item in proposal.knowledge[:5]:
                if not item.text:
                    continue
                record = self.knowledge.append(
                    kind=item.kind,
                    text=item.text,
                    source="model_consolidation",
                    evidence_refs=_merge_refs(base_refs, item.evidence_refs or []),
                    confidence=item.confidence,
                )
                knowledge_ids.append(record.knowledge_id)
            for item in proposal.skills[:3]:
                if not item.name or not item.purpose or not item.when_to_use:
                    continue
                skill = self.skills.upsert(
                    name=item.name,
                    purpose=item.purpose,
                    when_to_use=item.when_to_use,
                    tools=item.tools or [],
                    verification_steps=item.verification_steps or [],
                    failure_modes=item.failure_modes or [],
                    confidence=item.confidence,
                )
                skill_ids.append(skill.skill_id)
            for item in proposal.persona[:5]:
                if not item.text:
                    continue
                if item.kind == "fact":
                    self.persona.add_fact(item.text)
                else:
                    self.persona.add_preference(item.text)
                persona_updates.append(f"{item.kind}:{item.text[:200]}")
        status = proposal.status
        if status == ConsolidationStatus.RECORDED and not (knowledge_ids or skill_ids or persona_updates):
            status = ConsolidationStatus.SKIPPED
        return ConsolidationRecord(
            consolidation_id=new_id("consolidation"),
            goal_id=reflection.goal_id,
            task_id=reflection.task_id,
            run_id=run.run_id,
            reflection_id=reflection.reflection_id,
            learning_id=learning.learning_id,
            status=status,
            summary=_clean(proposal.summary, limit=1_500) or "Experience consolidation completed.",
            knowledge_ids=knowledge_ids,
            skill_ids=skill_ids,
            persona_updates=persona_updates,
            created_at=utc_now(),
        )


def _consolidation_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "summary", "knowledge", "skills", "persona", "skip_reason"],
        "properties": {
            "status": {"type": "string", "enum": [ConsolidationStatus.RECORDED.value, ConsolidationStatus.SKIPPED.value]},
            "summary": {"type": "string"},
            "skip_reason": {"type": "string"},
            "knowledge": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["kind", "text", "confidence", "evidence_refs"],
                    "properties": {
                        "kind": {"type": "string", "enum": [kind.value for kind in KnowledgeKind]},
                        "text": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                    },
                },
            },
            "skills": {
                "type": "array",
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name", "purpose", "when_to_use", "tools", "verification_steps", "failure_modes", "confidence"],
                    "properties": {
                        "name": {"type": "string"},
                        "purpose": {"type": "string"},
                        "when_to_use": {"type": "string"},
                        "tools": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                        "verification_steps": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                        "failure_modes": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                },
            },
            "persona": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["kind", "text"],
                    "properties": {
                        "kind": {"type": "string", "enum": ["preference", "fact"]},
                        "text": {"type": "string"},
                    },
                },
            },
        },
    }


def _parse_model_proposal(raw: str) -> ConsolidationProposal:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Consolidation output must be a JSON object.")
    status = ConsolidationStatus(str(payload["status"]))
    summary = _clean(payload.get("summary") or payload.get("skip_reason") or "", limit=1_500)
    knowledge = [_parse_knowledge(item) for item in _dict_items(payload.get("knowledge"))]
    skills = [_parse_skill(item) for item in _dict_items(payload.get("skills"))]
    persona = [_parse_persona(item) for item in _dict_items(payload.get("persona"))]
    return ConsolidationProposal(
        status=status,
        summary=summary,
        knowledge=[item for item in knowledge if item.text],
        skills=[item for item in skills if item.name and item.purpose and item.when_to_use],
        persona=[item for item in persona if item.text],
    )


def _parse_knowledge(item: dict[str, Any]) -> KnowledgeProposal:
    return KnowledgeProposal(
        kind=_knowledge_kind(item.get("kind")),
        text=redact_secrets(_clean(item.get("text"), limit=3_000)),
        confidence=_confidence(item.get("confidence")),
        evidence_refs=[redact_secrets(value) for value in _string_list(item.get("evidence_refs"), limit=500)],
    )


def _parse_skill(item: dict[str, Any]) -> SkillProposal:
    return SkillProposal(
        name=redact_secrets(_clean(item.get("name"), limit=120)),
        purpose=redact_secrets(_clean(item.get("purpose"), limit=1_000)),
        when_to_use=redact_secrets(_clean(item.get("when_to_use"), limit=1_000)),
        tools=_string_list(item.get("tools"), limit=120),
        verification_steps=[redact_secrets(value) for value in _string_list(item.get("verification_steps"), limit=300)],
        failure_modes=[redact_secrets(value) for value in _string_list(item.get("failure_modes"), limit=300)],
        confidence=_confidence(item.get("confidence")),
    )


def _parse_persona(item: dict[str, Any]) -> PersonaProposal:
    kind = str(item.get("kind") or "preference").strip().lower()
    if kind not in {"preference", "fact"}:
        kind = "preference"
    return PersonaProposal(kind=kind, text=redact_secrets(_clean(item.get("text"), limit=500)))


def _run_for_model(run: AgentRunResult) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "request": redact_secrets(run.request),
        "final_response": redact_secrets(run.final_response[:4_000]),
        "approvals": [asdict(approval) for approval in run.approvals],
        "results": [
            {
                "tool_name": result.tool_name,
                "status": result.status.value,
                "risk_level": result.risk_level.value,
                "summary": redact_secrets(result.summary[:1_500]),
                "error": redact_secrets((result.error or "")[:1_500]),
                "output": _bounded_output(result.output),
            }
            for result in run.results
        ],
        "note_path": run.note_path or "",
    }


def _bounded_output(output: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(output, ensure_ascii=False, sort_keys=True, default=str)
    if len(text) <= 4_000:
        return output
    return {"truncated_json": redact_secrets(text[:4_000]), "truncated": True}


def _base_evidence_refs(run: AgentRunResult, reflection: ReflectionRecord, learning: LearningRecord) -> list[str]:
    refs = [
        f"run:{run.run_id}",
        f"reflection:{reflection.reflection_id}",
        f"learning:{learning.learning_id}",
    ]
    if run.note_path:
        refs.append(f"note:{run.note_path}")
    return refs


def _merge_refs(base: list[str], extra: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for item in [*base, *extra]:
        cleaned = _clean(item, limit=500)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            merged.append(cleaned)
    return merged[:30]


def _dict_items(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _knowledge_kind(value: object) -> KnowledgeKind:
    try:
        return KnowledgeKind(str(value or KnowledgeKind.CONTEXT.value))
    except ValueError:
        return KnowledgeKind.CONTEXT


def _confidence(value: object) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return 0.5


def _string_list(value: object, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean(item, limit=limit) for item in value if _clean(item, limit=limit)]


def _clean(value: object, *, limit: int) -> str:
    return " ".join(str(value or "").strip().split())[:limit]
