from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
import uuid

from humungousaur.config import AgentConfig


CHANNEL_CATALOG_PATH = Path(__file__).resolve().parents[1] / "resources" / "channel_catalog.json"
CHANNEL_OUTBOX_LIMIT = 100


def load_channel_catalog() -> list[dict[str, Any]]:
    payload = json.loads(CHANNEL_CATALOG_PATH.read_text(encoding="utf-8"))
    channels = payload.get("channels") if isinstance(payload, dict) else None
    if not isinstance(channels, list):
        return []
    return [channel for channel in channels if isinstance(channel, dict)]


def find_channel(channel_id: str) -> dict[str, Any] | None:
    cleaned = _clean_id(channel_id)
    if not cleaned:
        return None
    return next((channel for channel in load_channel_catalog() if channel.get("channel_id") == cleaned), None)


def prepare_outbound_message(
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
    channel = find_channel(channel_id)
    if channel is None:
        raise ValueError(f"Unknown channel_id: {channel_id}")
    if not conversation_id.strip():
        raise ValueError("conversation_id is required for channel message preparation.")
    if not text.strip() and not media_paths:
        raise ValueError("Channel message preparation requires text or media paths.")
    message_id = f"channel-message-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    payload = {
        "message_id": message_id,
        "status": "prepared_not_sent",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "channel_id": channel["channel_id"],
        "channel_name": channel.get("name", ""),
        "conversation_id": conversation_id.strip(),
        "text": text,
        "media_paths": [str(item) for item in (media_paths or [])],
        "metadata": metadata if isinstance(metadata, dict) else {},
        "reason": reason,
        "delivery": {
            "requires_trusted_runtime": True,
            "plugin_status": channel.get("plugin_status", ""),
            "transport": channel.get("transport", ""),
        },
        "rendering_hints": _rendering_hints(channel, text),
    }
    outbox_dir = channel_outbox_dir(normalized)
    path = outbox_dir / f"{message_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    payload["path"] = str(path)
    return payload


def list_outbox(config: AgentConfig, limit: int = 20) -> list[dict[str, Any]]:
    outbox = channel_outbox_dir(config.normalized())
    if not outbox.exists():
        return []
    messages: list[dict[str, Any]] = []
    for path in sorted(outbox.glob("channel-message-*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        messages.append(
            {
                "message_id": payload.get("message_id", path.stem),
                "status": payload.get("status", ""),
                "created_at": payload.get("created_at", ""),
                "channel_id": payload.get("channel_id", ""),
                "channel_name": payload.get("channel_name", ""),
                "conversation_id": payload.get("conversation_id", ""),
                "text_preview": str(payload.get("text", ""))[:240],
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

    stimulus = Stimulus(
        text=text,
        source="channel_message",
        metadata={
            **metadata,
            "channel_id": channel_id,
            "channel_name": channel.get("name", ""),
            "conversation_id": conversation_id,
            "conversation_type": str(payload.get("conversation_type") or ""),
            "sender_id": str(payload.get("sender_id") or ""),
            "ambient": bool(payload.get("ambient", False)),
            "requires_response": bool(payload.get("requires_response", False)),
            "message_tool_allowed": bool(payload.get("message_tool_allowed", False)),
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
    if bool(payload.get("prepare_reply", True)) and result.run is not None and result.run.final_response.strip():
        reply = prepare_outbound_message(
            config,
            channel_id=channel_id,
            conversation_id=conversation_id,
            text=result.run.final_response,
            metadata={
                "source_stimulus_id": stimulus.stimulus_id,
                "source_run_id": result.run.run_id,
                "prepared_by": "channel_inbound_handle",
            },
            reason="Prepared channel reply from agent run result.",
        )
    return {
        "channel": channel,
        "stimulus": asdict(stimulus),
        "harness": harness_result_to_dict(result),
        "prepared_reply": reply,
    }


def channel_outbox_dir(config: AgentConfig) -> Path:
    path = config.data_dir / "channel_outbox"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _rendering_hints(channel: dict[str, Any], text: str) -> dict[str, Any]:
    channel_id = str(channel.get("channel_id") or "")
    return {
        "markdown_image_media_conversion": channel_id == "telegram" and "![" in text and "](" in text,
        "group_policy_applies": "group" in channel.get("conversation_types", []) or "mpim" in channel.get("conversation_types", []),
        "bot_loop_protection_required": True,
        "ambient_room_events_supported": "room" in channel.get("conversation_types", []) or "channel" in channel.get("conversation_types", []),
    }


def _clean_id(value: object) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", "_").split())[:120]
