from __future__ import annotations

from humungousaur.config import AgentConfig
from humungousaur.memory.event_store import EventStore
from humungousaur.planning.model_factory import build_model_client
from humungousaur.schemas import ActionStatus, AgentRunResult

from .consolidation import (
    ConsolidationEngine,
    ConsolidationStore,
    EvidenceConsolidationProvider,
    ModelConsolidationProvider,
)
from .delegation import SpecialistDelegationRunner
from .event_bus import CognitiveEventBus
from .focus import FocusStore
from .goals import GoalStore
from .knowledge import KnowledgeStore
from .learning import LearningEngine, LearningStore
from .models import (
    AttentionAction,
    AutonomousCycleResult,
    CognitivePriority,
    FocusMode,
    GoalStatus,
    RuntimeCycleStatus,
    RuntimeEvent,
    StepBoundaryAction,
    TaskStatus,
)
from .queue import RuntimeEventQueue
from .recorder import CognitiveRecorder
from .persona import PersonaStore
from .priority import (
    EvidencePriorityReviewProvider,
    ModelPriorityReviewProvider,
    PriorityReviewEngine,
    PriorityReviewStatus,
    PriorityReviewStore,
)
from .recovery import EvidenceRecoveryProvider, ModelRecoveryProvider, RecoveryEngine, RecoveryStatus, RecoveryStore
from .reflection import EvidenceReflectionProvider, ModelReflectionProvider, ReflectionEngine, ReflectionStatus, ReflectionStore
from .skills import SkillStore
from .step_boundary import AtomicStepBoundary
from .wakeups import WakeupStore, scheduled_for_from_delay


REQUEST_EVENTS = {"USER_REQUEST", "VOICE_REQUEST", "STIMULUS", "PASSIVE_STIMULUS"}
CONTROL_EVENTS = {"PAUSE", "RESUME", "INTERRUPT"}


class AutonomousRuntime:
    """Durable one-cycle autonomous runtime.

    This is intentionally stepwise: one call handles at most one queued event or
    one ready task. Long-running autonomy is built by repeatedly calling
    ``run_once`` from a daemon, scheduler, or UI loop.
    """

    def __init__(self, config: AgentConfig) -> None:
        self.config = config.normalized()
        self.queue = RuntimeEventQueue(self.config.cognition_db_path)
        self.wakeups = WakeupStore(self.config.cognition_db_path)
        self.boundary = AtomicStepBoundary(self.queue)
        self.goals = GoalStore(self.config.cognition_db_path)
        self.events = CognitiveEventBus(self.config.cognition_db_path)
        self.focus = FocusStore(self.config.cognition_db_path)
        self.memory = EventStore(self.config.memory_db_path)
        self.recorder = CognitiveRecorder(self.config)
        self.delegation = SpecialistDelegationRunner(self.config)
        self.reflection = ReflectionEngine(
            ReflectionStore(self.config.cognition_db_path),
            provider=_build_reflection_provider(self.config),
        )
        self.learning = LearningEngine(LearningStore(self.config.cognition_db_path))
        self.consolidation = ConsolidationEngine(
            ConsolidationStore(self.config.cognition_db_path),
            KnowledgeStore(self.config.cognition_db_path),
            SkillStore(self.config.skill_library_path),
            PersonaStore(self.config.persona_path),
            provider=_build_consolidation_provider(self.config),
        )
        self.recovery = RecoveryEngine(
            RecoveryStore(self.config.cognition_db_path),
            self.goals,
            provider=_build_recovery_provider(self.config),
        )

    def submit_user_request(
        self,
        text: str,
        *,
        source: str = "user_text",
        response_mode: str | None = None,
        priority: CognitivePriority = CognitivePriority.HIGH,
        metadata: dict[str, object] | None = None,
    ) -> RuntimeEvent:
        payload = {
            "text": text,
            "source": source,
            "metadata": metadata or {},
        }
        if response_mode:
            payload["response_mode"] = response_mode
        event_type = "VOICE_REQUEST" if source == "voice_transcript" else "USER_REQUEST"
        return self.queue.push(event_type, payload=payload, priority=priority, source=source)

    def run_once(self, *, approve_high_risk: bool = False, allow_initiative: bool = False) -> AutonomousCycleResult:
        self._enqueue_due_wakeups()
        boundary_action = self.boundary.check()
        if boundary_action == StepBoundaryAction.PAUSE:
            event = self.queue.pop_type("PAUSE")
            return self._record_cycle(
                AutonomousCycleResult(RuntimeCycleStatus.PAUSED, "Autonomous runtime paused.", event=event)
            )
        if boundary_action == StepBoundaryAction.INTERRUPT:
            event = self.queue.pop_next()
            return self._handle_event(event, approve_high_risk=approve_high_risk, interrupted=True) if event else self._no_op()

        event = self.queue.pop_next()
        if event is not None:
            return self._handle_event(event, approve_high_risk=approve_high_risk)

        ready = self.goals.ready_tasks(limit=1)
        if ready:
            return self._execute_task(ready[0], approve_high_risk=approve_high_risk)
        if allow_initiative:
            initiative = self._queue_model_initiative()
            if initiative is not None:
                return initiative
        return self._no_op()

    def _handle_event(
        self,
        event: RuntimeEvent,
        *,
        approve_high_risk: bool,
        interrupted: bool = False,
    ) -> AutonomousCycleResult:
        if event.event_type in CONTROL_EVENTS:
            status = RuntimeCycleStatus.INTERRUPTED if interrupted or event.event_type == "INTERRUPT" else RuntimeCycleStatus.OBSERVED
            return self._record_cycle(AutonomousCycleResult(status, f"Observed control event {event.event_type}.", event=event))
        if event.event_type in REQUEST_EVENTS:
            return self._handle_request_event(event, approve_high_risk=approve_high_risk, interrupted=interrupted)
        self.events.append(event.source, event.event_type, {"runtime_event": event.payload}, priority=event.priority, event_id=event.event_id)
        return self._record_cycle(AutonomousCycleResult(RuntimeCycleStatus.OBSERVED, f"Recorded event {event.event_type}.", event=event))

    def _handle_request_event(
        self,
        event: RuntimeEvent,
        *,
        approve_high_risk: bool,
        interrupted: bool,
    ) -> AutonomousCycleResult:
        payload = event.payload
        text = str(payload.get("text", "")).strip()
        source = str(payload.get("source", event.source or "user_text")).strip() or "user_text"
        metadata = payload.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        response_mode = str(payload.get("response_mode", "")).strip() or None
        cognitive_event, decision, goal_id, task_id = self.recorder.begin_stimulus(
            source=source,
            text=text,
            metadata=metadata,
            response_mode=response_mode,
            event_id=event.event_id,
        )
        if not decision.should_run_agent:
            self.recorder.finish_stimulus(cognitive_event.event_id, decision, goal_id, task_id, run=None)
            self._schedule_decision_wakeup(decision, event, goal_id=goal_id, task_id=task_id)
            return self._record_cycle(
                AutonomousCycleResult(
                    RuntimeCycleStatus.OBSERVED,
                    decision.reason,
                    event=event,
                    goal_id=goal_id,
                    task_id=task_id,
                    next_wakeup_seconds=decision.next_wakeup_seconds,
                )
            )

        from humungousaur.orchestrator import AgentOrchestrator

        run = AgentOrchestrator(self.config).run(decision.request, approve_high_risk=approve_high_risk)
        self.recorder.finish_stimulus(cognitive_event.event_id, decision, goal_id, task_id, run=run)
        self._schedule_decision_wakeup(decision, event, goal_id=goal_id, task_id=task_id)
        status = _cycle_status_for_run(run)
        if interrupted and status == RuntimeCycleStatus.RUN_FINISHED:
            status = RuntimeCycleStatus.INTERRUPTED
        return self._record_cycle(
            AutonomousCycleResult(
                status,
                "Autonomous request cycle completed.",
                event=event,
                goal_id=goal_id,
                task_id=task_id,
                run_id=run.run_id,
                final_response=run.final_response,
                approvals_requested=len(run.approvals),
                next_wakeup_seconds=decision.next_wakeup_seconds,
            )
        )

    def _execute_task(self, task: object, *, approve_high_risk: bool) -> AutonomousCycleResult:
        request = str(getattr(task, "metadata", {}).get("request") or getattr(task, "title", "")).strip()
        task_id = str(getattr(task, "task_id"))
        goal_id = str(getattr(task, "goal_id"))
        if not request:
            self.goals.update_task(task_id, TaskStatus.BLOCKED, "Task has no executable request.")
            self.goals.update_goal(goal_id, GoalStatus.BLOCKED)
            return self._record_cycle(
                AutonomousCycleResult(RuntimeCycleStatus.FAILED, "Ready task had no executable request.", goal_id=goal_id, task_id=task_id)
            )
        self.goals.update_task(task_id, TaskStatus.RUNNING)
        self.focus.update(
            mode=FocusMode.DEEP_WORK,
            active_goal_id=goal_id,
            active_task_id=task_id,
            summary=f"Executing autonomous task: {getattr(task, 'title', task_id)}",
            metadata={"owner": getattr(task, "owner", ""), "source": "autonomous_runtime"},
        )
        delegation = self.delegation.run_task(task, approve_high_risk=approve_high_risk)
        run = delegation.run
        criteria = [str(item) for item in getattr(task, "metadata", {}).get("success_criteria", []) if str(item)]
        goal = self.goals.get_goal(goal_id)
        if not criteria and goal is not None:
            criteria = list(goal.success_criteria)
        reflection = self.reflection.evaluate_task(goal_id=goal_id, task_id=task_id, run=run, criteria=criteria)
        learning = self.learning.record_reflection(reflection=reflection, run=run)
        consolidation = self.consolidation.consolidate_task(run=run, reflection=reflection, learning=learning)
        recovery = self.recovery.recover_task(goal=goal, task=task, run=run, reflection=reflection, learning=learning)
        task_status = _task_status_for_reflection(reflection.status)
        if recovery.status == RecoveryStatus.PLANNED:
            task_status = TaskStatus.RECOVERING
        self.goals.update_task(
            task_id,
            task_status,
            result_summary=(recovery.summary if recovery.status == RecoveryStatus.PLANNED else run.final_response)[:1_000],
            metadata={
                **getattr(task, "metadata", {}),
                "run_id": run.run_id,
                "approvals_requested": len(run.approvals),
                "delegated_owner": delegation.owner,
                "specialist_id": delegation.specialist.specialist_id if delegation.specialist else "",
                "reflection_id": reflection.reflection_id,
                "reflection_status": reflection.status.value,
                "learning_id": learning.learning_id,
                "consolidation_id": consolidation.consolidation_id,
                "consolidation_status": consolidation.status.value,
                "recovery_id": recovery.recovery_id,
                "recovery_status": recovery.status.value,
                "recovery_task_ids": recovery.created_task_ids,
            },
        )
        terminal = self.goals.goal_is_terminal(goal_id)
        if terminal is not None:
            self.goals.update_goal(goal_id, terminal)
        keep_active = task_status in {TaskStatus.RECOVERING, TaskStatus.WAITING_APPROVAL, TaskStatus.BLOCKED, TaskStatus.FAILED}
        self.focus.update(
            mode=FocusMode.WAITING if task_status == TaskStatus.WAITING_APPROVAL else FocusMode.IDLE,
            active_goal_id=goal_id if keep_active else "",
            active_task_id=task_id if keep_active else "",
            summary=recovery.summary if recovery.status == RecoveryStatus.PLANNED else reflection.summary,
            metadata={
                "task_status": task_status.value,
                "reflection_id": reflection.reflection_id,
                "learning_id": learning.learning_id,
                "consolidation_id": consolidation.consolidation_id,
                "recovery_id": recovery.recovery_id,
                "recovery_status": recovery.status.value,
            },
        )
        return self._record_cycle(
            AutonomousCycleResult(
                _cycle_status_for_recovery(recovery.status, reflection.status),
                "Autonomous task cycle planned recovery." if recovery.status == RecoveryStatus.PLANNED else "Autonomous task cycle completed.",
                goal_id=goal_id,
                task_id=task_id,
                run_id=run.run_id,
                final_response=run.final_response,
                approvals_requested=len(run.approvals),
            )
        )

    def _record_cycle(self, result: AutonomousCycleResult) -> AutonomousCycleResult:
        self.memory.append(
            "autonomous_cycle",
            {
                "status": result.status.value,
                "reason": result.reason,
                "event_id": result.event.event_id if result.event else "",
                "event_type": result.event.event_type if result.event else "",
                "goal_id": result.goal_id or "",
                "task_id": result.task_id or "",
                "run_id": result.run_id or "",
                "approvals_requested": result.approvals_requested,
                "next_wakeup_seconds": result.next_wakeup_seconds,
            },
        )
        return result

    def _no_op(self) -> AutonomousCycleResult:
        return self._record_cycle(AutonomousCycleResult(RuntimeCycleStatus.NO_OP, "No queued events or ready tasks."))

    def _queue_model_initiative(self) -> AutonomousCycleResult | None:
        if self.config.planner_provider != "model":
            return None
        review = PriorityReviewEngine(
            PriorityReviewStore(self.config.cognition_db_path),
            provider=_build_priority_review_provider(self.config),
        ).review(snapshot=self.recorder.snapshot(), purpose="autonomous_idle_initiative")
        if review.status != PriorityReviewStatus.GENERATED or not review.next_actions:
            return self._record_cycle(
                AutonomousCycleResult(
                    RuntimeCycleStatus.NO_OP,
                    review.summary or "No model-led initiative was queued.",
                )
            )
        text = review.next_actions[0].strip()
        if not text:
            return self._record_cycle(
                AutonomousCycleResult(RuntimeCycleStatus.NO_OP, "Priority review produced an empty initiative action.")
            )
        event = self.queue.push(
            "STIMULUS",
            payload={
                "text": text,
                "source": "initiative",
                "metadata": {
                    "should_run_agent": True,
                    "intent": "task",
                    "priority_review_id": review.review_id,
                    "evidence_refs": review.evidence_refs,
                },
                "response_mode": "silent",
            },
            priority=CognitivePriority.NORMAL,
            source="initiative",
        )
        return self._record_cycle(
            AutonomousCycleResult(
                RuntimeCycleStatus.INITIATIVE_QUEUED,
                f"Queued model-led initiative from priority review {review.review_id}.",
                event=event,
            )
        )

    def _enqueue_due_wakeups(self) -> list[RuntimeEvent]:
        events: list[RuntimeEvent] = []
        for wakeup in self.wakeups.due(limit=10):
            payload = dict(wakeup.payload)
            metadata = payload.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            metadata.update(
                {
                    "wakeup_id": wakeup.wakeup_id,
                    "goal_id": wakeup.goal_id,
                    "task_id": wakeup.task_id,
                    "scheduled_for": wakeup.scheduled_for,
                    "wakeup_reason": wakeup.reason,
                    "should_run_agent": metadata.get("should_run_agent", True),
                    "intent": metadata.get("intent", "task"),
                }
            )
            payload["metadata"] = metadata
            payload["source"] = str(payload.get("source") or wakeup.source or "wakeup")
            event = self.queue.push(wakeup.event_type, payload=payload, priority=wakeup.priority, source=wakeup.source)
            self.wakeups.mark_fired(wakeup.wakeup_id, fired_event_id=event.event_id)
            events.append(event)
        return events

    def _schedule_decision_wakeup(
        self,
        decision: object,
        event: RuntimeEvent,
        *,
        goal_id: str | None,
        task_id: str | None,
    ) -> None:
        seconds = getattr(decision, "next_wakeup_seconds", None)
        if not isinstance(seconds, int) or seconds <= 0:
            return
        text = str(getattr(decision, "request", "") or event.payload.get("text", "")).strip()
        if not text:
            return
        metadata = {
            "origin_event_id": event.event_id,
            "goal_id": goal_id or "",
            "task_id": task_id or "",
            "should_run_agent": True,
            "intent": "task",
        }
        self.wakeups.schedule(
            scheduled_for=scheduled_for_from_delay(seconds),
            event_type="STIMULUS",
            payload={
                "text": text,
                "source": "wakeup",
                "metadata": metadata,
                "response_mode": getattr(decision, "response_mode", "silent") or "silent",
            },
            priority=CognitivePriority.NORMAL,
            source="wakeup",
            goal_id=goal_id or "",
            task_id=task_id or "",
            reason=str(getattr(decision, "reason", "") or "Model-led attention requested a future wakeup.")[:1_000],
        )


def _cycle_status_for_run(run: AgentRunResult, task: bool = False) -> RuntimeCycleStatus:
    if run.approvals:
        return RuntimeCycleStatus.WAITING_APPROVAL
    if any(result.status in {ActionStatus.FAILED, ActionStatus.BLOCKED} for result in run.results):
        return RuntimeCycleStatus.FAILED
    return RuntimeCycleStatus.TASK_FINISHED if task else RuntimeCycleStatus.RUN_FINISHED


def _task_status_for_run(run: AgentRunResult) -> TaskStatus:
    if run.approvals:
        return TaskStatus.WAITING_APPROVAL
    if any(result.status == ActionStatus.FAILED for result in run.results):
        return TaskStatus.FAILED
    if any(result.status == ActionStatus.BLOCKED for result in run.results):
        return TaskStatus.BLOCKED
    if any(result.status == ActionStatus.CANCELLED for result in run.results):
        return TaskStatus.CANCELLED
    return TaskStatus.COMPLETED


def _task_status_for_reflection(status: ReflectionStatus) -> TaskStatus:
    if status == ReflectionStatus.PASSED:
        return TaskStatus.COMPLETED
    if status == ReflectionStatus.NEEDS_APPROVAL:
        return TaskStatus.WAITING_APPROVAL
    if status == ReflectionStatus.FAILED:
        return TaskStatus.FAILED
    if status == ReflectionStatus.BLOCKED:
        return TaskStatus.BLOCKED
    return TaskStatus.BLOCKED


def _cycle_status_for_reflection(status: ReflectionStatus) -> RuntimeCycleStatus:
    if status == ReflectionStatus.PASSED:
        return RuntimeCycleStatus.TASK_FINISHED
    if status == ReflectionStatus.NEEDS_APPROVAL:
        return RuntimeCycleStatus.WAITING_APPROVAL
    return RuntimeCycleStatus.FAILED


def _cycle_status_for_recovery(status: RecoveryStatus, reflection_status: ReflectionStatus) -> RuntimeCycleStatus:
    if status == RecoveryStatus.PLANNED:
        return RuntimeCycleStatus.RECOVERY_PLANNED
    return _cycle_status_for_reflection(reflection_status)


def _build_reflection_provider(config: AgentConfig) -> EvidenceReflectionProvider | ModelReflectionProvider:
    fallback = EvidenceReflectionProvider()
    if config.planner_provider != "model":
        return fallback
    return ModelReflectionProvider(build_model_client(config), fallback=fallback)


def _build_consolidation_provider(config: AgentConfig) -> EvidenceConsolidationProvider | ModelConsolidationProvider:
    fallback = EvidenceConsolidationProvider()
    if config.planner_provider != "model":
        return fallback
    return ModelConsolidationProvider(build_model_client(config), fallback=fallback)


def _build_recovery_provider(config: AgentConfig) -> EvidenceRecoveryProvider | ModelRecoveryProvider:
    fallback = EvidenceRecoveryProvider()
    if config.planner_provider != "model":
        return fallback
    return ModelRecoveryProvider(build_model_client(config), fallback=fallback)


def _build_priority_review_provider(config: AgentConfig) -> EvidencePriorityReviewProvider | ModelPriorityReviewProvider:
    fallback = EvidencePriorityReviewProvider()
    if config.planner_provider != "model":
        return fallback
    return ModelPriorityReviewProvider(build_model_client(config), fallback=fallback)
