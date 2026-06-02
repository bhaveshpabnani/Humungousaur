from __future__ import annotations

import uuid

from humungousaur.config import AgentConfig
from humungousaur.safety.policy import PolicyEngine
from humungousaur.schemas import ActionStatus, ApprovalRequest, PlannedStep, RiskLevel, ToolResult
from humungousaur.tools.base import Tool
from humungousaur.tools.validation import ToolInputValidationError, validate_tool_input


class Executor:
    def __init__(self, tools: dict[str, Tool], policy: PolicyEngine) -> None:
        self.tools = tools
        self.policy = policy

    def execute(self, step: PlannedStep, config: AgentConfig, approved: bool = False) -> ToolResult:
        tool = self.tools.get(step.tool_name)
        if tool is None:
            return ToolResult(
                tool_name=step.tool_name,
                status=ActionStatus.FAILED,
                risk_level=RiskLevel.BLOCKED,
                summary=f"Unknown tool: {step.tool_name}",
                error=f"Unknown tool: {step.tool_name}",
            )
        try:
            validate_tool_input(step.tool_input, tool.input_schema)
        except ToolInputValidationError as exc:
            return ToolResult(
                tool_name=tool.name,
                status=ActionStatus.FAILED,
                risk_level=tool.risk_level,
                summary=f"Invalid input for {tool.name}.",
                output={"input_schema": tool.input_schema},
                error=str(exc),
            )
        decision = self.policy.evaluate(tool, approved=approved)
        if not decision.allowed:
            status = ActionStatus.NEEDS_APPROVAL if decision.requires_approval else ActionStatus.BLOCKED
            output = {}
            if status == ActionStatus.NEEDS_APPROVAL:
                approval = ApprovalRequest(
                    tool_name=tool.name,
                    tool_input=step.tool_input,
                    risk_level=tool.risk_level,
                    reason=decision.reason,
                    approval_token=str(uuid.uuid4()),
                )
                output["approval"] = {
                    "tool_name": approval.tool_name,
                    "tool_input": approval.tool_input,
                    "risk_level": approval.risk_level.value,
                    "reason": approval.reason,
                    "approval_token": approval.approval_token,
                }
            return ToolResult(
                tool_name=tool.name,
                status=status,
                risk_level=tool.risk_level,
                summary=decision.reason,
                output=output,
                error=decision.reason,
            )
        try:
            return tool.execute(step.tool_input, config)
        except Exception as exc:
            return ToolResult(
                tool_name=tool.name,
                status=ActionStatus.FAILED,
                risk_level=tool.risk_level,
                summary=f"{tool.name} failed.",
                error=str(exc),
            )
