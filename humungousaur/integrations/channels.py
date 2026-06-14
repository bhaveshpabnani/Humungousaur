from __future__ import annotations

from datetime import datetime, timezone
import base64
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any
from urllib import parse, request
import uuid

from humungousaur.config import AgentConfig
from humungousaur.env import load_workspace_environment


CHANNEL_CATALOG_PATH = Path(__file__).resolve().parents[1] / "resources" / "channel_catalog.json"
CHANNEL_OUTBOX_LIMIT = 100
CHANNEL_STATE_FILENAME = "channel_setups.json"
BOT_LOOP_STATE_FILENAME = "bot_loop_events.json"
BOT_LOOP_DEFAULTS = {
    "max_events_per_window": 20,
    "window_seconds": 60,
    "cooldown_seconds": 60,
}


def load_channel_catalog() -> list[dict[str, Any]]:
    payload = json.loads(CHANNEL_CATALOG_PATH.read_text(encoding="utf-8"))
    channels = payload.get("channels") if isinstance(payload, dict) else None
    if not isinstance(channels, list):
        return []
    return [_normalized_channel(channel) for channel in channels if isinstance(channel, dict)]


def find_channel(channel_id: str) -> dict[str, Any] | None:
    cleaned = _clean_id(channel_id)
    if not cleaned:
        return None
    return next((channel for channel in load_channel_catalog() if channel.get("channel_id") == cleaned), None)


def channel_setup_requirements(channel_id: str) -> dict[str, Any]:
    channel = find_channel(channel_id)
    if channel is None:
        raise ValueError(f"Unknown channel_id: {channel_id}")
    setup = channel.get("setup", {})
    if not isinstance(setup, dict):
        setup = {}
    return {
        "channel_id": channel["channel_id"],
        "display_name": channel.get("display_name", channel.get("name", "")),
        "setup_kind": channel.get("setup_kind", ""),
        "runtime_adapter": channel.get("runtime_adapter", ""),
        "setup": setup,
        "delivery": channel.get("delivery", {}),
        "policies": channel.get("policies", {}),
        "runtime": channel.get("runtime", {}),
    }


def load_channel_setups(config: AgentConfig) -> dict[str, Any]:
    path = channel_setup_path(config.normalized())
    if not path.exists():
        return {"channels": {}, "updated_at": ""}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"channels": {}, "updated_at": ""}
    if not isinstance(payload, dict):
        return {"channels": {}, "updated_at": ""}
    channels = payload.get("channels")
    if not isinstance(channels, dict):
        payload["channels"] = {}
    return payload


def save_channel_setup(config: AgentConfig, channel_id: str, setup: dict[str, Any]) -> dict[str, Any]:
    normalized = config.normalized()
    channel = find_channel(channel_id)
    if channel is None:
        raise ValueError(f"Unknown channel_id: {channel_id}")
    current = load_channel_setups(normalized)
    channels = current.setdefault("channels", {})
    if not isinstance(channels, dict):
        channels = {}
        current["channels"] = channels
    record = _clean_setup_record(channel, setup)
    record["updated_at"] = datetime.now(timezone.utc).isoformat()
    channels[channel["channel_id"]] = record
    current["updated_at"] = record["updated_at"]
    path = channel_setup_path(normalized)
    path.write_text(json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def channel_setup_status(config: AgentConfig, channel_id: str | None = None) -> dict[str, Any]:
    normalized = config.normalized()
    load_workspace_environment(normalized.workspace)
    setups = load_channel_setups(normalized)
    channels = load_channel_catalog()
    if channel_id:
        cleaned = _clean_id(channel_id)
        channels = [channel for channel in channels if channel.get("channel_id") == cleaned]
    statuses = [_channel_status(normalized, channel, setups) for channel in channels]
    return {
        "channels": statuses,
        "state_path": str(channel_setup_path(normalized)),
        "prepared_outbox_dir": str(channel_outbox_dir(normalized)),
    }


def channel_doctor(config: AgentConfig, channel_id: str | None = None) -> dict[str, Any]:
    status = channel_setup_status(config, channel_id=channel_id)
    findings: list[dict[str, Any]] = []
    for item in status["channels"]:
        missing_send = item.get("missing_send_env", [])
        missing_setup = item.get("missing_setup_checks", [])
        if item.get("can_prepare"):
            findings.append(
                {
                    "channel_id": item["channel_id"],
                    "severity": "info",
                    "message": "Prepared outbox is available.",
                    "evidence": {"outbox_supported": True},
                }
            )
        if item.get("send_implemented") and not missing_send:
            findings.append(
                {
                    "channel_id": item["channel_id"],
                    "severity": "ok",
                    "message": "Direct outbound send credentials are present.",
                    "evidence": {"mode": item.get("send_mode", "")},
                }
            )
        elif item.get("send_implemented"):
            findings.append(
                {
                    "channel_id": item["channel_id"],
                    "severity": "warning",
                    "message": "Direct outbound send is implemented but credentials are missing.",
                    "evidence": {"missing_env": missing_send},
                }
            )
        if missing_setup:
            findings.append(
                {
                    "channel_id": item["channel_id"],
                    "severity": "warning",
                    "message": "Setup checks are incomplete.",
                    "evidence": {"missing_checks": missing_setup},
                }
            )
    severity_rank = {"warning": 2, "info": 1, "ok": 0}
    overall = "ok" if not any(finding["severity"] == "warning" for finding in findings) else "needs_setup"
    return {
        **status,
        "overall_status": overall,
        "findings": sorted(findings, key=lambda item: (item["channel_id"], -severity_rank.get(item["severity"], 0))),
    }


def channel_integration_smoke(
    config: AgentConfig,
    *,
    channel_ids: list[str] | None = None,
    prepare_messages: bool = True,
    dry_run_sends: bool = True,
) -> dict[str, Any]:
    from humungousaur.integrations.channel_listeners import channel_listener_status

    normalized = config.normalized()
    channels = load_channel_catalog()
    selected_ids = [_clean_id(item) for item in (channel_ids or []) if _clean_id(item)]
    if selected_ids:
        selected = set(selected_ids)
        channels = [channel for channel in channels if channel.get("channel_id") in selected]
    elif any(_saved_setup_enabled(item) for item in load_channel_setups(normalized).get("channels", {}).values() if isinstance(item, dict)):
        enabled_ids = {
            str(channel_id)
            for channel_id, setup in load_channel_setups(normalized).get("channels", {}).items()
            if isinstance(setup, dict) and _saved_setup_enabled(setup)
        }
        channels = [channel for channel in channels if channel.get("channel_id") in enabled_ids]
    else:
        priority = {"telegram", "slack", "discord", "whatsapp", "sms", "webchat", "googlechat", "msteams"}
        channels = [channel for channel in channels if channel.get("channel_id") in priority]
    status_by_id = {
        item["channel_id"]: item
        for item in channel_setup_status(normalized, channel_id=None).get("channels", [])
        if isinstance(item, dict)
    }
    listener_by_id = {
        item["channel_id"]: item
        for item in channel_listener_status(normalized).get("listeners", [])
        if isinstance(item, dict)
    }
    doctor = channel_doctor(normalized)
    findings_by_id: dict[str, list[dict[str, Any]]] = {}
    for finding in doctor.get("findings", []):
        if isinstance(finding, dict):
            findings_by_id.setdefault(str(finding.get("channel_id", "")), []).append(finding)
    setups = load_channel_setups(normalized)
    smoke_config = AgentConfig(
        workspace=normalized.workspace,
        data_dir=normalized.data_dir,
        max_file_bytes=normalized.max_file_bytes,
        max_search_results=normalized.max_search_results,
        dry_run=True,
        planner_provider=normalized.planner_provider,
        model_provider=normalized.model_provider,
        model_name=normalized.model_name,
        model_base_url=normalized.model_base_url,
        model_api_key_env=normalized.model_api_key_env,
        model_timeout_seconds=normalized.model_timeout_seconds,
        runtime_secrets=normalized.runtime_secrets,
        allowed_read_roots=normalized.allowed_read_roots,
        allowed_write_roots=normalized.allowed_write_roots,
    ).normalized()
    results = [
        _channel_smoke_result(
            normalized,
            smoke_config,
            channel,
            status_by_id.get(channel["channel_id"], {}),
            listener_by_id.get(channel["channel_id"], {}),
            findings_by_id.get(channel["channel_id"], []),
            setups,
            prepare_messages=prepare_messages,
            dry_run_sends=dry_run_sends,
        )
        for channel in channels
    ]
    ready_count = sum(1 for item in results if item.get("readiness") == "ready")
    partial_count = sum(1 for item in results if item.get("readiness") == "partial")
    blocked_count = sum(1 for item in results if item.get("readiness") == "blocked")
    overall = "ready" if results and blocked_count == 0 and partial_count == 0 else "needs_setup"
    if results and ready_count == 0 and partial_count > 0 and blocked_count == 0:
        overall = "partial"
    return {
        "overall_status": overall,
        "channel_count": len(results),
        "ready_count": ready_count,
        "partial_count": partial_count,
        "blocked_count": blocked_count,
        "prepare_messages": bool(prepare_messages),
        "dry_run_sends": bool(dry_run_sends),
        "channels": results,
        "source": "humungousaur_native_channel_smoke",
        "live_send_performed": False,
    }


def _channel_smoke_result(
    config: AgentConfig,
    smoke_config: AgentConfig,
    channel: dict[str, Any],
    status: dict[str, Any],
    listener: dict[str, Any],
    findings: list[dict[str, Any]],
    setups: dict[str, Any],
    *,
    prepare_messages: bool,
    dry_run_sends: bool,
) -> dict[str, Any]:
    channel_id = str(channel.get("channel_id", ""))
    saved = setups.get("channels", {}).get(channel_id, {}) if isinstance(setups.get("channels", {}), dict) else {}
    if not isinstance(saved, dict):
        saved = {}
    defaults = saved.get("conversation_defaults", {}) if isinstance(saved.get("conversation_defaults", {}), dict) else {}
    conversation_id = str(defaults.get("conversation_id") or _smoke_conversation_id(channel))
    text = f"Humungousaur channel integration smoke for {channel.get('display_name', channel_id)}. This message was not sent."
    prepared: dict[str, Any] | None = None
    prepare_error = ""
    if prepare_messages:
        try:
            prepared = prepare_outbound_message(
                config,
                channel_id=channel_id,
                conversation_id=conversation_id,
                text=text,
                metadata={"source": "channel_integration_smoke", "dry_run": True},
                reason="Verify desktop/channel integration envelope preparation without sending.",
            )
        except Exception as exc:
            prepare_error = str(exc)
    dry_run: dict[str, Any] | None = None
    dry_run_error = ""
    if dry_run_sends:
        try:
            dry_run = send_outbound_message(
                smoke_config,
                channel_id=channel_id,
                conversation_id=conversation_id,
                text=text,
                metadata={"source": "channel_integration_smoke", "dry_run": True},
                reason="Verify approval-gated send path in dry-run mode.",
            )
        except Exception as exc:
            dry_run_error = str(exc)
    missing_credentials = list(status.get("missing_send_env", [])) if isinstance(status.get("missing_send_env", []), list) else []
    listener_missing = list(listener.get("missing_env", [])) if isinstance(listener.get("missing_env", []), list) else []
    send_implemented = bool(status.get("send_implemented", False))
    send_ready = bool(status.get("ready_for_send", False))
    listener_required = bool(channel.get("runtime", {}).get("listener_required_for_inbound", False)) if isinstance(channel.get("runtime", {}), dict) else False
    listener_ready = bool(listener.get("ready", False))
    prepare_ok = not prepare_messages or (prepared is not None and prepared.get("status") == "prepared_not_sent")
    dry_run_ok = not dry_run_sends or (dry_run is not None and dry_run.get("status") == "dry_run_not_sent")
    if prepare_ok and dry_run_ok and ((not send_implemented) or send_ready) and ((not listener_required) or listener_ready):
        readiness = "ready"
    elif prepare_ok and dry_run_ok:
        readiness = "partial"
    else:
        readiness = "blocked"
    blockers = []
    if prepare_error:
        blockers.append({"kind": "prepare_error", "detail": prepare_error})
    if dry_run_error:
        blockers.append({"kind": "dry_run_error", "detail": dry_run_error})
    if missing_credentials:
        blockers.append({"kind": "missing_send_credentials", "detail": missing_credentials})
    if listener_missing:
        blockers.append({"kind": "missing_listener_credentials", "detail": listener_missing})
    if listener_required and not listener_ready:
        blockers.append({"kind": "listener_not_ready", "detail": listener.get("listener_mode", "")})
    return {
        "channel_id": channel_id,
        "display_name": channel.get("display_name", channel.get("name", "")),
        "readiness": readiness,
        "conversation_id": conversation_id,
        "setup_enabled": bool(saved.get("enabled", False)),
        "prepared_outbox_ready": prepare_ok,
        "prepared_message_id": prepared.get("message_id", "") if prepared else "",
        "dry_run_send_ready": dry_run_ok,
        "dry_run_message_id": dry_run.get("message_id", "") if dry_run else "",
        "direct_send_implemented": send_implemented,
        "direct_send_ready": send_ready,
        "send_mode": status.get("send_mode", ""),
        "missing_send_env": missing_credentials,
        "listener_required": listener_required,
        "listener_ready": listener_ready,
        "listener_mode": listener.get("listener_mode", ""),
        "webhook_path": listener.get("webhook_path", ""),
        "missing_listener_env": listener_missing,
        "doctor_findings": findings,
        "blockers": blockers,
    }


def _saved_setup_enabled(setup: dict[str, Any]) -> bool:
    return bool(setup.get("enabled", False))


def _smoke_conversation_id(channel: dict[str, Any]) -> str:
    target = str(_official_send_contract(channel).get("target", "conversation_id"))
    if target == "env_webhook":
        return "configured-webhook"
    channel_id = str(channel.get("channel_id", "channel"))
    if channel_id == "sms":
        return "+15555550100"
    if channel_id == "whatsapp":
        return "+15555550100"
    return f"{channel_id}-smoke-conversation"


def prepare_outbound_message(
    config: AgentConfig,
    *,
    channel_id: str,
    conversation_id: str,
    text: str,
    media_paths: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    reason: str = "",
    status: str = "prepared_not_sent",
) -> dict[str, Any]:
    normalized = config.normalized()
    channel = find_channel(channel_id)
    if channel is None:
        raise ValueError(f"Unknown channel_id: {channel_id}")
    if not conversation_id.strip():
        raise ValueError("conversation_id is required for channel message preparation.")
    if not text.strip() and not media_paths:
        raise ValueError("Channel message preparation requires text or media paths.")
    media = _media_payload(channel, text, media_paths or [])
    message_id = f"channel-message-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    payload = {
        "message_id": message_id,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "channel_id": channel["channel_id"],
        "channel_name": channel.get("display_name", channel.get("name", "")),
        "conversation_id": conversation_id.strip(),
        "text": text,
        "media_paths": [str(item) for item in (media_paths or [])],
        "media": media,
        "metadata": metadata if isinstance(metadata, dict) else {},
        "reason": reason,
        "delivery": {
            "requires_trusted_runtime": True,
            "plugin_status": channel.get("plugin_status", ""),
            "runtime_adapter": channel.get("runtime_adapter", ""),
            "transport": channel.get("transport", ""),
            "official_send": _official_send_contract(channel),
        },
        "rendering_hints": _rendering_hints(channel, text),
        "delivery_hints": _delivery_hints(channel),
    }
    outbox_dir = channel_outbox_dir(normalized)
    path = outbox_dir / f"{message_id}.json"
    _write_message(path, payload)
    payload["path"] = str(path)
    return payload


def prepare_channel_action(
    config: AgentConfig,
    *,
    channel_id: str,
    conversation_id: str,
    action_type: str,
    target_message_id: str = "",
    text: str = "",
    media_paths: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    reason: str = "",
) -> dict[str, Any]:
    normalized = config.normalized()
    channel = find_channel(channel_id)
    if channel is None:
        raise ValueError(f"Unknown channel_id: {channel_id}")
    action_type = _clean_action_type(action_type)
    if action_type not in _supported_action_types(channel):
        raise ValueError(f"Channel action '{action_type}' is not supported for {channel['channel_id']}.")
    if not conversation_id.strip():
        raise ValueError("conversation_id is required for channel action preparation.")
    if action_type in {"reaction_add", "reaction_remove", "pin", "unpin", "thread_reply"} and not target_message_id.strip():
        raise ValueError(f"target_message_id is required for {action_type}.")
    if action_type in {"thread_reply", "file_share"} and not text.strip() and not media_paths:
        raise ValueError(f"{action_type} requires text or media paths.")
    action_id = f"channel-action-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    payload = {
        "action_id": action_id,
        "status": "prepared_not_sent",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "channel_id": channel["channel_id"],
        "channel_name": channel.get("display_name", channel.get("name", "")),
        "conversation_id": conversation_id.strip(),
        "action_type": action_type,
        "target_message_id": target_message_id.strip(),
        "text": text,
        "media_paths": [str(item) for item in (media_paths or [])],
        "metadata": metadata if isinstance(metadata, dict) else {},
        "reason": reason,
        "requires_approval": True,
        "delivery": {
            "requires_trusted_runtime": True,
            "plugin_status": channel.get("plugin_status", ""),
            "runtime_adapter": channel.get("runtime_adapter", ""),
            "transport": channel.get("transport", ""),
            "direct_adapter_implemented": False,
        },
        "capability_hints": _channel_action_hints(channel),
    }
    path = channel_outbox_dir(normalized) / f"{action_id}.json"
    _write_message(path, payload)
    payload["path"] = str(path)
    return payload


def send_outbound_message(
    config: AgentConfig,
    *,
    channel_id: str,
    conversation_id: str,
    text: str,
    media_paths: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    reason: str = "",
) -> dict[str, Any]:
    normalized = config.normalized()
    load_workspace_environment(normalized.workspace)
    message = prepare_outbound_message(
        normalized,
        channel_id=channel_id,
        conversation_id=conversation_id,
        text=text,
        media_paths=media_paths,
        metadata=metadata,
        reason=reason,
        status="send_requested",
    )
    path = Path(message["path"])
    if normalized.dry_run:
        message["status"] = "dry_run_not_sent"
        message["delivery"]["sent"] = False
        message["delivery"]["dry_run"] = True
        message["updated_at"] = datetime.now(timezone.utc).isoformat()
        _write_message(path, message)
        return message
    channel = find_channel(channel_id)
    if channel is None:
        raise ValueError(f"Unknown channel_id: {channel_id}")
    contract = _official_send_contract(channel)
    if not contract.get("implemented", False):
        message["status"] = "blocked_no_direct_sender"
        message["delivery"]["sent"] = False
        message["delivery"]["block_reason"] = "This channel currently supports prepared outbox envelopes only."
        message["updated_at"] = datetime.now(timezone.utc).isoformat()
        _write_message(path, message)
        return message
    missing = _missing_env(normalized, contract.get("required_env", []))
    if missing:
        message["status"] = "blocked_missing_credentials"
        message["delivery"]["sent"] = False
        message["delivery"]["missing_env"] = missing
        message["updated_at"] = datetime.now(timezone.utc).isoformat()
        _write_message(path, message)
        return message
    try:
        response = _send_via_official_adapter(normalized, channel, message)
    except Exception as exc:
        message["status"] = "send_failed"
        message["delivery"]["sent"] = False
        message["delivery"]["error"] = str(exc)
        message["updated_at"] = datetime.now(timezone.utc).isoformat()
        _write_message(path, message)
        return message
    message["status"] = "sent"
    message["delivery"]["sent"] = True
    message["delivery"]["provider_response"] = response
    message["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_message(path, message)
    return message


def list_outbox(config: AgentConfig, limit: int = 20) -> list[dict[str, Any]]:
    outbox = channel_outbox_dir(config.normalized())
    if not outbox.exists():
        return []
    messages: list[dict[str, Any]] = []
    paths = list(outbox.glob("channel-message-*.json")) + list(outbox.glob("channel-action-*.json"))
    for path in sorted(paths, key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        item_type = "action" if str(payload.get("action_id", "")).startswith("channel-action-") else "message"
        messages.append(
            {
                "item_type": item_type,
                "message_id": payload.get("message_id", payload.get("action_id", path.stem)),
                "action_id": payload.get("action_id", ""),
                "action_type": payload.get("action_type", ""),
                "status": payload.get("status", ""),
                "created_at": payload.get("created_at", ""),
                "updated_at": payload.get("updated_at", ""),
                "channel_id": payload.get("channel_id", ""),
                "channel_name": payload.get("channel_name", ""),
                "conversation_id": payload.get("conversation_id", ""),
                "text": str(payload.get("text", ""))[:500],
                "text_preview": str(payload.get("text", ""))[:240],
                "media_count": len(payload.get("media", [])) if isinstance(payload.get("media"), list) else 0,
                "path": str(path),
            }
        )
        if len(messages) >= max(1, min(limit, CHANNEL_OUTBOX_LIMIT)):
            break
    return messages


def handle_channel_inbound(
    payload: dict[str, Any],
    config: AgentConfig,
    *,
    response_mode: str | None = None,
    approve_high_risk: bool = False,
) -> dict[str, Any]:
    channel_id = _clean_id(payload.get("channel_id"))
    channel = find_channel(channel_id)
    if channel is None:
        raise ValueError(f"Unknown channel_id: {channel_id or '<empty>'}")
    preflight = _inbound_preflight(payload, channel, config.normalized())
    if preflight["ignored"]:
        return {
            "channel": channel,
            "ignored": True,
            "ignore_reason": preflight["reason"],
            "policy": preflight,
            "prepared_reply": None,
            "harness": None,
            "stimulus": None,
        }
    text = str(payload.get("text", "")).strip()
    if not text:
        raise ValueError("Inbound channel message text is required.")
    conversation_id = str(payload.get("conversation_id") or "").strip()
    if not conversation_id:
        raise ValueError("conversation_id is required.")
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    from dataclasses import asdict

    from humungousaur.interaction import InteractionHarness, Stimulus, harness_result_to_dict

    ambient = bool(preflight["ambient"])
    requires_response = bool(payload.get("requires_response", False)) and not ambient
    message_tool_allowed = bool(payload.get("message_tool_allowed", False) or ambient)
    stimulus = Stimulus(
        text=text,
        source="channel_message",
        metadata={
            **metadata,
            "channel_id": channel_id,
            "channel_name": channel.get("display_name", channel.get("name", "")),
            "conversation_id": conversation_id,
            "conversation_type": str(payload.get("conversation_type") or ""),
            "sender_id": str(payload.get("sender_id") or ""),
            "sender_is_bot": _structured_bool(payload, metadata, "sender_is_bot")
            or _structured_bool(payload, metadata, "from_bot")
            or _structured_bool(payload, metadata, "bot_author"),
            "ambient": ambient,
            "mentioned": bool(payload.get("mentioned", False)),
            "requires_response": requires_response,
            "message_tool_allowed": message_tool_allowed,
            "visible_reply_mode": "message_tool" if ambient else "automatic",
            "response_mode": response_mode or payload.get("response_mode") or "text",
        },
        stimulus_id=str(payload.get("message_id") or "") or f"channel-stimulus-{uuid.uuid4().hex[:12]}",
        occurred_at=str(payload.get("occurred_at") or "") or datetime.now(timezone.utc).isoformat(),
    )
    result = InteractionHarness(config).handle(
        stimulus,
        response_mode=response_mode or str(payload.get("response_mode") or "text"),
        approve_high_risk=approve_high_risk,
    )
    reply: dict[str, Any] | None = None
    prepare_reply = bool(payload.get("prepare_reply", True)) and not ambient
    if prepare_reply and result.run is not None and result.run.final_response.strip():
        reply = prepare_outbound_message(
            config,
            channel_id=channel_id,
            conversation_id=conversation_id,
            text=result.run.final_response,
            metadata={
                "source_stimulus_id": stimulus.stimulus_id,
                "source_run_id": result.run.run_id,
                "prepared_by": "channel_inbound_handle",
                "visible_reply_mode": "automatic",
            },
            reason="Prepared channel reply from agent run result.",
        )
    return {
        "channel": channel,
        "ignored": False,
        "policy": preflight,
        "stimulus": asdict(stimulus),
        "harness": harness_result_to_dict(result),
        "prepared_reply": reply,
    }


def channel_outbox_dir(config: AgentConfig) -> Path:
    path = config.data_dir / "channel_outbox"
    path.mkdir(parents=True, exist_ok=True)
    return path


def channel_state_dir(config: AgentConfig) -> Path:
    path = config.data_dir / "channel_state"
    path.mkdir(parents=True, exist_ok=True)
    return path


def channel_setup_path(config: AgentConfig) -> Path:
    path = channel_state_dir(config.normalized()) / CHANNEL_STATE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _normalized_channel(channel: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(channel)
    if "display_name" not in normalized:
        normalized["display_name"] = normalized.get("name", "")
    if "name" not in normalized:
        normalized["name"] = normalized.get("display_name", "")
    if "plugin_kind" not in normalized:
        normalized["plugin_kind"] = normalized.get("plugin_status", "")
    setup = normalized.get("setup", {})
    if isinstance(setup, str):
        normalized["setup_kind"] = setup
        normalized["setup"] = {
            "auth_type": setup,
            "required_fields": ["conversation_id"],
            "required_secrets": [],
            "optional_secrets": [],
            "steps": [],
            "doctor_checks": [],
            "notes": [],
        }
    elif not isinstance(setup, dict):
        normalized["setup"] = {}
    normalized.setdefault("setup_kind", normalized["setup"].get("auth_type", ""))
    normalized.setdefault("policies", {})
    normalized.setdefault("delivery", {})
    normalized.setdefault("runtime", {})
    return normalized


def _clean_setup_record(channel: dict[str, Any], setup: dict[str, Any]) -> dict[str, Any]:
    secret_refs = setup.get("secret_refs", {})
    if isinstance(secret_refs, list):
        secret_refs = {str(item): str(item) for item in secret_refs}
    if not isinstance(secret_refs, dict):
        secret_refs = {}
    return {
        "channel_id": channel["channel_id"],
        "enabled": bool(setup.get("enabled", False)),
        "listen_enabled": bool(setup.get("listen_enabled", setup.get("enabled", False))),
        "conversation_defaults": _json_object(setup.get("conversation_defaults", {}), max_items=50),
        "allowlist": _json_list(setup.get("allowlist", []), limit=200),
        "group_allowlist": _json_list(setup.get("group_allowlist", []), limit=200),
        "secret_refs": {str(key)[:120]: str(value)[:160] for key, value in list(secret_refs.items())[:50]},
        "secret_configured": {str(key)[:120]: bool(value) for key, value in list((setup.get("secret_configured", {}) or {}).items())[:50]}
        if isinstance(setup.get("secret_configured", {}), dict)
        else {},
        "notes": str(setup.get("notes", ""))[:2000],
    }


def _channel_status(config: AgentConfig, channel: dict[str, Any], setups: dict[str, Any]) -> dict[str, Any]:
    channels = setups.get("channels", {})
    saved = channels.get(channel["channel_id"], {}) if isinstance(channels, dict) else {}
    if not isinstance(saved, dict):
        saved = {}
    setup = channel.get("setup", {}) if isinstance(channel.get("setup"), dict) else {}
    contract = _official_send_contract(channel)
    required_env = [str(item) for item in contract.get("required_env", []) if str(item)]
    missing_send_env = _missing_env(config, required_env)
    credential_source = _credential_source(config, required_env)
    connector_readiness = _channel_connector_readiness(config, str(channel["channel_id"]))
    setup_checks = [str(item) for item in setup.get("doctor_checks", []) if str(item)]
    missing_setup = [check for check in setup_checks if not _check_available(config, check)]
    enabled = bool(saved.get("enabled", False))
    listen_enabled = bool(saved.get("listen_enabled", enabled))
    return {
        "channel_id": channel["channel_id"],
        "display_name": channel.get("display_name", channel.get("name", "")),
        "enabled": enabled,
        "listen_enabled": listen_enabled,
        "setup_kind": channel.get("setup_kind", ""),
        "runtime_adapter": channel.get("runtime_adapter", ""),
        "can_prepare": bool(channel.get("delivery", {}).get("prepared_outbox", True)),
        "send_implemented": bool(contract.get("implemented", False)),
        "send_mode": str(contract.get("mode", "")),
        "missing_send_env": missing_send_env,
        "credential_source": credential_source,
        "connector_provider_id": _channel_connector_provider_id(str(channel["channel_id"])) or "",
        "connector_readiness": connector_readiness,
        "missing_setup_checks": missing_setup,
        "configured_secret_refs": sorted((saved.get("secret_refs", {}) or {}).keys()) if isinstance(saved.get("secret_refs", {}), dict) else [],
        "ready_for_send": bool(contract.get("implemented", False)) and not missing_send_env,
        "ready_for_inbound": enabled and listen_enabled and not missing_setup,
        "setup": setup,
    }


def _official_send_contract(channel: dict[str, Any]) -> dict[str, Any]:
    delivery = channel.get("delivery", {})
    if not isinstance(delivery, dict):
        return {}
    contract = delivery.get("official_send", {})
    return contract if isinstance(contract, dict) else {}


def _rendering_hints(channel: dict[str, Any], text: str) -> dict[str, Any]:
    delivery = channel.get("delivery", {}) if isinstance(channel.get("delivery"), dict) else {}
    policies = channel.get("policies", {}) if isinstance(channel.get("policies"), dict) else {}
    markdown_images = _extract_markdown_images(text) if delivery.get("markdown_image_to_media", False) else []
    return {
        "markdown_image_media_conversion": bool(markdown_images),
        "markdown_image_count": len(markdown_images),
        "group_policy_applies": _has_group_conversation(channel),
        "bot_loop_protection_required": bool(policies.get("bot_loop_protection_supported", False)),
        "ambient_room_events_supported": bool(policies.get("ambient_room_events_supported", False)),
    }


def _delivery_hints(channel: dict[str, Any]) -> dict[str, Any]:
    policies = channel.get("policies", {}) if isinstance(channel.get("policies"), dict) else {}
    delivery = channel.get("delivery", {}) if isinstance(channel.get("delivery"), dict) else {}
    return {
        "dm_policy": policies.get("dm_policy", ""),
        "group_policy": policies.get("group_policy", ""),
        "mention_required_by_default": bool(policies.get("mention_required_by_default", False)),
        "mpim_as_group": bool(policies.get("mpim_as_group", False)),
        "ambient_room_events_supported": bool(policies.get("ambient_room_events_supported", False)),
        "bot_loop_protection_supported": bool(policies.get("bot_loop_protection_supported", False)),
        "approval_reactions_supported": bool(delivery.get("approval_reactions", False)),
        "native_threads_supported": bool(delivery.get("native_threads", False)),
    }


def _channel_action_hints(channel: dict[str, Any]) -> dict[str, Any]:
    policies = channel.get("policies", {}) if isinstance(channel.get("policies"), dict) else {}
    delivery = channel.get("delivery", {}) if isinstance(channel.get("delivery"), dict) else {}
    return {
        "supported_action_types": sorted(_supported_action_types(channel)),
        "supports_reactions": bool(channel.get("supports_reactions", False)),
        "supports_media": bool(channel.get("supports_media", False) or delivery.get("media", False)),
        "native_threads_supported": bool(delivery.get("native_threads", False)),
        "approval_reactions_supported": bool(delivery.get("approval_reactions", False)),
        "ambient_room_events_supported": bool(policies.get("ambient_room_events_supported", False)),
        "bot_loop_protection_supported": bool(policies.get("bot_loop_protection_supported", False)),
    }


def _supported_action_types(channel: dict[str, Any]) -> set[str]:
    delivery = channel.get("delivery", {}) if isinstance(channel.get("delivery"), dict) else {}
    action_types = {"typing_indicator", "read_receipt"}
    if bool(channel.get("supports_reactions", False) or delivery.get("reactions", False) or delivery.get("approval_reactions", False)):
        action_types.update({"reaction_add", "reaction_remove"})
    if bool(channel.get("supports_media", False) or delivery.get("media", False)):
        action_types.add("file_share")
    if bool(delivery.get("native_threads", False)):
        action_types.add("thread_reply")
    if channel.get("channel_id") in {"slack", "discord", "mattermost", "msteams"}:
        action_types.update({"pin", "unpin"})
    return action_types


def _media_payload(channel: dict[str, Any], text: str, media_paths: list[str]) -> list[dict[str, Any]]:
    media = [{"kind": "file", "path": str(path)} for path in media_paths]
    delivery = channel.get("delivery", {}) if isinstance(channel.get("delivery"), dict) else {}
    if delivery.get("markdown_image_to_media", False):
        media.extend(_extract_markdown_images(text))
    return media


def _extract_markdown_images(text: str) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    index = 0
    while index < len(text):
        marker = text.find("![", index)
        if marker < 0:
            break
        alt_end = text.find("]", marker + 2)
        if alt_end < 0 or alt_end + 1 >= len(text) or text[alt_end + 1] != "(":
            index = marker + 2
            continue
        url_end = text.find(")", alt_end + 2)
        if url_end < 0:
            index = alt_end + 1
            continue
        alt = text[marker + 2 : alt_end].strip()
        url = text[alt_end + 2 : url_end].strip()
        if url:
            images.append({"kind": "image", "url": url, "alt": alt, "source": "markdown_image"})
        index = url_end + 1
    return images[:10]


def _inbound_preflight(payload: dict[str, Any], channel: dict[str, Any], config: AgentConfig) -> dict[str, Any]:
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    bot_authored = (
        _structured_bool(payload, metadata, "sender_is_bot")
        or _structured_bool(payload, metadata, "from_bot")
        or _structured_bool(payload, metadata, "bot_author")
    )
    policies = channel.get("policies", {}) if isinstance(channel.get("policies"), dict) else {}
    allow_bot = _structured_bool(payload, metadata, "allow_bot_message")
    if bot_authored and not allow_bot:
        return {
            "ignored": True,
            "reason": "bot_authored_message_blocked",
            "ambient": False,
            "bot_loop_protection": "not_reached",
        }
    if bot_authored and policies.get("bot_loop_protection_supported", False):
        loop = _bot_loop_check(config, payload, channel)
        if loop.get("suppressed"):
            return {
                "ignored": True,
                "reason": "bot_loop_protection_suppressed_pair",
                "ambient": False,
                "bot_loop_protection": loop,
            }
    ambient = _ambient_room_event(payload, channel)
    return {
        "ignored": False,
        "reason": "accepted_ambient_room_event" if ambient else "accepted",
        "ambient": ambient,
        "bot_loop_protection": "checked" if bot_authored else "not_applicable",
    }


def _ambient_room_event(payload: dict[str, Any], channel: dict[str, Any]) -> bool:
    policies = channel.get("policies", {}) if isinstance(channel.get("policies"), dict) else {}
    if not policies.get("ambient_room_events_supported", False):
        return False
    conversation_type = str(payload.get("conversation_type") or "").strip().lower()
    if conversation_type not in {"group", "channel", "private_channel", "mpim", "room", "server_channel", "supergroup", "topic"}:
        return False
    if bool(payload.get("mentioned", False)):
        return False
    if bool(payload.get("requires_response", False)):
        return False
    return bool(payload.get("ambient", True))


def _bot_loop_check(config: AgentConfig, payload: dict[str, Any], channel: dict[str, Any]) -> dict[str, Any]:
    state_path = channel_state_dir(config.normalized()) / BOT_LOOP_STATE_FILENAME
    now = time.time()
    state = _load_json_object(state_path)
    events = state.get("events", [])
    if not isinstance(events, list):
        events = []
    conversation_id = str(payload.get("conversation_id") or "")
    sender_id = str(payload.get("sender_id") or "unknown-bot")
    receiver_id = str(payload.get("receiver_bot_id") or payload.get("bot_id") or "humungousaur")
    pair_key = "|".join([str(channel.get("channel_id", "")), conversation_id, *sorted([sender_id, receiver_id])])
    window = float(BOT_LOOP_DEFAULTS["window_seconds"])
    recent = [
        event
        for event in events
        if isinstance(event, dict)
        and event.get("pair_key") == pair_key
        and now - float(event.get("created_at", 0.0)) <= window
    ]
    suppressed = len(recent) >= int(BOT_LOOP_DEFAULTS["max_events_per_window"])
    recent.append({"pair_key": pair_key, "created_at": now})
    state["events"] = [
        event
        for event in events
        if isinstance(event, dict) and now - float(event.get("created_at", 0.0)) <= window
    ][-500:] + [{"pair_key": pair_key, "created_at": now}]
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "pair_key": pair_key,
        "events_in_window": len(recent),
        "max_events_per_window": BOT_LOOP_DEFAULTS["max_events_per_window"],
        "window_seconds": BOT_LOOP_DEFAULTS["window_seconds"],
        "suppressed": suppressed,
    }


def _send_via_official_adapter(config: AgentConfig, channel: dict[str, Any], message: dict[str, Any]) -> dict[str, Any]:
    mode = str(_official_send_contract(channel).get("mode", ""))
    if mode == "slack_chat_post_message":
        return _send_slack(config, message)
    if mode == "telegram_send_message":
        return _send_telegram(config, message)
    if mode == "discord_channel_message":
        return _send_discord(config, message)
    if mode == "whatsapp_cloud_text":
        return _send_whatsapp_cloud(config, message)
    if mode == "google_chat_webhook":
        return _send_webhook(_required_secret(config, "GOOGLE_CHAT_WEBHOOK_URL"), {"text": message["text"]})
    if mode == "teams_webhook":
        return _send_webhook(_required_secret(config, "TEAMS_WEBHOOK_URL"), {"text": message["text"]})
    if mode == "twilio_sms":
        return _send_twilio_sms(config, message)
    raise ValueError(f"No Humungousaur official adapter for send mode: {mode}")


def _send_slack(config: AgentConfig, message: dict[str, Any]) -> dict[str, Any]:
    payload = {"channel": message["conversation_id"], "text": message["text"]}
    thread_ts = message.get("metadata", {}).get("thread_ts") if isinstance(message.get("metadata"), dict) else None
    if thread_ts:
        payload["thread_ts"] = str(thread_ts)
    response = _http_json(
        "https://slack.com/api/chat.postMessage",
        payload,
        headers={"Authorization": f"Bearer {_required_secret(config, 'SLACK_BOT_TOKEN')}"},
    )
    if response.get("ok") is not True:
        raise ValueError(f"Slack send failed: {response.get('error', 'unknown_error')}")
    return _redacted_response(response)


def _send_telegram(config: AgentConfig, message: dict[str, Any]) -> dict[str, Any]:
    token = _required_secret(config, "TELEGRAM_BOT_TOKEN")
    payload = {"chat_id": message["conversation_id"], "text": message["text"]}
    response = _http_json(f"https://api.telegram.org/bot{token}/sendMessage", payload)
    if response.get("ok") is not True:
        raise ValueError(f"Telegram send failed: {response.get('description', 'unknown_error')}")
    return _redacted_response(response)


def _send_discord(config: AgentConfig, message: dict[str, Any]) -> dict[str, Any]:
    channel_id = parse.quote(str(message["conversation_id"]), safe="")
    payload = {"content": message["text"]}
    response = _http_json(
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        payload,
        headers={"Authorization": f"Bot {_required_secret(config, 'DISCORD_BOT_TOKEN')}"},
    )
    return _redacted_response(response)


def _send_whatsapp_cloud(config: AgentConfig, message: dict[str, Any]) -> dict[str, Any]:
    phone_number_id = parse.quote(_required_secret(config, "WHATSAPP_PHONE_NUMBER_ID"), safe="")
    payload = {
        "messaging_product": "whatsapp",
        "to": message["conversation_id"],
        "type": "text",
        "text": {"preview_url": False, "body": message["text"]},
    }
    response = _http_json(
        f"https://graph.facebook.com/v20.0/{phone_number_id}/messages",
        payload,
        headers={"Authorization": f"Bearer {_required_secret(config, 'WHATSAPP_ACCESS_TOKEN')}"},
    )
    return _redacted_response(response)


def _send_webhook(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _http_json(url, payload)


def _send_twilio_sms(config: AgentConfig, message: dict[str, Any]) -> dict[str, Any]:
    sid = _required_secret(config, "TWILIO_ACCOUNT_SID")
    token = _required_secret(config, "TWILIO_AUTH_TOKEN")
    form = parse.urlencode(
        {
            "From": _required_secret(config, "TWILIO_FROM_NUMBER"),
            "To": message["conversation_id"],
            "Body": message["text"],
        }
    ).encode("utf-8")
    auth = base64.b64encode(f"{sid}:{token}".encode("utf-8")).decode("ascii")
    req = request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{parse.quote(sid, safe='')}/Messages.json",
        data=form,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=25) as response:
        body = response.read().decode("utf-8")
    parsed = json.loads(body) if body else {}
    return _redacted_response(parsed if isinstance(parsed, dict) else {"body": parsed})


def _http_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request_headers = {"Content-Type": "application/json; charset=utf-8", **(headers or {})}
    req = request.Request(url, data=data, headers=request_headers, method="POST")
    with request.urlopen(req, timeout=25) as response:
        body = response.read().decode("utf-8")
    if not body:
        return {"ok": True}
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        return {"body": parsed}
    return parsed


def _check_available(config: AgentConfig, check: str) -> bool:
    if check.startswith("env:"):
        return bool(_secret(config, check.removeprefix("env:")))
    if check.startswith("any_env:"):
        names = [item for item in check.removeprefix("any_env:").split("|") if item]
        return any(_secret(config, name) for name in names)
    if check.startswith("bin:"):
        return shutil.which(check.removeprefix("bin:")) is not None
    if check.startswith("api:"):
        return True
    if check.startswith("platform:"):
        value = check.removeprefix("platform:")
        if value == "darwin_or_relay":
            return os.name == "posix" or bool(os.environ.get("IMESSAGE_RELAY_HOST"))
    return True


def _missing_env(config: AgentConfig, required_env: list[str]) -> list[str]:
    return [name for name in required_env if name and not _secret(config, name)]


def _secret(config: AgentConfig, name: str) -> str | None:
    return config.normalized().secret_value(name) or os.environ.get(name) or _connector_secret(config, name)


def _credential_source(config: AgentConfig, required_env: list[str]) -> str:
    names = [name for name in required_env if name]
    if not names:
        return "none"
    env_count = sum(1 for name in names if config.normalized().secret_value(name) or os.environ.get(name))
    connector_count = sum(1 for name in names if _connector_secret(config, name))
    if env_count == len(names):
        return "env"
    if connector_count == len(names):
        return "connector"
    if env_count or connector_count:
        return "mixed"
    return "missing"


_CHANNEL_ENV_CREDENTIALS: dict[str, tuple[tuple[str, str], ...]] = {
    "SLACK_BOT_TOKEN": (("slack", "bot_access_token"), ("slack", "access_token"), ("slack", "bot_token")),
    "TELEGRAM_BOT_TOKEN": (("telegram", "bot_token"),),
    "DISCORD_BOT_TOKEN": (("discord", "bot_token"),),
    "WHATSAPP_PHONE_NUMBER_ID": (("whatsapp", "phone_number_id"),),
    "WHATSAPP_ACCESS_TOKEN": (("whatsapp", "access_token"),),
    "GOOGLE_CHAT_WEBHOOK_URL": (("googlechat", "webhook_url"),),
    "TEAMS_WEBHOOK_URL": (("msteams", "webhook_url"),),
    "TWILIO_ACCOUNT_SID": (("sms", "account_sid"), ("voice_call", "account_sid")),
    "TWILIO_AUTH_TOKEN": (("sms", "auth_token"), ("voice_call", "auth_token")),
    "TWILIO_FROM_NUMBER": (("sms", "from_number"), ("voice_call", "from_number")),
}


def _connector_secret(config: AgentConfig, env_name: str) -> str | None:
    candidates = _CHANNEL_ENV_CREDENTIALS.get(str(env_name or ""), ())
    if not candidates:
        return None
    try:
        from humungousaur.connectors import ConnectorRuntime

        runtime = ConnectorRuntime(config.normalized())
    except Exception:
        return None
    for provider_id, key in candidates:
        try:
            value = runtime.credential_value(provider_id, key)
        except Exception:
            value = None
        if value:
            return value
    return None


def _channel_connector_provider_id(channel_id: str) -> str:
    mapping = {
        "slack": "slack",
        "telegram": "telegram",
        "discord": "discord",
        "whatsapp": "whatsapp",
        "googlechat": "googlechat",
        "msteams": "msteams",
        "sms": "sms",
        "voice_call": "voice_call",
    }
    return mapping.get(str(channel_id or ""), "")


def _channel_connector_readiness(config: AgentConfig, channel_id: str) -> dict[str, Any]:
    provider_id = _channel_connector_provider_id(channel_id)
    if not provider_id:
        return {}
    try:
        from humungousaur.connectors import ConnectorRuntime

        return ConnectorRuntime(config.normalized()).readiness(provider_id)
    except Exception:
        return {}


def _required_secret(config: AgentConfig, name: str) -> str:
    value = _secret(config, name)
    if not value:
        raise KeyError(name)
    return value


def _has_group_conversation(channel: dict[str, Any]) -> bool:
    conversation_types = channel.get("conversation_types", [])
    return any(item in {"group", "channel", "mpim", "room", "server_channel", "private_channel", "supergroup"} for item in conversation_types)


def _structured_bool(payload: dict[str, Any], metadata: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    if isinstance(value, bool):
        return value
    value = metadata.get(key)
    return value if isinstance(value, bool) else False


def _write_message(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = dict(payload)
    serializable.pop("path", None)
    path.write_text(json.dumps(serializable, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _json_object(value: Any, *, max_items: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, Any] = {}
    for index, (key, item) in enumerate(value.items()):
        if index >= max_items:
            break
        cleaned[str(key)[:120]] = _json_value(item)
    return cleaned


def _json_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item)[:200] for item in value[:limit]]


def _json_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_json_value(item) for item in value[:50]]
    if isinstance(value, dict):
        return _json_object(value, max_items=50)
    return str(value)


def _redacted_response(response: dict[str, Any]) -> dict[str, Any]:
    redacted = {}
    for key, value in response.items():
        if "token" in key.lower() or "secret" in key.lower() or "authorization" in key.lower():
            redacted[key] = "[redacted]"
        else:
            redacted[key] = value
    return redacted


def _clean_id(value: object) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", "_").split())[:120]


def _clean_action_type(value: object) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", "_").split())[:80]
