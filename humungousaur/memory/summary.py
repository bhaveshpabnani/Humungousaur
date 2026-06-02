from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from humungousaur.memory.event_store import EventStore

SUMMARY_PERIODS = {"today", "yesterday", "week", "recent"}
SUMMARY_LIMIT = 200
HIGHLIGHT_LIMIT = 12


def summarize_memory(
    store: EventStore,
    period: str = "today",
    query: str = "",
    limit: int = SUMMARY_LIMIT,
    now: datetime | None = None,
    event_filter: Any | None = None,
) -> dict[str, Any]:
    normalized_period = _normalize_period(period)
    start_at, end_at = memory_period_bounds(normalized_period, now=now)
    events = store.between(start_at=start_at, end_at=end_at, limit=limit, ascending=True)
    if event_filter is not None:
        events = [event for event in events if event_filter(event)]
    if query.strip():
        events = _filter_events(events, query)
    counts = Counter(str(event.get("event_type", "unknown")) for event in events)
    highlights = [_event_highlight(event) for event in events[-HIGHLIGHT_LIMIT:]]
    agent_runs = [_agent_run_summary(event) for event in events if event.get("event_type") == "agent_run"]
    preferences = [
        _memory_text(event)
        for event in events
        if event.get("event_type") == "user_memory"
        and str(event.get("payload", {}).get("kind", "")).lower() in {"preference", "workflow", "user_note"}
    ]
    payload = {
        "period": normalized_period,
        "query": query.strip(),
        "since": start_at.astimezone(timezone.utc).isoformat() if start_at else None,
        "until": end_at.astimezone(timezone.utc).isoformat() if end_at else None,
        "total_events": len(events),
        "event_counts": dict(sorted(counts.items())),
        "highlights": highlights,
        "agent_runs": agent_runs[-HIGHLIGHT_LIMIT:],
        "preferences": [item for item in preferences[-HIGHLIGHT_LIMIT:] if item],
    }
    payload["summary"] = _summary_text(payload)
    return payload


def memory_period_bounds(period: str, now: datetime | None = None) -> tuple[datetime | None, datetime | None]:
    local_now = now.astimezone() if now else datetime.now().astimezone()
    today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "today":
        return today, today + timedelta(days=1)
    if period == "yesterday":
        start = today - timedelta(days=1)
        return start, today
    if period == "week":
        return local_now - timedelta(days=7), local_now + timedelta(seconds=1)
    return None, None


def _normalize_period(period: str) -> str:
    normalized = period.strip().lower() or "today"
    if normalized in {"daily", "day"}:
        return "today"
    if normalized in {"weekly", "last_week", "last-week", "7d"}:
        return "week"
    if normalized not in SUMMARY_PERIODS:
        return "recent"
    return normalized


def _filter_events(events: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    needle = query.strip().lower()
    return [event for event in events if needle in _event_search_text(event).lower()]


def _event_search_text(event: dict[str, Any]) -> str:
    return f"{event.get('event_type', '')} {json.dumps(event.get('payload', {}), ensure_ascii=False, sort_keys=True)}"


def _event_highlight(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "created_at": event.get("created_at"),
        "event_type": event.get("event_type"),
        "text": _memory_text(event),
    }


def _agent_run_summary(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload", {})
    return {
        "created_at": event.get("created_at"),
        "request": _redact_secrets(str(payload.get("request", "")))[:500],
        "status": payload.get("status", "unknown"),
        "approvals_requested": payload.get("approvals_requested", 0),
        "note_path": payload.get("note_path"),
    }


def _memory_text(event: dict[str, Any]) -> str:
    payload = event.get("payload", {})
    if event.get("event_type") == "agent_run":
        request = _redact_secrets(str(payload.get("request", ""))).strip()
        status = str(payload.get("status", "unknown"))
        approvals = payload.get("approvals_requested", 0)
        return f"Agent run: {request} [{status}, approvals: {approvals}]".strip()
    if event.get("event_type") == "user_memory":
        kind = str(payload.get("kind", "note"))
        text = _redact_secrets(str(payload.get("text", ""))).strip()
        return f"{kind}: {text}".strip()
    text = payload.get("text") or payload.get("summary") or payload.get("request")
    if text:
        return _redact_secrets(str(text)).strip()[:700]
    return _redact_secrets(json.dumps(payload, ensure_ascii=False, sort_keys=True))[:700]


def _redact_secrets(text: str) -> str:
    redacted = re.sub(r"sk-[A-Za-z0-9_*\-.]+", "sk-REDACTED", text)
    return re.sub(r"Bearer\s+[A-Za-z0-9_*\-.]+", "Bearer REDACTED", redacted, flags=re.IGNORECASE)


def _summary_text(payload: dict[str, Any]) -> str:
    period = payload["period"]
    total = payload["total_events"]
    query = payload.get("query")
    heading = f"Memory recap for {period}"
    if query:
        heading += f" matching '{query}'"
    lines = [f"{heading}: {total} event(s)."]
    counts = payload.get("event_counts", {})
    if counts:
        count_text = ", ".join(f"{name}: {count}" for name, count in counts.items())
        lines.append(f"Event mix: {count_text}.")
    runs = payload.get("agent_runs", [])
    if runs:
        lines.append("Recent work:")
        for run in runs[-5:]:
            lines.append(f"- {run['request']} [{run['status']}]")
    preferences = payload.get("preferences", [])
    if preferences:
        lines.append("Useful remembered context:")
        for preference in preferences[-5:]:
            lines.append(f"- {preference}")
    if not counts:
        lines.append("No matching local memory events were found.")
    return "\n".join(lines)
