from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from humungousaur.schemas import ApprovalRequest, ToolResult


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ApprovalRecord:
    approval_token: str
    run_id: str
    request: str
    tool_name: str
    tool_input: dict[str, Any]
    risk_level: str
    reason: str
    status: str
    created_at: str
    decided_at: str | None = None
    decision_note: str | None = None
    result: dict[str, Any] | None = None


class ApprovalStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_token TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    request TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    tool_input TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    decided_at TEXT,
                    decision_note TEXT,
                    result TEXT
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_approvals_created_at ON approvals(created_at)")
            connection.commit()

    def create_pending(self, run_id: str, request: str, approval: ApprovalRequest) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO approvals (
                    approval_token, run_id, request, tool_name, tool_input, risk_level,
                    reason, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval.approval_token,
                    run_id,
                    request,
                    approval.tool_name,
                    json.dumps(approval.tool_input, ensure_ascii=False, sort_keys=True),
                    approval.risk_level.value,
                    approval.reason,
                    "pending",
                    _now(),
                ),
            )
            connection.commit()

    def list(self, status: str | None = "pending", limit: int = 20) -> list[ApprovalRecord]:
        query = """
            SELECT approval_token, run_id, request, tool_name, tool_input, risk_level,
                   reason, status, created_at, decided_at, decision_note, result
            FROM approvals
        """
        parameters: tuple[Any, ...]
        if status:
            query += " WHERE status = ?"
            parameters = (status,)
        else:
            parameters = ()
        query += " ORDER BY created_at DESC LIMIT ?"
        parameters = parameters + (limit,)
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query, parameters).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get(self, approval_token: str) -> ApprovalRecord | None:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT approval_token, run_id, request, tool_name, tool_input, risk_level,
                       reason, status, created_at, decided_at, decision_note, result
                FROM approvals
                WHERE approval_token = ?
                """,
                (approval_token,),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def reject(self, approval_token: str, note: str = "") -> ApprovalRecord:
        record = self.get(approval_token)
        if record is None:
            raise KeyError(f"Unknown approval token: {approval_token}")
        if record.status != "pending":
            raise ValueError(f"Approval is not pending: {approval_token} ({record.status})")
        self._update_decision(approval_token, "rejected", note, None)
        updated = self.get(approval_token)
        if updated is None:
            raise RuntimeError(f"Approval disappeared after rejection: {approval_token}")
        return updated

    def update_tool_input(
        self,
        approval_token: str,
        tool_input: dict[str, Any],
        note: str = "",
    ) -> ApprovalRecord:
        record = self.get(approval_token)
        if record is None:
            raise KeyError(f"Unknown approval token: {approval_token}")
        if record.status != "pending":
            raise ValueError(f"Approval is not pending: {approval_token} ({record.status})")
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE approvals
                SET tool_input = ?, decision_note = ?
                WHERE approval_token = ?
                """,
                (
                    json.dumps(tool_input, ensure_ascii=False, sort_keys=True),
                    note,
                    approval_token,
                ),
            )
            connection.commit()
        updated = self.get(approval_token)
        if updated is None:
            raise RuntimeError(f"Approval disappeared after update: {approval_token}")
        return updated

    def mark_executed(self, approval_token: str, result: ToolResult, note: str = "approved") -> ApprovalRecord:
        record = self.get(approval_token)
        if record is None:
            raise KeyError(f"Unknown approval token: {approval_token}")
        if record.status != "pending":
            raise ValueError(f"Approval is not pending: {approval_token} ({record.status})")
        self._update_decision(
            approval_token,
            "executed" if result.status.value == "succeeded" else "failed",
            note,
            {
                "tool_name": result.tool_name,
                "status": result.status.value,
                "risk_level": result.risk_level.value,
                "summary": result.summary,
                "output": result.output,
                "error": result.error,
            },
        )
        updated = self.get(approval_token)
        if updated is None:
            raise RuntimeError(f"Approval disappeared after execution: {approval_token}")
        return updated

    def _update_decision(
        self,
        approval_token: str,
        status: str,
        note: str,
        result: dict[str, Any] | None,
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE approvals
                SET status = ?, decided_at = ?, decision_note = ?, result = ?
                WHERE approval_token = ?
                """,
                (
                    status,
                    _now(),
                    note,
                    json.dumps(result, ensure_ascii=False, sort_keys=True) if result is not None else None,
                    approval_token,
                ),
            )
            connection.commit()

    def _row_to_record(self, row: sqlite3.Row) -> ApprovalRecord:
        return ApprovalRecord(
            approval_token=row["approval_token"],
            run_id=row["run_id"],
            request=row["request"],
            tool_name=row["tool_name"],
            tool_input=json.loads(row["tool_input"]),
            risk_level=row["risk_level"],
            reason=row["reason"],
            status=row["status"],
            created_at=row["created_at"],
            decided_at=row["decided_at"],
            decision_note=row["decision_note"],
            result=json.loads(row["result"]) if row["result"] else None,
        )
