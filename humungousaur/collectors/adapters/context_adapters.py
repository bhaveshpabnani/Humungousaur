from __future__ import annotations

import platform
import subprocess
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.tools.os_tools import active_window_snapshot

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile


ACTIVE_WINDOW_BRIDGE_STIMULUS_TYPES = {"active_window_changed"}
BROWSER_CONTEXT_BRIDGE_STIMULUS_TYPES = {"browser_tab_changed"}


def collect_active_window(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    bridge_events = read_bridge_events(config, state, "active_window", ACTIVE_WINDOW_BRIDGE_STIMULUS_TYPES, source="activity", max_events=1)
    if bridge_events:
        return bridge_events
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
    del profile
    bridge_events = read_bridge_events(config, state, "browser", BROWSER_CONTEXT_BRIDGE_STIMULUS_TYPES, source="browser", max_events=1)
    if bridge_events:
        return bridge_events
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


def _browser_snapshot() -> dict[str, Any]:
    if platform.system().lower() == "darwin":
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
        "  set frontApp to first application process whose frontmost is true\n"
        "  set appName to name of frontApp\n"
        '  set winTitle to ""\n'
        "  try\n"
        "    set winTitle to name of front window of frontApp\n"
        "  end try\n"
        '  return appName & "\\t" & winTitle\n'
        "end tell"
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


def _run(command: list[str], *, timeout: float = 5.0) -> dict[str, Any]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        return {"returncode": -1, "stdout": "", "stderr": str(exc)}
    return {"returncode": completed.returncode, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}
