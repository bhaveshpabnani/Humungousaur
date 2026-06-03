from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from .models import GoalRecord, GoalStatus, TaskRecord, TaskStatus, new_id, utc_now


class GoalStore:
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
                CREATE TABLE IF NOT EXISTS cognitive_goals (
                    goal_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    success_criteria TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cognitive_tasks (
                    task_id TEXT PRIMARY KEY,
                    goal_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    depends_on TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    result_summary TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cognitive_goals_status ON cognitive_goals(status)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cognitive_tasks_goal ON cognitive_tasks(goal_id)")
            connection.commit()

    def create_goal(
        self,
        title: str,
        success_criteria: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        goal_id: str | None = None,
    ) -> GoalRecord:
        goal = GoalRecord(
            goal_id=goal_id or new_id("goal"),
            title=_compact_title(title),
            success_criteria=success_criteria or [],
            metadata=metadata or {},
        )
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO cognitive_goals
                (goal_id, title, status, success_criteria, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    goal.goal_id,
                    goal.title,
                    goal.status.value,
                    json.dumps(goal.success_criteria, ensure_ascii=False, sort_keys=True),
                    json.dumps(goal.metadata, ensure_ascii=False, sort_keys=True),
                    goal.created_at,
                    goal.updated_at,
                ),
            )
            connection.commit()
        return goal

    def add_task(
        self,
        goal_id: str,
        title: str,
        owner: str = "master",
        depends_on: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> TaskRecord:
        task = TaskRecord(
            task_id=task_id or new_id("task"),
            goal_id=goal_id,
            title=_compact_title(title),
            owner=owner,
            depends_on=depends_on or [],
            metadata=metadata or {},
        )
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO cognitive_tasks
                (task_id, goal_id, title, status, depends_on, owner, result_summary, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.goal_id,
                    task.title,
                    task.status.value,
                    json.dumps(task.depends_on, ensure_ascii=False, sort_keys=True),
                    task.owner,
                    task.result_summary,
                    json.dumps(task.metadata, ensure_ascii=False, sort_keys=True),
                    task.created_at,
                    task.updated_at,
                ),
            )
            connection.commit()
        return task

    def update_task(
        self,
        task_id: str,
        status: TaskStatus,
        result_summary: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        updates = {
            "status": status.value,
            "result_summary": result_summary,
            "updated_at": utc_now(),
        }
        if metadata is not None:
            updates["metadata"] = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
        assignments = ", ".join(f"{key} = ?" for key in updates)
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                f"UPDATE cognitive_tasks SET {assignments} WHERE task_id = ?",
                (*updates.values(), task_id),
            )
            connection.commit()
        return cursor.rowcount > 0

    def update_goal(self, goal_id: str, status: GoalStatus) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE cognitive_goals
                SET status = ?, updated_at = ?
                WHERE goal_id = ?
                """,
                (status.value, utc_now(), goal_id),
            )
            connection.commit()
        return cursor.rowcount > 0

    def get_task(self, task_id: str) -> TaskRecord | None:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT task_id, goal_id, title, status, depends_on, owner, result_summary, metadata, created_at, updated_at
                FROM cognitive_tasks
                WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()
        return self._row_to_task(row) if row else None

    def get_goal(self, goal_id: str) -> GoalRecord | None:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT goal_id, title, status, success_criteria, metadata, created_at, updated_at
                FROM cognitive_goals
                WHERE goal_id = ?
                """,
                (goal_id,),
            ).fetchone()
        return self._row_to_goal(row) if row else None

    def tasks_for_goal(self, goal_id: str) -> list[TaskRecord]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT task_id, goal_id, title, status, depends_on, owner, result_summary, metadata, created_at, updated_at
                FROM cognitive_tasks
                WHERE goal_id = ?
                ORDER BY created_at ASC
                """,
                (goal_id,),
            ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def ready_tasks(self, limit: int = 10) -> list[TaskRecord]:
        planned = [
            task for task in self.recent_tasks(limit=200)
            if task.status == TaskStatus.PLANNED
        ]
        completed = {
            task.task_id
            for task in self.recent_tasks(limit=1_000)
            if task.status == TaskStatus.COMPLETED
        }
        ready = [task for task in planned if all(dep in completed for dep in task.depends_on)]
        ready.sort(key=lambda item: item.created_at)
        return ready[: max(1, min(limit, 100))]

    def goal_is_terminal(self, goal_id: str) -> GoalStatus | None:
        tasks = self.tasks_for_goal(goal_id)
        if not tasks:
            return None
        task_by_id = {task.task_id: task for task in tasks}
        if any(task.status == TaskStatus.WAITING_APPROVAL for task in tasks):
            return GoalStatus.WAITING
        if any(task.status in {TaskStatus.PLANNED, TaskStatus.RUNNING} for task in tasks):
            return None
        if any(task.status == TaskStatus.RECOVERING and not _effectively_completed(task, task_by_id) for task in tasks):
            return None
        if any(task.status in {TaskStatus.BLOCKED, TaskStatus.FAILED} for task in tasks):
            return GoalStatus.BLOCKED
        if all(_effectively_completed(task, task_by_id) for task in tasks):
            return GoalStatus.COMPLETED
        return None

    def active_goals(self, limit: int = 10) -> list[GoalRecord]:
        return self._goals_by_status({GoalStatus.ACTIVE, GoalStatus.WAITING, GoalStatus.BLOCKED}, limit=limit)

    def recent_goals(self, limit: int = 20) -> list[GoalRecord]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT goal_id, title, status, success_criteria, metadata, created_at, updated_at
                FROM cognitive_goals
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._row_to_goal(row) for row in rows]

    def active_tasks(self, limit: int = 20) -> list[TaskRecord]:
        statuses = {
            TaskStatus.PLANNED.value,
            TaskStatus.RUNNING.value,
            TaskStatus.RECOVERING.value,
            TaskStatus.WAITING_APPROVAL.value,
            TaskStatus.FAILED.value,
            TaskStatus.BLOCKED.value,
        }
        placeholders = ", ".join("?" for _ in statuses)
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT task_id, goal_id, title, status, depends_on, owner, result_summary, metadata, created_at, updated_at
                FROM cognitive_tasks
                WHERE status IN ({placeholders})
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (*statuses, max(1, min(limit, 200))),
            ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def recent_tasks(self, limit: int = 20) -> list[TaskRecord]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT task_id, goal_id, title, status, depends_on, owner, result_summary, metadata, created_at, updated_at
                FROM cognitive_tasks
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def _goals_by_status(self, statuses: set[GoalStatus], limit: int) -> list[GoalRecord]:
        values = [status.value for status in statuses]
        placeholders = ", ".join("?" for _ in values)
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT goal_id, title, status, success_criteria, metadata, created_at, updated_at
                FROM cognitive_goals
                WHERE status IN ({placeholders})
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (*values, max(1, min(limit, 100))),
            ).fetchall()
        return [self._row_to_goal(row) for row in rows]

    def _row_to_goal(self, row: sqlite3.Row) -> GoalRecord:
        return GoalRecord(
            goal_id=row["goal_id"],
            title=row["title"],
            status=GoalStatus(row["status"]),
            success_criteria=json.loads(row["success_criteria"]),
            metadata=json.loads(row["metadata"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_task(self, row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            task_id=row["task_id"],
            goal_id=row["goal_id"],
            title=row["title"],
            status=TaskStatus(row["status"]),
            depends_on=json.loads(row["depends_on"]),
            owner=row["owner"],
            result_summary=row["result_summary"],
            metadata=json.loads(row["metadata"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


def _compact_title(value: str) -> str:
    title = " ".join(str(value or "").strip().split())
    return title[:160] or "Untitled goal"


def _effectively_completed(task: TaskRecord, task_by_id: dict[str, TaskRecord], seen: set[str] | None = None) -> bool:
    if task.status == TaskStatus.COMPLETED:
        return True
    if task.status != TaskStatus.RECOVERING:
        return False
    seen = seen or set()
    if task.task_id in seen:
        return False
    seen.add(task.task_id)
    recovery_task_ids = _string_list(task.metadata.get("recovery_task_ids"))
    if not recovery_task_ids:
        return False
    return all(
        child_id in task_by_id and _effectively_completed(task_by_id[child_id], task_by_id, seen)
        for child_id in recovery_task_ids
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]
