from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from humungousaur.memory.event_store import EventStore


PROFILE_LIMIT = 200
PROFILE_SECTIONS = {
    "preference": "preferences",
    "preferences": "preferences",
    "fact": "facts",
    "facts": "facts",
    "workflow": "workflows",
    "workflows": "workflows",
    "task_note": "task_notes",
    "task-notes": "task_notes",
    "user_note": "notes",
    "note": "notes",
}


def build_user_profile(store: EventStore, limit: int = PROFILE_LIMIT) -> dict[str, Any]:
    events = [
        event
        for event in store.between(limit=limit, ascending=True)
        if event.get("event_type") == "user_memory"
    ]
    sections: dict[str, list[dict[str, Any]]] = {
        "preferences": [],
        "facts": [],
        "workflows": [],
        "task_notes": [],
        "notes": [],
    }
    kind_counts: Counter[str] = Counter()
    for event in events:
        payload = event.get("payload", {})
        kind = str(payload.get("kind", "note")).strip().lower() or "note"
        section = PROFILE_SECTIONS.get(kind, "notes")
        text = _redact_secrets(str(payload.get("text", ""))).strip()
        if not text:
            continue
        kind_counts[kind] += 1
        sections[section].append(
            {
                "text": text[:1_000],
                "kind": kind,
                "created_at": event.get("created_at"),
                "source_event_id": event.get("event_id"),
            }
        )
    return {
        "total_memories": sum(len(items) for items in sections.values()),
        "kind_counts": dict(sorted(kind_counts.items())),
        **sections,
        "summary": _profile_summary(sections),
    }


def compact_user_profile(profile: dict[str, Any], per_section: int = 5) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "total_memories": profile.get("total_memories", 0),
        "kind_counts": profile.get("kind_counts", {}),
    }
    for section in ("preferences", "facts", "workflows", "task_notes", "notes"):
        compact[section] = [
            {"text": item.get("text", ""), "kind": item.get("kind", "")}
            for item in profile.get(section, [])[-per_section:]
        ]
    return compact


def _profile_summary(sections: dict[str, list[dict[str, Any]]]) -> str:
    total = sum(len(items) for items in sections.values())
    lines = [f"User profile: {total} explicit remembered item(s)."]
    for section, label in (
        ("preferences", "Preferences"),
        ("facts", "Facts"),
        ("workflows", "Workflows"),
        ("task_notes", "Task notes"),
        ("notes", "Notes"),
    ):
        items = sections[section]
        if not items:
            continue
        lines.append(f"{label}:")
        for item in items[-5:]:
            lines.append(f"- {item['text']}")
    if total == 0:
        lines.append("No explicit user profile memories have been saved yet.")
    return "\n".join(lines)


def _redact_secrets(text: str) -> str:
    redacted = re.sub(r"sk-[A-Za-z0-9_*\-.]+", "sk-REDACTED", text)
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9_*\-.]+", "Bearer REDACTED", redacted, flags=re.IGNORECASE)
    return _redact_key_value_shapes(redacted)


def _redact_key_value_shapes(text: str) -> str:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text
    if not isinstance(payload, dict):
        return text
    safe_payload = {
        key: ("REDACTED" if any(marker in key.lower() for marker in ("key", "token", "secret", "password")) else value)
        for key, value in payload.items()
    }
    return json.dumps(safe_payload, ensure_ascii=False, sort_keys=True)
