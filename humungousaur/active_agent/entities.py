from __future__ import annotations

import hashlib
from typing import Any


HASH_KEYS = {
    "account_id",
    "app_bundle",
    "board_id",
    "calendar_id",
    "channel_id",
    "chat_id",
    "conversation_id",
    "customer_id",
    "dashboard_id",
    "database_id",
    "deck_id",
    "display_id",
    "document_id",
    "drive_id",
    "file_id",
    "folder_id",
    "form_id",
    "issue_id",
    "meeting_id",
    "message_id",
    "notebook_id",
    "object_id",
    "page_id",
    "pr_id",
    "project_id",
    "repo_id",
    "session_id",
    "sheet_id",
    "space_id",
    "task_id",
    "thread_id",
    "ticket_id",
    "url_host",
    "workspace_id",
}

SAFE_REF_PREFIXES = (
    "app_hash:",
    "document_id_hash:",
    "entity_hash:",
    "file_hash:",
    "folder_hash:",
    "object_id_hash:",
    "repo_id_hash:",
    "thread_id_hash:",
    "url_hash:",
    "workspace_hash:",
)


def extract_entity_refs(event: dict[str, Any], *, limit: int = 20) -> list[str]:
    """Extract stable, LLM-safe entity refs from collector metadata.

    Raw values are not returned. Existing `*_hash` fields are preserved as refs;
    known non-content identifiers are hashed with their key namespace. Textual
    content fields, paths, URLs, titles, names, bodies, snippets, and labels are
    intentionally ignored unless a collector already supplied a hashed form.
    """

    refs: list[str] = []
    seen: set[str] = set()
    for section_name in ("metadata", "payload", "redaction"):
        section = event.get(section_name, {})
        if not isinstance(section, dict):
            continue
        for key, value in section.items():
            for ref in _refs_for_value(str(key), value):
                if ref in seen:
                    continue
                seen.add(ref)
                refs.append(ref)
                if len(refs) >= max(1, int(limit or 20)):
                    return refs
    collector = str(event.get("collector") or "").strip()
    source = str(event.get("source") or "").strip()
    if collector and source:
        ref = f"collector_source_hash:{_digest(f'{collector}:{source}')}"
        if ref not in seen:
            refs.append(ref)
    return refs[: max(1, int(limit or 20))]


def _refs_for_value(key: str, value: Any) -> list[str]:
    normalized_key = key.strip().lower()
    if value is None or value == "":
        return []
    if normalized_key.endswith("_hash") or normalized_key in {
        "object_id_hash",
        "document_id_hash",
        "thread_id_hash",
        "repo_id_hash",
    }:
        text = _safe_text(value)
        if not text:
            return []
        return [f"{normalized_key}:{text}"]
    if normalized_key in {"entity_ref", "ref"}:
        text = _safe_text(value)
        if text.startswith(SAFE_REF_PREFIXES) or "_hash:" in text:
            return [text]
        return []
    if normalized_key == "entity_refs" and isinstance(value, list):
        refs: list[str] = []
        for item in value:
            text = _safe_text(item)
            if text.startswith(SAFE_REF_PREFIXES) or "_hash:" in text:
                refs.append(text)
        return refs
    if normalized_key in HASH_KEYS:
        text = _safe_text(value)
        if not text:
            return []
        return [f"{normalized_key}_hash:{_digest(text)}"]
    if normalized_key.endswith("_id") and _looks_like_identifier(value):
        return [f"{normalized_key}_hash:{_digest(_safe_text(value))}"]
    if isinstance(value, dict):
        refs: list[str] = []
        for child_key, child_value in value.items():
            refs.extend(_refs_for_value(str(child_key), child_value))
        return refs
    return []


def _looks_like_identifier(value: Any) -> bool:
    text = _safe_text(value)
    if not text or len(text) > 160:
        return False
    if any(ch.isspace() for ch in text):
        return False
    return any(ch.isdigit() for ch in text) or any(ch in text for ch in ("_", "-", ":", "/"))


def _safe_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())[:240]


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:24]
