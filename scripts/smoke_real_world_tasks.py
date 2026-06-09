from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import replace
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from humungousaur.config import AgentConfig
from humungousaur.env import load_workspace_environment
from humungousaur.schemas import ActionStatus, ToolResult
from humungousaur.tools import default_tools


SAFE_PASS_STATUSES = {ActionStatus.SUCCEEDED, ActionStatus.SKIPPED}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run safe real-world task readiness smokes for app, browser, and calendar-style workflows.")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--data-dir", type=Path, default=Path("artifacts/real-world-smoke"))
    parser.add_argument("--live-browser", action="store_true", help="Launch a real headless Playwright browser against a local test page.")
    args = parser.parse_args()

    workspace = args.workspace.expanduser().resolve()
    load_workspace_environment(workspace)
    base_config = AgentConfig(workspace=workspace, data_dir=args.data_dir, planner_provider="explicit").normalized()
    dry_config = replace(base_config, dry_run=True)
    tools = default_tools(base_config)
    results: list[dict[str, Any]] = []

    def record(name: str, result: ToolResult, *, allow_skipped: bool = False, extra_ok: bool = True) -> None:
        statuses = SAFE_PASS_STATUSES if allow_skipped else {ActionStatus.SUCCEEDED}
        ok = result.status in statuses and extra_ok
        results.append(
            {
                "name": name,
                "ok": ok,
                "status": result.status.value,
                "summary": result.summary,
                "error": result.error,
                "output": _jsonable(result.output),
            }
        )

    record("system_status", tools["system_status"].execute({}, base_config))
    record("browser_live_status", tools["browser_live_status"].execute({}, base_config))
    record(
        "browser_live_open_dry_run",
        tools["browser_live_open"].execute({"url": "https://example.com", "headless": True}, dry_config),
        allow_skipped=True,
    )
    record(
        "os_launch_allowlisted_app_dry_run",
        tools["os_launch_app"].execute({"app": "calculator", "reason": "real-world smoke verifies app launch command without starting it"}, dry_config),
        allow_skipped=True,
    )
    record(
        "os_observe_ui_dry_run",
        tools["os_observe_ui"].execute({"max_elements": 5, "include_values": False, "reason": "real-world smoke verifies UI observation approval boundary"}, dry_config),
        allow_skipped=True,
    )
    calendar = tools["google_workspace_operation_prepare"].execute(
        {
            "app": "calendar",
            "operation": "create_event",
            "calendar_id": "primary",
            "title": "Humungousaur smoke event",
            "description": "Prepared only; no Google API call is made.",
            "start": "2026-06-10T09:00:00+05:30",
            "end": "2026-06-10T09:15:00+05:30",
            "timezone": "Asia/Kolkata",
            "reason": "real-world smoke verifies calendar operation preparation without external mutation",
        },
        base_config,
    )
    record(
        "google_calendar_operation_prepare",
        calendar,
        extra_ok=calendar.output.get("approval_required") is True and "googleapis.com/calendar" in str(calendar.output.get("endpoint", "")),
    )

    if args.live_browser:
        _run_live_browser_cycle(tools, base_config, record)

    base_config.data_dir.mkdir(parents=True, exist_ok=True)
    result_path = base_config.data_dir / "real-world-smoke-results.json"
    payload = {"ok": all(item["ok"] for item in results), "live_browser": bool(args.live_browser), "results": results}
    result_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": payload["ok"], "result_path": str(result_path), "failed": [item for item in results if not item["ok"]]}, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1


def _run_live_browser_cycle(tools: dict[str, Any], config: AgentConfig, record) -> None:
    with local_web_page() as url:
        opened = tools["browser_live_open"].execute({"url": url, "headless": True, "viewport_width": 800, "viewport_height": 600}, config)
        live_session_id = str(opened.output.get("live_session_id", "")) if isinstance(opened.output, dict) else ""
        record("browser_live_open_local_page", opened, extra_ok=bool(live_session_id))
        if not live_session_id:
            return
        observed = tools["browser_live_observe"].execute({"live_session_id": live_session_id, "include_text": True, "max_elements": 20}, config)
        record("browser_live_observe_local_page", observed, extra_ok="Humungousaur live browser smoke" in json.dumps(observed.output))
        closed = tools["browser_live_close"].execute({"live_session_id": live_session_id, "reason": "real-world smoke complete"}, config)
        record("browser_live_close_local_page", closed)


@contextmanager
def local_web_page():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        (root / "index.html").write_text(
            "<!doctype html><html><head><title>Humungousaur Smoke</title></head>"
            "<body><main><h1>Humungousaur live browser smoke</h1><button>Ready</button></main></body></html>",
            encoding="utf-8",
        )

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(root), **kwargs)

            def log_message(self, format: str, *args) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/index.html"
        finally:
            server.shutdown()
            server.server_close()


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
