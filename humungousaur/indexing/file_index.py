from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.tools.file_tools import _is_within, _iter_allowed_text_files, _relative


SCHEMA_VERSION = 1


class FileIndex:
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
                CREATE TABLE IF NOT EXISTS index_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS indexed_files (
                    path TEXT PRIMARY KEY,
                    display_path TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    mtime_ns INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS indexed_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL,
                    line_number INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    FOREIGN KEY(path) REFERENCES indexed_files(path) ON DELETE CASCADE
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_indexed_lines_text ON indexed_lines(text)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_indexed_lines_path ON indexed_lines(path)")
            connection.commit()

    def rebuild(self, config: AgentConfig) -> dict[str, Any]:
        normalized = config.normalized()
        files = _iter_allowed_text_files(normalized)
        line_count = 0
        started = datetime.now(timezone.utc)
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM indexed_lines")
            connection.execute("DELETE FROM indexed_files")
            connection.execute("DELETE FROM index_meta")
            for path in files:
                stat = path.stat()
                connection.execute(
                    """
                    INSERT INTO indexed_files (path, display_path, size, mtime_ns)
                    VALUES (?, ?, ?, ?)
                    """,
                    (str(path), _relative(path, normalized), stat.st_size, stat.st_mtime_ns),
                )
                for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
                    connection.execute(
                        """
                        INSERT INTO indexed_lines (path, line_number, text)
                        VALUES (?, ?, ?)
                        """,
                        (str(path), line_number, line.strip()),
                    )
                    line_count += 1
            self._set_meta(connection, "schema_version", str(SCHEMA_VERSION))
            self._set_meta(connection, "indexed_at", started.isoformat())
            self._set_meta(connection, "allowed_read_roots", "\n".join(str(path) for path in normalized.allowed_read_roots))
            connection.commit()
        status = self.status(normalized)
        status["indexed_lines"] = line_count
        return status

    def search(self, query: str, config: AgentConfig, limit: int | None = None) -> list[dict[str, Any]]:
        normalized = config.normalized()
        if not self.is_usable_for(normalized):
            return []
        needle = query.strip().lower()
        if not needle:
            return []
        maximum = limit or normalized.max_search_results
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT indexed_files.path, indexed_files.display_path, indexed_lines.line_number, indexed_lines.text
                FROM indexed_lines
                JOIN indexed_files ON indexed_files.path = indexed_lines.path
                WHERE lower(indexed_lines.text) LIKE ?
                ORDER BY indexed_files.display_path ASC, indexed_lines.line_number ASC
                LIMIT ?
                """,
                (f"%{needle}%", maximum),
            ).fetchall()
        matches: list[dict[str, Any]] = []
        for row in rows:
            path = Path(row["path"])
            if not _is_within(path, normalized.allowed_read_roots):
                continue
            matches.append(
                {
                    "path": row["display_path"],
                    "line": row["line_number"],
                    "text": row["text"],
                    "source": "index",
                }
            )
        return matches

    def is_usable_for(self, config: AgentConfig) -> bool:
        return bool(self.status(config)["usable"])

    def status(self, config: AgentConfig) -> dict[str, Any]:
        normalized = config.normalized()
        with closing(self._connect()) as connection:
            meta = dict(connection.execute("SELECT key, value FROM index_meta").fetchall())
            file_count = connection.execute("SELECT COUNT(*) FROM indexed_files").fetchone()[0]
            line_count = connection.execute("SELECT COUNT(*) FROM indexed_lines").fetchone()[0]
            indexed_files = {
                row[0]: {"size": row[1], "mtime_ns": row[2]}
                for row in connection.execute("SELECT path, size, mtime_ns FROM indexed_files").fetchall()
            }
        roots = meta.get("allowed_read_roots", "")
        schema_version = int(meta.get("schema_version", "0") or "0")
        indexed_roots = roots.splitlines() if roots else []
        current_roots = [str(path) for path in normalized.allowed_read_roots]
        scope_matches = indexed_roots == current_roots and schema_version == SCHEMA_VERSION
        drift = self._drift(normalized, indexed_files) if scope_matches else {"stale": False, "stale_reasons": []}
        return {
            "path": str(self.path),
            "schema_version": schema_version,
            "indexed_at": meta.get("indexed_at"),
            "indexed_files": file_count,
            "indexed_lines": line_count,
            "allowed_read_roots": indexed_roots,
            "current_read_roots": current_roots,
            "scope_matches": scope_matches,
            "stale": drift["stale"],
            "stale_reasons": drift["stale_reasons"],
            "usable": scope_matches and not drift["stale"],
        }

    def _set_meta(self, connection: sqlite3.Connection, key: str, value: str) -> None:
        connection.execute(
            """
            INSERT OR REPLACE INTO index_meta (key, value)
            VALUES (?, ?)
            """,
            (key, value),
        )

    def _drift(self, config: AgentConfig, indexed_files: dict[str, dict[str, int]]) -> dict[str, Any]:
        current_files: dict[str, dict[str, int]] = {}
        for path in _iter_allowed_text_files(config):
            try:
                stat = path.stat()
            except OSError:
                continue
            current_files[str(path)] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}

        indexed_paths = set(indexed_files)
        current_paths = set(current_files)
        missing = sorted(indexed_paths - current_paths)
        added = sorted(current_paths - indexed_paths)
        changed = sorted(
            path
            for path in indexed_paths & current_paths
            if indexed_files[path]["size"] != current_files[path]["size"]
            or indexed_files[path]["mtime_ns"] != current_files[path]["mtime_ns"]
        )
        stale_reasons: list[str] = []
        if missing:
            stale_reasons.append(f"missing_files:{len(missing)}")
        if added:
            stale_reasons.append(f"new_files:{len(added)}")
        if changed:
            stale_reasons.append(f"changed_files:{len(changed)}")
        return {"stale": bool(stale_reasons), "stale_reasons": stale_reasons}
