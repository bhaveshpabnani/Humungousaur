from __future__ import annotations

from typing import Any

from humungousaur.planning.providers import ExplicitFallbackPlanProvider, PlanProvider
from humungousaur.schemas import PlanResult


class Planner:
    """Planner facade that can swap model-backed and explicit providers."""

    def __init__(self, provider: PlanProvider | None = None) -> None:
        self.provider = provider or ExplicitFallbackPlanProvider()

    def plan(self, request: str, context: dict[str, Any] | None = None) -> PlanResult:
        return self.provider.plan(request, context=context)
