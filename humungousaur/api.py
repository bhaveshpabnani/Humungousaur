from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from humungousaur.config import AgentConfig
from humungousaur.cognition.loop import AutonomousLoopRunner, autonomous_loop_result_to_dict, autonomous_status
from humungousaur.cognition.queue import RuntimeEventQueue
from humungousaur.cognition.triggers import TriggerStore, stimulus_from_input
from humungousaur.integrations.channel_listeners import (
    channel_listener_status,
    channel_listener_tick,
    process_channel_webhook,
)
from humungousaur.integrations.channels import (
    channel_doctor,
    channel_setup_status,
    handle_channel_inbound,
    list_outbox,
    load_channel_catalog,
    save_channel_setup,
)
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
from humungousaur.tools import default_tools
from humungousaur.tools.browser_tools import BrowserSessionStore
from humungousaur.tools.capability_tools import CapabilitySurfaceTool, ToolDescribeTool, ToolSearchTool
from humungousaur.tools.cognition_tools import (
    AutomationDaemonConfigureTool,
    AutomationDaemonStatusTool,
    AutomationDaemonTickTool,
    MultiAgentBoardTool,
    MultiAgentCoordinateTool,
    SkillForgeDraftTool,
    SkillForgePacksTool,
)
from humungousaur.tools.os_tools import list_screenshot_captures
from humungousaur.tools.plugin_tools import discover_plugin_manifests, load_plugin_catalog
from humungousaur.tools.system_tools import collect_system_status
from humungousaur.tools.voice_tools import VoiceProviderStatusTool
from humungousaur.tools.workflow_tools import (
    CanvasA2uiCreateTool,
    CanvasA2uiRenderTool,
    DiffRenderTool,
    LlmTaskJsonTool,
    LobsterWorkflowApproveTool,
    LobsterWorkflowStartTool,
    LobsterWorkflowStatusTool,
    TokenjuiceCompactTool,
)


DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboard"


def make_handler(config: AgentConfig) -> type[BaseHTTPRequestHandler]:
    base_config = config.normalized()
    settings_store = PermissionSettingsStore(base_config.permission_settings_path)
    request_log_lock = threading.Lock()

    def effective_config() -> AgentConfig:
        return settings_store.effective_config(base_config)

    def permissions_payload() -> dict[str, Any]:
        config = effective_config()
        index = FileIndex(config.file_index_db_path)
        return permissions_snapshot(config, settings_store.load(), index.status(config))

    class HumungousaurAPIHandler(BaseHTTPRequestHandler):
        server_version = "HumungousaurAPI/0.1"

        def do_OPTIONS(self) -> None:
            self._mark_request_started()
            self._send_json({"ok": True})

        def do_GET(self) -> None:
            self._mark_request_started()
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
                if path == "/tools":
                    self._send_json(_tool_catalog_payload(effective_config()))
                    return
                if path == "/capabilities":
                    result = CapabilitySurfaceTool().execute(
                        {
                            "include_records": _bool_arg(query, "include_records", False),
                            "include_tool_schemas": _bool_arg(query, "include_tool_schemas", False),
                        },
                        effective_config(),
                    )
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output})
                    return
                if path == "/tools/search":
                    result = ToolSearchTool().execute(
                        {
                            "query": _str_arg(query, "q"),
                            "kind": _str_arg(query, "kind", "all"),
                            "limit": _int_arg(query, "limit", 10),
                            "include_tool_schemas": _bool_arg(query, "include_tool_schemas", False),
                        },
                        effective_config(),
                    )
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output})
                    return
                if path == "/tools/describe":
                    result = ToolDescribeTool().execute(
                        {
                            "record_id": _str_arg(query, "record_id"),
                            "include_tool_schema": _bool_arg(query, "include_tool_schema", True),
                        },
                        effective_config(),
                    )
                    status = HTTPStatus.OK if result.status == ActionStatus.SUCCEEDED else HTTPStatus.NOT_FOUND
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output}, status)
                    return
                if path == "/voice/status":
                    result = VoiceProviderStatusTool().execute({}, effective_config())
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output})
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
                if path == "/automation/daemon":
                    result = AutomationDaemonStatusTool().execute(
                        {"limit": _int_arg(query, "limit", 10)},
                        effective_config(),
                    )
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output})
                    return
                if path == "/multi-agent/board":
                    result = MultiAgentBoardTool().execute(
                        {"limit": _int_arg(query, "limit", 20)},
                        effective_config(),
                    )
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output})
                    return
                if path == "/skills/forge/packs":
                    result = SkillForgePacksTool().execute(
                        {"limit": _int_arg(query, "limit", 20)},
                        effective_config(),
                    )
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output})
                    return
                if path == "/workflow/lobster/status":
                    result = LobsterWorkflowStatusTool().execute(
                        {
                            "workflow_id": _str_arg(query, "workflow_id"),
                            "limit": _int_arg(query, "limit", 20),
                        },
                        effective_config(),
                    )
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output})
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
                if path == "/plugins/catalog":
                    self._send_json(load_plugin_catalog())
                    return
                if path == "/channels":
                    self._send_json(load_channel_catalog())
                    return
                if path == "/channels/status":
                    self._send_json(channel_setup_status(effective_config(), channel_id=_str_arg(query, "channel_id") or None))
                    return
                if path == "/channels/doctor":
                    self._send_json(channel_doctor(effective_config(), channel_id=_str_arg(query, "channel_id") or None))
                    return
                if path == "/channels/outbox":
                    self._send_json({"messages": list_outbox(effective_config(), limit=_int_arg(query, "limit", 20))})
                    return
                if path == "/channels/listeners":
                    self._send_json(channel_listener_status(effective_config(), channel_id=_str_arg(query, "channel_id") or None))
                    return
                webhook_channel_id = _channel_webhook_route(path)
                if webhook_channel_id is not None:
                    challenge = _str_arg(query, "hub.challenge") or _str_arg(query, "challenge")
                    if webhook_channel_id == "whatsapp" and challenge:
                        self._send_text(challenge)
                        return
                    self._send_json(
                        {
                            "channel_id": webhook_channel_id,
                            "webhook_path": f"/channels/webhook/{webhook_channel_id}",
                            "status": "ready_for_post_events",
                        }
                    )
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
            self._mark_request_started()
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
                if path == "/channels/inbound":
                    run_config = request_config(effective_config(), payload)
                    result = handle_channel_inbound(
                        payload,
                        run_config,
                        response_mode=payload.get("response_mode"),
                        approve_high_risk=bool(payload.get("approve_high_risk", False)),
                    )
                    self._send_json(result, HTTPStatus.CREATED)
                    return
                if path == "/voice/status":
                    run_config = request_config(effective_config(), payload)
                    result = VoiceProviderStatusTool().execute({}, run_config)
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output}, HTTPStatus.CREATED)
                    return
                if path == "/channels/status":
                    run_config = request_config(effective_config(), payload)
                    self._send_json(channel_setup_status(run_config, channel_id=str(payload.get("channel_id") or "") or None), HTTPStatus.CREATED)
                    return
                if path == "/channels/doctor":
                    run_config = request_config(effective_config(), payload)
                    self._send_json(channel_doctor(run_config, channel_id=str(payload.get("channel_id") or "") or None), HTTPStatus.CREATED)
                    return
                if path == "/channels/listeners":
                    run_config = request_config(effective_config(), payload)
                    self._send_json(channel_listener_status(run_config, channel_id=str(payload.get("channel_id") or "") or None), HTTPStatus.CREATED)
                    return
                if path == "/channels/listeners/tick":
                    run_config = request_config(effective_config(), payload)
                    result = channel_listener_tick(
                        run_config,
                        channel_id=str(payload.get("channel_id") or "") or None,
                        limit=_payload_int(payload, "limit", 20),
                        prepare_replies=_payload_bool(payload, "prepare_replies", True),
                        approve_high_risk=bool(payload.get("approve_high_risk", False)),
                    )
                    self._send_json(result, HTTPStatus.CREATED)
                    return
                webhook_channel_id = _channel_webhook_route(path)
                if webhook_channel_id is not None:
                    run_config = request_config(effective_config(), payload)
                    result = process_channel_webhook(
                        run_config,
                        channel_id=webhook_channel_id,
                        payload=payload,
                        prepare_reply=_payload_bool(payload, "prepare_reply", True),
                        approve_high_risk=bool(payload.get("approve_high_risk", False)),
                        response_mode=payload.get("response_mode"),
                    )
                    self._send_json(result, HTTPStatus.CREATED)
                    return
                if path == "/channels/setup":
                    channel_id = str(payload.get("channel_id", "")).strip()
                    if not channel_id:
                        self._send_error(HTTPStatus.BAD_REQUEST, "Field 'channel_id' is required.")
                        return
                    setup = save_channel_setup(effective_config(), channel_id, payload)
                    self._send_json({"setup": setup, **channel_setup_status(effective_config(), channel_id=channel_id)}, HTTPStatus.CREATED)
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
                    self._send_json({"run_id": run_id, "status": ActionStatus.PLANNED.value}, HTTPStatus.ACCEPTED)
                    if isinstance(self.server, HumungousaurAPIServer):
                        self.server.start_background_worker(worker)
                    else:
                        worker.start()
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
                if path == "/automation/daemon/configure":
                    run_config = request_config(effective_config(), payload)
                    result = AutomationDaemonConfigureTool().execute(payload, run_config)
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output}, HTTPStatus.CREATED)
                    return
                if path == "/automation/daemon/tick":
                    run_config = request_config(effective_config(), payload)
                    result = AutomationDaemonTickTool().execute(payload, run_config)
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output}, HTTPStatus.CREATED)
                    return
                if path == "/multi-agent/coordinate":
                    run_config = request_config(effective_config(), payload)
                    result = MultiAgentCoordinateTool().execute(payload, run_config)
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output}, HTTPStatus.CREATED)
                    return
                if path == "/workflow/diff":
                    run_config = request_config(effective_config(), payload)
                    result = DiffRenderTool().execute(payload, run_config)
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output}, HTTPStatus.CREATED)
                    return
                if path == "/workflow/llm-task":
                    run_config = request_config(effective_config(), payload)
                    result = LlmTaskJsonTool().execute(payload, run_config)
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output}, HTTPStatus.CREATED)
                    return
                if path == "/workflow/tokenjuice":
                    run_config = request_config(effective_config(), payload)
                    result = TokenjuiceCompactTool().execute(payload, run_config)
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output}, HTTPStatus.CREATED)
                    return
                if path == "/workflow/lobster/start":
                    run_config = request_config(effective_config(), payload)
                    result = LobsterWorkflowStartTool().execute(payload, run_config)
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output}, HTTPStatus.CREATED)
                    return
                if path == "/workflow/lobster/approve":
                    run_config = request_config(effective_config(), payload)
                    result = LobsterWorkflowApproveTool().execute(payload, run_config)
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output}, HTTPStatus.CREATED)
                    return
                if path == "/canvas/a2ui/create":
                    run_config = request_config(effective_config(), payload)
                    result = CanvasA2uiCreateTool().execute(payload, run_config)
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output}, HTTPStatus.CREATED)
                    return
                if path == "/canvas/a2ui/render":
                    run_config = request_config(effective_config(), payload)
                    result = CanvasA2uiRenderTool().execute(payload, run_config)
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output}, HTTPStatus.CREATED)
                    return
                if path == "/skills/forge":
                    run_config = request_config(effective_config(), payload)
                    result = SkillForgeDraftTool().execute(payload, run_config)
                    self._send_json({"status": result.status.value, "summary": result.summary, **result.output}, HTTPStatus.CREATED)
                    return
                if path == "/triggers/evaluate":
                    run_config = request_config(effective_config(), payload)
                    if not str(payload.get("source", "")).strip():
                        self._send_error(HTTPStatus.BAD_REQUEST, "Field 'source' is required.")
                        return
                    stimulus = stimulus_from_input(payload)
                    fired = TriggerStore(run_config.cognition_db_path).evaluate(
                        stimulus,
                        RuntimeEventQueue(run_config.cognition_db_path),
                        limit=_payload_int(payload, "limit", 20),
                    )
                    self._send_json({"stimulus": stimulus, "fired": fired}, HTTPStatus.CREATED)
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

        def _mark_request_started(self) -> None:
            self._request_started_at = time.perf_counter()
            self._request_received_at = datetime.now(timezone.utc).isoformat()
            self._request_payload_summary = {}

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
            self._request_payload_summary = _payload_summary(payload)
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
            self._log_response(status, payload)

        def _send_text(self, payload: str, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = payload.encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1")
            self.end_headers()
            self.wfile.write(body)
            self._log_response(status, {"content_type": "text/plain", "text_length": len(payload)})

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
            self._log_response(HTTPStatus.OK, {"asset": relative, "content_type": content_type, "bytes": len(body)})

        def _send_error(self, status: HTTPStatus, message: str) -> None:
            self._send_json({"error": message}, status)

        def _log_response(self, status: HTTPStatus, payload: Any) -> None:
            started = getattr(self, "_request_started_at", time.perf_counter())
            entry = {
                "created_at": getattr(self, "_request_received_at", datetime.now(timezone.utc).isoformat()),
                "method": self.command,
                "path": self._route_parts()[0],
                "query": _query_keys(self.path),
                "status": int(status.value),
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "request": getattr(self, "_request_payload_summary", {}),
            }
            if isinstance(payload, dict) and payload.get("error"):
                entry["error"] = str(payload.get("error", ""))[:1000]
            _append_request_log(base_config, entry, request_log_lock)

    return HumungousaurAPIHandler


class HumungousaurAPIServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class: type[BaseHTTPRequestHandler]) -> None:
        super().__init__(server_address, handler_class)
        self._background_threads: list[threading.Thread] = []
        self._background_threads_lock = threading.Lock()

    def start_background_worker(self, worker: threading.Thread) -> None:
        with self._background_threads_lock:
            self._background_threads = [thread for thread in self._background_threads if thread.is_alive()]
            self._background_threads.append(worker)
        worker.start()

    def join_background_workers(self, timeout_seconds: float = 10.0) -> None:
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        while True:
            with self._background_threads_lock:
                alive = [thread for thread in self._background_threads if thread.is_alive()]
                self._background_threads = alive
            if not alive:
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            alive[0].join(timeout=min(0.25, remaining))

    def server_close(self) -> None:
        self.join_background_workers()
        super().server_close()


def create_api_server(config: AgentConfig, host: str = "127.0.0.1", port: int = 8765) -> HumungousaurAPIServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Humungousaur API binds to loopback hosts only by default.")
    return HumungousaurAPIServer((host, port), make_handler(config))


def _append_request_log(config: AgentConfig, entry: dict[str, Any], lock: threading.Lock) -> None:
    path = config.data_dir / "api_requests.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        return


def _payload_summary(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata")
    runtime_secrets = payload.get("runtime_secrets", payload.get("secrets", {}))
    summary: dict[str, Any] = {
        "keys": sorted(str(key) for key in payload.keys()),
    }
    if payload.get("text") is not None:
        text = str(payload.get("text") or "")
        summary["text_preview"] = text[:160]
        summary["text_length"] = len(text)
    for name in ("source", "response_mode", "planner", "model_provider", "model"):
        if payload.get(name) is not None:
            summary[name] = str(payload.get(name) or "")
    if isinstance(metadata, dict):
        summary["metadata_keys"] = sorted(str(key) for key in metadata.keys())
    if isinstance(runtime_secrets, dict):
        summary["runtime_secret_names"] = sorted(str(key) for key in runtime_secrets.keys())
    return summary


def _query_keys(path: str) -> list[str]:
    parsed = urlparse(path)
    return sorted(parse_qs(parsed.query).keys())


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


def _tool_catalog_payload(config: AgentConfig) -> dict[str, Any]:
    tools = default_tools(config)
    items = []
    groups: dict[str, int] = {}
    for tool in sorted(tools.values(), key=lambda item: (item.capability_group, item.name)):
        groups[tool.capability_group] = groups.get(tool.capability_group, 0) + 1
        items.append(
            {
                "name": tool.name,
                "description": tool.description,
                "risk_level": tool.risk_level.value,
                "requires_approval": tool.requires_approval,
                "capability_group": tool.capability_group,
                "input_schema": tool.input_schema,
            }
        )
    return {
        "tool_count": len(items),
        "groups": [{"name": name, "tool_count": count} for name, count in sorted(groups.items())],
        "tools": items,
    }


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


def _channel_webhook_route(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "channels" and parts[1] == "webhook":
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
