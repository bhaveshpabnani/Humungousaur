from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from humungousaur.janus.store import JanusStore
from humungousaur.config import AgentConfig
from humungousaur.tools.activity.implementation import ActivityPolicyStore, _activity_policy_match, activity_policy_path

from .definitions import DEFAULT_COLLECTOR_RATE_LIMITS_PER_MINUTE, DEFAULT_COLLECTORS, DEFAULT_RICH_CAPTURE_OPT_IN
from .envelope import CollectorEventEnvelope
from .event_log import CollectorEventLog
from .models import CollectorProfile
from .policies import (
    activity_payload,
    rate_limit_reason,
    remember_rate_limit_event,
    remember_signature,
    signature_seen,
)


source_ingestion_consumer_name = "source_ingestion_gate"


@dataclass(frozen=True, slots=True)
class SourceIngestionDecision:
    accepted: bool
    reason: str = ""
    appended: dict[str, Any] | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            **(self.appended or {}),
        }


def append_source_envelope(config: AgentConfig, envelope: CollectorEventEnvelope) -> SourceIngestionDecision:
    """Apply local collector gates before a direct app/SaaS/browser source event is stored."""

    normalized = config.normalized()
    event_log = CollectorEventLog(normalized.collector_events_db_path)
    profile = _load_source_profile(normalized)
    gate_reason = _profile_gate_reason(profile, envelope)
    if gate_reason is not None:
        return SourceIngestionDecision(False, gate_reason)

    state = event_log.consumer_state(source_ingestion_consumer_name)
    state.setdefault("signatures", {})
    state.setdefault("rate_limits", {})
    event = envelope.to_collector_event()
    signature = event.stable_signature()
    collector_signatures = state["signatures"].setdefault(event.collector, {})
    if signature_seen(collector_signatures, event.stimulus_type, signature):
        return SourceIngestionDecision(False, "duplicate")

    rate_reason = rate_limit_reason(state, profile, event, force=False)
    if rate_reason is not None:
        return SourceIngestionDecision(False, rate_reason)

    policy = ActivityPolicyStore(activity_policy_path(normalized)).load()
    policy_match = _activity_policy_match(activity_payload(event), policy)
    if policy_match is not None:
        return SourceIngestionDecision(False, policy_match)

    muted_scope = JanusStore(normalized.janus_db_path).active_muted_scope_for(envelope.to_record())
    if muted_scope is not None and muted_scope.do_not_store:
        return SourceIngestionDecision(False, "Janus muted scope blocked storage")

    appended = event_log.append(envelope)
    remember_signature(collector_signatures, event.stimulus_type, signature)
    remember_rate_limit_event(state, event)
    event_log.save_consumer_state(source_ingestion_consumer_name, state)
    return SourceIngestionDecision(True, appended=appended)


def _profile_gate_reason(profile: CollectorProfile, envelope: CollectorEventEnvelope) -> str | None:
    if not profile.enabled:
        return "collector profile disabled"
    if not bool(profile.collectors.get(envelope.collector, False)):
        return f"collector disabled: {envelope.collector}"
    if envelope.privacy_tier == "rich_capture" and not bool(profile.rich_capture_opt_in.get(envelope.collector, False)):
        return f"rich capture collector is not opted in: {envelope.collector}"
    return None


def _load_source_profile(config: AgentConfig) -> CollectorProfile:
    path = _collector_profile_path(config)
    if not path.exists():
        return _first_run_source_profile()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return CollectorProfile()
    if not isinstance(payload, dict):
        return CollectorProfile()
    return _profile_from_payload(payload)


def _collector_profile_path(config: AgentConfig) -> Path:
    return config.normalized().data_dir / "collectors_profile.json"


def _profile_from_payload(payload: dict[str, Any]) -> CollectorProfile:
    collectors = dict(DEFAULT_COLLECTORS)
    raw_collectors = payload.get("collectors", {})
    if isinstance(raw_collectors, dict):
        for name, enabled in raw_collectors.items():
            if name in collectors:
                collectors[name] = bool(enabled)

    rich_capture_opt_in = dict(DEFAULT_RICH_CAPTURE_OPT_IN)
    raw_rich = payload.get("rich_capture_opt_in", {})
    if isinstance(raw_rich, dict):
        for name, enabled in raw_rich.items():
            if name in rich_capture_opt_in:
                rich_capture_opt_in[name] = bool(enabled)

    collector_rate_limits = dict(DEFAULT_COLLECTOR_RATE_LIMITS_PER_MINUTE)
    raw_limits = payload.get("collector_rate_limits_per_minute", {})
    if isinstance(raw_limits, dict):
        for name, limit in raw_limits.items():
            if name in collector_rate_limits:
                collector_rate_limits[name] = max(0, min(int(limit or 0), 600))

    return CollectorProfile(
        enabled=bool(payload.get("enabled", False)),
        collectors=collectors,
        rich_capture_opt_in=rich_capture_opt_in,
        collector_rate_limits_per_minute=collector_rate_limits,
    )


def _first_run_source_profile() -> CollectorProfile:
    return CollectorProfile(
        enabled=True,
        collectors={name: True for name in DEFAULT_COLLECTORS},
        rich_capture_opt_in=dict(DEFAULT_RICH_CAPTURE_OPT_IN),
        collector_rate_limits_per_minute=dict(DEFAULT_COLLECTOR_RATE_LIMITS_PER_MINUTE),
    )
