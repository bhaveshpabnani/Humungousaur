from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ACTIVE_MESSAGE_STATUSES = {"queued", "running", "planned", "cancelling", "needs_approval"}
TERMINAL_RUN_STATUSES = {"succeeded", "failed", "cancelled", "skipped", "blocked"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DesktopChatStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_conversations (
                    conversation_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_message_at TEXT NOT NULL,
                    metadata TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    message_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source TEXT NOT NULL,
                    run_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    FOREIGN KEY(conversation_id) REFERENCES chat_conversations(conversation_id)
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation ON chat_messages(conversation_id, sequence)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_run_id ON chat_messages(run_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_chat_conversations_updated ON chat_conversations(updated_at)")
            connection.commit()

    def create_conversation(self, *, title: str = "", source: str = "desktop_app", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        now = utc_now()
        conversation_id = str(uuid.uuid4())
        clean_title = _clean_title(title) or "New chat"
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO chat_conversations (
                    conversation_id, title, source, status, created_at, updated_at, last_message_at, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (conversation_id, clean_title, str(source or "desktop_app"), "active", now, now, now, _json(metadata)),
            )
            connection.commit()
        conversation = self.get_conversation(conversation_id)
        if conversation is None:
            raise RuntimeError("Conversation disappeared after creation.")
        return conversation

    def list_conversations(self, *, limit: int = 50) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit or 50), 200))
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT c.*, COUNT(m.message_id) AS message_count
                FROM chat_conversations c
                LEFT JOIN chat_messages m ON m.conversation_id = c.conversation_id
                GROUP BY c.conversation_id
                ORDER BY c.last_message_at DESC, c.created_at DESC
                LIMIT ?
                """,
                (bounded,),
            ).fetchall()
        return [_conversation_row_to_dict(row) for row in rows]

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT c.*, COUNT(m.message_id) AS message_count
                FROM chat_conversations c
                LEFT JOIN chat_messages m ON m.conversation_id = c.conversation_id
                WHERE c.conversation_id = ?
                GROUP BY c.conversation_id
                """,
                (conversation_id,),
            ).fetchone()
        return _conversation_row_to_dict(row) if row else None

    def append_message(
        self,
        conversation_id: str,
        *,
        role: str,
        text: str,
        status: str = "succeeded",
        source: str = "desktop_app",
        run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        if self.get_conversation(conversation_id) is None:
            raise KeyError(f"Unknown chat conversation: {conversation_id}")
        now = utc_now()
        message_id = message_id or str(uuid.uuid4())
        with closing(self._connect()) as connection:
            sequence = int(
                connection.execute(
                    "SELECT COALESCE(MAX(sequence), 0) + 1 FROM chat_messages WHERE conversation_id = ?",
                    (conversation_id,),
                ).fetchone()[0]
            )
            connection.execute(
                """
                INSERT INTO chat_messages (
                    message_id, conversation_id, sequence, role, text, status, source, run_id, created_at, updated_at, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    conversation_id,
                    sequence,
                    _clean_role(role),
                    str(text or ""),
                    str(status or "succeeded"),
                    str(source or "desktop_app"),
                    run_id,
                    now,
                    now,
                    _json(metadata),
                ),
            )
            self._touch_conversation(connection, conversation_id, now, title_hint=text if role == "user" else "")
            connection.commit()
        message = self.get_message(message_id)
        if message is None:
            raise RuntimeError("Message disappeared after creation.")
        return message

    def update_message(
        self,
        message_id: str,
        *,
        text: str | None = None,
        status: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        existing = self.get_message(message_id)
        if existing is None:
            raise KeyError(f"Unknown chat message: {message_id}")
        merged_metadata = dict(existing.get("metadata") or {})
        if metadata:
            merged_metadata.update(metadata)
        now = utc_now()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE chat_messages
                SET text = ?, status = ?, updated_at = ?, metadata = ?
                WHERE message_id = ?
                """,
                (
                    existing["text"] if text is None else str(text),
                    existing["status"] if status is None else str(status),
                    now,
                    _json(merged_metadata),
                    message_id,
                ),
            )
            self._touch_conversation(connection, existing["conversation_id"], now)
            connection.commit()
        updated = self.get_message(message_id)
        if updated is None:
            raise RuntimeError("Message disappeared after update.")
        return updated

    def get_message(self, message_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM chat_messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
        return _message_row_to_dict(row) if row else None

    def messages(self, conversation_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        if self.get_conversation(conversation_id) is None:
            raise KeyError(f"Unknown chat conversation: {conversation_id}")
        bounded = max(1, min(int(limit or 200), 500))
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM chat_messages
                WHERE conversation_id = ?
                ORDER BY sequence ASC
                LIMIT ?
                """,
                (conversation_id, bounded),
            ).fetchall()
        return [_message_row_to_dict(row) for row in rows]

    def sync_run_messages(self, audit: Any) -> None:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT message_id, run_id
                FROM chat_messages
                WHERE role = 'assistant'
                  AND run_id IS NOT NULL
                  AND status IN ('queued', 'running', 'planned', 'cancelling', 'needs_approval')
                """
            ).fetchall()
        for row in rows:
            run = audit.get_run(str(row["run_id"]))
            if not run:
                continue
            status = str(run.get("status") or "")
            if status in TERMINAL_RUN_STATUSES:
                response = str(run.get("final_response") or "").strip()
                if not response:
                    response = f"Run finished with status: {status}."
                self.update_message(str(row["message_id"]), text=response, status=status)
            elif status:
                self.update_message(str(row["message_id"]), status=status)

    def _touch_conversation(self, connection: sqlite3.Connection, conversation_id: str, now: str, *, title_hint: str = "") -> None:
        title = _clean_title(title_hint)
        if title:
            current = connection.execute(
                "SELECT title FROM chat_conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            if current and str(current["title"]) == "New chat":
                connection.execute(
                    """
                    UPDATE chat_conversations
                    SET title = ?, updated_at = ?, last_message_at = ?
                    WHERE conversation_id = ?
                    """,
                    (title, now, now, conversation_id),
                )
                return
        connection.execute(
            "UPDATE chat_conversations SET updated_at = ?, last_message_at = ? WHERE conversation_id = ?",
            (now, now, conversation_id),
        )


def chat_db_path(data_dir: Path) -> Path:
    return data_dir / "desktop_chats.sqlite3"


def _conversation_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "conversation_id": row["conversation_id"],
        "title": row["title"],
        "source": row["source"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_message_at": row["last_message_at"],
        "message_count": int(row["message_count"]),
        "metadata": _loads(row["metadata"]),
    }


def _message_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "message_id": row["message_id"],
        "conversation_id": row["conversation_id"],
        "sequence": row["sequence"],
        "role": row["role"],
        "text": row["text"],
        "status": row["status"],
        "source": row["source"],
        "run_id": row["run_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "metadata": _loads(row["metadata"]),
    }


def _json(payload: dict[str, Any] | None) -> str:
    return json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)


def _loads(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _clean_role(role: str) -> str:
    normalized = str(role or "").strip().lower()
    if normalized in {"user", "assistant", "system", "error"}:
        return normalized
    return "system"


def _clean_title(value: str) -> str:
    title = " ".join(str(value or "").split())
    if not title:
        return ""
    return title[:80]
