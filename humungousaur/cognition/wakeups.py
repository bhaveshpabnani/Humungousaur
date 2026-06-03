from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from .models import CognitivePriority, WakeupRecord, WakeupStatus, new_id, utc_now


class WakeupStore:
    """Durable future triggers for proactive autonomous cycles."""

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
                CREATE TABLE IF NOT EXISTS cognitive_wakeups (
                    wakeup_id TEXT PRIMARY KEY,
                    scheduled_for TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    priority_rank INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    goal_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL,
                    fired_event_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_cognitive_wakeups_due ON cognitive_wakeups(status, scheduled_for, priority_rank)"
            )
            connection.commit()

    def schedule(
        self,
        *,
        scheduled_for: str,
        event_type: str = "STIMULUS",
        payload: dict[str, Any] | None = None,
        priority: CognitivePriority = CognitivePriority.NORMAL,
        source: str = "wakeup",
        goal_id: str = "",
        task_id: str = "",
        reason: str = "",
    ) -> WakeupRecord:
        now = utc_now()
        record = WakeupRecord(
            wakeup_id=new_id("wakeup"),
            scheduled_for=normalize_scheduled_for(scheduled_for),
            event_type=_clean_event_type(event_type),
            payload=payload if isinstance(payload, dict) else {},
            priority=priority,
            source=_clean(source, limit=120) or "wakeup",
            goal_id=_clean(goal_id, limit=120),
            task_id=_clean(task_id, limit=120),
            reason=_clean(reason, limit=1_000),
            created_at=now,
            updated_at=now,
        )
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO cognitive_wakeups
                (wakeup_id, scheduled_for, event_type, payload, priority, priority_rank, source, goal_id, task_id, reason, status, fired_event_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.wakeup_id,
                    record.scheduled_for,
                    record.event_type,
                    json.dumps(record.payload, ensure_ascii=False, sort_keys=True),
                    record.priority.value,
                    _priority_rank(record.priority),
                    record.source,
                    record.goal_id,
                    record.task_id,
                    record.reason,
                    record.status.value,
                    record.fired_event_id,
                    record.created_at,
                    record.updated_at,
                ),
            )
            connection.commit()
        return record

    def due(self, *, now: str | None = None, limit: int = 20) -> list[WakeupRecord]:
        due_at = normalize_scheduled_for(now or utc_now())
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT wakeup_id, scheduled_for, event_type, payload, priority, source, goal_id, task_id, reason, status, fired_event_id, created_at, updated_at
                FROM cognitive_wakeups
                WHERE status = ? AND scheduled_for <= ?
                ORDER BY priority_rank ASC, scheduled_for ASC, created_at ASC
                LIMIT ?
                """,
                (WakeupStatus.SCHEDULED.value, due_at, max(1, min(limit, 200))),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def scheduled(self, limit: int = 20) -> list[WakeupRecord]:
        return self._by_status(WakeupStatus.SCHEDULED, limit=limit)

    def recent(self, limit: int = 20) -> list[WakeupRecord]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT wakeup_id, scheduled_for, event_type, payload, priority, source, goal_id, task_id, reason, status, fired_event_id, created_at, updated_at
                FROM cognitive_wakeups
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def mark_fired(self, wakeup_id: str, *, fired_event_id: str = "") -> WakeupRecord | None:
        return self._transition(wakeup_id, WakeupStatus.FIRED, fired_event_id=fired_event_id)

    def cancel(self, wakeup_id: str, *, reason: str = "") -> WakeupRecord | None:
        record = self.get(wakeup_id)
        if record is None or record.status != WakeupStatus.SCHEDULED:
            return record
        cancel_reason = _clean(reason, limit=500)
        updated_reason = record.reason
        if cancel_reason:
            updated_reason = f"{record.reason} Cancelled: {cancel_reason}".strip()
        now = utc_now()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE cognitive_wakeups
                SET status = ?, reason = ?, updated_at = ?
                WHERE wakeup_id = ? AND status = ?
                """,
                (WakeupStatus.CANCELLED.value, updated_reason, now, wakeup_id, WakeupStatus.SCHEDULED.value),
            )
            connection.commit()
        return self.get(wakeup_id)

    def get(self, wakeup_id: str) -> WakeupRecord | None:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT wakeup_id, scheduled_for, event_type, payload, priority, source, goal_id, task_id, reason, status, fired_event_id, created_at, updated_at
                FROM cognitive_wakeups
                WHERE wakeup_id = ?
                """,
                (wakeup_id,),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def _transition(self, wakeup_id: str, status: WakeupStatus, *, fired_event_id: str = "") -> WakeupRecord | None:
        now = utc_now()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE cognitive_wakeups
                SET status = ?, fired_event_id = ?, updated_at = ?
                WHERE wakeup_id = ? AND status = ?
                """,
                (status.value, _clean(fired_event_id, limit=120), now, wakeup_id, WakeupStatus.SCHEDULED.value),
            )
            connection.commit()
        return self.get(wakeup_id)

    def _by_status(self, status: WakeupStatus, *, limit: int) -> list[WakeupRecord]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT wakeup_id, scheduled_for, event_type, payload, priority, source, goal_id, task_id, reason, status, fired_event_id, created_at, updated_at
                FROM cognitive_wakeups
                WHERE status = ?
                ORDER BY scheduled_for ASC, created_at ASC
                LIMIT ?
                """,
                (status.value, max(1, min(limit, 200))),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: sqlite3.Row) -> WakeupRecord:
        return WakeupRecord(
            wakeup_id=row["wakeup_id"],
            scheduled_for=row["scheduled_for"],
            event_type=row["event_type"],
            payload=json.loads(row["payload"]),
            priority=CognitivePriority(row["priority"]),
            source=row["source"],
            goal_id=row["goal_id"],
            task_id=row["task_id"],
            reason=row["reason"],
            status=WakeupStatus(row["status"]),
            fired_event_id=row["fired_event_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


def scheduled_for_from_delay(delay_seconds: int | float) -> str:
    seconds = max(1, min(int(delay_seconds), 31_536_000))
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def normalize_scheduled_for(value: str) -> str:
    return try_normalize_scheduled_for(value) or utc_now()


def try_normalize_scheduled_for(value: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _priority_rank(priority: CognitivePriority) -> int:
    ranks = {
        CognitivePriority.CRITICAL: 0,
        CognitivePriority.HIGH: 1,
        CognitivePriority.NORMAL: 2,
        CognitivePriority.LOW: 3,
    }
    return ranks[priority]


def _clean_event_type(value: str) -> str:
    return "_".join(str(value or "STIMULUS").strip().upper().split())[:80] or "STIMULUS"


def _clean(value: object, *, limit: int) -> str:
    return " ".join(str(value or "").strip().split())[:limit]
