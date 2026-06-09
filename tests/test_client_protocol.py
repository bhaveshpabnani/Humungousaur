from __future__ import annotations

import io
import json
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from humungousaur.client_protocol import (
    ClientProtocolService,
    ClientProtocolStore,
    prepare_spawn_environment,
    run_client_protocol_stdio,
)
from humungousaur.config import AgentConfig
from humungousaur.safety.audit import AuditLog
from humungousaur.schemas import ActionStatus, AgentRunResult, RiskLevel, ToolResult


def test_client_protocol_identity_and_session_lifecycle() -> None:
    with TemporaryDirectory() as td:
        config = _config(Path(td))
        service = ClientProtocolService(config)

        identity = service.handle("initialize", {})
        assert identity["agent"] == "Humungousaur"
        assert "session_lifecycle" in identity["capabilities"]

        created = service.handle(
            "session/new",
            {"title": "Desk", "mode": "focused", "metadata": {"channel": "cli"}},
        )["session"]
        assert created["title"] == "Desk"
        assert created["mode"] == "focused"
        assert created["status"] == "idle"

        updated = service.handle(
            "session/update",
            {"session_id": created["session_id"], "title": "Desk 2", "config": {"planner": "explicit"}},
        )
        assert updated["session"]["title"] == "Desk 2"
        assert updated["session"]["config_overrides"]["planner"] == "explicit"

        loaded = service.handle("session/load", {"session_id": created["session_id"]})
        assert loaded["session"]["session_id"] == created["session_id"]


def test_client_protocol_conversation_binding_persists() -> None:
    with TemporaryDirectory() as td:
        config = _config(Path(td))
        service = ClientProtocolService(config)
        session_id = service.handle("session/new", {})["session"]["session_id"]

        binding = service.handle(
            "session/bind",
            {
                "session_id": session_id,
                "channel": "signal",
                "conversation_id": "thread-1",
                "gateway_id": "gateway-a",
                "user_id": "user-a",
            },
        )["binding"]
        assert binding["channel"] == "signal"

        reloaded = ClientProtocolStore(config).bindings_for_session(session_id)
        assert len(reloaded) == 1
        assert reloaded[0].conversation_id == "thread-1"


def test_prepare_spawn_environment_uses_safe_defaults_and_explicit_passthrough() -> None:
    prepared = prepare_spawn_environment(
        base_env={
            "PATH": "/bin",
            "HOME": "/tmp/home",
            "SECRET_TOKEN": "nope",
            "CUSTOM_KEY": "yes",
        },
        passthrough=["CUSTOM_KEY", "MISSING_KEY"],
        extra_env={"LOCAL_FLAG": "1"},
    )

    assert prepared["env"]["PATH"] == "/bin"
    assert prepared["env"]["CUSTOM_KEY"] == "yes"
    assert prepared["env"]["LOCAL_FLAG"] == "1"
    assert "SECRET_TOKEN" not in prepared["env"]
    assert "SECRET_TOKEN" in prepared["policy"]["denied_secret_like_keys"]
    assert "MISSING_KEY" in prepared["policy"]["missing"]


def test_client_protocol_prompt_runs_through_native_orchestrator() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        (root / "README.md").write_text("hello", encoding="utf-8")
        config = _config(root)
        service = ClientProtocolService(config)
        session_id = service.handle("session/new", {"config": {"planner": "explicit"}})["session"]["session_id"]

        result = service.handle("session/prompt", {"session_id": session_id, "prompt": "system_status {}"})

        assert result["session"]["status"] == "idle"
        assert result["run"]["run_id"] == result["audit_run"]["run_id"]
        assert result["run"]["results"][0]["tool_name"] == "system_status"
        assert result["timed_out"] is False
        assert any(event["event_type"] == "client_turn_finished" for event in result["events"])


def test_client_protocol_cancel_scopes_to_active_session_run() -> None:
    with TemporaryDirectory() as td:
        config = _config(Path(td))
        runner_started = threading.Event()

        def runner(
            run_config: AgentConfig,
            prompt: str,
            run_id: str,
            is_cancel_requested,
            approve_high_risk: bool,
        ) -> AgentRunResult:
            runner_started.set()
            deadline = time.time() + 2.0
            while time.time() < deadline and not is_cancel_requested():
                time.sleep(0.01)
            status = ActionStatus.CANCELLED if is_cancel_requested() else ActionStatus.SUCCEEDED
            AuditLog(run_config.audit_db_path).finish_run(run_id, status, status.value)
            return AgentRunResult(
                run_id=run_id,
                request=prompt,
                final_response=status.value,
                results=[ToolResult("wait", status, RiskLevel.LOW, status.value)],
            )

        service = ClientProtocolService(config, runner=runner)
        session_id = service.handle("session/new", {})["session"]["session_id"]
        prompt_result: dict[str, object] = {}

        thread = threading.Thread(
            target=lambda: prompt_result.update(
                service.handle("session/prompt", {"session_id": session_id, "prompt": "wait"})
            )
        )
        thread.start()
        assert runner_started.wait(1.0)
        cancel_result = service.handle("session/cancel", {"session_id": session_id, "reason": "test cancel"})
        thread.join(2.0)

        assert cancel_result["cancelled"] is True
        assert prompt_result["session"]["status"] == "cancelled"
        assert prompt_result["run"]["results"][0]["status"] == "cancelled"


def test_client_protocol_recovery_marks_active_sessions_interrupted() -> None:
    with TemporaryDirectory() as td:
        config = _config(Path(td))
        store = ClientProtocolStore(config)
        session = store.create_session()
        run_id = AuditLog(config.audit_db_path).start_run("unfinished")
        store.save_session(
            store.update_session(session.session_id, status="running")
        )
        running = store.load_session(session.session_id)
        store.save_session(
            type(running)(
                **{
                    **{
                        "session_id": running.session_id,
                        "created_at": running.created_at,
                        "updated_at": running.updated_at,
                        "status": running.status,
                        "title": running.title,
                        "mode": running.mode,
                        "config_overrides": running.config_overrides,
                        "metadata": running.metadata,
                        "active_run_id": run_id,
                        "active_turn_id": "turn-1",
                        "last_request": running.last_request,
                        "last_response": running.last_response,
                        "last_error": running.last_error,
                        "last_activity_at": running.last_activity_at,
                        "timeout_seconds": running.timeout_seconds,
                    }
                }
            )
        )

        recovered = store.recover_active_turns(reason="restart")

        assert len(recovered) == 1
        assert recovered[0]["status"] == "interrupted"
        assert store.load_session(session.session_id).active_run_id is None
        assert AuditLog(config.audit_db_path).get_run(run_id)["status"] == "cancelling"


def test_client_protocol_stdio_jsonl_round_trip() -> None:
    with TemporaryDirectory() as td:
        config = _config(Path(td))
        stdin = io.StringIO(
            json.dumps({"id": 1, "method": "initialize", "params": {}})
            + "\n"
            + json.dumps({"id": 2, "method": "session/new", "params": {"title": "stdio"}})
            + "\n"
        )
        stdout = io.StringIO()

        run_client_protocol_stdio(config, stdin=stdin, stdout=stdout)

        lines = [json.loads(line) for line in stdout.getvalue().splitlines()]
        assert lines[0]["ok"] is True
        assert lines[0]["result"]["agent"] == "Humungousaur"
        assert lines[1]["ok"] is True
        assert lines[1]["result"]["session"]["title"] == "stdio"


def _config(root: Path) -> AgentConfig:
    return AgentConfig(workspace=root, data_dir=root / "artifacts", planner_provider="explicit").normalized()
