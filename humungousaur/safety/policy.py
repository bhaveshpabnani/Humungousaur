from __future__ import annotations

from dataclasses import dataclass

from humungousaur.schemas import RiskLevel
from humungousaur.tools.base import Tool


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    requires_approval: bool
    reason: str


class PolicyEngine:
    """Central action gate. All tool calls pass through here before execution."""

    def evaluate(self, tool: Tool, approved: bool = False) -> PolicyDecision:
        if tool.risk_level == RiskLevel.BLOCKED:
            return PolicyDecision(False, False, "Tool is blocked by policy.")
        if tool.risk_level == RiskLevel.HIGH:
            if approved:
                return PolicyDecision(True, True, "High-risk action approved.")
            return PolicyDecision(False, True, "High-risk action requires explicit approval.")
        if tool.requires_approval and not approved:
            return PolicyDecision(False, True, "Tool requires explicit approval.")
        return PolicyDecision(True, tool.requires_approval, "Allowed by local policy.")
