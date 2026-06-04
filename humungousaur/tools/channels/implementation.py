from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.integrations.channels import (
    find_channel,
    list_outbox,
    load_channel_catalog,
    prepare_outbound_message,
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
                "source": "openclaw_style_gateway_catalog",
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


def default_channel_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        ChannelCatalogTool(),
        ChannelManifestTool(),
        ChannelMessagePrepareTool(),
        ChannelOutboxTool(),
    ]
    return {tool.name: tool for tool in tools}


def _channel_summary(channel: dict[str, Any], *, include_notes: bool) -> dict[str, Any]:
    payload = {
        "channel_id": channel.get("channel_id", ""),
        "name": channel.get("name", ""),
        "transport": channel.get("transport", ""),
        "plugin_status": channel.get("plugin_status", ""),
        "setup": channel.get("setup", ""),
        "supports_text": bool(channel.get("supports_text", False)),
        "supports_media": bool(channel.get("supports_media", False)),
        "supports_reactions": bool(channel.get("supports_reactions", False)),
        "conversation_types": channel.get("conversation_types", []),
    }
    if include_notes:
        payload["notes"] = channel.get("notes", [])
    return payload


def _clean_id(value: object) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", "_").split())[:120]
