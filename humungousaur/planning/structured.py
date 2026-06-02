from __future__ import annotations

import json
from typing import Any

from humungousaur.schemas import PlannedStep


class PlanValidationError(ValueError):
    pass


class StructuredPlanParser:
    """Parse model-produced plans into validated tool steps.

    This is deliberately strict because model output is untrusted until it passes
    schema and allowlist checks.
    """

    def __init__(self, allowed_tools: set[str], max_steps: int = 8) -> None:
        self.allowed_tools = allowed_tools
        self.max_steps = max_steps

    def json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["steps"],
            "properties": {
                "steps": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": self.max_steps,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["tool_name", "tool_input", "reason"],
                        "properties": {
                            "tool_name": {"type": "string", "enum": sorted(self.allowed_tools)},
                            "tool_input": {"type": "object", "additionalProperties": True},
                            "reason": {"type": "string", "minLength": 1},
                        },
                    },
                }
            },
        }

    def parse(self, payload: str) -> list[PlannedStep]:
        try:
            document = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise PlanValidationError(f"Plan must be valid JSON: {exc}") from exc

        if not isinstance(document, dict):
            raise PlanValidationError("Plan must be a JSON object.")
        steps = document.get("steps")
        if steps is None:
            steps = self._single_step_alias(document)
        if not isinstance(steps, list) or not steps:
            raise PlanValidationError("Plan must include a non-empty steps list.")
        if len(steps) > self.max_steps:
            raise PlanValidationError(f"Plan has too many steps; maximum is {self.max_steps}.")

        parsed: list[PlannedStep] = []
        for index, item in enumerate(steps, start=1):
            if not isinstance(item, dict):
                raise PlanValidationError(f"Step {index} must be an object.")
            tool_name = item.get("tool_name")
            tool_input = item.get("tool_input", {})
            reason = item.get("reason", "Model-planned step.")
            self._validate_step(index, tool_name, tool_input, reason)
            parsed.append(PlannedStep(str(tool_name), tool_input, str(reason), "structured-json"))
        return parsed

    def _single_step_alias(self, document: dict[str, Any]) -> list[dict[str, Any]] | None:
        tool_name = document.get("tool_name") or document.get("tool") or document.get("function_name")
        if not tool_name:
            return None
        tool_input = document.get("tool_input", document.get("input", document.get("args", {})))
        reason = document.get("reason", "Model-planned step.")
        return [{"tool_name": tool_name, "tool_input": tool_input, "reason": reason}]

    def _validate_step(self, index: int, tool_name: Any, tool_input: Any, reason: Any) -> None:
        if not isinstance(tool_name, str) or not tool_name:
            raise PlanValidationError(f"Step {index} has invalid tool_name.")
        if tool_name not in self.allowed_tools:
            raise PlanValidationError(f"Step {index} uses unknown or disallowed tool: {tool_name}")
        if not isinstance(tool_input, dict):
            raise PlanValidationError(f"Step {index} tool_input must be an object.")
        if not isinstance(reason, str) or not reason.strip():
            raise PlanValidationError(f"Step {index} reason must be a non-empty string.")
