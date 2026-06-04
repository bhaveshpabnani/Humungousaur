from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from humungousaur.config import AgentConfig

from .goals import GoalStore
from .loop import AutonomousLoopRunner, autonomous_loop_result_to_dict
from .models import GoalRecord, SpecialistRecord, TaskRecord, utc_now
from .specialists import SpecialistStore


@dataclass(slots=True)
class MultiAgentCoordination:
    goal: GoalRecord
    tasks: list[TaskRecord]
    specialists: list[SpecialistRecord] = field(default_factory=list)
    cycles: dict[str, Any] | None = None
    created_at: str = field(default_factory=utc_now)


class MultiAgentCoordinator:
    """Coordinates specialist contracts through the existing autonomous graph runtime."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config.normalized()
        self.goals = GoalStore(self.config.cognition_db_path)
        self.specialists = SpecialistStore(self.config.specialist_registry_path)

    def create_coordination(
        self,
        *,
        goal_title: str,
        success_criteria: list[str] | None,
        specialists: list[dict[str, Any]] | None,
        tasks: list[dict[str, Any]],
        run_cycles: bool = False,
        max_cycles: int = 1,
        approve_high_risk: bool = False,
    ) -> MultiAgentCoordination:
        title = _clean(goal_title, limit=160)
        if not title:
            raise ValueError("Goal title is empty.")
        if not tasks:
            raise ValueError("At least one task is required.")
        specialist_records = self._upsert_specialists(specialists or [])
        goal = self.goals.create_goal(
            title,
            success_criteria=_string_list(success_criteria, limit=300),
            metadata={"source": "multi_agent_coordinate", "specialist_count": len(specialist_records)},
        )
        created = self._create_tasks(goal.goal_id, tasks)
        cycles = None
        if run_cycles:
            result = AutonomousLoopRunner(self.config).run(
                max_cycles=max(1, min(int(max_cycles), 20)),
                stop_after_idle_cycles=1,
                approve_high_risk=approve_high_risk,
                allow_initiative=False,
            )
            cycles = autonomous_loop_result_to_dict(result)
        return MultiAgentCoordination(goal=goal, tasks=created, specialists=specialist_records, cycles=cycles)

    def board(self, *, limit: int = 20) -> dict[str, Any]:
        limit = max(1, min(int(limit), 100))
        specialists = self.specialists.list(limit=limit)
        active_goals = self.goals.active_goals(limit=limit)
        ready_tasks = self.goals.ready_tasks(limit=limit)
        active_tasks = self.goals.active_tasks(limit=limit)
        tasks_by_owner: dict[str, list[dict[str, Any]]] = {}
        for task in active_tasks:
            tasks_by_owner.setdefault(task.owner or "master", []).append(asdict(task))
        return {
            "specialists": [asdict(record) for record in specialists],
            "active_goals": [asdict(record) for record in active_goals],
            "ready_tasks": [asdict(record) for record in ready_tasks],
            "active_tasks_by_owner": tasks_by_owner,
            "coordination_contract": {
                "execution": "dependency-aware task graph",
                "delegation": "task owner names are matched to exact specialist contracts",
                "current_parallelism": "single orchestrator, bounded cycles",
            },
        }

    def _upsert_specialists(self, specialists: list[dict[str, Any]]) -> list[SpecialistRecord]:
        records: list[SpecialistRecord] = []
        for item in specialists[:30]:
            if not isinstance(item, dict):
                continue
            name = _clean(item.get("name"), limit=120)
            purpose = _clean(item.get("purpose"), limit=1_000)
            contract = _clean(item.get("contract"), limit=2_000)
            if not name or not purpose or not contract:
                continue
            records.append(
                self.specialists.upsert(
                    name=name,
                    purpose=purpose,
                    contract=contract,
                    tools=_string_list(item.get("tools"), limit=120),
                    success_criteria=_string_list(item.get("success_criteria"), limit=300),
                    permission_notes=_string_list(item.get("permission_notes"), limit=300),
                    confidence=_confidence(item.get("confidence")),
                )
            )
        return records

    def _create_tasks(self, goal_id: str, tasks: list[dict[str, Any]]) -> list[TaskRecord]:
        id_map: dict[str, str] = {}
        for index, raw in enumerate(tasks[:50], start=1):
            local_id = _safe_local_id(str(raw.get("task_id") or f"task-{index}") if isinstance(raw, dict) else f"task-{index}")
            id_map[local_id] = f"{goal_id}-{local_id}"[:120]
        created: list[TaskRecord] = []
        for index, raw in enumerate(tasks[:50], start=1):
            if not isinstance(raw, dict):
                continue
            local_id = _safe_local_id(str(raw.get("task_id") or f"task-{index}"))
            depends_on = [
                id_map[_safe_local_id(str(dep))]
                for dep in raw.get("depends_on", [])
                if _safe_local_id(str(dep)) in id_map
            ]
            title = _clean(raw.get("title") or f"Task {index}", limit=160)
            owner = _clean(raw.get("owner") or "master", limit=120) or "master"
            request = _clean(raw.get("request") or title, limit=4_000)
            created.append(
                self.goals.add_task(
                    goal_id,
                    title,
                    owner=owner,
                    depends_on=depends_on,
                    metadata={
                        "request": request,
                        "local_task_id": local_id,
                        "success_criteria": _string_list(raw.get("success_criteria"), limit=300),
                        "source": "multi_agent_coordinate",
                    },
                    task_id=id_map[local_id],
                )
            )
        return created


def coordination_to_dict(record: MultiAgentCoordination) -> dict[str, Any]:
    return {
        "goal": asdict(record.goal),
        "tasks": [asdict(task) for task in record.tasks],
        "specialists": [asdict(specialist) for specialist in record.specialists],
        "cycles": record.cycles,
        "created_at": record.created_at,
    }


def _safe_local_id(value: str) -> str:
    cleaned = []
    previous_dash = False
    for char in str(value or "").casefold():
        if char.isalnum():
            cleaned.append(char)
            previous_dash = False
        elif not previous_dash:
            cleaned.append("-")
            previous_dash = True
    return ("".join(cleaned).strip("-") or "task")[:48]


def _string_list(value: object, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        cleaned = _clean(item, limit=limit)
        if cleaned:
            items.append(cleaned)
    return items[:50]


def _clean(value: object, *, limit: int) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _confidence(value: object) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return 0.5
