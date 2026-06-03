from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from .models import CognitivePriority, RuntimeEvent, RuntimeEventStatus, new_id, utc_now


PRIORITY_RANK = {
    CognitivePriority.CRITICAL: 0,
    CognitivePriority.HIGH: 1,
    CognitivePriority.NORMAL: 2,
    CognitivePriority.LOW: 3,
}


class RuntimeEventQueue:
    """SQLite-backed event queue for autonomous cognitive cycles."""

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
                CREATE TABLE IF NOT EXISTS runtime_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    priority_rank INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    consumed_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_runtime_events_queue ON runtime_events(status, priority_rank, created_at)"
            )
            connection.commit()

    def push(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        priority: CognitivePriority = CognitivePriority.NORMAL,
        source: str = "runtime",
        event_id: str | None = None,
    ) -> RuntimeEvent:
        event = RuntimeEvent(
            event_id=event_id or new_id("rt-event"),
            event_type=_clean_event_type(event_type),
            payload=payload or {},
            priority=priority,
            source=source or "runtime",
        )
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO runtime_events
                (event_id, event_type, payload, priority, priority_rank, source, status, created_at, consumed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.event_type,
                    json.dumps(event.payload, ensure_ascii=False, sort_keys=True),
                    event.priority.value,
                    PRIORITY_RANK[event.priority],
                    event.source,
                    event.status.value,
                    event.created_at,
                    event.consumed_at,
                ),
            )
            connection.commit()
        return event

    def peek_next(self) -> RuntimeEvent | None:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT event_id, event_type, payload, priority, source, status, created_at, consumed_at
                FROM runtime_events
                WHERE status = ?
                ORDER BY priority_rank ASC, created_at ASC
                LIMIT 1
                """,
                (RuntimeEventStatus.QUEUED.value,),
            ).fetchone()
        return self._row_to_event(row) if row else None

    def pop_next(self) -> RuntimeEvent | None:
        event = self.peek_next()
        if event is None:
            return None
        return self.consume(event.event_id)

    def peek_type(self, event_type: str) -> RuntimeEvent | None:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT event_id, event_type, payload, priority, source, status, created_at, consumed_at
                FROM runtime_events
                WHERE status = ? AND event_type = ?
                ORDER BY priority_rank ASC, created_at ASC
                LIMIT 1
                """,
                (RuntimeEventStatus.QUEUED.value, _clean_event_type(event_type)),
            ).fetchone()
        return self._row_to_event(row) if row else None

    def pop_type(self, event_type: str) -> RuntimeEvent | None:
        event = self.peek_type(event_type)
        if event is None:
            return None
        return self.consume(event.event_id)

    def consume(self, event_id: str) -> RuntimeEvent | None:
        event = self._get(event_id)
        if event is None or event.status != RuntimeEventStatus.QUEUED:
            return None
        consumed_at = utc_now()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE runtime_events
                SET status = ?, consumed_at = ?
                WHERE event_id = ? AND status = ?
                """,
                (RuntimeEventStatus.CONSUMED.value, consumed_at, event.event_id, RuntimeEventStatus.QUEUED.value),
            )
            connection.commit()
        event.status = RuntimeEventStatus.CONSUMED
        event.consumed_at = consumed_at
        return event

    def _get(self, event_id: str) -> RuntimeEvent | None:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT event_id, event_type, payload, priority, source, status, created_at, consumed_at
                FROM runtime_events
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()
        return self._row_to_event(row) if row else None

    def queued(self, limit: int = 20) -> list[RuntimeEvent]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT event_id, event_type, payload, priority, source, status, created_at, consumed_at
                FROM runtime_events
                WHERE status = ?
                ORDER BY priority_rank ASC, created_at ASC
                LIMIT ?
                """,
                (RuntimeEventStatus.QUEUED.value, max(1, min(limit, 200))),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def recent(self, limit: int = 20) -> list[RuntimeEvent]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT event_id, event_type, payload, priority, source, status, created_at, consumed_at
                FROM runtime_events
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def _row_to_event(self, row: sqlite3.Row) -> RuntimeEvent:
        return RuntimeEvent(
            event_id=row["event_id"],
            event_type=row["event_type"],
            payload=json.loads(row["payload"]),
            priority=CognitivePriority(row["priority"]),
            source=row["source"],
            status=RuntimeEventStatus(row["status"]),
            created_at=row["created_at"],
            consumed_at=row["consumed_at"],
        )


def _clean_event_type(value: str) -> str:
    return "_".join(str(value or "event").strip().upper().split())[:80] or "EVENT"
