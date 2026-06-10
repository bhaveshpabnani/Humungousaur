from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.cognition.models import CognitivePriority, new_id, utc_now
from humungousaur.cognition.queue import RuntimeEventQueue
from humungousaur.memory.event_store import EventStore


SEMANTIC_EVENT_TYPES = {
    "system_session_started",
    "system_idle_started",
    "system_idle_ended",
    "app_focus_changed",
    "app_lifecycle_changed",
    "browser_context_changed",
    "browser_lifecycle_changed",
    "browser_page_activity",
    "research_session_started",
    "research_session_updated",
    "research_session_ended",
    "project_files_changed",
    "voice_wake_detected",
    "voice_command_received",
    "screen_context_changed",
    "clipboard_changed",
    "input_device_activity",
    "ide_activity",
    "terminal_activity",
    "window_lifecycle_changed",
    "user_returned_to_work",
    "task_context_resumed",
    "possible_blocker_detected",
    "explicit_user_request",
    "external_message_received",
    "calendar_event_started",
    "ci_failure_detected",
}

PASSIVE_CONTEXT_TYPES = {
    "app_focus_changed",
    "browser_context_changed",
    "research_session_updated",
    "project_files_changed",
    "screen_context_changed",
    "clipboard_changed",
}


@dataclass(slots=True)
class SemanticEvent:
    event_id: str
    event_type: str
    source: str
    summary: str
    occurred_at: str
    metadata: dict[str, Any] = field(default_factory=dict)
    related_goal_id: str = ""
    related_task_id: str = ""
    confidence: float = 1.0
    privacy_level: str = "compact"
    raw_ref: str = ""
    sent_to_llm: bool = False


@dataclass(slots=True)
class AutonomousActionCandidate:
    action_id: str
    trigger_event_id: str
    action_type: str
    reason: str
    risk: str = "low"
    requires_user_approval: bool = False
    status: str = "queued"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)


def current_context_path(config: AgentConfig) -> Path:
    return config.normalized().data_dir / "current_context.md"


def events_markdown_path(config: AgentConfig) -> Path:
    return config.normalized().data_dir / "events.md"


def semantic_events_status(config: AgentConfig, *, limit: int = 20) -> dict[str, Any]:
    normalized = config.normalized()
    limit = max(1, min(limit, 100))
    memory = EventStore(normalized.memory_db_path)
    recent = memory.tail(limit=max(limit * 6, 50))
    semantic_events = [event for event in recent if event.get("event_type") == "semantic_event"][:limit]
    action_candidates = [event for event in recent if event.get("event_type") == "autonomous_action_candidate"][:limit]
    context_path = current_context_path(normalized)
    timeline_path = events_markdown_path(normalized)
    return {
        "semantic_events": semantic_events,
        "action_candidates": action_candidates,
        "queued_action_events": [
            asdict(event)
            for event in RuntimeEventQueue(normalized.cognition_db_path).queued(limit=limit)
            if event.source == "semantic_trigger" or event.event_type == "AUTONOMOUS_ACTION_CANDIDATE"
        ],
        "current_context_path": str(context_path),
        "events_path": str(timeline_path),
        "current_context_exists": context_path.exists(),
        "events_exists": timeline_path.exists(),
        "current_context_preview": _preview_file(context_path),
        "events_preview": _preview_file(timeline_path),
    }


def rebuild_current_context(config: AgentConfig, *, limit: int = 40, record_event: bool = True) -> dict[str, Any]:
    normalized = config.normalized()
    memory = EventStore(normalized.memory_db_path)
    recent = [event for event in memory.tail(limit=max(limit * 8, 100)) if event.get("event_type") == "semantic_event"][:limit]
    actions = [event for event in memory.tail(limit=max(limit * 8, 100)) if event.get("event_type") == "autonomous_action_candidate"][:limit]
    context_markdown = _render_current_context(recent, actions)
    events_markdown = _render_events_markdown(recent)
    context_path = current_context_path(normalized)
    timeline_path = events_markdown_path(normalized)
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(context_markdown, encoding="utf-8")
    timeline_path.write_text(events_markdown, encoding="utf-8")
    if record_event:
        memory.append(
            "current_context_brief",
            {
                "current_context_path": str(context_path),
                "events_path": str(timeline_path),
                "semantic_event_count": len(recent),
                "action_candidate_count": len(actions),
                "privacy_note": "Generated from compact semantic events, not raw screenshots, audio, video, or clipboard contents.",
            },
        )
    return {
        "current_context_path": str(context_path),
        "events_path": str(timeline_path),
        "semantic_event_count": len(recent),
        "action_candidate_count": len(actions),
    }


def record_attention_batch_semantics(config: AgentConfig, attention_batch: dict[str, Any]) -> dict[str, Any]:
    normalized = config.normalized()
    events = semantic_events_from_attention_batch(attention_batch)
    return record_semantic_events(normalized, events)


def record_stimulus_semantics(config: AgentConfig, stimulus: dict[str, Any], *, decision: str = "") -> dict[str, Any]:
    normalized = config.normalized()
    events = semantic_events_from_stimulus(stimulus, decision=decision)
    if not events:
        return {"semantic_events": [], "action_candidates": [], "context": {}}
    return record_semantic_events(normalized, events)


def record_semantic_events(config: AgentConfig, events: list[SemanticEvent]) -> dict[str, Any]:
    normalized = config.normalized()
    if not events:
        return {"semantic_events": [], "action_candidates": [], "context": rebuild_current_context(normalized, limit=40, record_event=False)}
    memory = EventStore(normalized.memory_db_path)
    recorded_events: list[dict[str, Any]] = []
    queued_candidates: list[dict[str, Any]] = []
    for event in events:
        payload = asdict(event)
        memory.append("semantic_event", payload)
        recorded_events.append(payload)
        for candidate in deterministic_action_candidates(normalized, event):
            candidate_payload = asdict(candidate)
            memory.append("autonomous_action_candidate", candidate_payload)
            RuntimeEventQueue(normalized.cognition_db_path).push(
                "AUTONOMOUS_ACTION_CANDIDATE",
                payload=candidate_payload,
                priority=_candidate_priority(candidate),
                source="semantic_trigger",
            )
            queued_candidates.append(candidate_payload)
    context = rebuild_current_context(normalized, limit=40, record_event=False)
    return {"semantic_events": recorded_events, "action_candidates": queued_candidates, "context": context}


def semantic_events_from_attention_batch(batch: dict[str, Any]) -> list[SemanticEvent]:
    compact_events = batch.get("events", [])
    if not isinstance(compact_events, list):
        compact_events = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in compact_events:
        if isinstance(item, dict):
            grouped.setdefault(str(item.get("collector") or "unknown"), []).append(item)
    occurred_at = str(batch.get("occurred_at") or utc_now())
    batch_id = str(batch.get("batch_id") or "")
    semantic: list[SemanticEvent] = []
    if grouped.get("active_window"):
        latest = grouped["active_window"][-1]
        semantic.append(
            _event(
                "app_focus_changed",
                "activity",
                _active_window_summary(latest),
                occurred_at=occurred_at,
                metadata=_safe_subset(latest, ("app_name", "window_title", "collector", "stimulus_type")),
                raw_ref=batch_id,
                sent_to_llm=True,
            )
        )
    if grouped.get("browser"):
        latest = grouped["browser"][-1]
        semantic.append(
            _event(
                "browser_context_changed",
                "browser",
                _browser_summary(latest),
                occurred_at=occurred_at,
                metadata=_safe_subset(latest, ("app_name", "window_title", "url", "collector", "stimulus_type")),
                raw_ref=batch_id,
                sent_to_llm=True,
            )
        )
    if grouped.get("app_lifecycle"):
        latest = grouped["app_lifecycle"][-1]
        semantic.append(
            _event(
                "app_lifecycle_changed",
                "activity",
                str(latest.get("summary") or "Application lifecycle changed."),
                occurred_at=occurred_at,
                metadata=_safe_subset(latest, ("app_name", "collector", "stimulus_type")),
                raw_ref=batch_id,
                sent_to_llm=True,
            )
        )
    if grouped.get("window_lifecycle"):
        latest = grouped["window_lifecycle"][-1]
        semantic.append(
            _event(
                "window_lifecycle_changed",
                "activity",
                str(latest.get("summary") or "Window lifecycle changed."),
                occurred_at=occurred_at,
                metadata=_safe_subset(latest, ("app_name", "window_title", "collector", "stimulus_type")),
                raw_ref=batch_id,
                sent_to_llm=True,
            )
        )
    if grouped.get("browser_lifecycle"):
        latest = grouped["browser_lifecycle"][-1]
        semantic.append(
            _event(
                "browser_lifecycle_changed",
                "browser",
                str(latest.get("summary") or "Browser lifecycle changed."),
                occurred_at=occurred_at,
                metadata=_safe_subset(latest, ("app_name", "window_title", "url", "collector", "stimulus_type")),
                raw_ref=batch_id,
                sent_to_llm=True,
            )
        )
    if grouped.get("input_device"):
        latest = grouped["input_device"][-1]
        semantic.append(
            _event(
                "input_device_activity",
                "activity",
                str(latest.get("summary") or "Input device activity changed."),
                occurred_at=occurred_at,
                metadata=_safe_subset(latest, ("input_event", "idle_bucket", "collector", "stimulus_type")),
                raw_ref=batch_id,
                sent_to_llm=True,
                privacy_level="metadata",
            )
        )
    for collector, event_type, source, privacy_level in (
        ("browser_page_activity", "browser_page_activity", "browser", "metadata"),
        ("terminal_activity", "terminal_activity", "activity", "metadata"),
        ("ide_activity", "ide_activity", "activity", "metadata"),
    ):
        if grouped.get(collector):
            latest = grouped[collector][-1]
            semantic.append(
                _event(
                    event_type,
                    source,
                    str(latest.get("summary") or f"{collector} event."),
                    occurred_at=occurred_at,
                    metadata=_safe_subset(latest, ("app_name", "window_title", "url", "collector", "stimulus_type", "bridge_event")),
                    raw_ref=batch_id,
                    sent_to_llm=True,
                    privacy_level=privacy_level,
                )
            )
    if grouped.get("filesystem"):
        paths = [str(item.get("path") or "") for item in grouped["filesystem"] if str(item.get("path") or "")]
        semantic.append(
            _event(
                "project_files_changed",
                "activity",
                f"{len(grouped['filesystem'])} project file change(s): {', '.join(paths[:8]) or 'paths omitted'}.",
                occurred_at=occurred_at,
                metadata={"file_count": len(grouped["filesystem"]), "paths": paths[:20]},
                raw_ref=batch_id,
                sent_to_llm=True,
            )
        )
    if grouped.get("clipboard"):
        latest = grouped["clipboard"][-1]
        semantic.append(
            _event(
                "clipboard_changed",
                "activity",
                f"Clipboard changed; content omitted ({int(latest.get('text_length') or 0)} chars).",
                occurred_at=occurred_at,
                metadata=_safe_subset(latest, ("text_length", "truncated", "collector", "stimulus_type")),
                raw_ref=batch_id,
                sent_to_llm=True,
                privacy_level="redacted",
            )
        )
    screen_count = len(grouped.get("screen_ocr", [])) + len(grouped.get("screenshot", [])) + len(grouped.get("video_frame", []))
    if screen_count:
        semantic.append(
            _event(
                "screen_context_changed",
                "screen_ocr",
                f"{screen_count} opt-in screen context change(s); raw pixels and OCR text omitted.",
                occurred_at=occurred_at,
                metadata={"screen_event_count": screen_count, "collectors": [name for name in ("screen_ocr", "screenshot", "video_frame") if grouped.get(name)]},
                raw_ref=batch_id,
                sent_to_llm=True,
                privacy_level="redacted",
            )
        )
    return semantic


def semantic_events_from_stimulus(stimulus: dict[str, Any], *, decision: str = "") -> list[SemanticEvent]:
    source = str(stimulus.get("source") or "user_text")
    if source not in {"user_text", "voice_transcript", "channel_message"}:
        return []
    metadata = stimulus.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    text = str(stimulus.get("text") or "").strip()
    occurred_at = str(stimulus.get("occurred_at") or utc_now())
    stimulus_id = str(stimulus.get("stimulus_id") or "")
    if not text:
        return []
    if source == "voice_transcript":
        events = []
        if metadata.get("wake_word_detected") or metadata.get("activation_id"):
            events.append(
                _event(
                    "voice_wake_detected",
                    source,
                    "Wake-word activation detected locally.",
                    occurred_at=occurred_at,
                    metadata=_safe_subset(metadata, ("activation_id", "wake_word", "provider")),
                    raw_ref=stimulus_id,
                    sent_to_llm=False,
                )
            )
        events.append(
            _event(
                "voice_command_received",
                source,
                _truncate(f"Voice command received: {text}", 500),
                occurred_at=occurred_at,
                metadata={"decision": decision, **_safe_subset(metadata, ("activation_id", "provider", "stt_provider"))},
                raw_ref=stimulus_id,
                sent_to_llm=True,
            )
        )
        return events
    if source == "channel_message":
        return [
            _event(
                "external_message_received",
                source,
                _truncate(f"External channel message received: {text}", 500),
                occurred_at=occurred_at,
                metadata={"decision": decision, **_safe_subset(metadata, ("channel_id", "conversation_id", "sender"))},
                raw_ref=stimulus_id,
                sent_to_llm=True,
            )
        ]
    return [
        _event(
            "explicit_user_request",
            source,
            _truncate(f"User request: {text}", 500),
            occurred_at=occurred_at,
            metadata={"decision": decision},
            raw_ref=stimulus_id,
            sent_to_llm=True,
        )
    ]


def deterministic_action_candidates(config: AgentConfig, event: SemanticEvent) -> list[AutonomousActionCandidate]:
    recent = _recent_semantic_payloads(config, limit=20)
    candidates: list[AutonomousActionCandidate] = []
    if event.event_type == "project_files_changed":
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Project files changed; refresh compact work context and keep the agent ready without interrupting the user.",
                metadata={"file_count": int(event.metadata.get("file_count") or 0), "paths": event.metadata.get("paths", [])},
            )
        )
    elif event.event_type == "browser_context_changed":
        candidates.append(
            _candidate(
                event,
                "monitor_research",
                "Browser context changed after dwell; observe research context silently unless it connects to an active request.",
                metadata=_safe_subset(event.metadata, ("app_name", "window_title", "url")),
            )
        )
    elif event.event_type == "app_focus_changed" and _looks_like_work_return(event, recent):
        candidates.append(
            _candidate(
                event,
                "prepare_resume_context",
                "User returned to a work surface after browser/research activity; prepare a concise resume context before speaking.",
                risk="low",
                metadata={"transition": "research_to_work"},
            )
        )
    elif event.event_type == "screen_context_changed":
        candidates.append(
            _candidate(
                event,
                "update_context",
                "Opt-in screen context changed; refresh compact context while omitting raw pixels and OCR.",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "ci_failure_detected":
        candidates.append(
            _candidate(
                event,
                "analyze",
                "CI failure is actionable and should be analyzed for the active workspace.",
                risk="medium",
                requires_user_approval=False,
                metadata=event.metadata,
            )
        )
    elif event.event_type == "calendar_event_started":
        candidates.append(
            _candidate(
                event,
                "prepare_briefing",
                "Calendar event started; prepare relevant context silently before deciding whether to interrupt.",
                metadata=event.metadata,
            )
        )
    elif event.event_type == "terminal_activity" and str(event.metadata.get("stimulus_type") or "").endswith(("failed", "crashed")):
        candidates.append(
            _candidate(
                event,
                "analyze",
                "Terminal, build, test, or server failure bridge event is actionable for the active workspace.",
                risk="medium",
                metadata=event.metadata,
            )
        )
    return candidates


def _event(
    event_type: str,
    source: str,
    summary: str,
    *,
    occurred_at: str,
    metadata: dict[str, Any] | None = None,
    raw_ref: str = "",
    sent_to_llm: bool = False,
    privacy_level: str = "compact",
) -> SemanticEvent:
    return SemanticEvent(
        event_id=new_id("semantic"),
        event_type=event_type if event_type in SEMANTIC_EVENT_TYPES else "system_session_started",
        source=source,
        summary=_truncate(summary, 1000),
        occurred_at=occurred_at,
        metadata=_json_safe(metadata or {}),
        raw_ref=raw_ref,
        sent_to_llm=sent_to_llm,
        privacy_level=privacy_level,
    )


def _candidate(
    event: SemanticEvent,
    action_type: str,
    reason: str,
    *,
    risk: str = "low",
    requires_user_approval: bool = False,
    metadata: dict[str, Any] | None = None,
) -> AutonomousActionCandidate:
    return AutonomousActionCandidate(
        action_id=new_id("action"),
        trigger_event_id=event.event_id,
        action_type=action_type,
        reason=_truncate(reason, 1000),
        risk=risk,
        requires_user_approval=requires_user_approval,
        metadata=_json_safe(metadata or {}),
    )


def _candidate_priority(candidate: AutonomousActionCandidate) -> CognitivePriority:
    if candidate.risk == "medium" or candidate.action_type in {"analyze", "prepare_resume_context"}:
        return CognitivePriority.NORMAL
    return CognitivePriority.LOW


def _recent_semantic_payloads(config: AgentConfig, *, limit: int) -> list[dict[str, Any]]:
    memory = EventStore(config.normalized().memory_db_path)
    return [event.get("payload", {}) for event in memory.tail(limit=max(limit * 4, 50)) if event.get("event_type") == "semantic_event"][:limit]


def _looks_like_work_return(event: SemanticEvent, recent: list[dict[str, Any]]) -> bool:
    app = str(event.metadata.get("app_name") or "").lower()
    title = str(event.metadata.get("window_title") or "").lower()
    work_surface = any(token in f"{app} {title}" for token in ("codex", "xcode", "terminal", "visual studio code", "vscode", "cursor"))
    recent_browser = any(item.get("event_type") in {"browser_context_changed", "research_session_updated"} for item in recent)
    return work_surface and recent_browser


def _render_current_context(semantic_events: list[dict[str, Any]], action_candidates: list[dict[str, Any]]) -> str:
    events = [event.get("payload", {}) for event in semantic_events]
    actions = [event.get("payload", {}) for event in action_candidates]
    latest_focus = next((event for event in events if event.get("event_type") == "app_focus_changed"), {})
    latest_browser = next((event for event in events if event.get("event_type") == "browser_context_changed"), {})
    latest_files = next((event for event in events if event.get("event_type") == "project_files_changed"), {})
    lines = [
        "# Current Context",
        "",
        "Privacy note: this brief is generated from compact semantic events. Raw continuous audio, video, screenshots, OCR text, and clipboard content are not included by default.",
        "",
        "## Focus",
        f"- Active work surface: {latest_focus.get('summary', 'No stable app focus recorded.')}",
        f"- Browser/research context: {latest_browser.get('summary', 'No stable browser context recorded.')}",
        f"- Project file activity: {latest_files.get('summary', 'No recent project file changes recorded.')}",
        "",
        "## Recent Semantic Events",
    ]
    for event in events[:12]:
        lines.append(f"- {event.get('occurred_at', '')}: {event.get('event_type', 'event')} - {event.get('summary', '')}")
    if not events:
        lines.append("- No semantic events recorded yet.")
    lines.extend(["", "## Queued Autonomous Candidates"])
    for candidate in actions[:12]:
        lines.append(f"- {candidate.get('action_type', 'action')}: {candidate.get('reason', '')}")
    if not actions:
        lines.append("- No autonomous candidates queued.")
    lines.append("")
    return "\n".join(lines)


def _render_events_markdown(semantic_events: list[dict[str, Any]]) -> str:
    lines = [
        "# Semantic Event Timeline",
        "",
        "Source of truth remains the local event store; this file is a compact generated view for LLM context and UI inspection.",
        "",
    ]
    for event in semantic_events:
        payload = event.get("payload", {})
        lines.append(f"- `{payload.get('event_type', 'event')}` {payload.get('occurred_at', '')}: {payload.get('summary', '')}")
    if not semantic_events:
        lines.append("- No semantic events recorded yet.")
    lines.append("")
    return "\n".join(lines)


def _active_window_summary(event: dict[str, Any]) -> str:
    app = str(event.get("app_name") or "unknown app")
    title = str(event.get("window_title") or "unknown window")
    return f"Active app became {app} - {title}."


def _browser_summary(event: dict[str, Any]) -> str:
    app = str(event.get("app_name") or "browser")
    title = str(event.get("window_title") or event.get("url") or "unknown page")
    return f"Browser context became {app} - {title}."


def _safe_subset(source: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return _json_safe({key: source.get(key) for key in keys if key in source})


def _json_safe(value: dict[str, Any]) -> dict[str, Any]:
    try:
        json.dumps(value, ensure_ascii=False, sort_keys=True)
        return value
    except (TypeError, ValueError):
        return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))


def _truncate(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _preview_file(path: Path, *, limit: int = 2000) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")[:limit]
    except OSError:
        return ""
