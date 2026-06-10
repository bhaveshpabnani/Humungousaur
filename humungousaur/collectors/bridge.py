from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig

from .models import CollectorEvent, utc_now


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
    offsets[collector] = len(lines)
    events: list[CollectorEvent] = []
    for line in lines[offset:]:
        if len(events) >= max_events:
            break
        parsed = _parse_bridge_line(line, collector, allowed_stimulus_types, source=source)
        if parsed is not None:
            events.append(parsed)
    return events


def collector_spool_path(config: AgentConfig, collector: str) -> Path:
    return config.normalized().data_dir / "collector_spool" / f"{collector}.jsonl"


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
