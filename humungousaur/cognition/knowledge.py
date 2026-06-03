from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .models import KnowledgeKind, KnowledgeRecord, new_id, utc_now


class KnowledgeStore:
    """Semantic and procedural memory records.

    Records are appended or archived by exact IDs. Selection and interpretation
    remain model-led through tool schemas and planning context.
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
                CREATE TABLE IF NOT EXISTS cognitive_knowledge (
                    knowledge_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    text TEXT NOT NULL,
                    source TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    archived_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cognitive_knowledge_kind ON cognitive_knowledge(kind, archived_at)")
            connection.commit()

    def append(
        self,
        *,
        kind: KnowledgeKind | str,
        text: str,
        source: str = "manual",
        evidence_refs: list[str] | None = None,
        confidence: float = 0.5,
    ) -> KnowledgeRecord:
        record = KnowledgeRecord(
            knowledge_id=new_id("knowledge"),
            kind=_knowledge_kind(kind),
            text=_clean(text, limit=3_000),
            source=_clean(source, limit=120) or "manual",
            evidence_refs=_string_list(evidence_refs),
            confidence=max(0.0, min(float(confidence), 1.0)),
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO cognitive_knowledge
                (knowledge_id, kind, text, source, evidence_refs, confidence, archived_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.knowledge_id,
                    record.kind.value,
                    record.text,
                    record.source,
                    json.dumps(record.evidence_refs, ensure_ascii=False, sort_keys=True),
                    record.confidence,
                    record.archived_at,
                    record.created_at,
                    record.updated_at,
                ),
            )
            connection.commit()
        return record

    def list(self, limit: int = 20, include_archived: bool = False) -> list[KnowledgeRecord]:
        where = "" if include_archived else "WHERE archived_at = ''"
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT knowledge_id, kind, text, source, evidence_refs, confidence, archived_at, created_at, updated_at
                FROM cognitive_knowledge
                {where}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def archive(self, knowledge_id: str, reason: str = "") -> KnowledgeRecord | None:
        now = utc_now()
        record = self.get(knowledge_id, include_archived=True)
        if record is None:
            return None
        evidence_refs = list(record.evidence_refs)
        if reason:
            evidence_refs.append(f"forget_reason:{_clean(reason, limit=300)}")
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE cognitive_knowledge
                SET evidence_refs = ?, archived_at = ?, updated_at = ?
                WHERE knowledge_id = ?
                """,
                (json.dumps(evidence_refs, ensure_ascii=False, sort_keys=True), now, now, knowledge_id),
            )
            connection.commit()
        return self.get(knowledge_id, include_archived=True)

    def get(self, knowledge_id: str, include_archived: bool = False) -> KnowledgeRecord | None:
        archived_clause = "" if include_archived else "AND archived_at = ''"
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                f"""
                SELECT knowledge_id, kind, text, source, evidence_refs, confidence, archived_at, created_at, updated_at
                FROM cognitive_knowledge
                WHERE knowledge_id = ? {archived_clause}
                """,
                (knowledge_id,),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def _row_to_record(self, row: sqlite3.Row) -> KnowledgeRecord:
        return KnowledgeRecord(
            knowledge_id=row["knowledge_id"],
            kind=_knowledge_kind(row["kind"]),
            text=row["text"],
            source=row["source"],
            evidence_refs=json.loads(row["evidence_refs"]),
            confidence=float(row["confidence"]),
            archived_at=row["archived_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


def _knowledge_kind(value: KnowledgeKind | str) -> KnowledgeKind:
    try:
        return value if isinstance(value, KnowledgeKind) else KnowledgeKind(str(value or KnowledgeKind.CONTEXT.value))
    except ValueError:
        return KnowledgeKind.CONTEXT


def _clean(value: object, *, limit: int) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean(item, limit=500) for item in value if _clean(item, limit=500)]
