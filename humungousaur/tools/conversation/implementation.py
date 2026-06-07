from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.planning.model_clients import redact_secrets
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


class ConversationResponsePrepareTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="conversation_response_prepare",
            description=(
                "Prepare a direct user-facing conversational reply when no external tool action is needed. "
                "Use this for greetings, brief chat, clarification, status acknowledgements, or lightweight responses."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "text": {"type": "string", "description": "The exact response text to show to the user."},
                    "reason": {"type": "string", "description": "Why a direct conversational response is sufficient."},
                    "tone": {"type": "string", "description": "Optional response tone, such as warm, concise, or calm."},
                },
                required=["text", "reason"],
            ),
            capability_group="conversation",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        del config
        text = redact_secrets(str(tool_input.get("text") or "").strip())
        reason = str(tool_input.get("reason") or "").strip()
        tone = str(tool_input.get("tone") or "").strip()
        if not text:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Conversation response text is required.")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            "Prepared direct conversational response.",
            {
                "text": text,
                "reason": reason,
                "tone": tone,
                "direct_user_response": True,
            },
        )


def default_conversation_tools() -> dict[str, Tool]:
    tool = ConversationResponsePrepareTool()
    return {tool.name: tool}
