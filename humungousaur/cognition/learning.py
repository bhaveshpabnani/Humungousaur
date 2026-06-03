from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from humungousaur.schemas import AgentRunResult

from .models import LearningRecord, ReflectionRecord, new_id, utc_now


class LearningStore:
    """Durable experience records produced from executions and reflections."""

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
                CREATE TABLE IF NOT EXISTS cognitive_learning (
                    learning_id TEXT PRIMARY KEY,
                    goal_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    reflection_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    lesson TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cognitive_learning_task ON cognitive_learning(task_id, created_at)")
            connection.commit()

    def append(
        self,
        *,
        goal_id: str = "",
        task_id: str = "",
        run_id: str = "",
        reflection_id: str = "",
        outcome: str,
        lesson: str,
        evidence_refs: list[str] | None = None,
    ) -> LearningRecord:
        record = LearningRecord(
            learning_id=new_id("learning"),
            goal_id=_clean(goal_id, limit=120),
            task_id=_clean(task_id, limit=120),
            run_id=_clean(run_id, limit=120),
            reflection_id=_clean(reflection_id, limit=120),
            outcome=_clean(outcome, limit=120),
            lesson=_clean(lesson, limit=1_500),
            evidence_refs=_string_list(evidence_refs),
            created_at=utc_now(),
        )
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO cognitive_learning
                (learning_id, goal_id, task_id, run_id, reflection_id, outcome, lesson, evidence_refs, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.learning_id,
                    record.goal_id,
                    record.task_id,
                    record.run_id,
                    record.reflection_id,
                    record.outcome,
                    record.lesson,
                    json.dumps(record.evidence_refs, ensure_ascii=False, sort_keys=True),
                    record.created_at,
                ),
            )
            connection.commit()
        return record

    def recent(self, limit: int = 20) -> list[LearningRecord]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT learning_id, goal_id, task_id, run_id, reflection_id, outcome, lesson, evidence_refs, created_at
                FROM cognitive_learning
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def for_task(self, task_id: str, limit: int = 10) -> list[LearningRecord]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT learning_id, goal_id, task_id, run_id, reflection_id, outcome, lesson, evidence_refs, created_at
                FROM cognitive_learning
                WHERE task_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (task_id, max(1, min(limit, 100))),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: sqlite3.Row) -> LearningRecord:
        return LearningRecord(
            learning_id=row["learning_id"],
            goal_id=row["goal_id"],
            task_id=row["task_id"],
            run_id=row["run_id"],
            reflection_id=row["reflection_id"],
            outcome=row["outcome"],
            lesson=row["lesson"],
            evidence_refs=json.loads(row["evidence_refs"]),
            created_at=row["created_at"],
        )


class LearningEngine:
    """Records compact execution experiences from structured runtime evidence."""

    def __init__(self, store: LearningStore) -> None:
        self.store = store

    def record_run(
        self,
        *,
        goal_id: str = "",
        task_id: str = "",
        run: AgentRunResult | None = None,
        outcome: str,
        lesson: str,
        evidence_refs: list[str] | None = None,
    ) -> LearningRecord:
        refs = list(evidence_refs or [])
        if run is not None:
            refs.append(f"run:{run.run_id}")
            if run.note_path:
                refs.append(f"note:{run.note_path}")
        return self.store.append(
            goal_id=goal_id,
            task_id=task_id,
            run_id=run.run_id if run else "",
            outcome=outcome,
            lesson=lesson,
            evidence_refs=refs,
        )

    def record_reflection(self, *, reflection: ReflectionRecord, run: AgentRunResult) -> LearningRecord:
        lesson = (
            "Task outcome was evaluated through reflection before updating durable task state. "
            f"Reflection summary: {reflection.summary}"
        )
        refs = [f"reflection:{reflection.reflection_id}", f"run:{run.run_id}"]
        if run.note_path:
            refs.append(f"note:{run.note_path}")
        return self.store.append(
            goal_id=reflection.goal_id,
            task_id=reflection.task_id,
            run_id=run.run_id,
            reflection_id=reflection.reflection_id,
            outcome=reflection.status.value,
            lesson=lesson,
            evidence_refs=refs,
        )


def _clean(value: object, *, limit: int) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean(item, limit=500) for item in value if _clean(item, limit=500)]
