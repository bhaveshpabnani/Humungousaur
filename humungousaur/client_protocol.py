from __future__ import annotations

import json
import os
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, TextIO

from humungousaur.config import AgentConfig
from humungousaur.orchestrator import AgentOrchestrator
from humungousaur.safety.audit import AuditLog
from humungousaur.schemas import ActionStatus, AgentRunResult
from humungousaur.tools import default_tools


CLIENT_PROTOCOL_VERSION = "2026-06-09"
SAFE_SPAWN_ENV_KEYS = ("HOME", "LANG", "LC_ALL", "PATH", "SHELL", "TMPDIR", "USER")
SESSION_ACTIVE_STATUSES = {"running", "cancelling", "awaiting_approval"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ClientProtocolSession:
    session_id: str
    created_at: str
    updated_at: str
    status: str = "idle"
    title: str = ""
    mode: str = "interactive"
    config_overrides: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    active_run_id: str | None = None
    active_turn_id: str | None = None
    last_request: str = ""
    last_response: str = ""
    last_error: str = ""
    last_activity_at: str = ""
    timeout_seconds: float | None = None


@dataclass(slots=True)
class ClientConversationBinding:
    binding_id: str
    session_id: str
    channel: str
    conversation_id: str
    gateway_id: str = ""
    user_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


def session_to_dict(session: ClientProtocolSession) -> dict[str, Any]:
    return asdict(session)


def binding_to_dict(binding: ClientConversationBinding) -> dict[str, Any]:
    return asdict(binding)


class ClientProtocolStore:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config.normalized()
        self.root = self.config.data_dir / "client_protocol"
        self.sessions_dir = self.root / "sessions"
        self.bindings_path = self.root / "bindings.json"
        self._lock = threading.RLock()
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        *,
        title: str = "",
        mode: str = "interactive",
        config_overrides: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> ClientProtocolSession:
        now = utc_now()
        session = ClientProtocolSession(
            session_id=session_id or str(uuid.uuid4()),
            created_at=now,
            updated_at=now,
            title=str(title or ""),
            mode=str(mode or "interactive"),
            config_overrides=_json_object(config_overrides),
            metadata=_json_object(metadata),
            last_activity_at=now,
        )
        self.save_session(session)
        return session

    def load_session(self, session_id: str) -> ClientProtocolSession:
        path = self._session_path(session_id)
        if not path.exists():
            raise KeyError(f"Unknown client protocol session: {session_id}")
        data = _read_json(path)
        return ClientProtocolSession(
            session_id=str(data["session_id"]),
            created_at=str(data.get("created_at") or utc_now()),
            updated_at=str(data.get("updated_at") or utc_now()),
            status=str(data.get("status") or "idle"),
            title=str(data.get("title") or ""),
            mode=str(data.get("mode") or "interactive"),
            config_overrides=_json_object(data.get("config_overrides")),
            metadata=_json_object(data.get("metadata")),
            active_run_id=_optional_string(data.get("active_run_id")),
            active_turn_id=_optional_string(data.get("active_turn_id")),
            last_request=str(data.get("last_request") or ""),
            last_response=str(data.get("last_response") or ""),
            last_error=str(data.get("last_error") or ""),
            last_activity_at=str(data.get("last_activity_at") or ""),
            timeout_seconds=_optional_float(data.get("timeout_seconds")),
        )

    def save_session(self, session: ClientProtocolSession) -> ClientProtocolSession:
        with self._lock:
            updated = replace(session, updated_at=utc_now())
            self._write_json(self._session_path(updated.session_id), session_to_dict(updated))
            return updated

    def update_session(
        self,
        session_id: str,
        *,
        title: str | None = None,
        mode: str | None = None,
        config_overrides: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> ClientProtocolSession:
        session = self.load_session(session_id)
        merged_metadata = dict(session.metadata)
        if metadata:
            merged_metadata.update(_json_object(metadata))
        merged_config = dict(session.config_overrides)
        if config_overrides:
            merged_config.update(_json_object(config_overrides))
        return self.save_session(
            replace(
                session,
                title=session.title if title is None else str(title),
                mode=session.mode if mode is None else str(mode),
                config_overrides=merged_config,
                metadata=merged_metadata,
                status=session.status if status is None else str(status),
                last_activity_at=utc_now(),
            )
        )

    def bind_conversation(
        self,
        session_id: str,
        *,
        channel: str,
        conversation_id: str,
        gateway_id: str = "",
        user_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ClientConversationBinding:
        self.load_session(session_id)
        bindings = self.load_bindings()
        channel_key = str(channel or "").strip()
        conversation_key = str(conversation_id or "").strip()
        if not channel_key or not conversation_key:
            raise ValueError("channel and conversation_id are required.")
        existing = next(
            (
                binding
                for binding in bindings
                if binding.session_id == session_id
                and binding.channel == channel_key
                and binding.conversation_id == conversation_key
            ),
            None,
        )
        now = utc_now()
        if existing is None:
            binding = ClientConversationBinding(
                binding_id=str(uuid.uuid4()),
                session_id=session_id,
                channel=channel_key,
                conversation_id=conversation_key,
                gateway_id=str(gateway_id or ""),
                user_id=str(user_id or ""),
                metadata=_json_object(metadata),
                created_at=now,
                updated_at=now,
            )
            bindings.append(binding)
        else:
            binding = replace(
                existing,
                gateway_id=str(gateway_id or existing.gateway_id),
                user_id=str(user_id or existing.user_id),
                metadata={**existing.metadata, **_json_object(metadata)},
                updated_at=now,
            )
            bindings = [binding if item.binding_id == binding.binding_id else item for item in bindings]
        self.save_bindings(bindings)
        return binding

    def load_bindings(self) -> list[ClientConversationBinding]:
        if not self.bindings_path.exists():
            return []
        data = _read_json(self.bindings_path)
        raw_bindings = data.get("bindings", []) if isinstance(data, dict) else data
        if not isinstance(raw_bindings, list):
            return []
        bindings: list[ClientConversationBinding] = []
        for item in raw_bindings:
            if not isinstance(item, dict):
                continue
            try:
                bindings.append(
                    ClientConversationBinding(
                        binding_id=str(item["binding_id"]),
                        session_id=str(item["session_id"]),
                        channel=str(item["channel"]),
                        conversation_id=str(item["conversation_id"]),
                        gateway_id=str(item.get("gateway_id") or ""),
                        user_id=str(item.get("user_id") or ""),
                        metadata=_json_object(item.get("metadata")),
                        created_at=str(item.get("created_at") or utc_now()),
                        updated_at=str(item.get("updated_at") or utc_now()),
                    )
                )
            except KeyError:
                continue
        return bindings

    def save_bindings(self, bindings: list[ClientConversationBinding]) -> None:
        self._write_json(self.bindings_path, {"bindings": [binding_to_dict(binding) for binding in bindings]})

    def bindings_for_session(self, session_id: str) -> list[ClientConversationBinding]:
        return [binding for binding in self.load_bindings() if binding.session_id == session_id]

    def recover_active_turns(self, *, reason: str = "Runtime restarted before the turn completed.") -> list[dict[str, Any]]:
        recovered: list[dict[str, Any]] = []
        audit = AuditLog(self.config.audit_db_path)
        for path in sorted(self.sessions_dir.glob("*.json")):
            session = self.load_session(path.stem)
            if session.status not in SESSION_ACTIVE_STATUSES:
                continue
            run_id = session.active_run_id
            if run_id:
                run = audit.get_run(run_id)
                if run and not run.get("finished_at"):
                    try:
                        audit.request_cancel_run(run_id, reason)
                    except KeyError:
                        pass
            updated = self.save_session(
                replace(
                    session,
                    status="interrupted",
                    active_run_id=None,
                    active_turn_id=None,
                    last_error=reason,
                    last_activity_at=utc_now(),
                )
            )
            recovered.append(session_to_dict(updated))
        return recovered

    def _session_path(self, session_id: str) -> Path:
        cleaned = _clean_id(session_id, "session_id")
        return self.sessions_dir / f"{cleaned}.json"

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        temp.replace(path)


class ClientProtocolService:
    def __init__(
        self,
        config: AgentConfig,
        *,
        runner: Callable[[AgentConfig, str, str, Callable[[], bool], bool], AgentRunResult] | None = None,
    ) -> None:
        self.config = config.normalized()
        self.store = ClientProtocolStore(self.config)
        self.audit = AuditLog(self.config.audit_db_path)
        self._runner = runner or _run_agent

    def identity(self) -> dict[str, Any]:
        tools = default_tools(self.config)
        return {
            "agent": "Humungousaur",
            "protocol": "client_protocol",
            "protocol_version": CLIENT_PROTOCOL_VERSION,
            "workspace": str(self.config.workspace),
            "data_dir": str(self.config.data_dir),
            "tool_count": len(tools),
            "capabilities": [
                "session_lifecycle",
                "prompt_runs",
                "run_cancellation",
                "approval_events",
                "conversation_bindings",
                "startup_recovery",
                "sanitized_spawn_environment",
            ],
        }

    def handle(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = _json_object(params)
        if method in {"initialize", "identity"}:
            return self.identity()
        if method == "session/new":
            session = self.store.create_session(
                title=str(payload.get("title") or ""),
                mode=str(payload.get("mode") or "interactive"),
                config_overrides=_json_object(payload.get("config")),
                metadata=_json_object(payload.get("metadata")),
                session_id=_optional_string(payload.get("session_id")),
            )
            return {"session": session_to_dict(session)}
        if method == "session/load":
            session = self.store.load_session(str(payload["session_id"]))
            return self._session_payload(session)
        if method == "session/update":
            session = self.store.update_session(
                str(payload["session_id"]),
                title=_optional_string(payload.get("title")),
                mode=_optional_string(payload.get("mode")),
                config_overrides=_json_object(payload.get("config")),
                metadata=_json_object(payload.get("metadata")),
                status=_optional_string(payload.get("status")),
            )
            return self._session_payload(session)
        if method == "session/prompt":
            return self.prompt(
                str(payload["session_id"]),
                str(payload.get("prompt") or ""),
                approve_high_risk=bool(payload.get("approve_high_risk", False)),
                timeout_seconds=_optional_float(payload.get("timeout_seconds")),
            )
        if method == "session/cancel":
            return self.cancel_session(str(payload["session_id"]), reason=str(payload.get("reason") or "Cancelled by client."))
        if method == "session/status":
            session = self.store.load_session(str(payload["session_id"]))
            return self._session_payload(
                session,
                after_event_id=int(payload.get("after_event_id", 0) or 0),
                event_limit=int(payload.get("event_limit", 100) or 100),
            )
        if method == "session/bind":
            binding = self.store.bind_conversation(
                str(payload["session_id"]),
                channel=str(payload.get("channel") or ""),
                conversation_id=str(payload.get("conversation_id") or ""),
                gateway_id=str(payload.get("gateway_id") or ""),
                user_id=str(payload.get("user_id") or ""),
                metadata=_json_object(payload.get("metadata")),
            )
            return {"binding": binding_to_dict(binding)}
        if method == "env/prepare":
            return prepare_spawn_environment(
                base_env=os.environ,
                passthrough=_string_list(payload.get("passthrough")),
                extra_env=_json_object(payload.get("extra_env")),
            )
        if method == "recover":
            return {"sessions": self.store.recover_active_turns(reason=str(payload.get("reason") or "Client protocol recovery."))}
        raise KeyError(f"Unsupported client protocol method: {method}")

    def prompt(
        self,
        session_id: str,
        prompt: str,
        *,
        approve_high_risk: bool = False,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        if not prompt.strip():
            raise ValueError("prompt is required.")
        session = self.store.load_session(session_id)
        request_config = _config_with_overrides(self.config, session.config_overrides)
        run_id = str(uuid.uuid4())
        turn_id = str(uuid.uuid4())
        self.audit.start_run(prompt, run_id=run_id)
        started = self.store.save_session(
            replace(
                session,
                status="running",
                active_run_id=run_id,
                active_turn_id=turn_id,
                last_request=prompt,
                last_error="",
                last_activity_at=utc_now(),
                timeout_seconds=timeout_seconds,
            )
        )
        self.audit.log_run_event(run_id, "client_turn_started", "Client protocol turn started.", {"session_id": session_id, "turn_id": turn_id})
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(
            self._runner,
            request_config,
            prompt,
            run_id,
            lambda: self.audit.is_run_cancel_requested(run_id),
            approve_high_risk,
        )
        try:
            result = future.result(timeout=timeout_seconds)
        except TimeoutError:
            self.audit.request_cancel_run(run_id, f"Timed out after {timeout_seconds} seconds.")
            self.audit.log_run_event(
                run_id,
                "client_turn_timed_out",
                "Client protocol turn timed out.",
                {"session_id": session_id, "turn_id": turn_id, "timeout_seconds": timeout_seconds},
            )
            updated = self.store.save_session(
                replace(
                    started,
                    status="timeout",
                    active_run_id=run_id,
                    active_turn_id=turn_id,
                    last_error=f"Timed out after {timeout_seconds} seconds.",
                    last_activity_at=utc_now(),
                )
            )
            executor.shutdown(wait=False, cancel_futures=True)
            return {
                "session": session_to_dict(updated),
                "run": self.audit.get_run(run_id),
                "events": self.audit.get_run_events(run_id),
                "timed_out": True,
            }
        except Exception as exc:
            self.audit.finish_run(run_id, ActionStatus.FAILED, str(exc))
            self.audit.log_run_event(run_id, "client_turn_failed", "Client protocol turn failed.", {"session_id": session_id, "turn_id": turn_id, "error": str(exc)})
            updated = self.store.save_session(
                replace(
                    started,
                    status="failed",
                    active_run_id=None,
                    active_turn_id=None,
                    last_error=str(exc),
                    last_activity_at=utc_now(),
                )
            )
            executor.shutdown(wait=False, cancel_futures=True)
            return {"session": session_to_dict(updated), "run": self.audit.get_run(run_id), "error": str(exc)}
        finally:
            if future.done():
                executor.shutdown(wait=False, cancel_futures=True)
        status = _session_status_from_result(result)
        updated = self.store.save_session(
            replace(
                started,
                status=status,
                active_run_id=None if status not in {"awaiting_approval", "cancelling"} else run_id,
                active_turn_id=None if status not in {"awaiting_approval", "cancelling"} else turn_id,
                last_response=result.final_response,
                last_error="",
                last_activity_at=utc_now(),
            )
        )
        self.audit.log_run_event(
            run_id,
            "client_turn_finished",
            f"Client protocol turn finished with session status {status}.",
            {"session_id": session_id, "turn_id": turn_id, "status": status},
        )
        return {
            "session": session_to_dict(updated),
            "run": _run_result_to_dict(result),
            "audit_run": self.audit.get_run(run_id),
            "events": self.audit.get_run_events(run_id),
            "timed_out": False,
        }

    def cancel_session(self, session_id: str, *, reason: str = "Cancelled by client.") -> dict[str, Any]:
        session = self.store.load_session(session_id)
        if not session.active_run_id:
            updated = self.store.save_session(replace(session, status="idle", last_activity_at=utc_now()))
            return {"session": session_to_dict(updated), "cancelled": False, "reason": "No active run is bound to this session."}
        try:
            run = self.audit.request_cancel_run(session.active_run_id, reason)
        except KeyError:
            run = None
        updated = self.store.save_session(replace(session, status="cancelling", last_error=reason, last_activity_at=utc_now()))
        return {"session": session_to_dict(updated), "cancelled": True, "run": run}

    def _session_payload(
        self,
        session: ClientProtocolSession,
        *,
        after_event_id: int = 0,
        event_limit: int = 100,
    ) -> dict[str, Any]:
        run_id = session.active_run_id
        events = self.audit.get_run_events(run_id, after_id=max(0, after_event_id), limit=max(1, min(event_limit, 500))) if run_id else []
        audit_run = self.audit.get_run(run_id) if run_id else None
        return {
            "session": session_to_dict(session),
            "run": audit_run,
            "events": events,
            "bindings": [binding_to_dict(binding) for binding in self.store.bindings_for_session(session.session_id)],
        }


def prepare_spawn_environment(
    *,
    base_env: dict[str, str] | None = None,
    passthrough: Iterable[str] = (),
    extra_env: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = dict(base_env or {})
    requested = _string_list(list(passthrough))
    allowed_keys = set(SAFE_SPAWN_ENV_KEYS) | set(requested)
    env: dict[str, str] = {}
    included: list[str] = []
    missing: list[str] = []
    for key in sorted(allowed_keys):
        if key in source:
            env[key] = str(source[key])
            included.append(key)
        elif key in requested:
            missing.append(key)
    denied = sorted(key for key in source if key not in allowed_keys and _looks_like_secret(key))
    for key, value in _json_object(extra_env).items():
        cleaned = str(key).strip()
        if cleaned:
            env[cleaned] = str(value)
            included.append(cleaned)
    return {
        "env": env,
        "policy": {
            "safe_defaults": list(SAFE_SPAWN_ENV_KEYS),
            "explicit_passthrough": requested,
            "included": sorted(set(included)),
            "missing": missing,
            "denied_secret_like_keys": denied,
        },
    }


def run_client_protocol_stdio(config: AgentConfig, stdin: TextIO | None = None, stdout: TextIO | None = None) -> None:
    service = ClientProtocolService(config)
    input_stream = stdin or sys.stdin
    output_stream = stdout or sys.stdout
    for line in input_stream:
        if not line.strip():
            continue
        request_id: Any = None
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("Protocol message must be a JSON object.")
            request_id = request.get("id")
            result = service.handle(str(request.get("method") or ""), _json_object(request.get("params")))
            response = {"id": request_id, "ok": True, "result": result}
        except Exception as exc:
            response = {"id": request_id, "ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}}
        output_stream.write(json.dumps(response, ensure_ascii=False, sort_keys=True) + "\n")
        output_stream.flush()


def _run_agent(
    config: AgentConfig,
    prompt: str,
    run_id: str,
    is_cancel_requested: Callable[[], bool],
    approve_high_risk: bool,
) -> AgentRunResult:
    return AgentOrchestrator(config).run(
        prompt,
        run_id=run_id,
        is_cancel_requested=is_cancel_requested,
        approve_high_risk=approve_high_risk,
    )


def _config_with_overrides(config: AgentConfig, overrides: dict[str, Any]) -> AgentConfig:
    if not overrides:
        return config.normalized()
    values = {
        "workspace": Path(str(overrides.get("workspace", config.workspace))),
        "data_dir": Path(str(overrides.get("data_dir", config.data_dir))),
        "dry_run": bool(overrides.get("dry_run", config.dry_run)),
        "planner_provider": str(overrides.get("planner", overrides.get("planner_provider", config.planner_provider))),
        "model_provider": str(overrides.get("model_provider", config.model_provider)),
        "model_name": str(overrides.get("model", overrides.get("model_name", config.model_name))),
        "model_base_url": overrides.get("model_base_url", config.model_base_url),
        "model_api_key_env": overrides.get("model_api_key_env", config.model_api_key_env),
        "model_timeout_seconds": float(overrides.get("model_timeout_seconds", config.model_timeout_seconds)),
        "runtime_secrets": {**dict(config.runtime_secrets or {}), **_json_object(overrides.get("runtime_secrets"))},
        "allowed_read_roots": config.allowed_read_roots,
        "allowed_write_roots": config.allowed_write_roots,
    }
    return AgentConfig(**values).normalized()


def _run_result_to_dict(result: AgentRunResult) -> dict[str, Any]:
    return asdict(result)


def _session_status_from_result(result: AgentRunResult) -> str:
    if result.approvals:
        return "awaiting_approval"
    statuses = {item.status for item in result.results}
    if ActionStatus.CANCELLED in statuses:
        return "cancelled"
    if ActionStatus.NEEDS_APPROVAL in statuses:
        return "awaiting_approval"
    if statuses and all(status == ActionStatus.SUCCEEDED for status in statuses):
        return "idle"
    if ActionStatus.FAILED in statuses or ActionStatus.BLOCKED in statuses:
        return "failed"
    return "idle"


def _json_object(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list | tuple | set):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _optional_string(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _clean_id(value: str, field_name: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned or any(char in cleaned for char in "/\\:"):
        raise ValueError(f"Invalid {field_name}: {value}")
    return cleaned


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object at {path}.")
    return data


def _looks_like_secret(key: str) -> bool:
    upper = key.upper()
    return any(marker in upper for marker in ("API_KEY", "AUTH", "CREDENTIAL", "PASSWORD", "SECRET", "TOKEN"))
