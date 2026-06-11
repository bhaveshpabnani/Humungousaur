from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig

from .models import ConnectorClientConfig, ConnectorOAuthState, ConnectorTokenStatus, DEFAULT_REDIRECT_URI


class ConnectorStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @classmethod
    def for_config(cls, config: AgentConfig) -> "ConnectorStore":
        return cls(config.normalized().data_dir / "connectors" / "connectors.sqlite3")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _init_db(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS connector_clients (
                    provider_id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    client_secret_ref TEXT NOT NULL DEFAULT '',
                    redirect_uri TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS connector_tokens (
                    provider_id TEXT PRIMARY KEY,
                    access_token_ref TEXT NOT NULL DEFAULT '',
                    refresh_token_ref TEXT NOT NULL DEFAULT '',
                    bot_access_token_ref TEXT NOT NULL DEFAULT '',
                    token_type TEXT NOT NULL DEFAULT '',
                    scopes_json TEXT NOT NULL DEFAULT '[]',
                    connected_at TEXT NOT NULL DEFAULT '',
                    expires_at INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS connector_oauth_states (
                    state TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    code_verifier TEXT NOT NULL DEFAULT '',
                    redirect_uri TEXT NOT NULL,
                    scopes_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    created_at_epoch REAL NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS connector_operation_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    risk_level TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            connection.commit()

    def save_client(self, client: ConnectorClientConfig) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO connector_clients (
                    provider_id, client_id, client_secret_ref, redirect_uri, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(provider_id) DO UPDATE SET
                    client_id = excluded.client_id,
                    client_secret_ref = excluded.client_secret_ref,
                    redirect_uri = excluded.redirect_uri,
                    updated_at = excluded.updated_at
                """,
                (client.provider_id, client.client_id, client.client_secret_ref, client.redirect_uri, client.updated_at),
            )
            connection.commit()

    def get_client(self, provider_id: str) -> ConnectorClientConfig | None:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM connector_clients WHERE provider_id = ?",
                (str(provider_id),),
            ).fetchone()
        if row is None:
            return None
        return ConnectorClientConfig(
            provider_id=str(row["provider_id"]),
            client_id=str(row["client_id"]),
            client_secret_ref=str(row["client_secret_ref"] or ""),
            redirect_uri=str(row["redirect_uri"] or DEFAULT_REDIRECT_URI),
            updated_at=str(row["updated_at"] or ""),
        )

    def list_clients(self) -> dict[str, ConnectorClientConfig]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("SELECT * FROM connector_clients").fetchall()
        return {
            str(row["provider_id"]): ConnectorClientConfig(
                provider_id=str(row["provider_id"]),
                client_id=str(row["client_id"]),
                client_secret_ref=str(row["client_secret_ref"] or ""),
                redirect_uri=str(row["redirect_uri"] or DEFAULT_REDIRECT_URI),
                updated_at=str(row["updated_at"] or ""),
            )
            for row in rows
        }

    def delete_client(self, provider_id: str) -> ConnectorClientConfig | None:
        existing = self.get_client(provider_id)
        if existing is None:
            return None
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM connector_clients WHERE provider_id = ?", (str(provider_id),))
            connection.commit()
        return existing

    def save_state(self, state: ConnectorOAuthState) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO connector_oauth_states (
                    state, provider_id, code_verifier, redirect_uri, scopes_json, created_at, created_at_epoch
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(state) DO UPDATE SET
                    provider_id = excluded.provider_id,
                    code_verifier = excluded.code_verifier,
                    redirect_uri = excluded.redirect_uri,
                    scopes_json = excluded.scopes_json,
                    created_at = excluded.created_at,
                    created_at_epoch = excluded.created_at_epoch
                """,
                (
                    state.state,
                    state.provider_id,
                    state.code_verifier,
                    state.redirect_uri,
                    _json_dumps(list(state.scopes)),
                    state.created_at,
                    float(state.created_at_epoch),
                ),
            )
            connection.commit()

    def pop_state(self, state_value: str) -> ConnectorOAuthState | None:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM connector_oauth_states WHERE state = ?",
                (str(state_value),),
            ).fetchone()
            if row is not None:
                connection.execute("DELETE FROM connector_oauth_states WHERE state = ?", (str(state_value),))
                connection.commit()
        if row is None:
            return None
        return ConnectorOAuthState(
            state=str(row["state"]),
            provider_id=str(row["provider_id"]),
            code_verifier=str(row["code_verifier"] or ""),
            redirect_uri=str(row["redirect_uri"] or DEFAULT_REDIRECT_URI),
            scopes=tuple(str(item) for item in _json_loads(row["scopes_json"], [])),
            created_at=str(row["created_at"] or ""),
            created_at_epoch=float(row["created_at_epoch"] or 0),
        )

    def save_token(self, token: ConnectorTokenStatus, metadata: dict[str, Any] | None = None) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO connector_tokens (
                    provider_id, access_token_ref, refresh_token_ref, bot_access_token_ref,
                    token_type, scopes_json, connected_at, expires_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider_id) DO UPDATE SET
                    access_token_ref = excluded.access_token_ref,
                    refresh_token_ref = excluded.refresh_token_ref,
                    bot_access_token_ref = excluded.bot_access_token_ref,
                    token_type = excluded.token_type,
                    scopes_json = excluded.scopes_json,
                    connected_at = excluded.connected_at,
                    expires_at = excluded.expires_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    token.provider_id,
                    token.access_token_ref,
                    token.refresh_token_ref,
                    token.bot_access_token_ref,
                    token.token_type,
                    _json_dumps(list(token.scopes)),
                    token.connected_at,
                    int(token.expires_at or 0),
                    _json_dumps(metadata or {}),
                ),
            )
            connection.commit()

    def get_token(self, provider_id: str) -> ConnectorTokenStatus | None:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM connector_tokens WHERE provider_id = ?",
                (str(provider_id),),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_token(row)

    def list_tokens(self) -> dict[str, ConnectorTokenStatus]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("SELECT * FROM connector_tokens").fetchall()
        return {str(row["provider_id"]): self._row_to_token(row) for row in rows}

    def delete_token(self, provider_id: str) -> ConnectorTokenStatus | None:
        existing = self.get_token(provider_id)
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM connector_tokens WHERE provider_id = ?", (str(provider_id),))
            connection.commit()
        return existing

    def audit_operation(self, provider_id: str, operation: str, status: str, created_at: str, metadata: dict[str, Any] | None = None, risk_level: str = "") -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO connector_operation_audit (
                    provider_id, operation, risk_level, status, created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (provider_id, operation, risk_level, status, created_at, _json_dumps(metadata or {})),
            )
            connection.commit()

    def _row_to_token(self, row: sqlite3.Row) -> ConnectorTokenStatus:
        return ConnectorTokenStatus(
            provider_id=str(row["provider_id"]),
            connected=bool(row["access_token_ref"] or row["bot_access_token_ref"]),
            access_token_ref=str(row["access_token_ref"] or ""),
            refresh_token_ref=str(row["refresh_token_ref"] or ""),
            bot_access_token_ref=str(row["bot_access_token_ref"] or ""),
            token_type=str(row["token_type"] or ""),
            scopes=tuple(str(item) for item in _json_loads(row["scopes_json"], [])),
            connected_at=str(row["connected_at"] or ""),
            expires_at=int(row["expires_at"] or 0),
        )


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(value: Any, fallback: Any) -> Any:
    try:
        parsed = json.loads(str(value or ""))
    except json.JSONDecodeError:
        return fallback
    return parsed
