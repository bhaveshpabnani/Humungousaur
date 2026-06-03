from __future__ import annotations

import json
import threading
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from humungousaur.config import AgentConfig
from humungousaur.cognition.loop import AutonomousLoopRunner, autonomous_loop_result_to_dict, autonomous_status
from humungousaur.indexing import FileIndex
from humungousaur.interaction import InteractionHarness, harness_result_to_dict
from humungousaur.memory.event_store import EventStore
from humungousaur.memory.profile import build_user_profile
from humungousaur.memory.summary import summarize_memory
from humungousaur.orchestrator import AgentOrchestrator
from humungousaur.performance import run_benchmarks
from humungousaur.runtime import (
    approval_record_to_dict,
    approve_pending_action,
    reject_pending_action,
    request_config,
    update_pending_approval_input,
)
from humungousaur.safety.approvals import ApprovalStore
from humungousaur.safety.audit import AuditLog
from humungousaur.safety.permissions import permissions_snapshot
from humungousaur.safety.settings import PermissionSettingsStore
from humungousaur.schemas import ActionStatus
from humungousaur.tools.browser_tools import BrowserSessionStore
from humungousaur.tools.os_tools import list_screenshot_captures
from humungousaur.tools.plugin_tools import discover_plugin_manifests
from humungousaur.tools.system_tools import collect_system_status


DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboard"


def make_handler(config: AgentConfig) -> type[BaseHTTPRequestHandler]:
    base_config = config.normalized()
    settings_store = PermissionSettingsStore(base_config.permission_settings_path)

    def effective_config() -> AgentConfig:
        return settings_store.effective_config(base_config)

    def permissions_payload() -> dict[str, Any]:
        config = effective_config()
        index = FileIndex(config.file_index_db_path)
        return permissions_snapshot(config, settings_store.load(), index.status(config))

    class HumungousaurAPIHandler(BaseHTTPRequestHandler):
        server_version = "HumungousaurAPI/0.1"

        def do_OPTIONS(self) -> None:
            self._send_json({"ok": True})

        def do_GET(self) -> None:
            try:
                path, query = self._route_parts()
                if path == "/" or path.startswith("/dashboard/"):
                    self._send_dashboard_asset(path)
                    return
                if path == "/health":
                    self._send_json(
                        {
                            "status": "ok",
                            "workspace": str(base_config.workspace),
                            "system": collect_system_status(effective_config()),
                        }
                    )
                    return
                if path == "/system/status":
                    self._send_json(collect_system_status(effective_config()))
                    return
                if path == "/screen/captures":
                    self._send_json(
                        {
                            "captures": list_screenshot_captures(
                                effective_config(),
                                limit=_int_arg(query, "limit", 10),
                            ),
                            "image_bytes_served": False,
                        }
                    )
                    return
                if path == "/permissions":
                    self._send_json(permissions_payload())
                    return
                if path == "/benchmarks":
                    self._send_json(
                        run_benchmarks(
                            effective_config(),
                            iterations=_int_arg(query, "iterations", 3),
                            query=_str_arg(query, "q", "project"),
                        )
                    )
                    return
                if path == "/autonomous/status":
                    self._send_json(autonomous_status(effective_config(), limit=_int_arg(query, "limit", 10)))
                    return
                if path == "/index/status":
                    self._send_json(FileIndex(effective_config().file_index_db_path).status(effective_config()))
                    return
                if path == "/browser/sessions":
                    sessions = BrowserSessionStore(effective_config().browser_sessions_db_path).list(
                        limit=_int_arg(query, "limit", 10)
                    )
                    self._send_json([_browser_session_summary(session) for session in sessions])
                    return
                browser_session_id = _browser_session_route(path)
                if browser_session_id is not None:
                    try:
                        session = BrowserSessionStore(effective_config().browser_sessions_db_path).get(browser_session_id)
                    except KeyError:
                        self._send_error(HTTPStatus.NOT_FOUND, "Unknown browser session.")
                        return
                    self._send_json(_browser_session_summary(session))
                    return
                if path == "/runs":
                    limit = _int_arg(query, "limit", 10)
                    self._send_json(AuditLog(effective_config().audit_db_path).recent_runs(limit=limit))
                    return
                run_route = _run_route(path)
                if run_route is not None:
                    run_id, child = run_route
                    audit = AuditLog(effective_config().audit_db_path)
                    if child == "timeline":
                        self._send_json(audit.get_run_events(run_id, after_id=_int_arg(query, "after_id", 0)))
                        return
                    if child == "":
                        run = audit.get_run(run_id)
                        if run is None:
                            self._send_error(HTTPStatus.NOT_FOUND, "Unknown run.")
                            return
                        self._send_json(run)
                        return
                if path == "/plans":
                    audit = AuditLog(effective_config().audit_db_path)
                    run_id = _str_arg(query, "run_id")
                    payload = audit.get_plan_trace(run_id) if run_id else audit.recent_plan_traces(limit=_int_arg(query, "limit", 10))
                    self._send_json(payload)
                    return
                if path == "/plugins":
                    manifests = discover_plugin_manifests(effective_config())
                    detail = _bool_arg(query, "detail", False)
                    self._send_json([manifest.detail() if detail else manifest.summary() for manifest in manifests])
                    return
                if path == "/memory":
                    self._send_json(EventStore(effective_config().memory_db_path).tail(limit=_int_arg(query, "limit", 10)))
                    return
                if path == "/memory/profile":
                    self._send_json(
                        build_user_profile(
                            EventStore(effective_config().memory_db_path),
                            limit=_int_arg(query, "limit", 100),
                        )
                    )
                    return
                if path == "/memory/summary":
                    self._send_json(
                        summarize_memory(
                            EventStore(effective_config().memory_db_path),
                            period=_str_arg(query, "period", "today"),
                            query=_str_arg(query, "q", ""),
                            limit=_int_arg(query, "limit", 100),
                        )
                    )
                    return
                if path == "/memory/search":
                    self._send_json(EventStore(effective_config().memory_db_path).search(_str_arg(query, "q"), limit=_int_arg(query, "limit", 10)))
                    return
                if path == "/approvals":
                    status = _str_arg(query, "status", "pending")
                    if status == "all":
                        status = None
                    records = ApprovalStore(effective_config().approvals_db_path).list(status=status, limit=_int_arg(query, "limit", 20))
                    self._send_json([approval_record_to_dict(record) for record in records])
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint.")
            except Exception as exc:
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

        def do_POST(self) -> None:
            try:
                path, _query = self._route_parts()
                payload = self._read_json()
                if path == "/runs":
                    request = str(payload.get("request", "")).strip()
                    if not request:
                        self._send_error(HTTPStatus.BAD_REQUEST, "Field 'request' is required.")
                        return
                    run_config = request_config(effective_config(), payload)
                    result = AgentOrchestrator(run_config).run(
                        request,
                        approve_high_risk=bool(payload.get("approve_high_risk", False)),
                    )
                    self._send_json(asdict(result), HTTPStatus.CREATED)
                    return
                if path == "/stimuli":
                    text = str(payload.get("text", "")).strip()
                    if not text:
                        self._send_error(HTTPStatus.BAD_REQUEST, "Field 'text' is required.")
                        return
                    run_config = request_config(effective_config(), payload)
                    stimulus = {
                        "text": text,
                        "source": str(payload.get("source", "user_text")),
                        "metadata": payload.get("metadata", {}),
                        "stimulus_id": payload.get("stimulus_id", ""),
                        "occurred_at": payload.get("occurred_at", ""),
                    }
                    result = InteractionHarness(run_config).handle(
                        stimulus,
                        response_mode=payload.get("response_mode"),
                        approve_high_risk=bool(payload.get("approve_high_risk", False)),
                    )
                    self._send_json(harness_result_to_dict(result), HTTPStatus.CREATED)
                    return
                if path == "/runs/async":
                    request = str(payload.get("request", "")).strip()
                    if not request:
                        self._send_error(HTTPStatus.BAD_REQUEST, "Field 'request' is required.")
                        return
                    run_config = request_config(effective_config(), payload)
                    audit = AuditLog(run_config.audit_db_path)
                    run_id = audit.start_run(request)
                    audit.log_run_event(run_id, "queued", "Run queued for background execution.", {"request": request})
                    worker = threading.Thread(
                        target=_run_agent_background,
                        args=(run_config, request, run_id, bool(payload.get("approve_high_risk", False))),
                        daemon=True,
                    )
                    worker.start()
                    self._send_json({"run_id": run_id, "status": ActionStatus.PLANNED.value}, HTTPStatus.ACCEPTED)
                    return
                if path == "/autonomous/cycles":
                    run_config = request_config(effective_config(), payload)
                    result = AutonomousLoopRunner(run_config).run(
                        max_cycles=_payload_int(payload, "max_cycles", 1),
                        idle_sleep_seconds=_payload_float(payload, "idle_sleep_seconds", 0.0),
                        stop_after_idle_cycles=_payload_int(payload, "stop_after_idle_cycles", 1),
                        approve_high_risk=bool(payload.get("approve_high_risk", False)),
                        allow_initiative=_payload_bool(payload, "allow_initiative", False),
                    )
                    self._send_json(autonomous_loop_result_to_dict(result), HTTPStatus.CREATED)
                    return
                if path == "/index/rebuild":
                    self._send_json(FileIndex(effective_config().file_index_db_path).rebuild(effective_config()))
                    return
                run_route = _run_route(path)
                if run_route is not None:
                    run_id, child = run_route
                    if child == "cancel":
                        reason = str(payload.get("reason", "Cancelled from API."))
                        run = AuditLog(effective_config().audit_db_path).request_cancel_run(run_id, reason=reason)
                        self._send_json(run)
                        return
                permission_action = _permission_action(path)
                if permission_action is not None:
                    action = permission_action
                    raw_path = str(payload.get("path", "")).strip()
                    if action == "add-read-root":
                        settings = settings_store.add_read_root(raw_path, base_config)
                    else:
                        settings = settings_store.remove_read_root(raw_path, base_config)
                    updated_config = effective_config()
                    index_status = FileIndex(updated_config.file_index_db_path).rebuild(updated_config)
                    self._send_json(permissions_snapshot(updated_config, settings, index_status))
                    return
                approval_action = _approval_action(path)
                if approval_action is not None:
                    token, action = approval_action
                    note = str(payload.get("note", f"{action} from API"))
                    if action == "approve":
                        self._send_json(approve_pending_action(effective_config(), token, note))
                        return
                    if action == "reject":
                        self._send_json(reject_pending_action(effective_config(), token, note))
                        return
                    if action == "edit":
                        tool_input = payload.get("tool_input")
                        if not isinstance(tool_input, dict):
                            self._send_error(HTTPStatus.BAD_REQUEST, "Field 'tool_input' must be an object.")
                            return
                        self._send_json(update_pending_approval_input(effective_config(), token, tool_input, note))
                        return
                self._send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint.")
            except (KeyError, ValueError) as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            except Exception as exc:
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _route_parts(self) -> tuple[str, dict[str, list[str]]]:
            parsed = urlparse(self.path)
            return parsed.path.rstrip("/") or "/", parse_qs(parsed.query)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            body = self.rfile.read(length).decode("utf-8")
            try:
                payload = json.loads(body)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Request body must be valid JSON: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            return payload

        def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1")
            self.send_header("Access-Control-Allow-Headers", "content-type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            self.wfile.write(body)

        def _send_dashboard_asset(self, path: str) -> None:
            relative = "index.html" if path == "/" else path.removeprefix("/dashboard/")
            asset_path = (DASHBOARD_DIR / relative).resolve()
            if DASHBOARD_DIR not in asset_path.parents and asset_path != DASHBOARD_DIR:
                self._send_error(HTTPStatus.NOT_FOUND, "Unknown dashboard asset.")
                return
            if not asset_path.exists() or not asset_path.is_file():
                self._send_error(HTTPStatus.NOT_FOUND, "Unknown dashboard asset.")
                return
            content_type = _content_type(asset_path)
            body = asset_path.read_bytes()
            self.send_response(HTTPStatus.OK.value)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, status: HTTPStatus, message: str) -> None:
            self._send_json({"error": message}, status)

    return HumungousaurAPIHandler


def create_api_server(config: AgentConfig, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Humungousaur API binds to loopback hosts only by default.")
    return ThreadingHTTPServer((host, port), make_handler(config))


def run_api_server(config: AgentConfig, host: str = "127.0.0.1", port: int = 8765) -> None:
    server = create_api_server(config, host=host, port=port)
    address, actual_port = server.server_address
    print(f"Humungousaur API listening on http://{address}:{actual_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _run_agent_background(config: AgentConfig, request: str, run_id: str, approve_high_risk: bool) -> None:
    audit = AuditLog(config.audit_db_path)
    try:
        AgentOrchestrator(config).run(
            request,
            approve_high_risk=approve_high_risk,
            run_id=run_id,
            is_cancel_requested=lambda: audit.is_run_cancel_requested(run_id),
        )
    except Exception as exc:
        audit.log_run_event(run_id, "run_error", "Run failed with an unhandled error.", {"error": str(exc)})
        audit.finish_run(run_id, ActionStatus.FAILED, f"Run failed: {exc}")


def _int_arg(query: dict[str, list[str]], name: str, default: int) -> int:
    try:
        return int(query.get(name, [str(default)])[0])
    except ValueError:
        return default


def _str_arg(query: dict[str, list[str]], name: str, default: str = "") -> str:
    return query.get(name, [default])[0]


def _bool_arg(query: dict[str, list[str]], name: str, default: bool = False) -> bool:
    raw = query.get(name, [str(default)])[0].strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def _payload_int(payload: dict[str, Any], name: str, default: int) -> int:
    try:
        return int(payload.get(name, default))
    except (TypeError, ValueError):
        return default


def _payload_float(payload: dict[str, Any], name: str, default: float) -> float:
    try:
        return float(payload.get(name, default))
    except (TypeError, ValueError):
        return default


def _payload_bool(payload: dict[str, Any], name: str, default: bool) -> bool:
    value = payload.get(name, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on"}
    return bool(value)


def _approval_action(path: str) -> tuple[str, str] | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "approvals" and parts[2] in {"approve", "reject", "edit"}:
        return parts[1], parts[2]
    return None


def _permission_action(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "permissions" and parts[1] == "read-roots" and parts[2] in {"add", "remove"}:
        return f"{parts[2]}-read-root"
    return None


def _run_route(path: str) -> tuple[str, str] | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 2 and parts[0] == "runs":
        return parts[1], ""
    if len(parts) == 3 and parts[0] == "runs" and parts[2] in {"timeline", "cancel"}:
        return parts[1], parts[2]
    return None


def _browser_session_route(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "browser" and parts[1] == "sessions":
        return parts[2]
    return None


def _browser_session_summary(session: dict[str, Any]) -> dict[str, Any]:
    forms = []
    drafts = session.get("form_drafts", {})
    for index, form in enumerate(session.get("forms", [])):
        forms.append(
            {
                "index": index,
                "action": form.get("action", ""),
                "method": form.get("method", "get"),
                "fields": [field["name"] for field in form.get("inputs", [])],
                "draft": drafts.get(str(index), {}),
            }
        )
    return {
        "session_id": session["session_id"],
        "current_url": session["current_url"],
        "title": session["title"],
        "summary": session["text"][:700],
        "links": [
            {"index": index, "href": link["href"], "text": link.get("text", "")}
            for index, link in enumerate(session.get("links", [])[:25])
        ],
        "images": [
            {"index": index, "src": image["src"], "alt": image.get("alt", ""), "title": image.get("title", "")}
            for index, image in enumerate(session.get("images", [])[:25])
        ],
        "forms": forms,
        "history_length": len(session.get("history", [])),
        "can_go_back": len(session.get("history", [])) > 1,
        "created_at": session["created_at"],
        "updated_at": session["updated_at"],
    }


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".html":
        return "text/html; charset=utf-8"
    if suffix == ".css":
        return "text/css; charset=utf-8"
    if suffix == ".js":
        return "application/javascript; charset=utf-8"
    return "application/octet-stream"
