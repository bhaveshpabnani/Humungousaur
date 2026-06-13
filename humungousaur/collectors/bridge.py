from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig

from .definitions import DEFINITIONS_BY_NAME
from .models import CollectorEvent, utc_now


BRIDGE_TEXT_LIMIT = 2_000


def read_bridge_events(
    config: AgentConfig,
    state: dict[str, Any],
    collector: str,
    allowed_stimulus_types: set[str],
    *,
    source: str = "activity",
    max_events: int = 20,
) -> list[CollectorEvent]:
    """Read structured events emitted by a native helper or browser extension.

    Bridge files are append-only JSONL. The collector stores an offset in local
    collector state so raw events are not reread every tick.
    """

    path = collector_spool_path(config, collector)
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    offsets = state.setdefault("spool_offsets", {})
    offset = max(0, min(int(offsets.get(collector, 0) or 0), len(lines)))
    events: list[CollectorEvent] = []
    consumed = 0
    for line in lines[offset:]:
        if len(events) >= max_events:
            break
        consumed += 1
        parsed = _parse_bridge_line(line, collector, allowed_stimulus_types, source=source)
        if parsed is not None:
            events.append(parsed)
    offsets[collector] = offset + consumed
    return events


def collector_spool_path(config: AgentConfig, collector: str) -> Path:
    return config.normalized().data_dir / "collector_spool" / f"{collector}.jsonl"


def append_bridge_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and append one bridge event for a collector helper."""

    normalized = config.normalized()
    collector = str(payload.get("collector") or "").strip()
    definition = DEFINITIONS_BY_NAME.get(collector)
    if definition is None:
        raise ValueError(f"Unknown collector: {collector or '<empty>'}")
    if not definition.bridge_supported:
        raise ValueError(f"Collector does not support bridge ingestion: {collector}")
    stimulus_type = str(payload.get("stimulus_type") or "").strip()
    if stimulus_type not in definition.stimulus_types:
        raise ValueError(f"Unsupported stimulus_type for {collector}: {stimulus_type or '<empty>'}")
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    raw_payload = payload.get("payload", {})
    if not isinstance(raw_payload, dict):
        raw_payload = {}
    event_id = str(payload.get("event_id") or "").strip()
    if not event_id:
        event_id = f"{collector}-{hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode('utf-8')).hexdigest()[:12]}"
    occurred_at = str(payload.get("occurred_at") or "").strip() or utc_now()
    text = _clean_text(payload.get("text") or _default_bridge_text(stimulus_type))
    record = {
        "event_id": event_id,
        "stimulus_type": stimulus_type,
        "text": text,
        "occurred_at": occurred_at,
        "metadata": _json_safe(metadata),
        "payload": _json_safe(raw_payload),
    }
    path = collector_spool_path(normalized, collector)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    return {
        "accepted": True,
        "collector": collector,
        "stimulus_type": stimulus_type,
        "event_id": event_id,
        "spool_path": str(path),
        "occurred_at": occurred_at,
    }


def _parse_bridge_line(
    line: str,
    collector: str,
    allowed_stimulus_types: set[str],
    *,
    source: str,
) -> CollectorEvent | None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    stimulus_type = str(payload.get("stimulus_type") or "").strip()
    if stimulus_type not in allowed_stimulus_types:
        return None
    text = str(payload.get("text") or _default_bridge_text(stimulus_type)).strip()
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    raw_payload = payload.get("payload", {})
    if not isinstance(raw_payload, dict):
        raw_payload = {}
    event_id = str(payload.get("event_id") or "").strip()
    occurred_at = str(payload.get("occurred_at") or "").strip() or utc_now()
    return CollectorEvent(
        collector=collector,
        source=source,
        stimulus_type=stimulus_type,
        text=text,
        metadata={**metadata, "bridge_event": True, "platform": platform.system()},
        payload=raw_payload,
        occurred_at=occurred_at,
        signature=event_id or f"{collector}:{stimulus_type}:{hashlib.sha256(line.encode('utf-8')).hexdigest()}",
    )


def _default_bridge_text(stimulus_type: str) -> str:
    return stimulus_type.replace("_", " ").capitalize()


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())[:BRIDGE_TEXT_LIMIT]


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    return value
