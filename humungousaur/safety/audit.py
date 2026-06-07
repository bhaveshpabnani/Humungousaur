from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from humungousaur.schemas import ActionStatus, PlanResult, ToolResult


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditLog:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._schema_initialized = False
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        db_exists = self.db_path.exists()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        if not db_exists and self._schema_initialized:
            self._init_schema(connection)
            connection.commit()
        return connection

    def _init_db(self) -> None:
        with closing(self._connect()) as connection:
            self._init_schema(connection)
            connection.commit()
        self._schema_initialized = True

    def _init_schema(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                request TEXT NOT NULL,
                status TEXT NOT NULL,
                final_response TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                cancel_requested_at TEXT,
                cancel_reason TEXT
            )
            """
        )
        self._ensure_column(connection, "runs", "cancel_requested_at", "TEXT")
        self._ensure_column(connection, "runs", "cancel_reason", "TEXT")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                status TEXT NOT NULL,
                tool_input TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS plan_traces (
                run_id TEXT PRIMARY KEY,
                requested_provider TEXT NOT NULL,
                used_provider TEXT NOT NULL,
                fallback_used INTEGER NOT NULL,
                error TEXT,
                duration_ms REAL NOT NULL,
                steps TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS run_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_run_events_run_id ON run_events(run_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_run_events_created_at ON run_events(created_at)")

    def _ensure_column(self, connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def start_run(self, request: str, run_id: str | None = None) -> str:
        run_id = run_id or str(uuid.uuid4())
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO runs (run_id, request, status, started_at) VALUES (?, ?, ?, ?)",
                (run_id, request, ActionStatus.PLANNED.value, _now()),
            )
            connection.commit()
        return run_id

    def log_action(self, run_id: str, tool_input: dict[str, Any], result: ToolResult) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO actions (run_id, tool_name, risk_level, status, tool_input, result, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    result.tool_name,
                    result.risk_level.value,
                    result.status.value,
                    json.dumps(tool_input, ensure_ascii=False, sort_keys=True),
                    json.dumps(asdict(result), ensure_ascii=False, sort_keys=True),
                    _now(),
                ),
            )
            connection.commit()

    def log_plan_trace(self, run_id: str, plan: PlanResult) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO plan_traces (
                    run_id, requested_provider, used_provider, fallback_used, error,
                    duration_ms, steps, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    plan.requested_provider,
                    plan.used_provider,
                    1 if plan.fallback_used else 0,
                    plan.error,
                    plan.duration_ms,
                    json.dumps([asdict(step) for step in plan.steps], ensure_ascii=False, sort_keys=True),
                    _now(),
                ),
            )
            connection.commit()

    def log_run_event(
        self,
        run_id: str,
        event_type: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO run_events (run_id, event_type, message, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    event_type,
                    message,
                    json.dumps(payload or {}, ensure_ascii=False, sort_keys=True),
                    _now(),
                ),
            )
            connection.commit()

    def finish_run(self, run_id: str, status: ActionStatus, final_response: str) -> None:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            existing = connection.execute(
                "SELECT cancel_requested_at FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if existing and existing["cancel_requested_at"] and status not in {ActionStatus.CANCELLING, ActionStatus.CANCELLED}:
                status = ActionStatus.CANCELLED
                final_response = "Run cancelled before completion."
            connection.execute(
                "UPDATE runs SET status = ?, final_response = ?, finished_at = ? WHERE run_id = ?",
                (status.value, final_response, _now(), run_id),
            )
            connection.commit()

    def pause_run(self, run_id: str, status: ActionStatus, final_response: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "UPDATE runs SET status = ?, final_response = ? WHERE run_id = ?",
                (status.value, final_response, run_id),
            )
            connection.commit()

    def request_cancel_run(self, run_id: str, reason: str = "Cancelled by user.") -> dict[str, Any]:
        now = _now()
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT run_id, request, status, final_response, started_at, finished_at,
                       cancel_requested_at, cancel_reason
                FROM runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown run: {run_id}")
            run = dict(row)
            if run["finished_at"]:
                self.log_run_event(
                    run_id,
                    "cancel_ignored",
                    "Run cancellation request ignored because the run already finished.",
                    {"reason": reason, "status": run["status"]},
                )
                return run
            connection.execute(
                """
                UPDATE runs
                SET status = ?, final_response = ?, cancel_requested_at = COALESCE(cancel_requested_at, ?),
                    cancel_reason = COALESCE(cancel_reason, ?)
                WHERE run_id = ?
                """,
                (ActionStatus.CANCELLING.value, "Cancellation requested.", now, reason, run_id),
            )
            connection.commit()
        self.log_run_event(run_id, "cancel_requested", "Run cancellation requested.", {"reason": reason})
        updated = self.get_run(run_id)
        if updated is None:
            raise RuntimeError(f"Run disappeared after cancellation request: {run_id}")
        return updated

    def is_run_cancel_requested(self, run_id: str) -> bool:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT cancel_requested_at FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return bool(row and row[0])

    def recent_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT run_id, request, status, final_response, started_at, finished_at,
                       cancel_requested_at, cancel_reason
                FROM runs
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT run_id, request, status, final_response, started_at, finished_at,
                       cancel_requested_at, cancel_reason
                FROM runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_run_events(self, run_id: str, after_id: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT id, run_id, event_type, message, payload, created_at
                FROM run_events
                WHERE run_id = ? AND id > ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (run_id, after_id, limit),
            ).fetchall()
        return [self._run_event_row_to_dict(row) for row in rows]

    def recent_plan_traces(self, limit: int = 10) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT run_id, requested_provider, used_provider, fallback_used, error,
                       duration_ms, steps, created_at
                FROM plan_traces
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._plan_trace_row_to_dict(row) for row in rows]

    def get_plan_trace(self, run_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT run_id, requested_provider, used_provider, fallback_used, error,
                       duration_ms, steps, created_at
                FROM plan_traces
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
        return self._plan_trace_row_to_dict(row) if row else None

    def _plan_trace_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "run_id": row["run_id"],
            "requested_provider": row["requested_provider"],
            "used_provider": row["used_provider"],
            "fallback_used": bool(row["fallback_used"]),
            "error": row["error"],
            "duration_ms": row["duration_ms"],
            "steps": json.loads(row["steps"]),
            "created_at": row["created_at"],
        }

    def _run_event_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "run_id": row["run_id"],
            "event_type": row["event_type"],
            "message": row["message"],
            "payload": json.loads(row["payload"]),
            "created_at": row["created_at"],
        }
