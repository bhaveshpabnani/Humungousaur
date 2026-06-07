from __future__ import annotations

from dataclasses import asdict, is_dataclass, replace
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.executor import Executor
from humungousaur.memory.event_store import EventStore
from humungousaur.safety.approvals import ApprovalRecord, ApprovalStore
from humungousaur.safety.audit import AuditLog
from humungousaur.safety.policy import PolicyEngine
from humungousaur.schemas import ActionStatus, PlannedStep
from humungousaur.tools import default_tools
from humungousaur.tools.validation import validate_tool_input


def approval_record_to_dict(record: ApprovalRecord) -> dict[str, Any]:
    return asdict(record) if is_dataclass(record) else dict(record)


def approve_pending_action(config: AgentConfig, approval_token: str, note: str) -> dict[str, Any]:
    approval_store = ApprovalStore(config.approvals_db_path)
    record = approval_store.get(approval_token)
    if record is None:
        raise KeyError(f"Unknown approval token: {approval_token}")
    if record.status != "pending":
        raise ValueError(f"Approval token is not pending: {approval_token} ({record.status})")

    audit = AuditLog(config.audit_db_path)
    memory = EventStore(config.memory_db_path)
    executor = Executor(default_tools(config), PolicyEngine())
    run_id = record.run_id
    audit.log_run_event(
        run_id,
        "approval_approved",
        f"Approval granted for {record.tool_name}.",
        {"approval_token": approval_token, "note": note},
    )
    step = PlannedStep(record.tool_name, record.tool_input, f"Approved replay of {record.run_id}", "approval-replay")
    audit.log_run_event(
        run_id,
        "action_started",
        f"Starting approved {record.tool_name}.",
        {"tool_name": record.tool_name, "tool_input": record.tool_input, "approval_token": approval_token},
    )
    tool_result = executor.execute(step, config, approved=True)
    audit.log_action(run_id, step.tool_input, tool_result)
    audit.log_run_event(
        run_id,
        "action_finished",
        f"{record.tool_name} {tool_result.status.value}.",
        {"tool_name": record.tool_name, "status": tool_result.status.value, "summary": tool_result.summary},
    )
    status = ActionStatus.SUCCEEDED if tool_result.status == ActionStatus.SUCCEEDED else ActionStatus.FAILED
    audit.finish_run(run_id, status, tool_result.summary)
    audit.log_run_event(
        run_id,
        "run_finished",
        f"Run finished after approval with status {status.value}.",
        {"status": status.value, "approval_token": approval_token},
    )
    updated = approval_store.mark_executed(approval_token, tool_result, note=note)
    memory.append(
        "approval_decision",
        {
            "approval_token": approval_token,
            "run_id": record.run_id,
            "status": updated.status,
            "tool_name": record.tool_name,
        },
    )
    return {
        "approval": approval_record_to_dict(updated),
        "run_id": run_id,
        "summary": tool_result.summary,
        "stdout": str(tool_result.output.get("stdout", "")).strip(),
        "stderr": str(tool_result.output.get("stderr", "")).strip(),
    }


def reject_pending_action(config: AgentConfig, approval_token: str, note: str) -> dict[str, Any]:
    approval_store = ApprovalStore(config.approvals_db_path)
    record = approval_store.reject(approval_token, note=note)
    audit = AuditLog(config.audit_db_path)
    memory = EventStore(config.memory_db_path)
    final_response = f"Approval rejected for {record.tool_name}; the requested action was not executed."
    audit.log_run_event(
        record.run_id,
        "approval_rejected",
        f"Approval rejected for {record.tool_name}.",
        {"approval_token": approval_token, "note": note},
    )
    audit.finish_run(record.run_id, ActionStatus.BLOCKED, final_response)
    audit.log_run_event(
        record.run_id,
        "run_finished",
        "Run finished because a required approval was rejected.",
        {"status": ActionStatus.BLOCKED.value, "approval_token": approval_token},
    )
    memory.append(
        "approval_decision",
        {
            "approval_token": approval_token,
            "run_id": record.run_id,
            "status": record.status,
            "tool_name": record.tool_name,
        },
    )
    return {
        "approval": approval_record_to_dict(record),
        "run_id": record.run_id,
        "summary": final_response,
    }


def update_pending_approval_input(
    config: AgentConfig,
    approval_token: str,
    tool_input: dict[str, Any],
    note: str,
) -> dict[str, Any]:
    approval_store = ApprovalStore(config.approvals_db_path)
    record = approval_store.get(approval_token)
    if record is None:
        raise KeyError(f"Unknown approval token: {approval_token}")
    if record.status != "pending":
        raise ValueError(f"Approval token is not pending: {approval_token} ({record.status})")
    tools = default_tools(config)
    tool = tools.get(record.tool_name)
    if tool is None:
        raise ValueError(f"Unknown approval tool: {record.tool_name}")
    validate_tool_input(tool_input, tool.input_schema)
    updated = approval_store.update_tool_input(approval_token, tool_input, note=note)
    audit = AuditLog(config.audit_db_path)
    memory = EventStore(config.memory_db_path)
    audit.log_run_event(
        updated.run_id,
        "approval_updated",
        f"Approval input updated for {updated.tool_name}.",
        {"approval_token": approval_token, "tool_name": updated.tool_name, "tool_input": updated.tool_input, "note": note},
    )
    memory.append(
        "approval_update",
        {
            "approval_token": approval_token,
            "run_id": updated.run_id,
            "tool_name": updated.tool_name,
        },
    )
    return {
        "approval": approval_record_to_dict(updated),
        "run_id": updated.run_id,
        "summary": f"Approval input updated for {updated.tool_name}.",
    }


def request_config(base: AgentConfig, payload: dict[str, Any]) -> AgentConfig:
    try:
        model_timeout_seconds = float(payload.get("model_timeout_seconds", base.model_timeout_seconds))
    except (TypeError, ValueError):
        model_timeout_seconds = base.model_timeout_seconds
    runtime_secrets = _runtime_secrets(payload)
    return replace(
        base,
        dry_run=bool(payload.get("dry_run", base.dry_run)),
        planner_provider=str(payload.get("planner", base.planner_provider)),
        model_provider=str(payload.get("model_provider", base.model_provider)),
        model_name=str(payload.get("model", base.model_name)),
        model_base_url=payload.get("model_base_url", base.model_base_url),
        model_api_key_env=payload.get("model_api_key_env", base.model_api_key_env),
        model_timeout_seconds=max(0.1, min(model_timeout_seconds, 300.0)),
        runtime_secrets={**dict(base.runtime_secrets or {}), **runtime_secrets},
    ).normalized()


def _runtime_secrets(payload: dict[str, Any]) -> dict[str, str]:
    raw = payload.get("runtime_secrets", payload.get("secrets", {}))
    if not isinstance(raw, dict):
        return {}
    return {
        str(key).strip(): str(value)
        for key, value in raw.items()
        if str(key).strip() and str(value)
    }
