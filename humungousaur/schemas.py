from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"


class ActionStatus(StrEnum):
    PLANNED = "planned"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    NEEDS_APPROVAL = "needs_approval"


@dataclass(slots=True)
class PlannedStep:
    tool_name: str
    tool_input: dict[str, Any]
    reason: str
    source: str = "explicit"


@dataclass(slots=True)
class PlanResult:
    requested_provider: str
    used_provider: str
    steps: list[PlannedStep]
    fallback_used: bool = False
    error: str | None = None
    duration_ms: float = 0.0


@dataclass(slots=True)
class ApprovalRequest:
    tool_name: str
    tool_input: dict[str, Any]
    risk_level: RiskLevel
    reason: str
    approval_token: str


@dataclass(slots=True)
class ToolResult:
    tool_name: str
    status: ActionStatus
    risk_level: RiskLevel
    summary: str
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(slots=True)
class AgentRunResult:
    run_id: str
    request: str
    final_response: str
    results: list[ToolResult]
    approvals: list[ApprovalRequest] = field(default_factory=list)
    note_path: str | None = None
