from __future__ import annotations

import platform
import subprocess
import time
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.tools.os_tools import active_window_snapshot

from .bridge import read_bridge_events
from .models import CollectorEvent, CollectorProfile, utc_now


INPUT_STIMULUS_TYPES = {
    "mouse_clicked",
    "mouse_double_clicked",
    "mouse_right_clicked",
    "mouse_forward",
    "mouse_back",
    "mouse_scroll_burst",
    "mouse_drag_started",
    "mouse_drag_dropped",
    "trackpad_gesture",
    "keyboard_shortcut_pressed",
    "user_idle_state_changed",
}
APP_LIFECYCLE_BRIDGE_STIMULUS_TYPES = {
    "app_opened",
    "app_closed",
    "app_focused",
    "app_hidden",
    "app_crashed",
    "app_not_responding",
    "permission_prompt_shown",
}
WINDOW_LIFECYCLE_BRIDGE_STIMULUS_TYPES = {
    "window_opened",
    "window_closed",
    "window_focused",
    "window_moved",
    "window_resized",
    "window_minimized",
    "window_title_changed",
}
BROWSER_BRIDGE_STIMULUS_TYPES = {
    "browser_tab_observed",
    "browser_url_changed",
    "browser_title_changed",
    "browser_tab_opened",
    "browser_tab_closed",
    "browser_tab_switched",
    "browser_reloaded",
    "browser_back",
    "browser_forward",
}
MAX_LIFECYCLE_EVENTS_PER_TICK = 20


def collect_input_device(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    events = read_bridge_events(config, state, "input_device", INPUT_STIMULUS_TYPES, source="activity")
    idle_event = _idle_state_event(state)
    if idle_event is not None:
        events.append(idle_event)
    return events[:MAX_LIFECYCLE_EVENTS_PER_TICK]


def collect_app_lifecycle(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    events = read_bridge_events(config, state, "app_lifecycle", APP_LIFECYCLE_BRIDGE_STIMULUS_TYPES, source="activity")
    current = _process_names()
    lifecycle = state.setdefault("app_lifecycle", {})
    previous = set(str(item) for item in lifecycle.get("process_names", []) if str(item))
    lifecycle["process_names"] = sorted(current)
    lifecycle["last_seen_at"] = utc_now()
    if not previous:
        return events[:MAX_LIFECYCLE_EVENTS_PER_TICK]

    opened = sorted(current - previous)[:5]
    closed = sorted(previous - current)[:5]
    for name in opened:
        events.append(
            CollectorEvent(
                collector="app_lifecycle",
                source="activity",
                stimulus_type="app_opened",
                text=f"App opened: {name}",
                metadata={"app_name": name, "platform": platform.system()},
                payload={"process_name": name},
                signature=f"app_opened:{name}:{int(time.time() // 5)}",
            )
        )
    for name in closed:
        events.append(
            CollectorEvent(
                collector="app_lifecycle",
                source="activity",
                stimulus_type="app_closed",
                text=f"App closed: {name}",
                metadata={"app_name": name, "platform": platform.system()},
                payload={"process_name": name},
                signature=f"app_closed:{name}:{int(time.time() // 5)}",
            )
        )
    return events[:MAX_LIFECYCLE_EVENTS_PER_TICK]


def collect_window_lifecycle(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    events = read_bridge_events(config, state, "window_lifecycle", WINDOW_LIFECYCLE_BRIDGE_STIMULUS_TYPES, source="activity")
    snapshot = active_window_snapshot()
    app = str(snapshot.get("app_name") or snapshot.get("process") or "").strip()
    title = str(snapshot.get("title") or "").strip()
    if not (app or title):
        return events[:MAX_LIFECYCLE_EVENTS_PER_TICK]
    signature = f"{app}\t{title}"
    lifecycle = state.setdefault("window_lifecycle", {})
    previous = str(lifecycle.get("active_signature") or "")
    lifecycle["active_signature"] = signature
    lifecycle["last_seen_at"] = utc_now()
    if not previous:
        return events[:MAX_LIFECYCLE_EVENTS_PER_TICK]
    stimulus_type = "window_title_changed" if previous.split("\t", 1)[0] == app else "window_focused"
    events.append(
        CollectorEvent(
            collector="window_lifecycle",
            source="activity",
            stimulus_type=stimulus_type,
            text=f"Window focused: {app + ' - ' if app else ''}{title or 'unknown'}",
            metadata={"app_name": app, "window_title": title, "platform": platform.system()},
            payload={"snapshot": snapshot, "previous_signature": previous},
            signature=f"{stimulus_type}:{signature}",
        )
    )
    return events[:MAX_LIFECYCLE_EVENTS_PER_TICK]


def collect_browser_lifecycle(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    events = read_bridge_events(config, state, "browser_lifecycle", BROWSER_BRIDGE_STIMULUS_TYPES, source="browser")
    snapshot = _browser_snapshot()
    if not snapshot.get("available"):
        return events[:MAX_LIFECYCLE_EVENTS_PER_TICK]
    app = str(snapshot.get("app_name") or "browser").strip()
    title = str(snapshot.get("title") or "").strip()
    url = str(snapshot.get("url") or "").strip()
    signature = f"{app}\t{title}\t{url}"
    lifecycle = state.setdefault("browser_lifecycle", {})
    previous = str(lifecycle.get("active_signature") or "")
    lifecycle["active_signature"] = signature
    lifecycle["last_seen_at"] = utc_now()
    if not previous:
        return events[:MAX_LIFECYCLE_EVENTS_PER_TICK]
    previous_parts = previous.split("\t", 2)
    previous_title = previous_parts[1] if len(previous_parts) > 1 else ""
    previous_url = previous_parts[2] if len(previous_parts) > 2 else ""
    if url and url != previous_url:
        events.append(
            CollectorEvent(
                collector="browser_lifecycle",
                source="browser",
                stimulus_type="browser_url_changed",
                text=f"Browser URL changed: {title or url}",
                metadata={"app_name": app, "window_title": title, "url": url, "platform": platform.system()},
                payload={"snapshot": snapshot, "previous_url": previous_url},
                signature=f"browser_url_changed:{url}",
            )
        )
    elif title and title != previous_title:
        events.append(
            CollectorEvent(
                collector="browser_lifecycle",
                source="browser",
                stimulus_type="browser_title_changed",
                text=f"Browser title changed: {title}",
                metadata={"app_name": app, "window_title": title, "url": url, "platform": platform.system()},
                payload={"snapshot": snapshot, "previous_title": previous_title},
                signature=f"browser_title_changed:{app}:{title}",
            )
        )
    return events[:MAX_LIFECYCLE_EVENTS_PER_TICK]


def _idle_state_event(state: dict[str, Any]) -> CollectorEvent | None:
    idle_seconds = _idle_seconds()
    if idle_seconds is None:
        return None
    bucket = "idle" if idle_seconds >= 300 else "active"
    input_state = state.setdefault("input_device", {})
    previous = str(input_state.get("idle_bucket") or "")
    input_state["idle_bucket"] = bucket
    input_state["idle_seconds"] = idle_seconds
    input_state["last_seen_at"] = utc_now()
    if not previous or previous == bucket:
        return None
    return CollectorEvent(
        collector="input_device",
        source="activity",
        stimulus_type="user_idle_state_changed",
        text=f"User state changed to {bucket}.",
        metadata={"idle_bucket": bucket, "idle_seconds": round(idle_seconds, 3), "platform": platform.system()},
        payload={"idle_seconds": idle_seconds, "previous_idle_bucket": previous},
        signature=f"user_idle_state_changed:{bucket}:{int(time.time() // 30)}",
    )


def _idle_seconds() -> float | None:
    system = platform.system().lower()
    if system == "darwin":
        output = _run(["ioreg", "-c", "IOHIDSystem"])
        if output.get("returncode") != 0:
            return None
        marker = "HIDIdleTime"
        for line in output.get("stdout", "").splitlines():
            if marker not in line:
                continue
            try:
                nanoseconds = int(line.split("=", 1)[1].strip())
            except (IndexError, ValueError):
                return None
            return nanoseconds / 1_000_000_000
    return None


def _process_names() -> set[str]:
    system = platform.system().lower()
    if system in {"darwin", "linux"}:
        output = _run(["ps", "-axo", "comm="], timeout=5.0)
        if output.get("returncode") != 0:
            return set()
        return {_process_label(line) for line in output.get("stdout", "").splitlines() if _process_label(line)}
    if system == "windows":
        output = _run(["powershell", "-NoProfile", "-Command", "Get-Process | Select-Object -ExpandProperty ProcessName"], timeout=5.0)
        if output.get("returncode") != 0:
            return set()
        return {_process_label(line) for line in output.get("stdout", "").splitlines() if _process_label(line)}
    return set()


def _process_label(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    name = Path(text).name.strip()
    if not name or name.startswith("."):
        return ""
    if name in {"ps", "grep", "awk", "sed"}:
        return ""
    return name[:120]


def _browser_snapshot() -> dict[str, Any]:
    system = platform.system().lower()
    if system == "darwin":
        for app in ("Google Chrome", "Safari", "Microsoft Edge", "Brave Browser"):
            output = _run(["osascript", "-e", _mac_browser_script(app)])
            if output.get("returncode") == 0 and output.get("stdout"):
                parts = output["stdout"].split("\t", 1)
                if len(parts) == 2 and (parts[0].strip() or parts[1].strip()):
                    return {"available": True, "app_name": app, "title": parts[0].strip(), "url": parts[1].strip(), "source": "macos_osascript"}
    return {"available": False, "platform": platform.system()}


def _mac_browser_script(app: str) -> str:
    if app == "Safari":
        return 'tell application "Safari" to if (count of windows) > 0 then return name of current tab of front window & "\\t" & URL of current tab of front window'
    return f'tell application "{app}" to if (count of windows) > 0 then return title of active tab of front window & "\\t" & URL of active tab of front window'


def _run(command: list[str], *, timeout: float = 5.0) -> dict[str, Any]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        return {"returncode": -1, "stdout": "", "stderr": str(exc)}
    return {"returncode": completed.returncode, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}
