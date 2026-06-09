from __future__ import annotations

from dataclasses import dataclass

from humungousaur.config import AgentConfig
from humungousaur.planning.prompt_templates import render_prompt_template
from humungousaur.schemas import AgentRunResult

from .models import SpecialistRecord, TaskRecord
from .specialists import SpecialistStore

COGNITION_PROMPT_RESOURCE = "resources/prompts/cognition.yaml"
SPECIALIST_DELEGATION_TEMPLATE = "specialist_delegation_request"


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
        return render_prompt_template(
            SPECIALIST_DELEGATION_TEMPLATE,
            resource=COGNITION_PROMPT_RESOURCE,
            specialist_name=specialist.name,
            specialist_purpose=specialist.purpose,
            specialist_contract=specialist.contract,
            specialist_success_criteria=_format_success_criteria(specialist.success_criteria),
            task_request=request,
        )


def _looks_like_explicit_tool_command(value: str) -> bool:
    text = value.strip()
    if not text or text.startswith("{"):
        return bool(text)
    if " " not in text:
        return False
    tool_name, _, payload = text.partition(" ")
    return bool(tool_name.replace("_", "").isalnum() and payload.strip().startswith("{"))


def _format_success_criteria(criteria: list[str]) -> str:
    if not criteria:
        return "- No explicit specialist criteria supplied."
    return "\n".join(f"- {criterion}" for criterion in criteria)
