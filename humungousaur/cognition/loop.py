from __future__ import annotations

from dataclasses import asdict, dataclass, field
from time import monotonic, sleep
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.memory.event_store import EventStore

from .autonomous import AutonomousRuntime
from .goals import GoalStore
from .models import AutonomousCycleResult, RuntimeCycleStatus, utc_now
from .queue import RuntimeEventQueue
from .wakeups import WakeupStore


@dataclass(slots=True)
class AutonomousLoopResult:
    cycles: list[AutonomousCycleResult] = field(default_factory=list)
    stopped_reason: str = ""
    idle_cycles: int = 0
    started_at: str = field(default_factory=utc_now)
    finished_at: str = ""
    duration_ms: float = 0.0

    @property
    def cycle_count(self) -> int:
        return len(self.cycles)


class AutonomousLoopRunner:
    """Bounded autonomous cycle runner for daemon, CLI, and API surfaces."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config.normalized()

    def run(
        self,
        *,
        max_cycles: int = 10,
        idle_sleep_seconds: float = 0.0,
        stop_after_idle_cycles: int = 1,
        approve_high_risk: bool = False,
        allow_initiative: bool = False,
    ) -> AutonomousLoopResult:
        max_cycles = max(1, min(int(max_cycles), 1_000))
        stop_after_idle_cycles = max(1, min(int(stop_after_idle_cycles), max_cycles))
        idle_sleep_seconds = max(0.0, min(float(idle_sleep_seconds), 60.0))
        runtime = AutonomousRuntime(self.config)
        result = AutonomousLoopResult()
        start = monotonic()
        idle_cycles = 0
        for _index in range(max_cycles):
            cycle = runtime.run_once(approve_high_risk=approve_high_risk, allow_initiative=allow_initiative)
            result.cycles.append(cycle)
            if cycle.status == RuntimeCycleStatus.NO_OP:
                idle_cycles += 1
            else:
                idle_cycles = 0
            result.idle_cycles = idle_cycles
            if idle_cycles >= stop_after_idle_cycles:
                result.stopped_reason = "idle"
                break
            if idle_sleep_seconds and cycle.status == RuntimeCycleStatus.NO_OP:
                sleep(idle_sleep_seconds)
        if not result.stopped_reason:
            result.stopped_reason = "max_cycles"
        result.finished_at = utc_now()
        result.duration_ms = round((monotonic() - start) * 1000, 3)
        EventStore(self.config.memory_db_path).append(
            "autonomous_loop",
            {
                "cycle_count": result.cycle_count,
                "stopped_reason": result.stopped_reason,
                "idle_cycles": result.idle_cycles,
                "duration_ms": result.duration_ms,
                "allow_initiative": allow_initiative,
                "cycle_statuses": [cycle.status.value for cycle in result.cycles],
            },
        )
        return result


def autonomous_status(config: AgentConfig, *, limit: int = 10) -> dict[str, Any]:
    normalized = config.normalized()
    limit = max(1, min(int(limit), 100))
    queue = RuntimeEventQueue(normalized.cognition_db_path)
    goals = GoalStore(normalized.cognition_db_path)
    wakeups = WakeupStore(normalized.cognition_db_path)
    memory = EventStore(normalized.memory_db_path)
    return {
        "queued_events": [asdict(event) for event in queue.queued(limit=limit)],
        "ready_tasks": [asdict(task) for task in goals.ready_tasks(limit=limit)],
        "active_goals": [asdict(goal) for goal in goals.active_goals(limit=limit)],
        "scheduled_wakeups": [asdict(wakeup) for wakeup in wakeups.scheduled(limit=limit)],
        "recent_wakeups": [asdict(wakeup) for wakeup in wakeups.recent(limit=limit)],
        "recent_cycles": memory.search("autonomous_cycle", limit=limit),
        "recent_loops": memory.search("autonomous_loop", limit=limit),
    }


def autonomous_loop_result_to_dict(result: AutonomousLoopResult) -> dict[str, Any]:
    return {
        "cycle_count": result.cycle_count,
        "stopped_reason": result.stopped_reason,
        "idle_cycles": result.idle_cycles,
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "duration_ms": result.duration_ms,
        "cycles": [asdict(cycle) for cycle in result.cycles],
    }
