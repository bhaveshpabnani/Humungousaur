from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from .common import CommunicationBridgeCollector, _require_connector_ready
from .events import append_communication_event


SIGNAL_COLLECTOR = CommunicationBridgeCollector(
    app="signal",
    provider_id="signal",
    display_name="Signal",
    required_scopes=("signal_cli_pairing",),
    description="Collects Signal message, edit/delete where exposed, group/thread, delivery/read, and attachment metadata from signal-cli JSON-RPC/daemon or local bridge ingress.",
    source_channel="signal_cli_json_rpc+daemon+local_bridge",
    docs_url="https://github.com/AsamK/signal-cli/blob/master/man/signal-cli-jsonrpc.5.adoc",
    implementation_level="local_poller_or_bridge",
    poller_supported=True,
    webhook_supported=False,
)


def append_signal_cli_receive(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize signal-cli JSON-RPC/daemon receive metadata."""

    _require_connector_ready(config, "signal")
    envelope = _signal_envelope(payload)
    message = _signal_message(envelope)
    event_type = "message_sent" if "sentMessage" in envelope else "message_received"
    if message.get("attachments"):
        event_type = "attachment_added"
    metadata = {
        "source_number_id": envelope.get("sourceNumber") or envelope.get("sourceUuid"),
        "sender_id": envelope.get("sourceUuid") or envelope.get("sourceNumber"),
        "group_id": (message.get("groupInfo") or {}).get("groupId") if isinstance(message.get("groupInfo"), dict) else "",
        "timestamp": envelope.get("timestamp") or message.get("timestamp"),
        "attachment_count": len(message.get("attachments") or []),
        "reaction_present": bool(message.get("reaction")),
        "quote_present": bool(message.get("quote")),
        "expires_in_seconds": message.get("expiresInSeconds"),
    }
    return append_communication_event(
        config,
        {
            "app": "signal",
            "provider_id": "signal",
            "event_type": event_type,
            "message_id": message.get("timestamp") or envelope.get("timestamp"),
            "conversation_id": metadata.get("group_id") or metadata.get("sender_id"),
            "metadata": metadata,
            "source_channel": "signal_cli_json_rpc",
            "occurred_at": str(envelope.get("timestamp") or message.get("timestamp") or ""),
        },
    )


def _signal_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    envelope = params.get("envelope") if isinstance(params.get("envelope"), dict) else payload.get("envelope")
    if isinstance(envelope, dict):
        return envelope
    if payload.get("method") == "receive" and isinstance(payload.get("result"), dict):
        result_envelope = payload["result"].get("envelope")
        if isinstance(result_envelope, dict):
            return result_envelope
    return payload


def _signal_message(envelope: dict[str, Any]) -> dict[str, Any]:
    for key in ("dataMessage", "syncMessage", "sentMessage", "editMessage"):
        value = envelope.get(key)
        if isinstance(value, dict):
            if key == "syncMessage" and isinstance(value.get("sentMessage"), dict):
                return value["sentMessage"]
            return value
    raise ValueError("unsupported signal-cli receive payload without message metadata")
