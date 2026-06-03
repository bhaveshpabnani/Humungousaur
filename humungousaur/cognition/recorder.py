from __future__ import annotations

from dataclasses import asdict
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.env import load_workspace_environment
from humungousaur.memory.event_store import EventStore
from humungousaur.planning.model_factory import build_model_client
from humungousaur.schemas import ActionStatus, AgentRunResult

from .consolidation import ConsolidationStore
from .briefing import BriefingStore
from .controller import CognitiveController, ExplicitCognitiveDecisionProvider, ModelCognitiveDecisionProvider
from .curation import CurationStore
from .event_bus import CognitiveEventBus
from .focus import FocusStore
from .goals import GoalStore
from .knowledge import KnowledgeStore
from .learning import LearningEngine, LearningStore
from .models import (
    CognitiveDecision,
    CognitiveEvent,
    CognitivePriority,
    CognitiveSnapshot,
    FocusMode,
    GoalStatus,
    TaskStatus,
)
from .persona import PersonaStore
from .recovery import RecoveryStore
from .skills import SkillStore
from .specialists import SpecialistStore
from .wakeups import WakeupStore


class CognitiveRecorder:
    """Durable cognitive state bridge for the existing interaction harness."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config.normalized()
        load_workspace_environment(self.config.workspace)
        self.events = CognitiveEventBus(self.config.cognition_db_path)
        self.focus = FocusStore(self.config.cognition_db_path)
        self.goals = GoalStore(self.config.cognition_db_path)
        self.knowledge = KnowledgeStore(self.config.cognition_db_path)
        self.learning_store = LearningStore(self.config.cognition_db_path)
        self.learning = LearningEngine(self.learning_store)
        self.consolidations = ConsolidationStore(self.config.cognition_db_path)
        self.wakeups = WakeupStore(self.config.cognition_db_path)
        self.recoveries = RecoveryStore(self.config.cognition_db_path)
        self.briefings = BriefingStore(self.config.cognition_db_path)
        self.curations = CurationStore(self.config.cognition_db_path)
        self.persona = PersonaStore(self.config.persona_path)
        self.skills = SkillStore(self.config.skill_library_path)
        self.specialists = SpecialistStore(self.config.specialist_registry_path)
        self.memory = EventStore(self.config.memory_db_path)
        self.controller = CognitiveController(_build_decision_provider(self.config))

    def snapshot(self) -> CognitiveSnapshot:
        return CognitiveSnapshot(
            active_goals=self.goals.active_goals(limit=8),
            active_tasks=self.goals.active_tasks(limit=16),
            focus=self.focus.load(),
            persona=self.persona.load(),
            knowledge=self.knowledge.list(limit=8),
            learning=self.learning_store.recent(limit=8),
            consolidations=self.consolidations.recent(limit=8),
            wakeups=self.wakeups.scheduled(limit=8),
            recoveries=self.recoveries.recent(limit=8),
            briefings=self.briefings.recent(limit=8),
            curations=self.curations.recent(limit=8),
            skills=self.skills.list(limit=8),
            specialists=self.specialists.list(limit=8),
        )

    def begin_stimulus(
        self,
        source: str,
        text: str,
        metadata: dict[str, Any],
        response_mode: str | None = None,
        event_id: str | None = None,
    ) -> tuple[CognitiveEvent, CognitiveDecision, str | None, str | None]:
        priority = CognitivePriority.HIGH if source in {"user_text", "voice_transcript"} else CognitivePriority.NORMAL
        event = self.events.append(source=source, text=text, metadata=metadata, priority=priority, event_id=event_id)
        decision = self.controller.decide(event, self.snapshot(), response_mode=response_mode)
        goal_id: str | None = decision.focus_goal_id
        task_id: str | None = None
        if decision.should_run_agent:
            if not goal_id:
                goal = self.goals.create_goal(
                    decision.create_goal_title or text,
                    success_criteria=["The user-visible request has an evidence-backed result or a clear blocker."],
                    metadata={"source_event_id": event.event_id, "source": source},
                )
                goal_id = goal.goal_id
            task = self.goals.add_task(
                goal_id,
                decision.create_task_title or text,
                metadata={"source_event_id": event.event_id, "response_mode": decision.response_mode},
            )
            task_id = task.task_id
            self.goals.update_task(task_id, TaskStatus.RUNNING)
            self.focus.update(
                mode=FocusMode.RESPONDING,
                active_goal_id=goal_id,
                active_task_id=task_id,
                summary=f"Handling {source} event.",
                metadata={"event_id": event.event_id, "source": source},
            )
        self.memory.append(
            "cognitive_decision",
            {
                "event_id": event.event_id,
                "source": source,
                "decision": decision.action.value,
                "reason": decision.reason,
                "should_run_agent": decision.should_run_agent,
                "goal_id": goal_id or "",
                "task_id": task_id or "",
                "memory_action": decision.memory_action.value,
            },
        )
        return event, decision, goal_id, task_id

    def finish_stimulus(
        self,
        event_id: str,
        decision: CognitiveDecision,
        goal_id: str | None,
        task_id: str | None,
        run: AgentRunResult | None,
        voice_result: dict[str, Any] | None = None,
    ) -> None:
        task_status = _task_status(run)
        goal_status = _goal_status(task_status, decision)
        result_summary = run.final_response[:1_000] if run else decision.reason
        if task_id:
            self.goals.update_task(
                task_id,
                task_status,
                result_summary=result_summary,
                metadata={
                    "event_id": event_id,
                    "run_id": run.run_id if run else "",
                    "approvals_requested": len(run.approvals) if run else 0,
                    "voice_response_id": (voice_result or {}).get("response_id", ""),
                },
            )
        if goal_id and task_status in {TaskStatus.COMPLETED, TaskStatus.WAITING_APPROVAL, TaskStatus.FAILED, TaskStatus.BLOCKED}:
            self.goals.update_goal(goal_id, goal_status)
        if task_id:
            next_mode = FocusMode.WAITING if task_status == TaskStatus.WAITING_APPROVAL else FocusMode.IDLE
            keep_active = task_status in {TaskStatus.WAITING_APPROVAL, TaskStatus.BLOCKED, TaskStatus.FAILED}
            self.focus.update(
                mode=next_mode,
                active_goal_id=goal_id or "" if keep_active else "",
                active_task_id=task_id if keep_active else "",
                summary=result_summary,
                metadata={
                    "event_id": event_id,
                    "run_id": run.run_id if run else "",
                    "task_status": task_status.value,
                    "goal_status": goal_status.value,
                },
            )
            self.learning.record_run(
                goal_id=goal_id or "",
                task_id=task_id,
                run=run,
                outcome=task_status.value,
                lesson=f"Stimulus finished with task status {task_status.value} and goal status {goal_status.value}.",
                evidence_refs=[f"event:{event_id}"],
            )
        self.memory.append(
            "cognitive_result",
            {
                "event_id": event_id,
                "decision": decision.action.value,
                "goal_id": goal_id or "",
                "task_id": task_id or "",
                "run_id": run.run_id if run else "",
                "task_status": task_status.value,
                "goal_status": goal_status.value,
                "voice_response_id": (voice_result or {}).get("response_id", ""),
            },
        )


def _task_status(run: AgentRunResult | None) -> TaskStatus:
    if run is None:
        return TaskStatus.COMPLETED
    if run.approvals:
        return TaskStatus.WAITING_APPROVAL
    if any(result.status == ActionStatus.FAILED for result in run.results):
        return TaskStatus.FAILED
    if any(result.status == ActionStatus.BLOCKED for result in run.results):
        return TaskStatus.BLOCKED
    if any(result.status == ActionStatus.CANCELLED for result in run.results):
        return TaskStatus.CANCELLED
    return TaskStatus.COMPLETED


def _goal_status(task_status: TaskStatus, decision: CognitiveDecision) -> GoalStatus:
    if task_status == TaskStatus.WAITING_APPROVAL:
        return GoalStatus.WAITING
    if task_status == TaskStatus.FAILED:
        return GoalStatus.BLOCKED
    if task_status == TaskStatus.BLOCKED:
        return GoalStatus.BLOCKED
    if task_status == TaskStatus.CANCELLED:
        return GoalStatus.CANCELLED
    if decision.stay_warm:
        return GoalStatus.WAITING
    return GoalStatus.COMPLETED


def _build_decision_provider(config: AgentConfig) -> ExplicitCognitiveDecisionProvider | ModelCognitiveDecisionProvider:
    fallback = ExplicitCognitiveDecisionProvider()
    if config.planner_provider != "model":
        return fallback
    return ModelCognitiveDecisionProvider(build_model_client(config), fallback=fallback)
