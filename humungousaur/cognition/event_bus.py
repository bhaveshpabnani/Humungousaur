from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from .models import CognitiveEvent, CognitivePriority, new_id, utc_now


class CognitiveEventBus:
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
                CREATE TABLE IF NOT EXISTS cognitive_events (
                    event_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    text TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_cognitive_events_created_at ON cognitive_events(created_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_cognitive_events_source ON cognitive_events(source)"
            )
            connection.commit()

    def append(
        self,
        source: str,
        text: str,
        metadata: dict[str, Any] | None = None,
        priority: CognitivePriority = CognitivePriority.NORMAL,
        event_id: str | None = None,
    ) -> CognitiveEvent:
        event = CognitiveEvent(
            event_id=event_id or new_id("event"),
            source=source,
            text=text,
            metadata=metadata or {},
            priority=priority,
            created_at=utc_now(),
        )
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO cognitive_events (event_id, source, text, metadata, priority, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.source,
                    event.text,
                    json.dumps(event.metadata, ensure_ascii=False, sort_keys=True),
                    event.priority.value,
                    event.created_at,
                ),
            )
            connection.commit()
        return event

    def recent(self, limit: int = 20) -> list[CognitiveEvent]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT event_id, source, text, metadata, priority, created_at
                FROM cognitive_events
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def _row_to_event(self, row: sqlite3.Row) -> CognitiveEvent:
        return CognitiveEvent(
            event_id=row["event_id"],
            source=row["source"],
            text=row["text"],
            metadata=json.loads(row["metadata"]),
            priority=CognitivePriority(row["priority"]),
            created_at=row["created_at"],
        )
