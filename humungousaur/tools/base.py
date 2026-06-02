from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.schemas import RiskLevel, ToolResult


@dataclass(slots=True)
class Tool(ABC):
    name: str
    description: str
    risk_level: RiskLevel
    requires_approval: bool = False
    input_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})
    capability_group: str = "core"

    @abstractmethod
    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        raise NotImplementedError


def object_input_schema(
    properties: dict[str, dict[str, Any]] | None = None,
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties or {},
        "required": required or [],
    }
