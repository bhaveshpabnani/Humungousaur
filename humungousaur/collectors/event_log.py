from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .envelope import CollectorEventEnvelope, utc_now
from .schema import validate_envelope_record


class CollectorEventLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _init_db(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS collector_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    schema_version INTEGER NOT NULL,
                    collector TEXT NOT NULL,
                    source TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    stimulus_type TEXT NOT NULL,
                    privacy_tier TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    text TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    redaction_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'accepted',
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_collector_events_occurred_at ON collector_events(occurred_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_collector_events_collector ON collector_events(collector)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_collector_events_signature ON collector_events(signature)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_collector_events_sequence_created ON collector_events(sequence, created_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS collector_consumer_offsets (
                    consumer_name TEXT PRIMARY KEY,
                    last_sequence INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS collector_consumer_failures (
                    consumer_name TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    attempts INTEGER NOT NULL,
                    last_error TEXT NOT NULL,
                    next_retry_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (consumer_name, sequence)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS collector_consumer_state (
                    consumer_name TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS collector_dead_letters (
                    dead_letter_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    consumer_name TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS collector_helper_health (
                    helper_id TEXT PRIMARY KEY,
                    collector TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    status TEXT NOT NULL,
                    pid INTEGER,
                    version TEXT NOT NULL DEFAULT '',
                    permission_state TEXT NOT NULL DEFAULT '',
                    last_event_at TEXT NOT NULL DEFAULT '',
                    last_heartbeat_at TEXT NOT NULL,
                    restart_count INTEGER NOT NULL DEFAULT 0,
                    message TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            connection.commit()

    def append(self, envelope: CollectorEventEnvelope) -> dict[str, Any]:
        validate_envelope_record(envelope.to_record())
        now = utc_now()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO collector_events (
                    event_id, schema_version, collector, source, platform, stimulus_type,
                    privacy_tier, occurred_at, received_at, signature, text,
                    metadata_json, payload_json, redaction_json, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'accepted', ?)
                """,
                (
                    envelope.event_id,
                    envelope.schema_version,
                    envelope.collector,
                    envelope.source,
                    envelope.platform,
                    envelope.stimulus_type,
                    envelope.privacy_tier,
                    envelope.occurred_at,
                    envelope.received_at,
                    envelope.signature,
                    envelope.text,
                    _json_dumps(envelope.metadata),
                    _json_dumps(envelope.payload),
                    _json_dumps(envelope.redaction),
                    now,
                ),
            )
            inserted = connection.total_changes > 0
            row = connection.execute(
                """
                SELECT sequence, event_id, created_at
                FROM collector_events
                WHERE event_id = ?
                """,
                (envelope.event_id,),
            ).fetchone()
            connection.commit()
        return {"sequence": int(row[0]), "event_id": row[1], "created_at": row[2], "inserted": inserted}

    def read_batch(self, consumer_name: str, *, limit: int = 100) -> list[dict[str, Any]]:
        last_sequence = self.consumer_offset(consumer_name)
        retry_cutoff = utc_now()
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT collector_events.*, collector_consumer_failures.next_retry_at AS failure_next_retry_at
                FROM collector_events
                LEFT JOIN collector_consumer_failures
                    ON collector_consumer_failures.consumer_name = ?
                    AND collector_consumer_failures.sequence = collector_events.sequence
                WHERE collector_events.sequence > ?
                ORDER BY collector_events.sequence ASC
                LIMIT ?
                """,
                (consumer_name, last_sequence, max(1, min(limit, 1000))),
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            next_retry_at = str(row["failure_next_retry_at"] or "")
            if next_retry_at and next_retry_at > retry_cutoff:
                break
            events.append(self._row_to_event(row))
        return events

    def ack(self, consumer_name: str, sequence: int) -> None:
        if sequence <= 0:
            return
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO collector_consumer_offsets (consumer_name, last_sequence, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(consumer_name) DO UPDATE SET
                    last_sequence = max(last_sequence, excluded.last_sequence),
                    updated_at = excluded.updated_at
                """,
                (consumer_name, int(sequence), utc_now()),
            )
            connection.execute(
                "DELETE FROM collector_consumer_failures WHERE consumer_name = ? AND sequence <= ?",
                (consumer_name, int(sequence)),
            )
            connection.commit()

    def retry_later(self, consumer_name: str, sequence: int, error: str, *, max_attempts: int = 3) -> dict[str, Any]:
        cleaned_error = " ".join(str(error).split())[:1000]
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT attempts
                FROM collector_consumer_failures
                WHERE consumer_name = ? AND sequence = ?
                """,
                (consumer_name, int(sequence)),
            ).fetchone()
            attempts = int(row[0]) + 1 if row else 1
            if attempts >= max_attempts:
                event = self.get(sequence) or {}
                connection.execute(
                    """
                    INSERT INTO collector_dead_letters (consumer_name, sequence, reason, event_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (consumer_name, int(sequence), cleaned_error, _json_dumps(event), utc_now()),
                )
                connection.execute(
                    "DELETE FROM collector_consumer_failures WHERE consumer_name = ? AND sequence = ?",
                    (consumer_name, int(sequence)),
                )
                connection.commit()
                self.ack(consumer_name, sequence)
                return {"dead_lettered": True, "attempts": attempts}
            connection.execute(
                """
                INSERT INTO collector_consumer_failures (
                    consumer_name, sequence, attempts, last_error, next_retry_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(consumer_name, sequence) DO UPDATE SET
                    attempts = excluded.attempts,
                    last_error = excluded.last_error,
                    next_retry_at = excluded.next_retry_at,
                    updated_at = excluded.updated_at
                """,
                (consumer_name, int(sequence), attempts, cleaned_error, _retry_time(attempts), utc_now()),
            )
            connection.commit()
        return {"dead_lettered": False, "attempts": attempts}

    def get(self, sequence: int) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM collector_events WHERE sequence = ?", (int(sequence),)).fetchone()
        return self._row_to_event(row) if row is not None else None

    def consumer_offset(self, consumer_name: str) -> int:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT last_sequence FROM collector_consumer_offsets WHERE consumer_name = ?",
                (consumer_name,),
            ).fetchone()
        return int(row[0]) if row else 0

    def consumer_state(self, consumer_name: str) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT state_json FROM collector_consumer_state WHERE consumer_name = ?",
                (consumer_name,),
            ).fetchone()
        if not row:
            return {}
        try:
            state = json.loads(row[0])
        except json.JSONDecodeError:
            return {}
        return state if isinstance(state, dict) else {}

    def save_consumer_state(self, consumer_name: str, state: dict[str, Any]) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO collector_consumer_state (consumer_name, state_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(consumer_name) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (consumer_name, _json_dumps(state), utc_now()),
            )
            connection.commit()

    def tail(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT *
                FROM collector_events
                ORDER BY sequence DESC
                LIMIT ?
                """,
                (max(1, min(limit, 1000)),),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def query(
        self,
        *,
        limit: int = 100,
        collector: str | None = None,
        stimulus_type: str | None = None,
        since_sequence: int = 0,
    ) -> list[dict[str, Any]]:
        clauses = ["sequence > ?"]
        values: list[Any] = [max(0, int(since_sequence or 0))]
        if collector:
            clauses.append("collector = ?")
            values.append(str(collector))
        if stimulus_type:
            clauses.append("stimulus_type = ?")
            values.append(str(stimulus_type))
        values.append(max(1, min(int(limit or 100), 1000)))
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT *
                FROM collector_events
                WHERE {' AND '.join(clauses)}
                ORDER BY sequence DESC
                LIMIT ?
                """,
                tuple(values),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def enforce_retention(self, *, max_events: int = 50_000, max_age_seconds: int = 7 * 24 * 3600) -> dict[str, Any]:
        max_events = max(1_000, int(max_events or 50_000))
        max_age_seconds = max(3600, int(max_age_seconds or 7 * 24 * 3600))
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)).isoformat()
        with closing(self._connect()) as connection:
            latest = connection.execute("SELECT COALESCE(MAX(sequence), 0) FROM collector_events").fetchone()[0]
            event_count = connection.execute("SELECT COUNT(*) FROM collector_events").fetchone()[0]
            offsets = [int(row[0]) for row in connection.execute("SELECT last_sequence FROM collector_consumer_offsets").fetchall()]
            if not offsets:
                return {"deleted": 0, "reason": "no consumer offsets yet", "event_count": int(event_count)}
            min_offset = min(offsets)
            overflow_floor = max(0, int(latest) - max_events)
            deleted = connection.execute(
                """
                DELETE FROM collector_events
                WHERE sequence <= ?
                AND (sequence <= ? OR created_at < ?)
                """,
                (min_offset, overflow_floor, cutoff),
            ).rowcount
            connection.commit()
        return {"deleted": int(deleted), "min_consumer_offset": min_offset, "max_events": max_events, "max_age_seconds": max_age_seconds}

    def record_helper_health(
        self,
        *,
        helper_id: str,
        collector: str,
        platform: str,
        status: str,
        pid: int | None = None,
        version: str = "",
        permission_state: str = "",
        last_event_at: str = "",
        restart_count: int = 0,
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO collector_helper_health (
                    helper_id, collector, platform, status, pid, version, permission_state,
                    last_event_at, last_heartbeat_at, restart_count, message, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(helper_id) DO UPDATE SET
                    collector = excluded.collector,
                    platform = excluded.platform,
                    status = excluded.status,
                    pid = excluded.pid,
                    version = excluded.version,
                    permission_state = excluded.permission_state,
                    last_event_at = excluded.last_event_at,
                    last_heartbeat_at = excluded.last_heartbeat_at,
                    restart_count = excluded.restart_count,
                    message = excluded.message,
                    metadata_json = excluded.metadata_json
                """,
                (
                    helper_id,
                    collector,
                    platform,
                    status,
                    pid,
                    version,
                    permission_state,
                    last_event_at,
                    utc_now(),
                    int(restart_count or 0),
                    " ".join(str(message or "").split())[:1000],
                    _json_dumps(metadata or {}),
                ),
            )
            connection.commit()

    def helper_health(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT *
                FROM collector_helper_health
                ORDER BY last_heartbeat_at DESC
                LIMIT ?
                """,
                (max(1, min(int(limit or 100), 1000)),),
            ).fetchall()
        return [
            {
                **dict(row),
                "metadata": _json_loads(row["metadata_json"]),
            }
            for row in rows
        ]

    def status(self, *, limit: int = 10) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            offsets = connection.execute(
                """
                SELECT consumer_name, last_sequence, updated_at
                FROM collector_consumer_offsets
                ORDER BY consumer_name
                """
            ).fetchall()
            failures = connection.execute(
                """
                SELECT consumer_name, sequence, attempts, last_error, next_retry_at, updated_at
                FROM collector_consumer_failures
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 100)),),
            ).fetchall()
            dead_letter_count = connection.execute("SELECT COUNT(*) FROM collector_dead_letters").fetchone()[0]
            event_count = connection.execute("SELECT COUNT(*) FROM collector_events").fetchone()[0]
            latest_sequence = connection.execute("SELECT COALESCE(MAX(sequence), 0) FROM collector_events").fetchone()[0]
            oldest_created = connection.execute("SELECT MIN(created_at) FROM collector_events").fetchone()[0]
            newest_created = connection.execute("SELECT MAX(created_at) FROM collector_events").fetchone()[0]
        offset_payload = [dict(row) for row in offsets]
        for item in offset_payload:
            item["lag"] = max(0, int(latest_sequence) - int(item.get("last_sequence") or 0))
        return {
            "event_log_path": str(self.path),
            "event_count": int(event_count),
            "latest_sequence": int(latest_sequence),
            "oldest_created_at": oldest_created,
            "newest_created_at": newest_created,
            "consumer_offsets": offset_payload,
            "consumer_failures": [dict(row) for row in failures],
            "dead_letter_count": int(dead_letter_count),
            "helper_health": self.helper_health(limit=limit),
            "recent_events": self.tail(limit=limit),
        }

    def _row_to_event(self, row: sqlite3.Row) -> dict[str, Any]:
        envelope = CollectorEventEnvelope(
            event_id=row["event_id"],
            schema_version=int(row["schema_version"]),
            collector=row["collector"],
            source=row["source"],
            platform=row["platform"],
            stimulus_type=row["stimulus_type"],
            privacy_tier=row["privacy_tier"],
            occurred_at=row["occurred_at"],
            received_at=row["received_at"],
            signature=row["signature"],
            text=row["text"],
            metadata=_json_loads(row["metadata_json"]),
            payload=_json_loads(row["payload_json"]),
            redaction=_json_loads(row["redaction_json"]),
        )
        record = envelope.to_record()
        record["sequence"] = int(row["sequence"])
        record["status"] = row["status"]
        record["created_at"] = row["created_at"]
        return record


def _json_dumps(value: Any) -> str:
    return json.dumps(value if isinstance(value, (dict, list)) else {}, ensure_ascii=False, sort_keys=True, default=str)


def _json_loads(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _retry_time(attempts: int) -> str:
    delay_seconds = min(300, max(1, 2 ** max(0, attempts - 1)))
    return (datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)).isoformat()
