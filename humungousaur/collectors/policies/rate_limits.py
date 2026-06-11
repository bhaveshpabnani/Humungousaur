from __future__ import annotations

import time
from typing import Any

from ..models import CollectorEvent, CollectorProfile


def rate_limit_reason(state: dict[str, Any], profile: CollectorProfile, event: CollectorEvent, *, force: bool) -> str | None:
    if force:
        return None
    limit = int(profile.collector_rate_limits_per_minute.get(event.collector, 0) or 0)
    if limit <= 0:
        return "collector minute budget disabled"
    now = time.time()
    timestamps = recent_rate_limit_timestamps(state, event.collector, now=now)
    if len(timestamps) >= limit:
        return f"collector minute budget exceeded ({limit}/min)"
    return None


def remember_rate_limit_event(state: dict[str, Any], event: CollectorEvent) -> None:
    now = time.time()
    timestamps = recent_rate_limit_timestamps(state, event.collector, now=now)
    timestamps.append(now)
    state.setdefault("rate_limits", {})[event.collector] = timestamps[-600:]


def recent_rate_limit_timestamps(state: dict[str, Any], collector: str, *, now: float) -> list[float]:
    raw = state.setdefault("rate_limits", {}).get(collector, [])
    if not isinstance(raw, list):
        raw = []
    return [float(item) for item in raw if isinstance(item, (int, float)) and now - float(item) < 60.0]
