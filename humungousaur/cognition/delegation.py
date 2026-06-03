from __future__ import annotations

from dataclasses import dataclass

from humungousaur.config import AgentConfig
from humungousaur.schemas import AgentRunResult

from .models import SpecialistRecord, TaskRecord
from .specialists import SpecialistStore


@dataclass(slots=True)
class DelegationResult:
    owner: str
    specialist: SpecialistRecord | None
    request: str
    run: AgentRunResult


class SpecialistDelegationRunner:
    """Runs explicitly assigned specialist tasks.

    Specialist choice is not inferred here. The task graph must already carry an
    owner/specialist name, typically produced by model-led planning.
    """

    def __init__(self, config: AgentConfig) -> None:
        self.config = config.normalized()
        self.specialists = SpecialistStore(self.config.specialist_registry_path)

    def run_task(self, task: TaskRecord, *, approve_high_risk: bool = False) -> DelegationResult:
        specialist = self.specialists.get_by_name(task.owner)
        if specialist is not None:
            self.specialists.mark_used(specialist.name)
        request = self._request_for_task(task, specialist)
        from humungousaur.orchestrator import AgentOrchestrator

        run = AgentOrchestrator(self.config).run(request, approve_high_risk=approve_high_risk)
        return DelegationResult(owner=task.owner, specialist=specialist, request=request, run=run)

    def _request_for_task(self, task: TaskRecord, specialist: SpecialistRecord | None) -> str:
        request = str(task.metadata.get("request") or task.title).strip()
        if not specialist:
            return request
        if _looks_like_explicit_tool_command(request):
            return request
        return (
            "Specialist contract:\n"
            f"name: {specialist.name}\n"
            f"purpose: {specialist.purpose}\n"
            f"instructions: {specialist.contract}\n"
            f"success criteria: {specialist.success_criteria}\n\n"
            f"Task request: {request}"
        )


def _looks_like_explicit_tool_command(value: str) -> bool:
    text = value.strip()
    if not text or text.startswith("{"):
        return bool(text)
    if " " not in text:
        return False
    tool_name, _, payload = text.partition(" ")
    return bool(tool_name.replace("_", "").isalnum() and payload.strip().startswith("{"))
