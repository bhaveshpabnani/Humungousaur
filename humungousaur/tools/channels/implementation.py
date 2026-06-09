from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any
import uuid

from humungousaur.config import AgentConfig
from humungousaur.integrations.channel_listeners import (
    channel_listener_status,
    channel_listener_tick,
    process_channel_webhook,
)
from humungousaur.integrations.channels import (
    channel_doctor,
    channel_integration_smoke,
    channel_setup_requirements,
    channel_setup_status,
    find_channel,
    list_outbox,
    prepare_channel_action,
    load_channel_catalog,
    prepare_outbound_message,
    save_channel_setup,
    send_outbound_message,
)
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


class ChannelCatalogTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="channel_catalog",
            description=(
                "List supported Gateway communication channels such as WhatsApp, Slack, Telegram, Discord, Teams, "
                "Signal, WebChat, SMS, and voice calls. This is a capability catalog, not an intent router."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "channel_id": {"type": "string", "description": "Optional exact channel id to return."},
                    "include_notes": {"type": "boolean", "description": "Include setup and delivery notes."},
                }
            ),
            capability_group="channels",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        del config
        channel_id = _clean_id(tool_input.get("channel_id"))
        include_notes = bool(tool_input.get("include_notes", True))
        channels = load_channel_catalog()
        if channel_id:
            channels = [channel for channel in channels if channel.get("channel_id") == channel_id]
        items = [_channel_summary(channel, include_notes=include_notes) for channel in channels]
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(items)} Gateway channel(s).",
            {
                "channels": items,
                "source": "humungousaur_gateway_catalog",
                "delivery_boundary": "Cataloged channels require a trusted runtime plugin before real outbound delivery.",
            },
        )


class ChannelManifestTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="channel_manifest",
            description="Read one exact Gateway channel manifest from the local channel catalog.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {"channel_id": {"type": "string", "description": "Exact channel id such as whatsapp, slack, telegram, or webchat."}},
                required=["channel_id"],
            ),
            capability_group="channels",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        del config
        channel_id = _clean_id(tool_input.get("channel_id"))
        channel = find_channel(channel_id)
        if channel is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown channel_id: {channel_id}")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Read channel manifest {channel_id}.",
            {"channel": channel},
        )


class ChannelSetupRequirementsTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="channel_setup_requirements",
            description="Read exact setup, secret-reference, policy, runtime, and delivery requirements for one Humungousaur channel.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {"channel_id": {"type": "string", "description": "Exact channel id such as whatsapp, slack, telegram, discord, or sms."}},
                required=["channel_id"],
            ),
            capability_group="channels",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        del config
        try:
            requirements = channel_setup_requirements(str(tool_input.get("channel_id") or ""))
        except ValueError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc), error=str(exc))
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Read setup requirements for {requirements['channel_id']}.",
            requirements,
        )


class ChannelSetupSaveTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="channel_setup_save",
            description=(
                "Save non-secret channel onboarding state, allowlists, conversation defaults, and secret reference names. "
                "Never store raw API keys or tokens in this tool input."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "channel_id": {"type": "string", "description": "Exact channel id."},
                    "enabled": {"type": "boolean", "description": "Whether the channel should be considered enabled by local setup."},
                    "listen_enabled": {"type": "boolean", "description": "Whether listener polling/webhook processing should be active for inbound events."},
                    "conversation_defaults": {"type": "object", "description": "Default conversation ids/types and routing hints."},
                    "allowlist": {"type": "array", "items": {"type": "string"}, "maxItems": 200},
                    "group_allowlist": {"type": "array", "items": {"type": "string"}, "maxItems": 200},
                    "secret_refs": {"type": "object", "description": "Mapping of required secret purpose to env var name, not the secret value."},
                    "secret_configured": {"type": "object", "description": "Optional booleans marking secrets configured outside this store."},
                    "notes": {"type": "string"},
                },
                required=["channel_id"],
            ),
            capability_group="channels",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would save channel setup.", dict(tool_input))
        try:
            setup = save_channel_setup(config, str(tool_input.get("channel_id") or ""), tool_input)
        except ValueError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc), error=str(exc))
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Saved setup state for {setup['channel_id']}.",
            {"setup": setup},
        )


class ChannelSetupStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="channel_setup_status",
            description="Report configured channel onboarding state, missing credentials, direct-send readiness, and outbox readiness.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"channel_id": {"type": "string", "description": "Optional exact channel id."}}),
            capability_group="channels",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        status = channel_setup_status(config, channel_id=str(tool_input.get("channel_id") or "") or None)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Checked setup state for {len(status['channels'])} channel(s).",
            status,
        )


class ChannelDoctorTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="channel_doctor",
            description="Diagnose channel setup, missing env secrets, local bridge requirements, and direct-send readiness.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"channel_id": {"type": "string", "description": "Optional exact channel id."}}),
            capability_group="channels",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        doctor = channel_doctor(config, channel_id=str(tool_input.get("channel_id") or "") or None)
        warnings = [item for item in doctor["findings"] if item.get("severity") == "warning"]
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Channel doctor finished with {len(warnings)} warning(s).",
            doctor,
        )


class ChannelIntegrationSmokeTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="channel_integration_smoke",
            description=(
                "Run a non-sending integration smoke for selected or priority channels. "
                "The report checks requirements, setup state, listener readiness, prepared outbox creation, and dry-run send wiring."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "channel_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                    "prepare_messages": {"type": "boolean"},
                    "dry_run_sends": {"type": "boolean"},
                    "reason": {"type": "string", "description": "Why channel integration readiness should be checked."},
                }
            ),
            capability_group="channels",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        channel_ids = tool_input.get("channel_ids", [])
        if not isinstance(channel_ids, list):
            channel_ids = []
        report = channel_integration_smoke(
            config,
            channel_ids=[str(item) for item in channel_ids],
            prepare_messages=bool(tool_input.get("prepare_messages", True)),
            dry_run_sends=bool(tool_input.get("dry_run_sends", True)),
        )
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Channel integration smoke checked {report['channel_count']} channel(s); {report['ready_count']} ready.",
            report,
        )


class ChannelMessagePrepareTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="channel_message_prepare",
            description=(
                "Prepare an outbound channel message envelope for a trusted Gateway plugin runtime. "
                "This writes an audited local outbox item and does not send the message."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "channel_id": {"type": "string", "description": "Exact channel id such as whatsapp, slack, telegram, or webchat."},
                    "conversation_id": {"type": "string", "description": "External channel conversation, room, or chat id."},
                    "text": {"type": "string", "description": "Message text to prepare."},
                    "media_paths": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
                    "metadata": {"type": "object", "description": "Opaque structured delivery metadata for the trusted runtime."},
                    "reason": {"type": "string", "description": "Why this message should be prepared."},
                },
                required=["channel_id", "conversation_id", "reason"],
            ),
            capability_group="channels",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would prepare channel message.", dict(tool_input))
        metadata = tool_input.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        try:
            message = prepare_outbound_message(
                config,
                channel_id=str(tool_input.get("channel_id") or ""),
                conversation_id=str(tool_input.get("conversation_id") or ""),
                text=str(tool_input.get("text") or ""),
                media_paths=[str(item) for item in tool_input.get("media_paths", [])],
                metadata=metadata,
                reason=str(tool_input.get("reason") or ""),
            )
        except ValueError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc), error=str(exc))
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            "Prepared outbound channel message envelope.",
            {"message": message},
        )


class ChannelMessageSendTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="channel_message_send",
            description=(
                "Send a channel message through a Humungousaur-owned official API adapter when configured, "
                "while also writing an audited outbox envelope. Requires approval because it contacts external people or rooms."
            ),
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "channel_id": {"type": "string", "description": "Exact channel id such as whatsapp, slack, telegram, discord, sms, googlechat, or msteams."},
                    "conversation_id": {"type": "string", "description": "External channel conversation, room, phone number, or chat id."},
                    "text": {"type": "string", "description": "Message text to send."},
                    "media_paths": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
                    "metadata": {"type": "object", "description": "Opaque structured delivery metadata for the adapter."},
                    "reason": {"type": "string", "description": "Why this message should be sent."},
                },
                required=["channel_id", "conversation_id", "text", "reason"],
            ),
            capability_group="channels",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        metadata = tool_input.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        try:
            message = send_outbound_message(
                config,
                channel_id=str(tool_input.get("channel_id") or ""),
                conversation_id=str(tool_input.get("conversation_id") or ""),
                text=str(tool_input.get("text") or ""),
                media_paths=[str(item) for item in tool_input.get("media_paths", [])],
                metadata=metadata,
                reason=str(tool_input.get("reason") or ""),
            )
        except ValueError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc), error=str(exc))
        status = ActionStatus.SUCCEEDED if message.get("status") == "sent" else ActionStatus.BLOCKED
        if message.get("status") in {"send_failed"}:
            status = ActionStatus.FAILED
        if message.get("status") == "dry_run_not_sent":
            status = ActionStatus.SKIPPED
        return ToolResult(
            self.name,
            status,
            self.risk_level,
            f"Channel send result: {message.get('status', 'unknown')}.",
            {"message": message},
            error=str(message.get("delivery", {}).get("error", "")) or None,
        )


class ChannelActionPrepareTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="channel_action_prepare",
            description=(
                "Prepare an approval-safe channel action envelope for reactions, file shares, thread replies, pins, "
                "typing indicators, and read receipts. This writes a local outbox item and never sends."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "channel_id": {"type": "string", "description": "Exact channel id such as slack, telegram, whatsapp, discord, or teams."},
                    "conversation_id": {"type": "string", "description": "External channel conversation, room, phone number, or chat id."},
                    "action_type": {
                        "type": "string",
                        "enum": ["reaction_add", "reaction_remove", "file_share", "thread_reply", "pin", "unpin", "typing_indicator", "read_receipt"],
                    },
                    "target_message_id": {"type": "string", "description": "Provider message id for reactions, pins, unpins, or thread replies."},
                    "text": {"type": "string", "description": "Optional body text for file shares or thread replies."},
                    "media_paths": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
                    "metadata": {"type": "object", "description": "Provider-specific fields such as emoji, thread_ts, topic_id, or file metadata."},
                    "reason": {"type": "string", "description": "Why this channel action should be prepared."},
                },
                required=["channel_id", "conversation_id", "action_type", "reason"],
            ),
            capability_group="channels",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        metadata = tool_input.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        try:
            action = prepare_channel_action(
                config,
                channel_id=str(tool_input.get("channel_id") or ""),
                conversation_id=str(tool_input.get("conversation_id") or ""),
                action_type=str(tool_input.get("action_type") or ""),
                target_message_id=str(tool_input.get("target_message_id") or ""),
                text=str(tool_input.get("text") or ""),
                media_paths=[str(item) for item in tool_input.get("media_paths", [])],
                metadata=metadata,
                reason=str(tool_input.get("reason") or ""),
            )
        except ValueError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc), error=str(exc))
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Prepared {action['action_type']} channel action envelope.",
            {"action": action},
        )


class ChannelOutboxTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="channel_outbox",
            description="List recent prepared outbound channel message envelopes.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"limit": {"type": "integer", "minimum": 1, "maximum": 100}}),
            capability_group="channels",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = max(1, min(int(tool_input.get("limit") or 20), 100))
        messages = list_outbox(config, limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(messages)} prepared channel message(s).",
            {"messages": messages},
        )


class ChannelListenerStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="channel_listener_status",
            description=(
                "Report native inbound listener readiness for enabled channels. "
                "Telegram can poll directly; Slack, Discord, WhatsApp, Teams, SMS, Google Chat, and WebChat use native webhook ingress."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"channel_id": {"type": "string", "description": "Optional exact channel id."}}),
            capability_group="channels",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        status = channel_listener_status(config, channel_id=str(tool_input.get("channel_id") or "") or None)
        ready = [item for item in status["listeners"] if item.get("ready", False)]
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"{len(ready)} channel listener(s) ready.",
            status,
        )


class ChannelListenerTickTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="channel_listener_tick",
            description=(
                "Poll native listener-capable channels once and route accepted inbound messages into the interaction harness. "
                "Currently this performs Telegram long-polling and reports webhook-ready state for other configured channels."
            ),
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "channel_id": {"type": "string", "description": "Optional exact channel id to tick."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    "prepare_replies": {"type": "boolean"},
                    "reason": {"type": "string", "description": "Why inbound channel listeners should be polled."},
                },
                required=["reason"],
            ),
            capability_group="channels",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would tick channel listeners.", dict(tool_input))
        result = channel_listener_tick(
            config,
            channel_id=str(tool_input.get("channel_id") or "") or None,
            limit=max(1, min(int(tool_input.get("limit") or 20), 100)),
            prepare_replies=bool(tool_input.get("prepare_replies", True)),
            approve_high_risk=False,
        )
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Processed {result['processed_count']} inbound channel event(s).",
            result,
        )


class ChannelWebhookIngestTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="channel_webhook_ingest",
            description=(
                "Normalize one provider webhook payload and route inbound channel messages into the interaction harness. "
                "Use for trusted local webhook forwarding from Slack, Discord, WhatsApp, SMS, Teams, Google Chat, Telegram, or WebChat."
            ),
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "channel_id": {"type": "string", "description": "Exact channel id."},
                    "payload": {"type": "object", "description": "Structured provider webhook payload."},
                    "prepare_reply": {"type": "boolean"},
                    "reason": {"type": "string", "description": "Why this webhook payload should be processed."},
                },
                required=["channel_id", "payload", "reason"],
            ),
            capability_group="channels",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        payload = tool_input.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        result = process_channel_webhook(
            config,
            channel_id=str(tool_input.get("channel_id") or ""),
            payload=payload,
            prepare_reply=bool(tool_input.get("prepare_reply", True)),
        )
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Processed {result.get('message_count', 0)} webhook message(s).",
            result,
        )


class ChannelRoutingPolicyPrepareTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="channel_routing_policy_prepare",
            description=(
                "Prepare native channel routing policy for access groups, broadcast groups, group routing, "
                "location events, ambient room events, pairing, and troubleshooting notes."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "channel_id": {"type": "string"},
                    "access_groups": {"type": "array", "items": {"type": "string"}, "maxItems": 100},
                    "broadcast_groups": {"type": "array", "items": {"type": "string"}, "maxItems": 100},
                    "group_routes": {"type": "array", "items": {"type": "object"}, "maxItems": 100},
                    "location_events_enabled": {"type": "boolean"},
                    "ambient_room_events_enabled": {"type": "boolean"},
                    "pairing_required": {"type": "boolean"},
                    "troubleshooting_notes": {"type": "array", "items": {"type": "string"}, "maxItems": 50},
                    "reason": {"type": "string"},
                },
                required=["channel_id", "reason"],
            ),
            capability_group="channels",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        channel_id = _clean_id(tool_input.get("channel_id"))
        channel = find_channel(channel_id)
        if channel is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown channel_id: {channel_id}")
        reason = str(tool_input.get("reason") or "").strip()
        if not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Reason is required.")
        policy_id = f"channel-routing-{channel_id}-{uuid.uuid4().hex[:8]}"
        policy = {
            "policy_id": policy_id,
            "channel_id": channel_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "prepared",
            "access_groups": _string_list(tool_input.get("access_groups"), limit=100),
            "broadcast_groups": _string_list(tool_input.get("broadcast_groups"), limit=100),
            "group_routes": _object_list(tool_input.get("group_routes"), limit=100),
            "location_events_enabled": bool(tool_input.get("location_events_enabled", False)),
            "ambient_room_events_enabled": bool(tool_input.get("ambient_room_events_enabled", False)),
            "pairing_required": bool(tool_input.get("pairing_required", channel.get("policies", {}).get("pairing_supported", False))),
            "troubleshooting_notes": _string_list(tool_input.get("troubleshooting_notes"), limit=50),
            "reason": reason,
            "catalog_policy": channel.get("policies", {}),
            "delivery_boundary": "Prepared routing policy only; live channel routing requires a trusted listener/runtime.",
        }
        path = (config.normalized().data_dir / "channel_state" / "routing_policies" / f"{policy_id}.json").resolve()
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would prepare channel routing policy.", {"policy": policy, "path": str(path)})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(policy, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        policy["path"] = str(path)
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Prepared channel routing policy for {channel_id}.", {"policy": policy})


class ChannelPairingPrepareTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="channel_pairing_prepare",
            description="Prepare a native channel pairing artifact for DM, group, device, or bridge setup without contacting the provider.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "channel_id": {"type": "string"},
                    "conversation_id": {"type": "string"},
                    "pairing_kind": {"type": "string", "enum": ["dm", "group", "device", "bridge", "webhook"]},
                    "identity_hint": {"type": "string"},
                    "expires_minutes": {"type": "integer", "minimum": 1, "maximum": 10080},
                    "reason": {"type": "string"},
                },
                required=["channel_id", "conversation_id", "pairing_kind", "reason"],
            ),
            capability_group="channels",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        channel_id = _clean_id(tool_input.get("channel_id"))
        channel = find_channel(channel_id)
        if channel is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown channel_id: {channel_id}")
        conversation_id = str(tool_input.get("conversation_id") or "").strip()
        reason = str(tool_input.get("reason") or "").strip()
        if not conversation_id or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "conversation_id and reason are required.")
        pairing_id = f"channel-pairing-{channel_id}-{uuid.uuid4().hex[:8]}"
        pairing = {
            "pairing_id": pairing_id,
            "channel_id": channel_id,
            "conversation_id": conversation_id,
            "pairing_kind": str(tool_input.get("pairing_kind") or "").strip(),
            "identity_hint": str(tool_input.get("identity_hint") or "").strip(),
            "expires_minutes": max(1, min(int(tool_input.get("expires_minutes") or 60), 10080)),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "prepared_not_paired",
            "reason": reason,
            "pairing_supported": bool(channel.get("policies", {}).get("pairing_supported", False)),
            "next_step": "Present this artifact through the trusted channel bridge or setup UI, then save non-secret setup state after human confirmation.",
        }
        path = (config.normalized().data_dir / "channel_state" / "pairings" / f"{pairing_id}.json").resolve()
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would prepare channel pairing.", {"pairing": pairing, "path": str(path)})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(pairing, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        pairing["path"] = str(path)
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Prepared channel pairing for {channel_id}.", {"pairing": pairing})


class ChannelTroubleshootingGuideTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="channel_troubleshooting_guide",
            description="Build a per-channel troubleshooting guide from setup requirements, doctor checks, policy, listener mode, and delivery contract.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"channel_id": {"type": "string"}}, required=["channel_id"]),
            capability_group="channels",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        del config
        channel_id = _clean_id(tool_input.get("channel_id"))
        channel = find_channel(channel_id)
        if channel is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown channel_id: {channel_id}")
        setup = channel.get("setup", {}) if isinstance(channel.get("setup"), dict) else {}
        guide = {
            "channel_id": channel_id,
            "display_name": channel.get("display_name", channel.get("name", "")),
            "setup_kind": channel.get("setup_kind", ""),
            "required_fields": setup.get("required_fields", []),
            "required_secrets": setup.get("required_secrets", []),
            "optional_secrets": setup.get("optional_secrets", []),
            "doctor_checks": setup.get("doctor_checks", []),
            "setup_steps": setup.get("steps", []),
            "policy": channel.get("policies", {}),
            "delivery": channel.get("delivery", {}),
            "runtime": channel.get("runtime", {}),
            "common_fixes": [
                "Verify all required env references are present in runtime secrets or the workspace environment.",
                "Confirm conversation_id matches the provider's native room, DM, phone number, or bridge id.",
                "Use channel_integration_smoke before attempting any live send.",
                "Keep prepared outbox review enabled until the channel bridge is trusted.",
            ],
        }
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Built troubleshooting guide for {channel_id}.", {"guide": guide})


def default_channel_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        ChannelCatalogTool(),
        ChannelManifestTool(),
        ChannelSetupRequirementsTool(),
        ChannelSetupSaveTool(),
        ChannelSetupStatusTool(),
        ChannelDoctorTool(),
        ChannelIntegrationSmokeTool(),
        ChannelMessagePrepareTool(),
        ChannelMessageSendTool(),
        ChannelActionPrepareTool(),
        ChannelOutboxTool(),
        ChannelListenerStatusTool(),
        ChannelListenerTickTool(),
        ChannelWebhookIngestTool(),
        ChannelRoutingPolicyPrepareTool(),
        ChannelPairingPrepareTool(),
        ChannelTroubleshootingGuideTool(),
    ]
    return {tool.name: tool for tool in tools}


def _channel_summary(channel: dict[str, Any], *, include_notes: bool) -> dict[str, Any]:
    payload = {
        "channel_id": channel.get("channel_id", ""),
        "name": channel.get("name", ""),
        "display_name": channel.get("display_name", channel.get("name", "")),
        "transport": channel.get("transport", ""),
        "runtime_adapter": channel.get("runtime_adapter", ""),
        "plugin_status": channel.get("plugin_status", ""),
        "plugin_kind": channel.get("plugin_kind", ""),
        "setup_kind": channel.get("setup_kind", ""),
        "setup": channel.get("setup", {}),
        "supports_text": bool(channel.get("supports_text", False)),
        "supports_media": bool(channel.get("supports_media", False)),
        "supports_reactions": bool(channel.get("supports_reactions", False)),
        "conversation_types": channel.get("conversation_types", []),
        "direct_send_implemented": bool(
            isinstance(channel.get("delivery", {}), dict)
            and isinstance(channel.get("delivery", {}).get("official_send", {}), dict)
            and channel.get("delivery", {}).get("official_send", {}).get("implemented", False)
        ),
    }
    if include_notes:
        payload["notes"] = channel.get("notes", [])
        payload["policies"] = channel.get("policies", {})
        payload["delivery"] = channel.get("delivery", {})
    return payload


def _clean_id(value: object) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", "_").split())[:120]


def _string_list(value: Any, *, limit: int) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value[:limit] if str(item).strip()]


def _object_list(value: Any, *, limit: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value[:limit] if isinstance(item, dict)]
