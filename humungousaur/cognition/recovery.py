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

from .goals import GoalStore
from .models import (
    GoalRecord,
    LearningRecord,
    RecoveryRecord,
    RecoveryStatus,
    ReflectionRecord,
    ReflectionStatus,
    TaskRecord,
    new_id,
    utc_now,
)


COGNITION_PROMPT_RESOURCE = "resources/prompts/cognition.yaml"


@dataclass(slots=True)
class RecoveryTaskProposal:
    title: str
    request: str
    owner: str = "master"
    success_criteria: list[str] | None = None
    depends_on: list[str] | None = None
    local_task_id: str = ""


@dataclass(slots=True)
class RecoveryProposal:
    status: RecoveryStatus
    summary: str
    tasks: list[RecoveryTaskProposal]


class RecoveryStore:
    """Durable records of adaptive recovery attempts."""

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
                CREATE TABLE IF NOT EXISTS cognitive_recoveries (
                    recovery_id TEXT PRIMARY KEY,
                    goal_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    reflection_id TEXT NOT NULL,
                    learning_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_task_ids TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cognitive_recoveries_task ON cognitive_recoveries(task_id, created_at)")
            connection.commit()

    def append(self, record: RecoveryRecord) -> RecoveryRecord:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO cognitive_recoveries
                (recovery_id, goal_id, task_id, run_id, reflection_id, learning_id, status, summary, created_task_ids, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.recovery_id,
                    record.goal_id,
                    record.task_id,
                    record.run_id,
                    record.reflection_id,
                    record.learning_id,
                    record.status.value,
                    record.summary,
                    json.dumps(record.created_task_ids, ensure_ascii=False, sort_keys=True),
                    record.created_at,
                ),
            )
            connection.commit()
        return record

    def recent(self, limit: int = 20) -> list[RecoveryRecord]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT recovery_id, goal_id, task_id, run_id, reflection_id, learning_id, status, summary, created_task_ids, created_at
                FROM cognitive_recoveries
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def for_task(self, task_id: str, limit: int = 10) -> list[RecoveryRecord]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT recovery_id, goal_id, task_id, run_id, reflection_id, learning_id, status, summary, created_task_ids, created_at
                FROM cognitive_recoveries
                WHERE task_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (task_id, max(1, min(limit, 100))),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: sqlite3.Row) -> RecoveryRecord:
        return RecoveryRecord(
            recovery_id=row["recovery_id"],
            goal_id=row["goal_id"],
            task_id=row["task_id"],
            run_id=row["run_id"],
            reflection_id=row["reflection_id"],
            learning_id=row["learning_id"],
            status=RecoveryStatus(row["status"]),
            summary=row["summary"],
            created_task_ids=json.loads(row["created_task_ids"]),
            created_at=row["created_at"],
        )


class RecoveryProvider(ABC):
    @abstractmethod
    def propose(
        self,
        *,
        goal: GoalRecord | None,
        task: TaskRecord,
        run: AgentRunResult,
        reflection: ReflectionRecord,
        learning: LearningRecord,
    ) -> RecoveryProposal:
        raise NotImplementedError


class EvidenceRecoveryProvider(RecoveryProvider):
    """Offline fallback that does not invent recovery tasks from language."""

    def propose(
        self,
        *,
        goal: GoalRecord | None,
        task: TaskRecord,
        run: AgentRunResult,
        reflection: ReflectionRecord,
        learning: LearningRecord,
    ) -> RecoveryProposal:
        del goal, task, run, reflection, learning
        return RecoveryProposal(
            status=RecoveryStatus.SKIPPED,
            summary="No model recovery provider was available; no adaptive repair tasks were inferred.",
            tasks=[],
        )


class ModelRecoveryProvider(RecoveryProvider):
    """Schema-driven provider for adaptive repair task proposals."""

    def __init__(self, model_client: ModelClient, fallback: RecoveryProvider | None = None) -> None:
        self.model_client = model_client
        self.fallback = fallback or EvidenceRecoveryProvider()

    def propose(
        self,
        *,
        goal: GoalRecord | None,
        task: TaskRecord,
        run: AgentRunResult,
        reflection: ReflectionRecord,
        learning: LearningRecord,
    ) -> RecoveryProposal:
        if reflection.status in {ReflectionStatus.PASSED, ReflectionStatus.NEEDS_APPROVAL}:
            return RecoveryProposal(RecoveryStatus.SKIPPED, "Recovery is not needed for this reflection state.", [])
        prompt = self._build_prompt(goal=goal, task=task, run=run, reflection=reflection, learning=learning)
        try:
            raw = self.model_client.complete_json(prompt, _recovery_schema())
            return _parse_model_recovery(raw)
        except (ModelClientError, ValueError, KeyError, json.JSONDecodeError):
            return self.fallback.propose(goal=goal, task=task, run=run, reflection=reflection, learning=learning)

    def _build_prompt(
        self,
        *,
        goal: GoalRecord | None,
        task: TaskRecord,
        run: AgentRunResult,
        reflection: ReflectionRecord,
        learning: LearningRecord,
    ) -> str:
        payload = {
            "goal": asdict(goal) if goal else None,
            "task": asdict(task),
            "run": _run_for_model(run),
            "reflection": asdict(reflection),
            "learning": asdict(learning),
        }
        return render_prompt_template(
            "recovery_planning",
            resource=COGNITION_PROMPT_RESOURCE,
            recovery_input=json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")),
        )


class RecoveryEngine:
    """Creates explicit follow-up task graph nodes from recovery proposals."""

    def __init__(self, store: RecoveryStore, goals: GoalStore, provider: RecoveryProvider | None = None) -> None:
        self.store = store
        self.goals = goals
        self.provider = provider or EvidenceRecoveryProvider()

    def recover_task(
        self,
        *,
        goal: GoalRecord | None,
        task: TaskRecord,
        run: AgentRunResult,
        reflection: ReflectionRecord,
        learning: LearningRecord,
    ) -> RecoveryRecord:
        try:
            proposal = self.provider.propose(goal=goal, task=task, run=run, reflection=reflection, learning=learning)
            record = self._apply_proposal(proposal, goal=goal, task=task, run=run, reflection=reflection, learning=learning)
        except Exception as exc:  # pragma: no cover - defensive runtime boundary
            record = RecoveryRecord(
                recovery_id=new_id("recovery"),
                goal_id=task.goal_id,
                task_id=task.task_id,
                run_id=run.run_id,
                reflection_id=reflection.reflection_id,
                learning_id=learning.learning_id,
                status=RecoveryStatus.FAILED,
                summary=redact_secrets(f"Recovery failed: {exc}")[:1_000],
                created_at=utc_now(),
            )
        return self.store.append(record)

    def _apply_proposal(
        self,
        proposal: RecoveryProposal,
        *,
        goal: GoalRecord | None,
        task: TaskRecord,
        run: AgentRunResult,
        reflection: ReflectionRecord,
        learning: LearningRecord,
    ) -> RecoveryRecord:
        created_task_ids: list[str] = []
        if goal is not None and proposal.status == RecoveryStatus.PLANNED:
            created_task_ids = self._create_recovery_tasks(proposal.tasks[:5], task=task)
        status = proposal.status
        if status == RecoveryStatus.PLANNED and not created_task_ids:
            status = RecoveryStatus.SKIPPED
        return RecoveryRecord(
            recovery_id=new_id("recovery"),
            goal_id=task.goal_id,
            task_id=task.task_id,
            run_id=run.run_id,
            reflection_id=reflection.reflection_id,
            learning_id=learning.learning_id,
            status=status,
            summary=_clean(proposal.summary, limit=1_500) or "Adaptive recovery completed.",
            created_task_ids=created_task_ids,
            created_at=utc_now(),
        )

    def _create_recovery_tasks(self, proposals: list[RecoveryTaskProposal], *, task: TaskRecord) -> list[str]:
        local_to_task_id: dict[str, str] = {}
        created: list[str] = []
        for index, item in enumerate(proposals, start=1):
            local_id = _safe_local_id(item.local_task_id or f"repair-{index}")
            local_to_task_id[local_id] = new_id("task")
        for index, item in enumerate(proposals, start=1):
            if not item.title or not item.request:
                continue
            local_id = _safe_local_id(item.local_task_id or f"repair-{index}")
            depends_on = [
                local_to_task_id[_safe_local_id(dep)]
                for dep in item.depends_on or []
                if _safe_local_id(dep) in local_to_task_id
            ]
            created_task = self.goals.add_task(
                task.goal_id,
                item.title,
                owner=item.owner or "master",
                depends_on=depends_on,
                metadata={
                    "request": item.request,
                    "success_criteria": _string_list(item.success_criteria),
                    "recovery_parent_task_id": task.task_id,
                    "recovery_local_task_id": local_id,
                },
                task_id=local_to_task_id[local_id],
            )
            created.append(created_task.task_id)
        return created


def _recovery_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "summary", "tasks"],
        "properties": {
            "status": {"type": "string", "enum": [RecoveryStatus.PLANNED.value, RecoveryStatus.SKIPPED.value]},
            "summary": {"type": "string"},
            "tasks": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["local_task_id", "title", "request", "owner", "success_criteria", "depends_on"],
                    "properties": {
                        "local_task_id": {"type": "string"},
                        "title": {"type": "string"},
                        "request": {"type": "string"},
                        "owner": {"type": "string"},
                        "success_criteria": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
                        "depends_on": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
                    },
                },
            },
        },
    }


def _parse_model_recovery(raw: str) -> RecoveryProposal:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Recovery output must be a JSON object.")
    status = RecoveryStatus(str(payload["status"]))
    tasks = [_parse_task(item) for item in _dict_items(payload.get("tasks"))]
    return RecoveryProposal(
        status=status,
        summary=redact_secrets(_clean(payload.get("summary"), limit=1_500)),
        tasks=[task for task in tasks if task.title and task.request],
    )


def _parse_task(item: dict[str, Any]) -> RecoveryTaskProposal:
    return RecoveryTaskProposal(
        local_task_id=_safe_local_id(str(item.get("local_task_id") or "")),
        title=redact_secrets(_clean(item.get("title"), limit=160)),
        request=redact_secrets(_clean(item.get("request"), limit=2_000)),
        owner=_clean(item.get("owner") or "master", limit=120) or "master",
        success_criteria=[redact_secrets(value) for value in _string_list(item.get("success_criteria"))],
        depends_on=[_safe_local_id(value) for value in _string_list(item.get("depends_on"))],
    )


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


def _dict_items(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean(item, limit=500) for item in value if _clean(item, limit=500)]


def _safe_local_id(value: str) -> str:
    cleaned = "-".join(str(value or "repair").strip().lower().split())
    cleaned = "".join(char for char in cleaned if char.isalnum() or char in {"-", "_"})
    return cleaned[:40] or "repair"


def _clean(value: object, *, limit: int) -> str:
    return " ".join(str(value or "").strip().split())[:limit]
