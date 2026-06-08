from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib import parse, request
import uuid

from humungousaur.config import AgentConfig
from humungousaur.env import load_workspace_environment
from humungousaur.integrations.channels import (
    channel_state_dir,
    find_channel,
    handle_channel_inbound,
    load_channel_catalog,
    load_channel_setups,
)


LISTENER_STATE_FILENAME = "channel_listeners.json"
LISTENER_EVENT_LIMIT = 200


def channel_listener_status(config: AgentConfig, channel_id: str | None = None) -> dict[str, Any]:
    normalized = config.normalized()
    load_workspace_environment(normalized.workspace)
    setups = load_channel_setups(normalized)
    channels = load_channel_catalog()
    if channel_id:
        cleaned = _clean_id(channel_id)
        channels = [channel for channel in channels if channel.get("channel_id") == cleaned]
    state = _load_listener_state(normalized)
    return {
        "listeners": [_listener_record(normalized, channel, setups, state) for channel in channels],
        "state_path": str(_listener_state_path(normalized)),
        "webhook_base_path": "/channels/webhook/{channel_id}",
        "polling_tick_endpoint": "/channels/listeners/tick",
    }


def channel_listener_tick(
    config: AgentConfig,
    *,
    channel_id: str | None = None,
    limit: int = 20,
    prepare_replies: bool = True,
    approve_high_risk: bool = False,
) -> dict[str, Any]:
    normalized = config.normalized()
    load_workspace_environment(normalized.workspace)
    statuses = channel_listener_status(normalized, channel_id=channel_id)["listeners"]
    processed: list[dict[str, Any]] = []
    listener_notes: list[dict[str, Any]] = []
    state = _load_listener_state(normalized)
    for status in statuses:
        if not status.get("enabled", False):
            listener_notes.append({"channel_id": status["channel_id"], "status": "disabled"})
            continue
        if status.get("polling_available", False):
            processed.extend(
                _poll_channel(
                    normalized,
                    status["channel_id"],
                    state,
                    limit=max(1, min(int(limit), 100)),
                    prepare_replies=prepare_replies,
                    approve_high_risk=approve_high_risk,
                )
            )
            continue
        listener_notes.append(
            {
                "channel_id": status["channel_id"],
                "status": "webhook_ready" if status.get("webhook_available", False) else "waiting_for_setup",
                "listener_mode": status.get("listener_mode", ""),
            }
        )
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_listener_state(normalized, state)
    return {
        "processed_count": len(processed),
        "processed": processed[-LISTENER_EVENT_LIMIT:],
        "listener_notes": listener_notes,
        "listeners": channel_listener_status(normalized, channel_id=channel_id)["listeners"],
    }


def process_channel_webhook(
    config: AgentConfig,
    *,
    channel_id: str,
    payload: dict[str, Any],
    prepare_reply: bool = True,
    approve_high_risk: bool = False,
    response_mode: str | None = None,
) -> dict[str, Any]:
    normalized = config.normalized()
    load_workspace_environment(normalized.workspace)
    channel = find_channel(channel_id)
    if channel is None:
        raise ValueError(f"Unknown channel_id: {channel_id}")
    special = _provider_handshake(channel["channel_id"], payload)
    if special is not None:
        return special
    inbound_messages = normalize_provider_payload(channel["channel_id"], payload, prepare_reply=prepare_reply)
    results = []
    for inbound in inbound_messages:
        results.append(
            handle_channel_inbound(
                inbound,
                normalized,
                response_mode=response_mode,
                approve_high_risk=approve_high_risk,
            )
        )
    _append_listener_events(normalized, channel["channel_id"], results)
    return {
        "channel_id": channel["channel_id"],
        "accepted": True,
        "message_count": len(results),
        "results": results,
    }


def normalize_provider_payload(channel_id: str, payload: dict[str, Any], *, prepare_reply: bool = True) -> list[dict[str, Any]]:
    channel = find_channel(channel_id)
    if channel is None:
        raise ValueError(f"Unknown channel_id: {channel_id}")
    cleaned = channel["channel_id"]
    if cleaned == "telegram":
        return _normalize_telegram(payload, prepare_reply=prepare_reply)
    if cleaned == "slack":
        return _normalize_slack(payload, prepare_reply=prepare_reply)
    if cleaned == "discord":
        return _normalize_discord(payload, prepare_reply=prepare_reply)
    if cleaned == "whatsapp":
        return _normalize_whatsapp(payload, prepare_reply=prepare_reply)
    if cleaned == "sms":
        return _normalize_sms(payload, prepare_reply=prepare_reply)
    if cleaned in {"googlechat", "msteams", "mattermost", "matrix", "webchat"}:
        return [_normalize_generic(cleaned, payload, prepare_reply=prepare_reply)]
    return [_normalize_generic(cleaned, payload, prepare_reply=prepare_reply)]


def _listener_record(config: AgentConfig, channel: dict[str, Any], setups: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    channel_id = channel["channel_id"]
    saved = setups.get("channels", {}).get(channel_id, {}) if isinstance(setups.get("channels", {}), dict) else {}
    if not isinstance(saved, dict):
        saved = {}
    runtime = channel.get("runtime", {}) if isinstance(channel.get("runtime"), dict) else {}
    setup = channel.get("setup", {}) if isinstance(channel.get("setup"), dict) else {}
    enabled = bool(saved.get("enabled", False))
    listen_enabled = bool(saved.get("listen_enabled", enabled))
    listener_mode = _listener_mode(channel)
    required_env = _listener_required_env(channel)
    missing_env = [name for name in required_env if not _secret(config, name)]
    required_binaries = [str(item) for item in setup.get("required_binaries", []) if str(item)]
    missing_binaries = [name for name in required_binaries if not _binary_available(name)]
    channel_state = state.get("channels", {}).get(channel_id, {}) if isinstance(state.get("channels", {}), dict) else {}
    if not isinstance(channel_state, dict):
        channel_state = {}
    polling_available = enabled and listen_enabled and channel_id == "telegram" and "TELEGRAM_BOT_TOKEN" not in missing_env
    webhook_available = enabled and listen_enabled and bool(runtime.get("listener_required_for_inbound", False)) and not missing_binaries
    ready = enabled and listen_enabled and (polling_available or webhook_available) and not missing_binaries
    return {
        "channel_id": channel_id,
        "display_name": channel.get("display_name", channel.get("name", "")),
        "enabled": enabled,
        "listen_enabled": listen_enabled,
        "listener_mode": listener_mode,
        "ready": ready,
        "polling_available": polling_available,
        "webhook_available": webhook_available,
        "webhook_path": f"/channels/webhook/{channel_id}",
        "missing_env": missing_env,
        "missing_binaries": missing_binaries,
        "last_poll_at": channel_state.get("last_poll_at", ""),
        "last_event_at": channel_state.get("last_event_at", ""),
        "processed_event_count": int(channel_state.get("processed_event_count", 0) or 0),
        "notes": _listener_notes(channel, listener_mode),
    }


def _poll_channel(
    config: AgentConfig,
    channel_id: str,
    state: dict[str, Any],
    *,
    limit: int,
    prepare_replies: bool,
    approve_high_risk: bool,
) -> list[dict[str, Any]]:
    if channel_id == "telegram":
        return _poll_telegram(
            config,
            state,
            limit=limit,
            prepare_replies=prepare_replies,
            approve_high_risk=approve_high_risk,
        )
    return []


def _poll_telegram(
    config: AgentConfig,
    state: dict[str, Any],
    *,
    limit: int,
    prepare_replies: bool,
    approve_high_risk: bool,
) -> list[dict[str, Any]]:
    token = _secret(config, "TELEGRAM_BOT_TOKEN") or ""
    if not token:
        return []
    channel_state = _channel_state(state, "telegram")
    offset = int(channel_state.get("telegram_update_offset", 0) or 0)
    query = parse.urlencode({"timeout": 0, "limit": max(1, min(limit, 100)), "offset": offset})
    url = f"https://api.telegram.org/bot{token}/getUpdates?{query}"
    with request.urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("ok") is not True:
        raise ValueError(f"Telegram polling failed: {payload.get('description', 'unknown_error')}")
    processed = []
    max_update_id = offset - 1
    for update in payload.get("result", []):
        if not isinstance(update, dict):
            continue
        update_id = int(update.get("update_id", 0) or 0)
        max_update_id = max(max_update_id, update_id)
        normalized_messages = normalize_provider_payload("telegram", update, prepare_reply=prepare_replies)
        for inbound in normalized_messages:
            result = handle_channel_inbound(inbound, config, approve_high_risk=approve_high_risk)
            processed.append(
                {
                    "channel_id": "telegram",
                    "provider_event_id": update_id,
                    "conversation_id": inbound.get("conversation_id", ""),
                    "ignored": result.get("ignored", False),
                    "prepared_reply": result.get("prepared_reply") is not None,
                }
            )
    if max_update_id >= offset:
        channel_state["telegram_update_offset"] = max_update_id + 1
    channel_state["last_poll_at"] = datetime.now(timezone.utc).isoformat()
    channel_state["processed_event_count"] = int(channel_state.get("processed_event_count", 0) or 0) + len(processed)
    if processed:
        channel_state["last_event_at"] = datetime.now(timezone.utc).isoformat()
    _append_listener_events(config, "telegram", processed)
    return processed


def _normalize_telegram(payload: dict[str, Any], *, prepare_reply: bool) -> list[dict[str, Any]]:
    message = _first_mapping(payload, ["message", "edited_message", "channel_post"])
    if not message:
        message = payload
    chat = message.get("chat", {}) if isinstance(message.get("chat"), dict) else {}
    sender = message.get("from", {}) if isinstance(message.get("from"), dict) else {}
    text = str(message.get("text") or message.get("caption") or "")
    if not text:
        return []
    return [
        {
            "channel_id": "telegram",
            "conversation_id": str(chat.get("id") or payload.get("chat_id") or ""),
            "conversation_type": str(chat.get("type") or "dm"),
            "sender_id": str(sender.get("id") or ""),
            "sender_is_bot": bool(sender.get("is_bot", False)),
            "text": text,
            "requires_response": True,
            "mentioned": _mentioned(payload),
            "prepare_reply": prepare_reply,
            "message_id": str(message.get("message_id") or payload.get("update_id") or uuid.uuid4().hex),
            "metadata": {"provider": "telegram", "raw_update_id": payload.get("update_id", "")},
        }
    ]


def _normalize_slack(payload: dict[str, Any], *, prepare_reply: bool) -> list[dict[str, Any]]:
    event = payload.get("event", payload)
    if not isinstance(event, dict):
        return []
    text = str(event.get("text") or payload.get("text") or "")
    if not text:
        return []
    conversation_id = str(event.get("channel") or payload.get("channel_id") or payload.get("channel") or "")
    conversation_type = str(event.get("channel_type") or payload.get("conversation_type") or "channel")
    return [
        {
            "channel_id": "slack",
            "conversation_id": conversation_id,
            "conversation_type": conversation_type,
            "sender_id": str(event.get("user") or event.get("bot_id") or payload.get("user_id") or ""),
            "sender_is_bot": bool(event.get("bot_id") or event.get("subtype") == "bot_message"),
            "text": text,
            "requires_response": _requires_response(payload, default=conversation_type == "im"),
            "mentioned": _mentioned(payload),
            "ambient": not _requires_response(payload, default=conversation_type == "im"),
            "prepare_reply": prepare_reply,
            "message_id": str(event.get("client_msg_id") or event.get("ts") or payload.get("event_id") or uuid.uuid4().hex),
            "metadata": {"provider": "slack", "thread_ts": event.get("thread_ts") or event.get("ts") or ""},
        }
    ]


def _normalize_discord(payload: dict[str, Any], *, prepare_reply: bool) -> list[dict[str, Any]]:
    author = payload.get("author", {}) if isinstance(payload.get("author"), dict) else {}
    text = str(payload.get("content") or payload.get("text") or "")
    if not text:
        return []
    return [
        {
            "channel_id": "discord",
            "conversation_id": str(payload.get("channel_id") or payload.get("conversation_id") or ""),
            "conversation_type": str(payload.get("conversation_type") or ("dm" if not payload.get("guild_id") else "server_channel")),
            "sender_id": str(author.get("id") or payload.get("sender_id") or ""),
            "sender_is_bot": bool(author.get("bot", False) or payload.get("sender_is_bot", False)),
            "text": text,
            "requires_response": _requires_response(payload, default=False),
            "mentioned": _mentioned(payload),
            "ambient": not _requires_response(payload, default=False),
            "prepare_reply": prepare_reply,
            "message_id": str(payload.get("id") or uuid.uuid4().hex),
            "metadata": {"provider": "discord", "guild_id": payload.get("guild_id", "")},
        }
    ]


def _normalize_whatsapp(payload: dict[str, Any], *, prepare_reply: bool) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for entry in payload.get("entry", []) if isinstance(payload.get("entry", []), list) else []:
        for change in entry.get("changes", []) if isinstance(entry, dict) else []:
            value = change.get("value", {}) if isinstance(change, dict) else {}
            for message in value.get("messages", []) if isinstance(value.get("messages", []), list) else []:
                text_payload = message.get("text", {}) if isinstance(message.get("text"), dict) else {}
                text = str(text_payload.get("body") or message.get("text") or "")
                if text:
                    messages.append(_whatsapp_message(message, text, prepare_reply))
    if messages:
        return messages
    text = str(payload.get("text") or payload.get("body") or "")
    if not text:
        return []
    return [_whatsapp_message(payload, text, prepare_reply)]


def _whatsapp_message(message: dict[str, Any], text: str, prepare_reply: bool) -> dict[str, Any]:
    return {
        "channel_id": "whatsapp",
        "conversation_id": str(message.get("from") or message.get("conversation_id") or ""),
        "conversation_type": "private",
        "sender_id": str(message.get("from") or ""),
        "sender_is_bot": False,
        "text": text,
        "requires_response": True,
        "mentioned": True,
        "prepare_reply": prepare_reply,
        "message_id": str(message.get("id") or uuid.uuid4().hex),
        "metadata": {"provider": "whatsapp"},
    }


def _normalize_sms(payload: dict[str, Any], *, prepare_reply: bool) -> list[dict[str, Any]]:
    text = str(payload.get("Body") or payload.get("body") or payload.get("text") or "")
    if not text:
        return []
    sender = str(payload.get("From") or payload.get("from") or payload.get("sender_id") or "")
    return [
        {
            "channel_id": "sms",
            "conversation_id": sender,
            "conversation_type": "phone_number",
            "sender_id": sender,
            "text": text,
            "requires_response": True,
            "mentioned": True,
            "prepare_reply": prepare_reply,
            "message_id": str(payload.get("MessageSid") or payload.get("message_id") or uuid.uuid4().hex),
            "metadata": {"provider": "sms"},
        }
    ]


def _normalize_generic(channel_id: str, payload: dict[str, Any], *, prepare_reply: bool) -> dict[str, Any]:
    return {
        "channel_id": channel_id,
        "conversation_id": str(payload.get("conversation_id") or payload.get("room_id") or payload.get("chat_id") or "default"),
        "conversation_type": str(payload.get("conversation_type") or "dm"),
        "sender_id": str(payload.get("sender_id") or payload.get("user_id") or ""),
        "sender_is_bot": bool(payload.get("sender_is_bot", False)),
        "text": str(payload.get("text") or payload.get("message") or ""),
        "requires_response": _requires_response(payload, default=True),
        "mentioned": _mentioned(payload),
        "ambient": bool(payload.get("ambient", False)),
        "prepare_reply": prepare_reply,
        "message_id": str(payload.get("message_id") or uuid.uuid4().hex),
        "metadata": {"provider": channel_id},
    }


def _listener_mode(channel: dict[str, Any]) -> str:
    channel_id = channel.get("channel_id", "")
    if channel_id == "telegram":
        return "telegram_long_polling_or_webhook"
    if channel_id == "slack":
        return "slack_events_webhook_or_socket_mode"
    if channel_id == "discord":
        return "discord_gateway_or_http_webhook"
    if channel_id == "whatsapp":
        return "whatsapp_cloud_webhook_or_local_bridge"
    if channel_id in {"googlechat", "msteams", "sms", "webchat"}:
        return f"{channel_id}_http_webhook"
    return str(channel.get("runtime_adapter") or "native_webhook")


def _listener_required_env(channel: dict[str, Any]) -> list[str]:
    channel_id = channel.get("channel_id", "")
    setup = channel.get("setup", {}) if isinstance(channel.get("setup"), dict) else {}
    if channel_id == "telegram":
        return ["TELEGRAM_BOT_TOKEN"]
    if channel_id == "slack":
        return [name for name in ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET"] if name in setup.get("required_secrets", []) + setup.get("optional_secrets", [])]
    if channel_id == "discord":
        return ["DISCORD_BOT_TOKEN"]
    if channel_id == "whatsapp":
        return ["WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"]
    return [str(name) for name in setup.get("required_secrets", []) if str(name)]


def _provider_handshake(channel_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if channel_id == "slack" and payload.get("type") == "url_verification":
        return {"channel_id": channel_id, "accepted": True, "handshake": "slack_url_verification", "challenge": payload.get("challenge", "")}
    if channel_id == "whatsapp" and "hub.challenge" in payload:
        return {"channel_id": channel_id, "accepted": True, "handshake": "whatsapp_webhook_verification", "challenge": payload.get("hub.challenge", "")}
    return None


def _append_listener_events(config: AgentConfig, channel_id: str, events: list[Any]) -> None:
    state = _load_listener_state(config)
    channel_state = _channel_state(state, channel_id)
    channel_state["processed_event_count"] = int(channel_state.get("processed_event_count", 0) or 0) + len(events)
    if events:
        channel_state["last_event_at"] = datetime.now(timezone.utc).isoformat()
    recent = state.setdefault("recent_events", [])
    if not isinstance(recent, list):
        recent = []
        state["recent_events"] = recent
    for event in events:
        recent.append({"channel_id": channel_id, "created_at": datetime.now(timezone.utc).isoformat(), "event": _event_summary(event)})
    state["recent_events"] = recent[-LISTENER_EVENT_LIMIT:]
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_listener_state(config, state)


def _event_summary(event: Any) -> dict[str, Any]:
    if not isinstance(event, dict):
        return {"kind": type(event).__name__}
    return {
        "ignored": bool(event.get("ignored", False)),
        "prepared_reply": event.get("prepared_reply") is not None if "prepared_reply" in event else bool(event.get("prepared_reply", False)),
        "stimulus_id": event.get("stimulus", {}).get("stimulus_id", "") if isinstance(event.get("stimulus"), dict) else "",
        "conversation_id": event.get("stimulus", {}).get("metadata", {}).get("conversation_id", "") if isinstance(event.get("stimulus"), dict) else event.get("conversation_id", ""),
    }


def _listener_notes(channel: dict[str, Any], listener_mode: str) -> list[str]:
    notes = [f"Native listener mode: {listener_mode}."]
    if channel.get("channel_id") == "telegram":
        notes.append("Polling is available locally when TELEGRAM_BOT_TOKEN is configured.")
    else:
        notes.append("Inbound uses the first-party webhook endpoint or a future trusted bridge for provider events.")
    return notes


def _load_listener_state(config: AgentConfig) -> dict[str, Any]:
    path = _listener_state_path(config.normalized())
    if not path.exists():
        return {"channels": {}, "recent_events": [], "updated_at": ""}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"channels": {}, "recent_events": [], "updated_at": ""}
    return payload if isinstance(payload, dict) else {"channels": {}, "recent_events": [], "updated_at": ""}


def _save_listener_state(config: AgentConfig, state: dict[str, Any]) -> None:
    path = _listener_state_path(config.normalized())
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _listener_state_path(config: AgentConfig) -> Path:
    path = channel_state_dir(config.normalized()) / LISTENER_STATE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _channel_state(state: dict[str, Any], channel_id: str) -> dict[str, Any]:
    channels = state.setdefault("channels", {})
    if not isinstance(channels, dict):
        channels = {}
        state["channels"] = channels
    channel_state = channels.setdefault(channel_id, {})
    if not isinstance(channel_state, dict):
        channel_state = {}
        channels[channel_id] = channel_state
    return channel_state


def _binary_available(name: str) -> bool:
    from shutil import which

    return which(name) is not None


def _secret(config: AgentConfig, name: str) -> str | None:
    return config.normalized().secret_value(name) or os.environ.get(name)


def _first_mapping(payload: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _requires_response(payload: dict[str, Any], *, default: bool) -> bool:
    value = payload.get("requires_response")
    return default if value is None else bool(value)


def _mentioned(payload: dict[str, Any]) -> bool:
    value = payload.get("mentioned")
    if value is not None:
        return bool(value)
    return bool(payload.get("mentions"))


def _clean_id(value: object) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", "_").split())[:120]
