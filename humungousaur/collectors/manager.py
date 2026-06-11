from __future__ import annotations

from dataclasses import asdict
import importlib.util
import json
import shutil
import time
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.active_agent.store import ActiveAgentStore
from humungousaur.cognition.loop import AutonomousLoopRunner, autonomous_loop_result_to_dict
from humungousaur.memory.event_store import EventStore
from humungousaur.tools.activity.implementation import (
    ActivityPolicyStore,
    _activity_policy_match,
    activity_policy_path,
)

from .definitions import (
    DEFAULT_COLLECTOR_RATE_LIMITS_PER_MINUTE,
    DEFAULT_COLLECTORS,
    DEFAULT_RICH_CAPTURE_OPT_IN,
    SENSITIVE_COLLECTORS,
    collector_capability_records,
)
from .consumers import ActiveAgentConsumer, AttentionBatchConsumer, AutonomousTriggerConsumer, MemoryMirrorConsumer, SemanticEventConsumer, UIStreamConsumer
from .envelope import CollectorEventEnvelope
from .event_log import CollectorEventLog
from .adapters.file_activity_adapters import file_activity_source_status
from .manifests import collector_source_manifest_records
from .models import CollectorEvent, CollectorProfile, CollectorTickResult, utc_now as _utc_now
from .policies import (
    activity_payload as policy_activity_payload,
    dwell_filter_reason as policy_dwell_filter_reason,
    rate_limit_reason as policy_rate_limit_reason,
    remember_rate_limit_event as policy_remember_rate_limit_event,
    remember_signature as policy_remember_signature,
    sensitive_event_reason as policy_sensitive_event_reason,
    signature_seen as policy_signature_seen,
)
from .registry import collector_registry
from .sources.ai_assistants import ai_assistant_source_status
from .sources.browser import browser_source_status
from .sources.cloud_files import cloud_file_source_status
from .sources.communication import communication_source_status
from .sources.google_workspace import google_workspace_source_status
from .sources.knowledge_base import knowledge_base_source_status
from .sources.planning import planning_source_status_map




def collector_profile_path(config: AgentConfig) -> Path:
    return config.normalized().data_dir / "collectors_profile.json"


def collector_state_path(config: AgentConfig) -> Path:
    return config.normalized().data_dir / "collectors_state.json"


def load_collector_profile(config: AgentConfig) -> CollectorProfile:
    path = collector_profile_path(config)
    if not path.exists():
        return _profile_from_payload({})
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _profile_from_payload({})
    return _profile_from_payload(payload if isinstance(payload, dict) else {})


def save_collector_profile(config: AgentConfig, payload: dict[str, Any]) -> CollectorProfile:
    existing = load_collector_profile(config)
    merged = asdict(existing)
    for key, value in payload.items():
        if key == "collectors" and isinstance(value, dict):
            next_collectors = dict(merged.get("collectors", {}))
            for name, enabled in value.items():
                if name in DEFAULT_COLLECTORS:
                    next_collectors[name] = bool(enabled)
            merged["collectors"] = next_collectors
        elif key == "rich_capture_opt_in" and isinstance(value, dict):
            next_rich = dict(merged.get("rich_capture_opt_in", {}))
            for name, enabled in value.items():
                if name in SENSITIVE_COLLECTORS:
                    next_rich[name] = bool(enabled)
            merged["rich_capture_opt_in"] = next_rich
        elif key == "collector_rate_limits_per_minute" and isinstance(value, dict):
            next_limits = dict(merged.get("collector_rate_limits_per_minute", {}))
            for name, limit in value.items():
                if name in DEFAULT_COLLECTORS:
                    next_limits[name] = limit
            merged["collector_rate_limits_per_minute"] = next_limits
        elif key in merged:
            merged[key] = value
    profile = _profile_from_payload(merged)
    profile.updated_at = _utc_now()
    path = collector_profile_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(profile), indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return profile


def collector_status(config: AgentConfig, *, limit: int = 10) -> dict[str, Any]:
    normalized = config.normalized()
    profile = load_collector_profile(normalized)
    state = _load_state(normalized)
    collector_event_log = CollectorEventLog(normalized.collector_events_db_path)
    recent = [
        event
        for event in EventStore(normalized.memory_db_path).tail(limit=max(1, min(limit * 4, 100)))
        if event.get("event_type") == "collector_stimulus"
    ][: max(1, min(limit, 50))]
    return {
        "profile": asdict(profile),
        "profile_path": str(collector_profile_path(normalized)),
        "state_path": str(collector_state_path(normalized)),
        "state": state,
        "capabilities": collector_capabilities(normalized),
        "recent_events": recent,
        "event_log": collector_event_log.status(limit=limit),
    }


def query_collector_events(
    config: AgentConfig,
    *,
    limit: int = 100,
    collector: str | None = None,
    stimulus_type: str | None = None,
    since_sequence: int = 0,
) -> dict[str, Any]:
    normalized = config.normalized()
    event_log = CollectorEventLog(normalized.collector_events_db_path)
    return {
        "events": event_log.query(
            limit=limit,
            collector=collector,
            stimulus_type=stimulus_type,
            since_sequence=since_sequence,
        ),
        "event_log_path": str(normalized.collector_events_db_path),
    }


def record_collector_helper_health(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = config.normalized()
    helper_id = str(payload.get("helper_id") or "").strip()
    collector = str(payload.get("collector") or "").strip()
    platform_name = str(payload.get("platform") or "").strip()
    status = str(payload.get("status") or "").strip()
    if not helper_id:
        raise ValueError("helper_id is required")
    if collector not in DEFAULT_COLLECTORS:
        raise ValueError(f"unknown collector: {collector or '<empty>'}")
    if not platform_name:
        raise ValueError("platform is required")
    if status not in {"starting", "running", "degraded", "permission_denied", "stopped", "failed"}:
        raise ValueError(f"unsupported helper status: {status or '<empty>'}")
    event_log = CollectorEventLog(normalized.collector_events_db_path)
    event_log.record_helper_health(
        helper_id=helper_id,
        collector=collector,
        platform=platform_name,
        status=status,
        pid=_optional_int(payload.get("pid")),
        version=str(payload.get("version") or ""),
        permission_state=str(payload.get("permission_state") or ""),
        last_event_at=str(payload.get("last_event_at") or ""),
        restart_count=max(0, int(payload.get("restart_count") or 0)),
        message=str(payload.get("message") or ""),
        metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
    )
    return {"accepted": True, "helper_id": helper_id, "collector": collector, "status": status}


def run_collector_tick(
    config: AgentConfig,
    *,
    profile: CollectorProfile | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> CollectorTickResult:
    normalized = config.normalized()
    active = profile or load_collector_profile(normalized)
    started = time.monotonic()
    result = CollectorTickResult(profile=asdict(active), collected=[], submitted=[], skipped=[])
    if not active.enabled and not force:
        result.skipped.append({"collector": "all", "reason": "collector profile disabled"})
        return _finish_tick(result, started, normalized, save_state=False)

    state = _load_state(normalized)
    state.setdefault("signatures", {})
    state.setdefault("last_capture_at", {})
    state.setdefault("dwell_candidates", {})
    state.setdefault("rate_limits", {})
    state.setdefault("pending_attention_events", [])
    policy = ActivityPolicyStore(activity_policy_path(normalized)).load()
    collector_event_log = CollectorEventLog(normalized.collector_events_db_path)
    events: list[CollectorEvent] = []
    errors: list[dict[str, Any]] = []
    for name, enabled in active.collectors.items():
        if not enabled:
            continue
        collector = collector_registry.get(name)
        if collector is None:
            result.skipped.append({"collector": name, "reason": "unknown collector"})
            continue
        try:
            events.extend(collector(normalized, active, state))
        except Exception as exc:
            errors.append({"collector": name, "error": str(exc), "error_type": type(exc).__name__})
    if errors:
        state["last_errors"] = errors[-10:]

    submitted_count = 0
    for event in events:
        if submitted_count >= active.max_events_per_tick:
            result.skipped.append({"collector": event.collector, "reason": "max_events_per_tick reached"})
            continue
        event_payload = _event_payload(event)
        signature = event.stable_signature()
        sensitivity_reason = policy_sensitive_event_reason(active, event)
        if sensitivity_reason is not None:
            result.skipped.append({"collector": event.collector, "stimulus_type": event.stimulus_type, "reason": sensitivity_reason})
            continue
        collector_signatures = state["signatures"].setdefault(event.collector, {})
        if policy_signature_seen(collector_signatures, event.stimulus_type, signature):
            result.skipped.append({"collector": event.collector, "stimulus_type": event.stimulus_type, "reason": "duplicate"})
            continue
        dwell_reason = policy_dwell_filter_reason(state, active, event, signature, force=force)
        if dwell_reason is not None:
            result.skipped.append({"collector": event.collector, "stimulus_type": event.stimulus_type, "reason": dwell_reason})
            continue
        rate_reason = policy_rate_limit_reason(state, active, event, force=force)
        if rate_reason is not None:
            result.skipped.append({"collector": event.collector, "stimulus_type": event.stimulus_type, "reason": rate_reason})
            continue
        policy_payload = policy_activity_payload(event)
        policy_match = _activity_policy_match(policy_payload, policy)
        if policy_match is not None:
            result.skipped.append({"collector": event.collector, "stimulus_type": event.stimulus_type, "reason": policy_match})
            continue
        muted_scope = ActiveAgentStore(normalized.active_agent_db_path).active_muted_scope_for(event_payload)
        if muted_scope is not None and muted_scope.do_not_store:
            result.skipped.append({"collector": event.collector, "stimulus_type": event.stimulus_type, "reason": "active agent muted scope blocked storage"})
            continue
        result.collected.append(event_payload)
        if not dry_run:
            _record_collector_event(normalized, event)
            policy_remember_signature(collector_signatures, event.stimulus_type, signature)
            policy_remember_rate_limit_event(state, event)
            submitted_count += 1
    state["last_tick_at"] = _utc_now()
    state["tick_count"] = int(state.get("tick_count", 0)) + 1
    state["last_collected_count"] = len(result.collected)
    if not dry_run:
        memory_result = MemoryMirrorConsumer(collector_event_log).consume(normalized)
        state["last_memory_consumer"] = memory_result
        state["last_semantic_event_consumer"] = SemanticEventConsumer(collector_event_log).consume(normalized)
        state["last_ui_stream_consumer"] = UIStreamConsumer(collector_event_log).consume()
        state["last_active_agent_consumer"] = ActiveAgentConsumer(collector_event_log).consume(normalized)
    if active.submit_to_harness and not dry_run:
        attention_result = AttentionBatchConsumer(collector_event_log).consume(normalized, active, force=force)
        state["last_attention_consumer"] = {
            key: value
            for key, value in attention_result.items()
            if key not in {"attention_batch", "semantic_result"}
        }
        attention_batch = attention_result.get("attention_batch")
        if isinstance(attention_batch, dict):
            result.attention_batches.append(attention_batch)
            semantic_result = attention_result.get("semantic_result", {})
            if isinstance(semantic_result, dict):
                result.semantic_events.extend(semantic_result.get("semantic_events", []))
                result.action_candidates.extend(semantic_result.get("action_candidates", []))
                result.current_context = semantic_result.get("context")
            submission = attention_result.get("submission")
            if isinstance(submission, dict):
                result.submitted.append(submission)
    if active.run_autonomous_cycle and not dry_run:
        state["last_autonomous_trigger_consumer"] = AutonomousTriggerConsumer(collector_event_log).consume()
    if not dry_run:
        state["last_event_log_retention"] = collector_event_log.enforce_retention()
    if not dry_run:
        _save_state(normalized, state)
    if active.run_autonomous_cycle and not dry_run:
        loop = AutonomousLoopRunner(normalized).run(max_cycles=1, stop_after_idle_cycles=1)
        result.loop = autonomous_loop_result_to_dict(loop)
    return _finish_tick(result, started, normalized, save_state=not dry_run)


def run_collector_loop(
    config: AgentConfig,
    *,
    max_ticks: int = 0,
    profile: CollectorProfile | None = None,
    force: bool = False,
) -> dict[str, Any]:
    ticks: list[dict[str, Any]] = []
    active = profile or load_collector_profile(config)
    tick_count = 0
    while True:
        result = run_collector_tick(config, profile=active, force=force)
        ticks.append(asdict(result))
        tick_count += 1
        if max_ticks and tick_count >= max_ticks:
            break
        time.sleep(active.poll_seconds)
    return {"tick_count": tick_count, "ticks": ticks}


def collector_capabilities(config: AgentConfig | None = None) -> dict[str, Any]:
    normalized = config.normalized() if config is not None else AgentConfig().normalized()
    return {
        "collectors": collector_capability_records(
            {
                "screen_ocr": {"tesseract_available": bool(shutil.which("tesseract"))},
                "audio_activity": {
                    "sounddevice_available": importlib.util.find_spec("sounddevice") is not None,
                    "numpy_available": importlib.util.find_spec("numpy") is not None,
                },
                "file_operation_activity": {"source_status": file_activity_source_status()},
                "folder_navigation_activity": {"source_status": file_activity_source_status()},
                "file_preview_activity": {"source_status": file_activity_source_status()},
                "trash_activity": {"source_status": file_activity_source_status()},
                "ai_assistant_activity": {"source_status": ai_assistant_source_status(normalized)},
            }
        ),
        "source_manifests": collector_source_manifest_records(normalized),
        "sources": {
            "ai_assistants": ai_assistant_source_status(normalized),
            "browsers": browser_source_status(normalized),
            "cloud_files": cloud_file_source_status(normalized),
            "communication": communication_source_status(normalized),
            "google_workspace": google_workspace_source_status(normalized),
            "knowledge_bases": knowledge_base_source_status(normalized),
            **planning_source_status_map(normalized),
        },
        "registry": {
            "registered_collectors": list(collector_registry.names()),
            "missing_registrations": collector_registry.validate_complete(),
        },
        "contract": {
            "default_privacy_mode": "privacy_first",
            "raw_capture_default": "off for rich collectors",
            "dwell": "active window and browser context require dwell before recording",
            "batching": "LLM receives attention_batch summaries, not individual raw collector events",
            "dedupe": "per collector and stimulus_type stable signatures",
            "rate_limits": "per collector minute budgets before local recording or harness submission",
            "privacy_policy": "activity_policy exclusions are applied before recording or harness submission",
            "llm_boundary": "raw collector events stay local; compact attention batches pass through InteractionHarness",
        },
    }


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
    response_mode = str(payload.get("response_mode") or "silent").strip() or "silent"
    if response_mode not in {"silent", "text", "voice_prepare", "voice_speak"}:
        response_mode = "silent"
    privacy_mode = str(payload.get("privacy_mode") or "privacy_first").strip().lower()
    if privacy_mode not in {"privacy_first"}:
        privacy_mode = "privacy_first"
    watch_paths = payload.get("watch_paths", [])
    if not isinstance(watch_paths, list):
        watch_paths = []
    return CollectorProfile(
        enabled=bool(payload.get("enabled", False)),
        privacy_mode=privacy_mode,
        poll_seconds=max(0.5, min(float(payload.get("poll_seconds") or 5.0), 3600.0)),
        response_mode=response_mode,
        submit_to_harness=bool(payload.get("submit_to_harness", True)),
        run_autonomous_cycle=bool(payload.get("run_autonomous_cycle", False)),
        max_events_per_tick=max(1, min(int(payload.get("max_events_per_tick") or 8), 50)),
        collectors=collectors,
        rich_capture_opt_in=rich_capture_opt_in,
        collector_rate_limits_per_minute=collector_rate_limits,
        watch_paths=[str(item) for item in watch_paths if str(item).strip()][:20],
        max_file_events=max(1, min(int(payload.get("max_file_events") or 5), 50)),
        max_text_chars=max(160, min(int(payload.get("max_text_chars") or 2000), 20_000)),
        dwell_seconds=max(0.5, min(float(payload.get("dwell_seconds") or 8.0), 120.0)),
        batch_seconds=max(1.0, min(float(payload.get("batch_seconds") or 20.0), 900.0)),
        llm_attention_interval_seconds=max(1.0, min(float(payload.get("llm_attention_interval_seconds") or 60.0), 3600.0)),
        screenshot_min_interval_seconds=max(5.0, min(float(payload.get("screenshot_min_interval_seconds") or 60.0), 3600.0)),
        ocr_min_interval_seconds=max(5.0, min(float(payload.get("ocr_min_interval_seconds") or 90.0), 3600.0)),
        video_frame_min_interval_seconds=max(5.0, min(float(payload.get("video_frame_min_interval_seconds") or 120.0), 3600.0)),
        audio_sample_seconds=max(0.25, min(float(payload.get("audio_sample_seconds") or 1.5), 10.0)),
        audio_rms_threshold=max(0.001, min(float(payload.get("audio_rms_threshold") or 0.02), 1.0)),
        note=" ".join(str(payload.get("note") or "").split())[:1000],
        updated_at=str(payload.get("updated_at") or _utc_now()),
    )


def _event_payload(event: CollectorEvent) -> dict[str, Any]:
    return {
        "collector": event.collector,
        "source": event.source,
        "stimulus_type": event.stimulus_type,
        "text": event.text,
        "metadata": event.metadata,
        "payload": event.payload,
        "occurred_at": event.occurred_at,
        "signature": event.stable_signature(),
    }


def _optional_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _record_collector_event(config: AgentConfig, event: CollectorEvent) -> None:
    CollectorEventLog(config.collector_events_db_path).append(CollectorEventEnvelope.from_collector_event(event))


def _load_state(config: AgentConfig) -> dict[str, Any]:
    path = collector_state_path(config)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_state(config: AgentConfig, state: dict[str, Any]) -> None:
    path = collector_state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _finish_tick(result: CollectorTickResult, started: float, config: AgentConfig, *, save_state: bool) -> CollectorTickResult:
    del config, save_state
    result.finished_at = _utc_now()
    result.duration_ms = round((time.monotonic() - started) * 1000, 3)
    return result
