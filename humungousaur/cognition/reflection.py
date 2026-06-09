from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from humungousaur.planning.model_clients import ModelClient, ModelClientError, redact_secrets
from humungousaur.planning.prompt_templates import render_prompt_template
from humungousaur.schemas import ActionStatus, AgentRunResult

from .models import ReflectionRecord, ReflectionStatus, new_id, utc_now


COGNITION_PROMPT_RESOURCE = "resources/prompts/cognition.yaml"


class ReflectionStore:
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
                CREATE TABLE IF NOT EXISTS cognitive_reflections (
                    reflection_id TEXT PRIMARY KEY,
                    goal_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    summary TEXT NOT NULL,
                    checked_criteria TEXT NOT NULL,
                    missing_evidence TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_cognitive_reflections_task ON cognitive_reflections(task_id, created_at)"
            )
            connection.commit()

    def append(self, record: ReflectionRecord) -> ReflectionRecord:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO cognitive_reflections
                (reflection_id, goal_id, task_id, run_id, status, confidence, summary, checked_criteria, missing_evidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.reflection_id,
                    record.goal_id,
                    record.task_id,
                    record.run_id,
                    record.status.value,
                    record.confidence,
                    record.summary,
                    json.dumps(record.checked_criteria, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.missing_evidence, ensure_ascii=False, sort_keys=True),
                    record.created_at,
                ),
            )
            connection.commit()
        return record

    def recent(self, limit: int = 20) -> list[ReflectionRecord]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT reflection_id, goal_id, task_id, run_id, status, confidence, summary, checked_criteria, missing_evidence, created_at
                FROM cognitive_reflections
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def for_task(self, task_id: str, limit: int = 10) -> list[ReflectionRecord]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT reflection_id, goal_id, task_id, run_id, status, confidence, summary, checked_criteria, missing_evidence, created_at
                FROM cognitive_reflections
                WHERE task_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (task_id, max(1, min(limit, 100))),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: sqlite3.Row) -> ReflectionRecord:
        return ReflectionRecord(
            reflection_id=row["reflection_id"],
            goal_id=row["goal_id"],
            task_id=row["task_id"],
            run_id=row["run_id"],
            status=ReflectionStatus(row["status"]),
            confidence=float(row["confidence"]),
            summary=row["summary"],
            checked_criteria=json.loads(row["checked_criteria"]),
            missing_evidence=json.loads(row["missing_evidence"]),
            created_at=row["created_at"],
        )


class ReflectionProvider(ABC):
    @abstractmethod
    def evaluate_task(
        self,
        *,
        goal_id: str,
        task_id: str,
        run: AgentRunResult,
        criteria: list[str] | None = None,
    ) -> ReflectionRecord:
        raise NotImplementedError


class ReflectionEngine:
    """Converts runtime evidence into a durable completion reflection."""

    def __init__(self, store: ReflectionStore, provider: ReflectionProvider | None = None) -> None:
        self.store = store
        self.provider = provider or EvidenceReflectionProvider()

    def evaluate_task(
        self,
        *,
        goal_id: str,
        task_id: str,
        run: AgentRunResult,
        criteria: list[str] | None = None,
    ) -> ReflectionRecord:
        record = self.provider.evaluate_task(goal_id=goal_id, task_id=task_id, run=run, criteria=criteria)
        return self.store.append(record)


class EvidenceReflectionProvider(ReflectionProvider):
    """Explicit fallback over structured runtime statuses only."""

    def evaluate_task(
        self,
        *,
        goal_id: str,
        task_id: str,
        run: AgentRunResult,
        criteria: list[str] | None = None,
    ) -> ReflectionRecord:
        checked_criteria = [str(item).strip() for item in criteria or [] if str(item).strip()]
        status = _reflection_status(run)
        missing_evidence = _missing_evidence_for_status(status, run)
        return ReflectionRecord(
            reflection_id=new_id("reflection"),
            goal_id=goal_id,
            task_id=task_id,
            run_id=run.run_id,
            status=status,
            confidence=_confidence(status, checked_criteria),
            summary=_reflection_summary(status, run),
            checked_criteria=checked_criteria,
            missing_evidence=missing_evidence,
            created_at=utc_now(),
        )


class ModelReflectionProvider(ReflectionProvider):
    """Schema-driven reflection provider for generalized completion judgment."""

    def __init__(self, model_client: ModelClient, fallback: ReflectionProvider | None = None) -> None:
        self.model_client = model_client
        self.fallback = fallback or EvidenceReflectionProvider()

    def evaluate_task(
        self,
        *,
        goal_id: str,
        task_id: str,
        run: AgentRunResult,
        criteria: list[str] | None = None,
    ) -> ReflectionRecord:
        checked_criteria = [str(item).strip() for item in criteria or [] if str(item).strip()]
        prompt = self._build_prompt(goal_id=goal_id, task_id=task_id, run=run, criteria=checked_criteria)
        try:
            raw = self.model_client.complete_json(prompt, _reflection_schema())
            record = _parse_model_reflection(raw, goal_id=goal_id, task_id=task_id, run=run, criteria=checked_criteria)
            return _enforce_evidence_boundaries(record, run)
        except (ModelClientError, ValueError, KeyError, json.JSONDecodeError):
            return self.fallback.evaluate_task(goal_id=goal_id, task_id=task_id, run=run, criteria=checked_criteria)

    def _build_prompt(self, *, goal_id: str, task_id: str, run: AgentRunResult, criteria: list[str]) -> str:
        payload = {
            "goal_id": goal_id,
            "task_id": task_id,
            "success_criteria": criteria,
            "run": {
                "run_id": run.run_id,
                "request": redact_secrets(run.request),
                "final_response": redact_secrets(run.final_response[:4_000]),
                "approvals": [asdict(approval) for approval in run.approvals],
                "results": [_result_for_model(result) for result in run.results],
                "note_path": run.note_path or "",
            },
        }
        return render_prompt_template(
            "task_reflection",
            resource=COGNITION_PROMPT_RESOURCE,
            reflection_input=json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")),
        )


def reflection_to_dict(record: ReflectionRecord) -> dict[str, Any]:
    return asdict(record)


def _reflection_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "confidence", "summary", "checked_criteria", "missing_evidence"],
        "properties": {
            "status": {"type": "string", "enum": [status.value for status in ReflectionStatus]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "summary": {"type": "string"},
            "checked_criteria": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
            "missing_evidence": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
        },
    }


def _parse_model_reflection(
    raw: str,
    *,
    goal_id: str,
    task_id: str,
    run: AgentRunResult,
    criteria: list[str],
) -> ReflectionRecord:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Reflection output must be a JSON object.")
    status = ReflectionStatus(str(payload["status"]))
    checked = [redact_secrets(str(item).strip()) for item in payload.get("checked_criteria", []) if str(item).strip()]
    if not checked:
        checked = criteria
    missing = [redact_secrets(str(item).strip()) for item in payload.get("missing_evidence", []) if str(item).strip()]
    return ReflectionRecord(
        reflection_id=new_id("reflection"),
        goal_id=goal_id,
        task_id=task_id,
        run_id=run.run_id,
        status=status,
        confidence=max(0.0, min(float(payload.get("confidence", 0.5)), 1.0)),
        summary=redact_secrets(str(payload.get("summary") or ""))[:1_500] or "Model reflection completed.",
        checked_criteria=checked[:30],
        missing_evidence=missing[:30],
        created_at=utc_now(),
    )


def _enforce_evidence_boundaries(record: ReflectionRecord, run: AgentRunResult) -> ReflectionRecord:
    boundary_status = _hard_boundary_status(run)
    if boundary_status is None:
        return record
    if boundary_status != record.status:
        missing = list(record.missing_evidence)
        missing.append(f"Runtime evidence boundary required status {boundary_status.value}.")
        return ReflectionRecord(
            reflection_id=record.reflection_id,
            goal_id=record.goal_id,
            task_id=record.task_id,
            run_id=record.run_id,
            status=boundary_status,
            confidence=min(record.confidence, 0.9),
            summary=f"{record.summary} Runtime evidence prevented claiming {record.status.value}.",
            checked_criteria=record.checked_criteria,
            missing_evidence=missing,
            created_at=record.created_at,
        )
    return record


def _hard_boundary_status(run: AgentRunResult) -> ReflectionStatus | None:
    if run.approvals:
        return ReflectionStatus.NEEDS_APPROVAL
    if any(result.status == ActionStatus.BLOCKED for result in run.results):
        return ReflectionStatus.BLOCKED
    if any(result.status == ActionStatus.FAILED for result in run.results):
        return ReflectionStatus.FAILED
    return None


def _result_for_model(result: Any) -> dict[str, Any]:
    return {
        "tool_name": result.tool_name,
        "status": result.status.value,
        "risk_level": result.risk_level.value,
        "summary": redact_secrets(result.summary[:1_500]),
        "error": redact_secrets((result.error or "")[:1_500]),
        "output": _bounded_output(result.output),
    }


def _bounded_output(output: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(output, ensure_ascii=False, sort_keys=True, default=str)
    if len(text) <= 4_000:
        return output
    return {"truncated_json": redact_secrets(text[:4_000]), "truncated": True}


def _reflection_status(run: AgentRunResult) -> ReflectionStatus:
    if run.approvals:
        return ReflectionStatus.NEEDS_APPROVAL
    if not run.results:
        return ReflectionStatus.INCONCLUSIVE
    if any(result.status == ActionStatus.BLOCKED for result in run.results):
        return ReflectionStatus.BLOCKED
    if any(result.status == ActionStatus.FAILED for result in run.results):
        return ReflectionStatus.FAILED
    if all(result.status in {ActionStatus.SUCCEEDED, ActionStatus.SKIPPED} for result in run.results):
        return ReflectionStatus.PASSED
    return ReflectionStatus.INCONCLUSIVE


def _missing_evidence_for_status(status: ReflectionStatus, run: AgentRunResult) -> list[str]:
    missing_evidence = []
    if status == ReflectionStatus.INCONCLUSIVE:
        missing_evidence.append("No tool results were available to verify task outcome.")
    if status == ReflectionStatus.NEEDS_APPROVAL:
        missing_evidence.append("One or more actions require human approval before completion can be claimed.")
    if status in {ReflectionStatus.FAILED, ReflectionStatus.BLOCKED}:
        missing_evidence.append("The run included failed or blocked tool results.")
    return missing_evidence


def _confidence(status: ReflectionStatus, criteria: list[str]) -> float:
    if status == ReflectionStatus.PASSED:
        return 0.75 if criteria else 0.65
    if status == ReflectionStatus.NEEDS_APPROVAL:
        return 0.9
    if status in {ReflectionStatus.FAILED, ReflectionStatus.BLOCKED}:
        return 0.9
    return 0.35


def _reflection_summary(status: ReflectionStatus, run: AgentRunResult) -> str:
    if status == ReflectionStatus.PASSED:
        return "Runtime evidence shows all completed tool results succeeded or were safely skipped."
    if status == ReflectionStatus.NEEDS_APPROVAL:
        return f"Completion is waiting on {len(run.approvals)} approval request(s)."
    if status == ReflectionStatus.FAILED:
        return "Completion is not proven because at least one tool result failed."
    if status == ReflectionStatus.BLOCKED:
        return "Completion is not proven because at least one tool result was blocked."
    return "Completion is inconclusive from available runtime evidence."
