from __future__ import annotations

import time
from typing import Any

from ..models import CollectorEvent, CollectorProfile


def dwell_filter_reason(
    state: dict[str, Any],
    profile: CollectorProfile,
    event: CollectorEvent,
    signature: str,
    *,
    force: bool,
) -> str | None:
    if force or event.collector not in {"active_window", "browser"}:
        return None
    now = time.time()
    candidates = state.setdefault("dwell_candidates", {})
    key = f"{event.collector}:{event.stimulus_type}"
    candidate = candidates.get(key)
    if not isinstance(candidate, dict) or candidate.get("signature") != signature:
        candidates[key] = {"signature": signature, "first_seen_at": now, "last_seen_at": now}
        return f"dwell pending for {profile.dwell_seconds:g}s"
    candidate["last_seen_at"] = now
    first_seen = float(candidate.get("first_seen_at", now) or now)
    if now - first_seen < profile.dwell_seconds:
        return f"dwell pending for {profile.dwell_seconds:g}s"
    candidates.pop(key, None)
    return None
