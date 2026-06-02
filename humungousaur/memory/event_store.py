from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class MemoryEvent:
    event_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: str


class EventStore:
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
                CREATE TABLE IF NOT EXISTS memory_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_events_created_at ON memory_events(created_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_events_type ON memory_events(event_type)"
            )
            connection.commit()

    def append(self, event_type: str, payload: dict[str, Any], created_at: datetime | None = None) -> str:
        event = MemoryEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            payload=payload,
            created_at=_utc_iso(created_at or datetime.now(timezone.utc)),
        )
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO memory_events (event_id, event_type, payload, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.event_type,
                    json.dumps(event.payload, ensure_ascii=False, sort_keys=True),
                    event.created_at,
                ),
            )
            connection.commit()
        return event.event_id

    def delete_before(self, event_type: str, before: datetime) -> int:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                DELETE FROM memory_events
                WHERE event_type = ? AND created_at < ?
                """,
                (event_type, _utc_iso(before)),
            )
            connection.commit()
        return int(cursor.rowcount)

    def tail(self, limit: int = 20) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT event_id, event_type, payload, created_at
                FROM memory_events
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def between(
        self,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int = 200,
        ascending: bool = True,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if start_at is not None:
            clauses.append("created_at >= ?")
            params.append(_utc_iso(start_at))
        if end_at is not None:
            clauses.append("created_at < ?")
            params.append(_utc_iso(end_at))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        direction = "ASC" if ascending else "DESC"
        params.append(max(1, min(limit, 1_000)))
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT event_id, event_type, payload, created_at
                FROM memory_events
                {where}
                ORDER BY created_at {direction}
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        needle = f"%{query.strip().lower()}%"
        if needle == "%%":
            return []
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT event_id, event_type, payload, created_at
                FROM memory_events
                WHERE lower(event_type) LIKE ? OR lower(payload) LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (needle, needle, limit),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def _row_to_event(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "event_id": row["event_id"],
            "event_type": row["event_type"],
            "payload": json.loads(row["payload"]),
            "created_at": row["created_at"],
        }


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
