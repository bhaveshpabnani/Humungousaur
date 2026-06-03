from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from .models import CognitivePriority, TriggerRecord, TriggerStatus, new_id, utc_now
from .queue import PRIORITY_RANK, RuntimeEventQueue


class TriggerStore:
    """Durable structured triggers that can queue autonomous work from external stimuli.

    Trigger matching is intentionally limited to exact structured fields. The store
    does not interpret natural language, run regexes, or choose intent from text.
    """

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
                CREATE TABLE IF NOT EXISTS cognitive_triggers (
                    trigger_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    match_source TEXT NOT NULL,
                    match_stimulus_type TEXT NOT NULL,
                    conditions TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    priority_rank INTEGER NOT NULL,
                    event_source TEXT NOT NULL,
                    goal_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL,
                    max_fires INTEGER NOT NULL,
                    fire_count INTEGER NOT NULL,
                    last_fired_at TEXT NOT NULL,
                    last_event_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_cognitive_triggers_status ON cognitive_triggers(status, priority_rank, created_at)"
            )
            connection.commit()

    def create(
        self,
        *,
        name: str,
        match_source: str = "",
        match_stimulus_type: str = "",
        conditions: dict[str, Any] | None = None,
        event_type: str = "STIMULUS",
        payload: dict[str, Any] | None = None,
        priority: CognitivePriority = CognitivePriority.NORMAL,
        event_source: str = "trigger",
        goal_id: str = "",
        task_id: str = "",
        reason: str = "",
        max_fires: int = 0,
    ) -> TriggerRecord:
        now = utc_now()
        record = TriggerRecord(
            trigger_id=new_id("trigger"),
            name=_clean(name, limit=160) or "Unnamed trigger",
            match_source=_clean(match_source, limit=120),
            match_stimulus_type=_clean(match_stimulus_type, limit=120),
            conditions=_clean_conditions(conditions or {}),
            event_type=_clean_event_type(event_type),
            payload=payload if isinstance(payload, dict) else {},
            priority=priority,
            event_source=_clean(event_source, limit=120) or "trigger",
            goal_id=_clean(goal_id, limit=120),
            task_id=_clean(task_id, limit=120),
            reason=_clean(reason, limit=1_000),
            max_fires=max(0, min(int(max_fires or 0), 1_000_000)),
            created_at=now,
            updated_at=now,
        )
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO cognitive_triggers
                (trigger_id, name, match_source, match_stimulus_type, conditions, event_type, payload, priority, priority_rank,
                 event_source, goal_id, task_id, reason, status, max_fires, fire_count, last_fired_at, last_event_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.trigger_id,
                    record.name,
                    record.match_source,
                    record.match_stimulus_type,
                    json.dumps(record.conditions, ensure_ascii=False, sort_keys=True),
                    record.event_type,
                    json.dumps(record.payload, ensure_ascii=False, sort_keys=True),
                    record.priority.value,
                    PRIORITY_RANK[record.priority],
                    record.event_source,
                    record.goal_id,
                    record.task_id,
                    record.reason,
                    record.status.value,
                    record.max_fires,
                    record.fire_count,
                    record.last_fired_at,
                    record.last_event_id,
                    record.created_at,
                    record.updated_at,
                ),
            )
            connection.commit()
        return record

    def active(self, limit: int = 20) -> list[TriggerRecord]:
        return self._by_status(TriggerStatus.ACTIVE, limit=limit)

    def recent(self, limit: int = 20) -> list[TriggerRecord]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT trigger_id, name, match_source, match_stimulus_type, conditions, event_type, payload, priority,
                       event_source, goal_id, task_id, reason, status, max_fires, fire_count, last_fired_at, last_event_id,
                       created_at, updated_at
                FROM cognitive_triggers
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get(self, trigger_id: str) -> TriggerRecord | None:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT trigger_id, name, match_source, match_stimulus_type, conditions, event_type, payload, priority,
                       event_source, goal_id, task_id, reason, status, max_fires, fire_count, last_fired_at, last_event_id,
                       created_at, updated_at
                FROM cognitive_triggers
                WHERE trigger_id = ?
                """,
                (trigger_id,),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def cancel(self, trigger_id: str, *, reason: str = "") -> TriggerRecord | None:
        record = self.get(trigger_id)
        if record is None or record.status == TriggerStatus.CANCELLED:
            return record
        updated_reason = record.reason
        cancel_reason = _clean(reason, limit=500)
        if cancel_reason:
            updated_reason = f"{record.reason} Cancelled: {cancel_reason}".strip()
        now = utc_now()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE cognitive_triggers
                SET status = ?, reason = ?, updated_at = ?
                WHERE trigger_id = ?
                """,
                (TriggerStatus.CANCELLED.value, updated_reason, now, trigger_id),
            )
            connection.commit()
        return self.get(trigger_id)

    def evaluate(
        self,
        stimulus: dict[str, Any],
        queue: RuntimeEventQueue,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        fired: list[dict[str, Any]] = []
        for trigger in self.active(limit=limit):
            if trigger.max_fires and trigger.fire_count >= trigger.max_fires:
                continue
            if not trigger_matches(trigger, stimulus):
                continue
            payload = _event_payload(trigger, stimulus)
            event = queue.push(
                trigger.event_type,
                payload=payload,
                priority=trigger.priority,
                source=trigger.event_source,
            )
            updated = self.mark_fired(trigger.trigger_id, event_id=event.event_id)
            fired.append(
                {
                    "trigger": asdict(updated or trigger),
                    "event": asdict(event),
                    "stimulus": _stimulus_evidence(stimulus),
                }
            )
        return fired

    def matching_triggers(self, stimulus: dict[str, Any], *, limit: int = 20) -> list[TriggerRecord]:
        matches: list[TriggerRecord] = []
        for trigger in self.active(limit=limit):
            if trigger.max_fires and trigger.fire_count >= trigger.max_fires:
                continue
            if trigger_matches(trigger, stimulus):
                matches.append(trigger)
        return matches

    def mark_fired(self, trigger_id: str, *, event_id: str) -> TriggerRecord | None:
        now = utc_now()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE cognitive_triggers
                SET fire_count = fire_count + 1, last_fired_at = ?, last_event_id = ?, updated_at = ?
                WHERE trigger_id = ? AND status = ?
                """,
                (now, _clean(event_id, limit=120), now, trigger_id, TriggerStatus.ACTIVE.value),
            )
            connection.commit()
        return self.get(trigger_id)

    def _by_status(self, status: TriggerStatus, *, limit: int) -> list[TriggerRecord]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT trigger_id, name, match_source, match_stimulus_type, conditions, event_type, payload, priority,
                       event_source, goal_id, task_id, reason, status, max_fires, fire_count, last_fired_at, last_event_id,
                       created_at, updated_at
                FROM cognitive_triggers
                WHERE status = ?
                ORDER BY priority_rank ASC, created_at ASC
                LIMIT ?
                """,
                (status.value, max(1, min(limit, 200))),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: sqlite3.Row) -> TriggerRecord:
        return TriggerRecord(
            trigger_id=row["trigger_id"],
            name=row["name"],
            match_source=row["match_source"],
            match_stimulus_type=row["match_stimulus_type"],
            conditions=json.loads(row["conditions"]),
            event_type=row["event_type"],
            payload=json.loads(row["payload"]),
            priority=CognitivePriority(row["priority"]),
            event_source=row["event_source"],
            goal_id=row["goal_id"],
            task_id=row["task_id"],
            reason=row["reason"],
            status=TriggerStatus(row["status"]),
            max_fires=int(row["max_fires"]),
            fire_count=int(row["fire_count"]),
            last_fired_at=row["last_fired_at"],
            last_event_id=row["last_event_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


def trigger_matches(trigger: TriggerRecord, stimulus: dict[str, Any]) -> bool:
    source = _clean(stimulus.get("source"), limit=120)
    stimulus_type = _clean(stimulus.get("stimulus_type"), limit=120)
    if trigger.match_source and trigger.match_source != source:
        return False
    if trigger.match_stimulus_type and trigger.match_stimulus_type != stimulus_type:
        return False
    conditions = trigger.conditions if isinstance(trigger.conditions, dict) else {}
    metadata = stimulus.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    payload = stimulus.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}
    if not _dict_contains_exact(metadata, conditions.get("metadata_equals")):
        return False
    if not _dict_contains_exact(payload, conditions.get("payload_equals")):
        return False
    if not _has_keys(metadata, conditions.get("required_metadata_keys")):
        return False
    if not _has_keys(payload, conditions.get("required_payload_keys")):
        return False
    text_equals = conditions.get("text_equals")
    if isinstance(text_equals, str) and text_equals != str(stimulus.get("text", "")):
        return False
    return True


def stimulus_from_input(tool_input: dict[str, Any]) -> dict[str, Any]:
    payload = tool_input.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}
    metadata = tool_input.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "stimulus_id": _clean(tool_input.get("stimulus_id"), limit=160),
        "source": _clean(tool_input.get("source"), limit=120),
        "stimulus_type": _clean(tool_input.get("stimulus_type"), limit=120),
        "text": str(tool_input.get("text", "")),
        "metadata": metadata,
        "payload": payload,
        "occurred_at": _clean(tool_input.get("occurred_at"), limit=160),
    }


def _event_payload(trigger: TriggerRecord, stimulus: dict[str, Any]) -> dict[str, Any]:
    payload = dict(trigger.payload)
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    metadata = dict(metadata)
    metadata["trigger_id"] = trigger.trigger_id
    metadata["trigger_name"] = trigger.name
    metadata["triggered_by"] = _stimulus_evidence(stimulus)
    if trigger.goal_id:
        metadata["goal_id"] = trigger.goal_id
    if trigger.task_id:
        metadata["task_id"] = trigger.task_id
    payload["metadata"] = metadata
    payload.setdefault("source", trigger.event_source)
    return payload


def _stimulus_evidence(stimulus: dict[str, Any]) -> dict[str, Any]:
    return {
        "stimulus_id": _clean(stimulus.get("stimulus_id"), limit=160),
        "source": _clean(stimulus.get("source"), limit=120),
        "stimulus_type": _clean(stimulus.get("stimulus_type"), limit=120),
        "occurred_at": _clean(stimulus.get("occurred_at"), limit=160),
    }


def _clean_conditions(value: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    if not isinstance(value, dict):
        return cleaned
    for key in ("metadata_equals", "payload_equals"):
        item = value.get(key)
        if isinstance(item, dict):
            cleaned[key] = _json_safe_dict(item, max_items=50)
    for key in ("required_metadata_keys", "required_payload_keys"):
        item = value.get(key)
        if isinstance(item, list):
            cleaned[key] = [_clean(raw, limit=120) for raw in item[:50] if _clean(raw, limit=120)]
    if isinstance(value.get("text_equals"), str):
        cleaned["text_equals"] = str(value["text_equals"])[:2_000]
    return cleaned


def _dict_contains_exact(actual: dict[str, Any], expected: object) -> bool:
    if not expected:
        return True
    if not isinstance(expected, dict):
        return False
    for key, value in expected.items():
        if actual.get(key) != value:
            return False
    return True


def _has_keys(actual: dict[str, Any], keys: object) -> bool:
    if not keys:
        return True
    if not isinstance(keys, list):
        return False
    return all(isinstance(key, str) and key in actual for key in keys)


def _json_safe_dict(value: dict[str, Any], *, max_items: int) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for index, (key, item) in enumerate(value.items()):
        if index >= max_items:
            break
        cleaned_key = _clean(key, limit=120)
        if cleaned_key:
            cleaned[cleaned_key] = _json_safe_value(item)
    return cleaned


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_json_safe_value(item) for item in value[:20]]
    if isinstance(value, dict):
        return _json_safe_dict(value, max_items=20)
    return str(value)


def _clean_event_type(value: object) -> str:
    return "_".join(str(value or "STIMULUS").strip().upper().split())[:80] or "STIMULUS"


def _clean(value: object, *, limit: int) -> str:
    return " ".join(str(value or "").strip().split())[:limit]
