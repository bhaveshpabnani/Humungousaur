from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from humungousaur.config import AgentConfig
from humungousaur.cognition.loop import AutonomousLoopRunner, autonomous_loop_result_to_dict
from humungousaur.cognition.semantic_events import record_attention_batch_semantics
from humungousaur.interaction import InteractionHarness, harness_result_to_dict
from humungousaur.memory.event_store import EventStore
from humungousaur.schemas import ActionStatus
from humungousaur.tools.activity.implementation import (
    ACTIVITY_SOURCES,
    ActivityPolicyStore,
    _activity_policy_match,
    activity_policy_path,
)
from humungousaur.tools.os_tools import ScreenshotCaptureTool, active_window_snapshot

from .activity_adapters import collect_browser_page_activity, collect_ide_activity, collect_terminal_activity
from .definitions import (
    DEFAULT_COLLECTOR_RATE_LIMITS_PER_MINUTE,
    DEFAULT_COLLECTORS,
    DEFAULT_RICH_CAPTURE_OPT_IN,
    SENSITIVE_COLLECTORS,
    collector_capability_records,
)
from .lifecycle import collect_app_lifecycle, collect_browser_lifecycle, collect_input_device, collect_window_lifecycle
from .models import CollectorEvent, CollectorProfile, CollectorTickResult, utc_now as _utc_now
from .productivity_adapters import (
    collect_accessibility_context,
    collect_agent_runtime,
    collect_calendar_activity,
    collect_communication_activity,
    collect_creative_activity,
    collect_document_activity,
    collect_mail_activity,
    collect_notification_activity,
    collect_security_context,
)




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
        "capabilities": collector_capabilities(),
        "recent_events": recent,
    }


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
    events: list[CollectorEvent] = []
    errors: list[dict[str, Any]] = []
    for name, enabled in active.collectors.items():
        if not enabled:
            continue
        collector = _COLLECTORS.get(name)
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
        sensitivity_reason = _sensitive_event_reason(active, event)
        if sensitivity_reason is not None:
            result.skipped.append({"collector": event.collector, "stimulus_type": event.stimulus_type, "reason": sensitivity_reason})
            continue
        collector_signatures = state["signatures"].setdefault(event.collector, {})
        if _signature_seen(collector_signatures, event.stimulus_type, signature):
            result.skipped.append({"collector": event.collector, "stimulus_type": event.stimulus_type, "reason": "duplicate"})
            continue
        dwell_reason = _dwell_filter_reason(state, active, event, signature, force=force)
        if dwell_reason is not None:
            result.skipped.append({"collector": event.collector, "stimulus_type": event.stimulus_type, "reason": dwell_reason})
            continue
        rate_reason = _rate_limit_reason(state, active, event, force=force)
        if rate_reason is not None:
            result.skipped.append({"collector": event.collector, "stimulus_type": event.stimulus_type, "reason": rate_reason})
            continue
        policy_payload = _activity_payload(event)
        policy_match = _activity_policy_match(policy_payload, policy)
        if policy_match is not None:
            result.skipped.append({"collector": event.collector, "stimulus_type": event.stimulus_type, "reason": policy_match})
            continue
        result.collected.append(event_payload)
        if not dry_run:
            _record_collector_event(normalized, event)
            if active.submit_to_harness and _llm_eligible_event(active, event):
                _queue_attention_event(state, event)
            _remember_signature(collector_signatures, event.stimulus_type, signature)
            _remember_rate_limit_event(state, event)
            submitted_count += 1
    state["last_tick_at"] = _utc_now()
    state["tick_count"] = int(state.get("tick_count", 0)) + 1
    state["last_collected_count"] = len(result.collected)
    if active.submit_to_harness and not dry_run:
        attention_batch = _maybe_build_attention_batch(state, active, force=force)
        if attention_batch is not None:
            result.attention_batches.append(attention_batch)
            EventStore(normalized.memory_db_path).append("attention_batch", attention_batch)
            semantic_result = record_attention_batch_semantics(normalized, attention_batch)
            result.semantic_events.extend(semantic_result.get("semantic_events", []))
            result.action_candidates.extend(semantic_result.get("action_candidates", []))
            result.current_context = semantic_result.get("context")
            harness = InteractionHarness(normalized).handle(_attention_stimulus(attention_batch), response_mode=active.response_mode)
            result.submitted.append(
                {
                    "collector": "attention_batch",
                    "stimulus_type": "attention_batch",
                    "decision": harness_result_to_dict(harness).get("decision", {}),
                    "run_id": harness.run.run_id if harness.run is not None else "",
                    "batch_id": attention_batch["batch_id"],
                }
            )
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


def collector_capabilities() -> dict[str, Any]:
    return {
        "collectors": collector_capability_records(
            {
                "screen_ocr": {"tesseract_available": bool(shutil.which("tesseract"))},
                "audio_activity": {
                    "sounddevice_available": importlib.util.find_spec("sounddevice") is not None,
                    "numpy_available": importlib.util.find_spec("numpy") is not None,
                },
            }
        ),
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


def collect_active_window(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del config, profile, state
    payload = active_window_snapshot()
    if not payload.get("supported") and platform.system().lower() == "darwin":
        payload = _mac_active_window_snapshot()
    title = str(payload.get("title") or "").strip()
    app = str(payload.get("app_name") or payload.get("process") or "").strip()
    text = "Active window changed"
    if app or title:
        text = f"Active window: {app + ' - ' if app else ''}{title or 'unknown'}"
    return [
        CollectorEvent(
            collector="active_window",
            source="activity",
            stimulus_type="active_window_changed",
            text=text,
            metadata={"app_name": app, "window_title": title, "platform": platform.system()},
            payload=payload,
        )
    ]


def collect_browser_context(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del config, profile, state
    snapshot = _browser_snapshot()
    if not snapshot.get("available"):
        return []
    title = str(snapshot.get("title") or "").strip()
    url = str(snapshot.get("url") or "").strip()
    app = str(snapshot.get("app_name") or "browser").strip()
    return [
        CollectorEvent(
            collector="browser",
            source="browser",
            stimulus_type="browser_tab_changed",
            text=f"Browser context: {title or url or app}",
            metadata={"app_name": app, "window_title": title, "url": url, "platform": platform.system()},
            payload=snapshot,
        )
    ]


def collect_clipboard(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del config, state
    text = _clipboard_text()
    if not text:
        return []
    trimmed = text[: profile.max_text_chars]
    return [
        CollectorEvent(
            collector="clipboard",
            source="activity",
            stimulus_type="clipboard_changed",
            text=f"Clipboard changed: {trimmed}",
            metadata={"text_length": len(text), "truncated": len(text) > len(trimmed), "platform": platform.system()},
            payload={"text_preview": trimmed, "text_length": len(text)},
        )
    ]


def collect_filesystem(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del state
    paths = profile.watch_paths or [str(config.workspace)]
    events: list[CollectorEvent] = []
    for path_text in paths:
        root = Path(path_text).expanduser()
        if not root.is_absolute():
            root = config.workspace / root
        if not root.exists():
            continue
        candidates = _recent_files(root, limit=profile.max_file_events, ignored_roots=[config.data_dir])
        for candidate in candidates:
            rel = _safe_relative(candidate, config.workspace)
            stat = candidate.stat()
            events.append(
                CollectorEvent(
                    collector="filesystem",
                    source="activity",
                    stimulus_type="file_changed",
                    text=f"File changed: {rel}",
                    metadata={"path": rel, "root": str(root), "size_bytes": stat.st_size},
                    payload={"path": str(candidate), "relative_path": rel, "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()},
                    signature=f"{candidate.resolve()}:{stat.st_mtime_ns}:{stat.st_size}",
                )
            )
    return events[: profile.max_file_events]


def collect_screenshot(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    if not _interval_elapsed(state, "screenshot", profile.screenshot_min_interval_seconds):
        return []
    result = ScreenshotCaptureTool().execute({"reason": "Opt-in continuous screenshot stimulus collector."}, config)
    if result.status != ActionStatus.SUCCEEDED:
        return []
    state.setdefault("last_capture_at", {})["screenshot"] = time.time()
    output = dict(result.output)
    return [
        CollectorEvent(
            collector="screenshot",
            source="screen_ocr",
            stimulus_type="screenshot_captured",
            text=f"Screenshot captured: {output.get('filename', '')}",
            metadata={"filename": output.get("filename", ""), "width": output.get("width"), "height": output.get("height")},
            payload={key: value for key, value in output.items() if key != "path"},
        )
    ]


def collect_screen_ocr(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    if not _interval_elapsed(state, "screen_ocr", profile.ocr_min_interval_seconds):
        return []
    result = ScreenshotCaptureTool().execute({"reason": "Opt-in OCR stimulus collector screenshot."}, config)
    if result.status != ActionStatus.SUCCEEDED:
        return []
    path = Path(str(result.output.get("path") or ""))
    text = _ocr_image(path)
    state.setdefault("last_capture_at", {})["screen_ocr"] = time.time()
    if not text:
        return []
    trimmed = text[: profile.max_text_chars]
    return [
        CollectorEvent(
            collector="screen_ocr",
            source="screen_ocr",
            stimulus_type="screen_text_changed",
            text=f"Screen OCR: {trimmed}",
            metadata={"filename": path.name, "text_length": len(text), "truncated": len(text) > len(trimmed)},
            payload={"text_preview": trimmed, "screenshot_filename": path.name},
        )
    ]


def collect_video_frame(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    if not _interval_elapsed(state, "video_frame", profile.video_frame_min_interval_seconds):
        return []
    result = ScreenshotCaptureTool().execute({"reason": "Opt-in video keyframe stimulus collector."}, config)
    if result.status != ActionStatus.SUCCEEDED:
        return []
    state.setdefault("last_capture_at", {})["video_frame"] = time.time()
    output = dict(result.output)
    return [
        CollectorEvent(
            collector="video_frame",
            source="screen_ocr",
            stimulus_type="video_keyframe_captured",
            text=f"Video keyframe captured: {output.get('filename', '')}",
            metadata={"filename": output.get("filename", ""), "width": output.get("width"), "height": output.get("height")},
            payload={key: value for key, value in output.items() if key != "path"},
        )
    ]


def collect_audio_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del config, state
    sample = _audio_rms_sample(profile.audio_sample_seconds)
    if sample is None:
        return []
    rms = float(sample.get("rms", 0.0))
    if rms < profile.audio_rms_threshold:
        return []
    return [
        CollectorEvent(
            collector="audio_activity",
            source="audio_transcript",
            stimulus_type="voice_activity_detected",
            text="Microphone voice activity detected without transcript.",
            metadata={"rms": round(rms, 6), "sample_seconds": profile.audio_sample_seconds},
            payload=sample,
            signature=f"voice_activity:{int(time.time() // 10)}",
        )
    ]


_COLLECTORS: dict[str, Callable[[AgentConfig, CollectorProfile, dict[str, Any]], list[CollectorEvent]]] = {
    "active_window": collect_active_window,
    "browser": collect_browser_context,
    "clipboard": collect_clipboard,
    "filesystem": collect_filesystem,
    "screenshot": collect_screenshot,
    "screen_ocr": collect_screen_ocr,
    "video_frame": collect_video_frame,
    "audio_activity": collect_audio_activity,
    "input_device": collect_input_device,
    "app_lifecycle": collect_app_lifecycle,
    "window_lifecycle": collect_window_lifecycle,
    "browser_lifecycle": collect_browser_lifecycle,
    "browser_page_activity": collect_browser_page_activity,
    "terminal_activity": collect_terminal_activity,
    "ide_activity": collect_ide_activity,
    "accessibility_context": collect_accessibility_context,
    "notification_activity": collect_notification_activity,
    "calendar_activity": collect_calendar_activity,
    "communication_activity": collect_communication_activity,
    "mail_activity": collect_mail_activity,
    "document_activity": collect_document_activity,
    "creative_activity": collect_creative_activity,
    "security_context": collect_security_context,
    "agent_runtime": collect_agent_runtime,
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


def _activity_payload(event: CollectorEvent) -> dict[str, Any]:
    activity_source = event.collector if event.collector in ACTIVITY_SOURCES else event.source
    return {
        "source": activity_source,
        "text": event.text,
        "app_name": str(event.metadata.get("app_name", "")),
        "window_title": str(event.metadata.get("window_title", "")),
        "url": str(event.metadata.get("url", "")),
        "metadata": {key: str(value) for key, value in event.metadata.items()},
    }


def _sensitive_event_reason(profile: CollectorProfile, event: CollectorEvent) -> str | None:
    if event.collector in SENSITIVE_COLLECTORS and not profile.rich_capture_opt_in.get(event.collector, False):
        return "rich capture collector is not opted in"
    if event.collector in {"active_window", "browser", "screen_ocr", "screenshot", "video_frame"}:
        text = " ".join(
            [
                str(event.metadata.get("app_name", "")),
                str(event.metadata.get("window_title", "")),
                str(event.metadata.get("url", "")),
            ]
        ).lower()
        if any(term in text for term in ("private browsing", "incognito", "password", "1password", "keychain")):
            return "sensitive private or credential context"
    return None


def _dwell_filter_reason(state: dict[str, Any], profile: CollectorProfile, event: CollectorEvent, signature: str, *, force: bool) -> str | None:
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


def _rate_limit_reason(state: dict[str, Any], profile: CollectorProfile, event: CollectorEvent, *, force: bool) -> str | None:
    if force:
        return None
    limit = int(profile.collector_rate_limits_per_minute.get(event.collector, 0) or 0)
    if limit <= 0:
        return "collector minute budget disabled"
    now = time.time()
    timestamps = _recent_rate_limit_timestamps(state, event.collector, now=now)
    if len(timestamps) >= limit:
        return f"collector minute budget exceeded ({limit}/min)"
    return None


def _remember_rate_limit_event(state: dict[str, Any], event: CollectorEvent) -> None:
    now = time.time()
    timestamps = _recent_rate_limit_timestamps(state, event.collector, now=now)
    timestamps.append(now)
    state.setdefault("rate_limits", {})[event.collector] = timestamps[-600:]


def _recent_rate_limit_timestamps(state: dict[str, Any], collector: str, *, now: float) -> list[float]:
    raw = state.setdefault("rate_limits", {}).get(collector, [])
    if not isinstance(raw, list):
        raw = []
    return [float(item) for item in raw if isinstance(item, (int, float)) and now - float(item) < 60.0]


def _llm_eligible_event(profile: CollectorProfile, event: CollectorEvent) -> bool:
    del profile
    if event.collector == "audio_activity":
        return False
    if event.source == "audio_transcript" and event.stimulus_type == "voice_activity_detected":
        return False
    return True


def _queue_attention_event(state: dict[str, Any], event: CollectorEvent) -> None:
    queued = state.setdefault("pending_attention_events", [])
    if not isinstance(queued, list):
        queued = []
    queued.append(_compact_attention_event(event))
    state["pending_attention_events"] = queued[-500:]


def _compact_attention_event(event: CollectorEvent) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "collector": event.collector,
        "source": event.source,
        "stimulus_type": event.stimulus_type,
        "occurred_at": event.occurred_at,
        "signature": event.stable_signature(),
    }
    if event.collector == "filesystem":
        compact["path"] = str(event.payload.get("relative_path") or event.metadata.get("path") or "")
        compact["size_bytes"] = int(event.metadata.get("size_bytes") or 0)
    elif event.collector == "browser":
        compact["app_name"] = str(event.metadata.get("app_name", ""))
        compact["window_title"] = str(event.metadata.get("window_title", ""))
        compact["url"] = str(event.metadata.get("url", ""))
    elif event.collector == "active_window":
        compact["app_name"] = str(event.metadata.get("app_name", ""))
        compact["window_title"] = str(event.metadata.get("window_title", ""))
    elif event.collector == "clipboard":
        compact["text_length"] = int(event.metadata.get("text_length") or 0)
        compact["truncated"] = bool(event.metadata.get("truncated", False))
    elif event.collector == "screen_ocr":
        compact["text_length"] = int(event.metadata.get("text_length") or 0)
        compact["truncated"] = bool(event.metadata.get("truncated", False))
    elif event.collector in {"screenshot", "video_frame"}:
        compact["filename"] = str(event.metadata.get("filename", ""))
        compact["width"] = event.metadata.get("width")
        compact["height"] = event.metadata.get("height")
    elif event.collector in {"app_lifecycle", "window_lifecycle"}:
        compact["app_name"] = str(event.metadata.get("app_name", ""))
        compact["window_title"] = str(event.metadata.get("window_title", ""))
        compact["summary"] = event.text[:240]
    elif event.collector == "browser_lifecycle":
        compact["app_name"] = str(event.metadata.get("app_name", ""))
        compact["window_title"] = str(event.metadata.get("window_title", ""))
        compact["url"] = str(event.metadata.get("url", ""))
        compact["summary"] = event.text[:240]
    elif event.collector == "input_device":
        compact["input_event"] = event.stimulus_type
        compact["idle_bucket"] = str(event.metadata.get("idle_bucket", ""))
        compact["summary"] = event.text[:240]
    elif event.collector in {
        "browser_page_activity",
        "terminal_activity",
        "ide_activity",
        "accessibility_context",
        "notification_activity",
        "calendar_activity",
        "communication_activity",
        "mail_activity",
        "document_activity",
        "creative_activity",
        "security_context",
        "agent_runtime",
    }:
        compact["summary"] = event.text[:240]
        compact["app_name"] = str(event.metadata.get("app_name", ""))
        compact["window_title"] = str(event.metadata.get("window_title", ""))
        compact["url"] = str(event.metadata.get("url", ""))
        compact["channel_id"] = str(event.metadata.get("channel_id", ""))
        compact["conversation_id"] = str(event.metadata.get("conversation_id", ""))
        compact["privacy_level"] = str(event.metadata.get("privacy_level", "metadata"))
        compact["bridge_event"] = bool(event.metadata.get("bridge_event", False))
    else:
        compact["summary"] = event.text[:240]
    return compact


def _maybe_build_attention_batch(state: dict[str, Any], profile: CollectorProfile, *, force: bool) -> dict[str, Any] | None:
    pending = state.get("pending_attention_events", [])
    if not isinstance(pending, list) or not pending:
        return None
    now = time.time()
    first_at = _parse_time(pending[0].get("occurred_at")) or now
    last_attention_at = float(state.get("last_attention_batch_at", 0.0) or 0.0)
    if not force and now - first_at < profile.batch_seconds:
        return None
    if not force and last_attention_at > 0.0 and now - last_attention_at < profile.llm_attention_interval_seconds:
        return None
    batch = _attention_batch_payload(pending, profile)
    state["pending_attention_events"] = []
    state["last_attention_batch_at"] = now
    return batch


def _attention_batch_payload(events: list[dict[str, Any]], profile: CollectorProfile) -> dict[str, Any]:
    batch_id = f"attention-{hashlib.sha256(json.dumps(events, sort_keys=True, default=str).encode('utf-8')).hexdigest()[:12]}"
    counts: dict[str, int] = {}
    for event in events:
        collector = str(event.get("collector", "unknown"))
        counts[collector] = counts.get(collector, 0) + 1
    text = _attention_batch_text(events, counts)
    return {
        "batch_id": batch_id,
        "event_type": "attention_batch",
        "source": "activity",
        "stimulus_type": "attention_batch",
        "text": text,
        "event_count": len(events),
        "collector_counts": counts,
        "events": events[-50:],
        "privacy_mode": profile.privacy_mode,
        "occurred_at": _utc_now(),
        "safety_note": "Compact local attention summary; raw screenshots, audio, video, and clipboard contents are not included.",
    }


def _attention_batch_text(events: list[dict[str, Any]], counts: dict[str, int]) -> str:
    lines = [f"Attention batch: {len(events)} filtered local event(s)."]
    filesystem_paths = [str(event.get("path", "")) for event in events if event.get("collector") == "filesystem" and event.get("path")]
    if filesystem_paths:
        lines.append(f"Filesystem changes: {len(filesystem_paths)} file(s): {', '.join(filesystem_paths[:5])}.")
    for collector in ("active_window", "browser"):
        latest = next((event for event in reversed(events) if event.get("collector") == collector), None)
        if latest:
            label = "Active window" if collector == "active_window" else "Browser context"
            title = str(latest.get("window_title") or latest.get("url") or "unknown")
            app = str(latest.get("app_name") or collector)
            lines.append(f"{label}: {app} - {title}.")
    if counts.get("clipboard"):
        latest_clipboard = next((event for event in reversed(events) if event.get("collector") == "clipboard"), {})
        lines.append(f"Clipboard changed ({latest_clipboard.get('text_length', 0)} chars); content omitted.")
    if counts.get("screen_ocr"):
        latest_ocr = next((event for event in reversed(events) if event.get("collector") == "screen_ocr"), {})
        lines.append(f"Screen OCR changed ({latest_ocr.get('text_length', 0)} chars); raw text omitted.")
    if counts.get("screenshot"):
        lines.append(f"Screenshot capture event(s): {counts['screenshot']}; image omitted.")
    if counts.get("video_frame"):
        lines.append(f"Video keyframe event(s): {counts['video_frame']}; frame omitted.")
    if counts.get("app_lifecycle"):
        lines.append(f"App lifecycle event(s): {counts['app_lifecycle']}.")
    if counts.get("window_lifecycle"):
        latest_window = next((event for event in reversed(events) if event.get("collector") == "window_lifecycle"), {})
        lines.append(
            f"Window lifecycle: {latest_window.get('app_name', 'app')} - {latest_window.get('window_title', 'window')}."
        )
    if counts.get("browser_lifecycle"):
        latest_browser = next((event for event in reversed(events) if event.get("collector") == "browser_lifecycle"), {})
        lines.append(f"Browser lifecycle: {latest_browser.get('window_title') or latest_browser.get('url') or 'browser event'}.")
    if counts.get("input_device"):
        lines.append(f"Input-device event(s): {counts['input_device']}; raw typed text is never collected.")
    if counts.get("browser_page_activity"):
        lines.append(f"Browser page activity event(s): {counts['browser_page_activity']}; selected text and form values are redacted by bridge policy.")
    if counts.get("terminal_activity"):
        lines.append(f"Terminal activity event(s): {counts['terminal_activity']}; command output is summarized by the bridge.")
    if counts.get("ide_activity"):
        lines.append(f"IDE activity event(s): {counts['ide_activity']}; file paths and diagnostics are compacted.")
    if counts.get("accessibility_context"):
        lines.append(f"Accessibility context event(s): {counts['accessibility_context']}; UI values and selected text are redacted unless explicitly summarized by the bridge.")
    if counts.get("notification_activity"):
        lines.append(f"Notification event(s): {counts['notification_activity']}.")
    if counts.get("calendar_activity"):
        lines.append(f"Calendar event(s): {counts['calendar_activity']}.")
    if counts.get("communication_activity"):
        lines.append(f"Communication event(s): {counts['communication_activity']}; message body is compacted by channel policy.")
    if counts.get("mail_activity"):
        lines.append(f"Mail event(s): {counts['mail_activity']}; email body is omitted.")
    if counts.get("document_activity"):
        lines.append(f"Document event(s): {counts['document_activity']}; document contents are not included.")
    if counts.get("creative_activity"):
        lines.append(f"Creative app event(s): {counts['creative_activity']}; asset contents are not included.")
    if counts.get("security_context"):
        lines.append(f"Security context event(s): {counts['security_context']}; sensitive contents are blocked.")
    if counts.get("agent_runtime"):
        lines.append(f"Agent runtime event(s): {counts['agent_runtime']}.")
    return " ".join(lines)


def _attention_stimulus(batch: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": str(batch.get("text", "")),
        "source": "activity",
        "metadata": {
            "collector": "attention_batch",
            "stimulus_type": "attention_batch",
            "privacy_mode": str(batch.get("privacy_mode", "privacy_first")),
            "event_count": int(batch.get("event_count") or 0),
            "collector_counts": batch.get("collector_counts", {}),
            "events": batch.get("events", []),
            "payload": {key: value for key, value in batch.items() if key != "events"},
        },
        "stimulus_id": str(batch.get("batch_id", "")) or f"attention-{hashlib.sha256(str(batch).encode('utf-8')).hexdigest()[:12]}",
        "occurred_at": str(batch.get("occurred_at", "")) or _utc_now(),
    }


def _parse_time(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _signature_seen(signatures: dict[str, Any], stimulus_type: str, signature: str) -> bool:
    previous = signatures.get(stimulus_type)
    if isinstance(previous, list):
        return signature in previous
    return previous == signature


def _remember_signature(signatures: dict[str, Any], stimulus_type: str, signature: str) -> None:
    previous = signatures.get(stimulus_type)
    if isinstance(previous, list):
        next_values = [item for item in previous if isinstance(item, str)]
    elif isinstance(previous, str) and previous:
        next_values = [previous]
    else:
        next_values = []
    if signature not in next_values:
        next_values.append(signature)
    signatures[stimulus_type] = next_values[-256:]


def _record_collector_event(config: AgentConfig, event: CollectorEvent) -> None:
    EventStore(config.memory_db_path).append("collector_stimulus", _event_payload(event))


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


def _browser_snapshot() -> dict[str, Any]:
    system = platform.system().lower()
    if system == "darwin":
        for app in ("Google Chrome", "Safari"):
            script = _mac_browser_script(app)
            output = _run(["osascript", "-e", script])
            if output.get("returncode") == 0 and output.get("stdout"):
                parts = output["stdout"].split("\t", 1)
                if len(parts) == 2 and (parts[0].strip() or parts[1].strip()):
                    return {"available": True, "app_name": app, "title": parts[0].strip(), "url": parts[1].strip(), "source": "macos_osascript"}
    return {"available": False, "platform": platform.system()}


def _mac_active_window_snapshot() -> dict[str, Any]:
    script = (
        'tell application "System Events"\n'
        '  set frontApp to first application process whose frontmost is true\n'
        '  set appName to name of frontApp\n'
        '  set winTitle to ""\n'
        '  try\n'
        '    set winTitle to name of front window of frontApp\n'
        '  end try\n'
        '  return appName & "\\t" & winTitle\n'
        'end tell'
    )
    output = _run(["osascript", "-e", script])
    if output.get("returncode") != 0:
        return {"platform": platform.system(), "title": "", "supported": False, "error": output.get("stderr", "")}
    parts = output.get("stdout", "").split("\t", 1)
    app = parts[0].strip() if parts else ""
    title = parts[1].strip() if len(parts) > 1 else ""
    return {
        "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine()},
        "app_name": app,
        "title": title,
        "supported": bool(app or title),
        "source": "macos_system_events",
    }


def _mac_browser_script(app: str) -> str:
    if app == "Safari":
        return 'tell application "Safari" to if (count of windows) > 0 then return name of current tab of front window & "\\t" & URL of current tab of front window'
    return 'tell application "Google Chrome" to if (count of windows) > 0 then return title of active tab of front window & "\\t" & URL of active tab of front window'


def _clipboard_text() -> str:
    system = platform.system().lower()
    if system == "darwin":
        output = _run(["pbpaste"])
        return output.get("stdout", "") if output.get("returncode") == 0 else ""
    if system == "windows":
        output = _run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"], timeout=3.0)
        return output.get("stdout", "") if output.get("returncode") == 0 else ""
    for command in (["wl-paste", "-n"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "-b", "-o"]):
        if shutil.which(command[0]):
            output = _run(command, timeout=3.0)
            return output.get("stdout", "") if output.get("returncode") == 0 else ""
    return ""


def _recent_files(root: Path, *, limit: int, ignored_roots: list[Path] | None = None) -> list[Path]:
    if root.is_file():
        return [] if _ignored_file_path(root) else [root]
    candidates: list[Path] = []
    resolved_ignored_roots = [item.resolve() for item in (ignored_roots or [])]
    try:
        for path in root.rglob("*"):
            if len(candidates) >= max(limit * 10, limit):
                break
            if _ignored_file_path(path):
                continue
            resolved = path.resolve()
            if any(resolved == ignored_root or ignored_root in resolved.parents for ignored_root in resolved_ignored_roots):
                continue
            if path.is_file():
                candidates.append(path)
    except OSError:
        return []
    return sorted(candidates, key=lambda item: item.stat().st_mtime_ns, reverse=True)[:limit]


def _ignored_file_path(path: Path) -> bool:
    ignored_parts = {".git", ".venv", "node_modules", ".build", "__pycache__", "artifacts", ".codex"}
    if any(part in ignored_parts for part in path.parts):
        return True
    name = path.name.lower()
    if name == ".env" or name.startswith(".env."):
        return True
    return name.endswith((".pem", ".key", ".p12", ".pfx", ".crt"))


def _ocr_image(path: Path) -> str:
    if path.exists() and shutil.which("tesseract"):
        output = _run(["tesseract", str(path), "stdout"], timeout=20.0)
        if output.get("returncode") == 0:
            return output.get("stdout", "").strip()
    return ""


def _audio_rms_sample(seconds: float) -> dict[str, Any] | None:
    if importlib.util.find_spec("sounddevice") is None or importlib.util.find_spec("numpy") is None:
        return None
    try:
        import numpy as np  # type: ignore[import-not-found]
        import sounddevice as sd  # type: ignore[import-not-found]

        sample_rate = 16_000
        audio = sd.rec(int(seconds * sample_rate), samplerate=sample_rate, channels=1, dtype="float32")
        sd.wait()
        rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
        return {"rms": rms, "sample_rate": sample_rate, "sample_seconds": seconds, "source": "sounddevice"}
    except Exception:
        return None


def _interval_elapsed(state: dict[str, Any], key: str, seconds: float) -> bool:
    last = float(state.get("last_capture_at", {}).get(key, 0.0) or 0.0)
    return time.time() - last >= seconds


def _run(command: list[str], *, timeout: float = 5.0) -> dict[str, Any]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        return {"returncode": -1, "stdout": "", "stderr": str(exc)}
    return {"returncode": completed.returncode, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)
