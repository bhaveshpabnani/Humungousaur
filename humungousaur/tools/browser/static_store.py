from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

class BrowserSessionStore:
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
                CREATE TABLE IF NOT EXISTS browser_sessions (
                    session_id TEXT PRIMARY KEY,
                    current_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    text TEXT NOT NULL,
                    links_json TEXT NOT NULL,
                    images_json TEXT NOT NULL DEFAULT '[]',
                    forms_json TEXT NOT NULL DEFAULT '[]',
                    form_drafts_json TEXT NOT NULL DEFAULT '{}',
                    history_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(browser_sessions)").fetchall()}
            if "forms_json" not in columns:
                connection.execute("ALTER TABLE browser_sessions ADD COLUMN forms_json TEXT NOT NULL DEFAULT '[]'")
            if "images_json" not in columns:
                connection.execute("ALTER TABLE browser_sessions ADD COLUMN images_json TEXT NOT NULL DEFAULT '[]'")
            if "form_drafts_json" not in columns:
                connection.execute("ALTER TABLE browser_sessions ADD COLUMN form_drafts_json TEXT NOT NULL DEFAULT '{}'")
            if "history_json" not in columns:
                connection.execute("ALTER TABLE browser_sessions ADD COLUMN history_json TEXT NOT NULL DEFAULT '[]'")
            connection.commit()

    def create_or_update(
        self,
        page: dict[str, Any],
        session_id: str | None = None,
        history: list[str] | None = None,
    ) -> dict[str, Any]:
        import json

        now = datetime.now(timezone.utc).isoformat()
        resolved_session_id = session_id or str(uuid.uuid4())
        with closing(self._connect()) as connection:
            existing = connection.execute(
                "SELECT created_at, current_url, history_json FROM browser_sessions WHERE session_id = ?",
                (resolved_session_id,),
            ).fetchone()
            created_at = existing[0] if existing else now
            if history is None:
                history_items = json.loads(existing[2]) if existing and existing[2] else []
                if not history_items and existing:
                    history_items = [existing[1]]
                if not history_items or history_items[-1] != page["url"]:
                    history_items.append(page["url"])
            else:
                history_items = history or [page["url"]]
            connection.execute(
                """
                INSERT OR REPLACE INTO browser_sessions (
                    session_id, current_url, title, text, links_json, images_json, forms_json, form_drafts_json,
                    history_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_session_id,
                    page["url"],
                    page["title"],
                    page["text"],
                    json.dumps(page["links"]),
                    json.dumps(page.get("images", [])),
                    json.dumps(page.get("forms", [])),
                    "{}",
                    json.dumps(history_items),
                    created_at,
                    now,
                ),
            )
            connection.commit()
        return self.get(resolved_session_id)

    def get(self, session_id: str) -> dict[str, Any]:
        import json

        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM browser_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Browser session does not exist: {session_id}")
        return {
            "session_id": row["session_id"],
            "current_url": row["current_url"],
            "title": row["title"],
            "text": row["text"],
            "links": json.loads(row["links_json"]),
            "images": json.loads(row["images_json"]),
            "forms": json.loads(row["forms_json"]),
            "form_drafts": json.loads(row["form_drafts_json"]),
            "history": json.loads(row["history_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list(self, limit: int = 20) -> list[dict[str, Any]]:
        import json

        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT session_id, current_url, title, text, links_json, images_json, forms_json,
                       form_drafts_json, history_json, created_at, updated_at
                FROM browser_sessions
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "session_id": row["session_id"],
                "current_url": row["current_url"],
                "title": row["title"],
                "text": row["text"],
                "links": json.loads(row["links_json"]),
                "images": json.loads(row["images_json"]),
                "forms": json.loads(row["forms_json"]),
                "form_drafts": json.loads(row["form_drafts_json"]),
                "history": json.loads(row["history_json"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def update_form_draft(self, session_id: str, form_index: int, values: dict[str, str]) -> dict[str, Any]:
        import json

        session = self.get(session_id)
        forms = session["forms"]
        if form_index < 0 or form_index >= len(forms):
            raise IndexError("Form index is out of range.")
        allowed_fields = {field["name"] for field in forms[form_index].get("inputs", [])}
        unknown_fields = sorted(set(values) - allowed_fields)
        if unknown_fields:
            raise ValueError(f"Unknown form fields: {', '.join(unknown_fields)}")
        drafts = session["form_drafts"]
        drafts[str(form_index)] = {key: str(value) for key, value in values.items()}
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE browser_sessions
                SET form_drafts_json = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (json.dumps(drafts, ensure_ascii=False, sort_keys=True), now, session_id),
            )
            connection.commit()
        return self.get(session_id)

    def update_form_field_draft(
        self,
        session_id: str,
        form_index: int,
        field_name: str,
        value: str,
    ) -> dict[str, Any]:
        session = self.get(session_id)
        forms = session["forms"]
        if form_index < 0 or form_index >= len(forms):
            raise IndexError("Form index is out of range.")
        allowed_fields = {field["name"] for field in forms[form_index].get("inputs", [])}
        if field_name not in allowed_fields:
            raise ValueError(f"Unknown form field: {field_name}")
        draft = dict(session.get("form_drafts", {}).get(str(form_index), {}))
        draft[field_name] = value
        return self.update_form_draft(session_id, form_index, draft)

    def delete(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM browser_sessions WHERE session_id = ?",
                (session_id,),
            )
            connection.commit()
        if cursor.rowcount != 1:
            raise KeyError(f"Browser session does not exist: {session_id}")
        return session
