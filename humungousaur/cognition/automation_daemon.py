from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig

from .loop import AutonomousLoopRunner, autonomous_loop_result_to_dict, autonomous_status
from .models import utc_now


@dataclass(slots=True)
class AutomationDaemonProfile:
    enabled: bool = False
    poll_seconds: float = 5.0
    max_cycles_per_tick: int = 3
    stop_after_idle_cycles: int = 1
    allow_initiative: bool = False
    approve_high_risk: bool = False
    response_mode: str = "silent"
    note: str = ""
    updated_at: str = field(default_factory=utc_now)


def automation_daemon_profile_path(config: AgentConfig) -> Path:
    return config.normalized().data_dir / "automation_daemon.json"


def load_automation_daemon_profile(config: AgentConfig) -> AutomationDaemonProfile:
    path = automation_daemon_profile_path(config)
    if not path.exists():
        return AutomationDaemonProfile()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AutomationDaemonProfile()
    if not isinstance(payload, dict):
        return AutomationDaemonProfile()
    return _profile_from_payload(payload)


def save_automation_daemon_profile(config: AgentConfig, payload: dict[str, Any]) -> AutomationDaemonProfile:
    profile = _profile_from_payload(payload)
    profile.updated_at = utc_now()
    path = automation_daemon_profile_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(profile), indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return profile


def automation_daemon_status(config: AgentConfig, *, limit: int = 10) -> dict[str, Any]:
    normalized = config.normalized()
    profile = load_automation_daemon_profile(normalized)
    command = [
        "python",
        "-m",
        "humungousaur.cli",
        "autonomous-loop",
        "--workspace",
        str(normalized.workspace),
        "--data-dir",
        str(normalized.data_dir),
        "--max-cycles",
        str(profile.max_cycles_per_tick),
        "--idle-sleep-seconds",
        str(profile.poll_seconds),
        "--stop-after-idle-cycles",
        str(profile.stop_after_idle_cycles),
        "--json",
    ]
    if profile.allow_initiative:
        command.append("--allow-initiative")
    if profile.approve_high_risk:
        command.append("--approve-high-risk")
    return {
        "profile": asdict(profile),
        "profile_path": str(automation_daemon_profile_path(normalized)),
        "autonomous": autonomous_status(normalized, limit=limit),
        "suggested_command": command,
        "runtime_contract": {
            "bounded_tick": True,
            "approval_boundary": "High-risk tool actions still require normal approval unless approve_high_risk is explicitly enabled.",
            "model_initiative": "When allow_initiative is true, idle cycles may ask the configured model for one next action.",
        },
    }


def run_automation_daemon_tick(config: AgentConfig, *, profile: AutomationDaemonProfile | None = None) -> dict[str, Any]:
    normalized = config.normalized()
    active = profile or load_automation_daemon_profile(normalized)
    result = AutonomousLoopRunner(normalized).run(
        max_cycles=active.max_cycles_per_tick,
        idle_sleep_seconds=0.0,
        stop_after_idle_cycles=active.stop_after_idle_cycles,
        approve_high_risk=active.approve_high_risk,
        allow_initiative=active.allow_initiative,
    )
    return {
        "profile": asdict(active),
        "loop": autonomous_loop_result_to_dict(result),
    }


def automation_daemon_profile_with_overrides(profile: AutomationDaemonProfile, payload: dict[str, Any]) -> AutomationDaemonProfile:
    merged = asdict(profile)
    for key in (
        "enabled",
        "poll_seconds",
        "max_cycles_per_tick",
        "stop_after_idle_cycles",
        "allow_initiative",
        "approve_high_risk",
        "response_mode",
        "note",
    ):
        if key in payload:
            merged[key] = payload[key]
    return _profile_from_payload(merged)


def _profile_from_payload(payload: dict[str, Any]) -> AutomationDaemonProfile:
    response_mode = str(payload.get("response_mode") or "silent").strip() or "silent"
    if response_mode not in {"silent", "text", "voice_prepare", "voice_speak"}:
        response_mode = "silent"
    return AutomationDaemonProfile(
        enabled=bool(payload.get("enabled", False)),
        poll_seconds=max(0.1, min(float(payload.get("poll_seconds") or 5.0), 3600.0)),
        max_cycles_per_tick=max(1, min(int(payload.get("max_cycles_per_tick") or 3), 100)),
        stop_after_idle_cycles=max(1, min(int(payload.get("stop_after_idle_cycles") or 1), 100)),
        allow_initiative=bool(payload.get("allow_initiative", False)),
        approve_high_risk=bool(payload.get("approve_high_risk", False)),
        response_mode=response_mode,
        note=" ".join(str(payload.get("note") or "").strip().split())[:1_000],
        updated_at=str(payload.get("updated_at") or utc_now()),
    )
