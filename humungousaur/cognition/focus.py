from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from .models import FocusMode, FocusState, utc_now


class FocusStore:
    """Durable current-focus state for the assistant runtime."""

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
                CREATE TABLE IF NOT EXISTS cognitive_focus (
                    focus_key TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    active_goal_id TEXT NOT NULL,
                    active_task_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    pinned_context TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def load(self) -> FocusState:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT mode, active_goal_id, active_task_id, summary, pinned_context, metadata, updated_at
                FROM cognitive_focus
                WHERE focus_key = 'current'
                """
            ).fetchone()
        return self._row_to_state(row) if row else FocusState()

    def update(
        self,
        *,
        mode: FocusMode | str | None = None,
        active_goal_id: str | None = None,
        active_task_id: str | None = None,
        summary: str | None = None,
        pinned_context: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> FocusState:
        current = self.load()
        next_state = FocusState(
            mode=_focus_mode(mode) if mode is not None else current.mode,
            active_goal_id=_clean(active_goal_id) if active_goal_id is not None else current.active_goal_id,
            active_task_id=_clean(active_task_id) if active_task_id is not None else current.active_task_id,
            summary=_clean(summary, limit=1_000) if summary is not None else current.summary,
            pinned_context=_string_list(pinned_context) if pinned_context is not None else current.pinned_context,
            metadata=metadata if metadata is not None else current.metadata,
            updated_at=utc_now(),
        )
        self._save(next_state)
        return next_state

    def clear(self, summary: str = "") -> FocusState:
        state = FocusState(summary=_clean(summary, limit=1_000), updated_at=utc_now())
        self._save(state)
        return state

    def _save(self, state: FocusState) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO cognitive_focus
                (focus_key, mode, active_goal_id, active_task_id, summary, pinned_context, metadata, updated_at)
                VALUES ('current', ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(focus_key) DO UPDATE SET
                    mode = excluded.mode,
                    active_goal_id = excluded.active_goal_id,
                    active_task_id = excluded.active_task_id,
                    summary = excluded.summary,
                    pinned_context = excluded.pinned_context,
                    metadata = excluded.metadata,
                    updated_at = excluded.updated_at
                """,
                (
                    state.mode.value,
                    state.active_goal_id,
                    state.active_task_id,
                    state.summary,
                    json.dumps(state.pinned_context, ensure_ascii=False, sort_keys=True),
                    json.dumps(state.metadata, ensure_ascii=False, sort_keys=True),
                    state.updated_at,
                ),
            )
            connection.commit()

    def _row_to_state(self, row: sqlite3.Row) -> FocusState:
        return FocusState(
            mode=_focus_mode(row["mode"]),
            active_goal_id=row["active_goal_id"],
            active_task_id=row["active_task_id"],
            summary=row["summary"],
            pinned_context=json.loads(row["pinned_context"]),
            metadata=json.loads(row["metadata"]),
            updated_at=row["updated_at"],
        )


def _focus_mode(value: FocusMode | str | None) -> FocusMode:
    try:
        return value if isinstance(value, FocusMode) else FocusMode(str(value or FocusMode.IDLE.value))
    except ValueError:
        return FocusMode.IDLE


def _clean(value: object, *, limit: int = 500) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean(item, limit=500) for item in value if _clean(item, limit=500)]
