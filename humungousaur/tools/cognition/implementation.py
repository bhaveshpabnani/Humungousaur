from __future__ import annotations

from dataclasses import asdict
from typing import Any

from humungousaur.cognition import (
    BriefingEngine,
    BriefingStore,
    CommitmentReviewEngine,
    CommitmentReviewStore,
    CommitmentStore,
    ConsolidationStore,
    CognitiveRecorder,
    CurationEngine,
    CurationStore,
    EnvironmentReviewEngine,
    EnvironmentReviewStore,
    EnvironmentStore,
    EvidenceBriefingProvider,
    EvidenceCommitmentReviewProvider,
    EvidenceCurationProvider,
    EvidenceEnvironmentReviewProvider,
    EvidenceInteractionReviewProvider,
    EvidencePersonaEvolutionProvider,
    EvidenceSelfReviewProvider,
    EvidenceSkillEvolutionProvider,
    FocusStore,
    GoalStore,
    InteractionReviewEngine,
    InteractionReviewStore,
    KnowledgeStore,
    LearningStore,
    ModelBriefingProvider,
    ModelCommitmentReviewProvider,
    ModelCurationProvider,
    ModelEnvironmentReviewProvider,
    ModelInteractionReviewProvider,
    ModelPersonaEvolutionProvider,
    ModelSelfReviewProvider,
    ModelSkillEvolutionProvider,
    PersonaStore,
    PersonaEvolutionEngine,
    PersonaEvolutionStore,
    RecoveryStore,
    ReflectionStore,
    SelfReviewEngine,
    SelfReviewStore,
    SkillEvolutionEngine,
    SkillEvolutionStore,
    SkillStore,
    SpecialistStore,
    WakeupStore,
)
from humungousaur.cognition.models import CognitivePriority, CommitmentStatus, EnvironmentKind, FocusMode, KnowledgeKind, WakeupStatus
from humungousaur.cognition.queue import RuntimeEventQueue
from humungousaur.cognition.wakeups import scheduled_for_from_delay, try_normalize_scheduled_for
from humungousaur.config import AgentConfig
from humungousaur.planning.model_factory import build_model_client
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


class CognitiveStateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_state",
            description="Inspect active goals, tasks, persona, and reusable skills for the personal assistant runtime.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = min(int(tool_input.get("limit") or 8), 20)
        snapshot = CognitiveRecorder(config).snapshot()
        reflections = ReflectionStore(config.cognition_db_path).recent(limit=limit)
        consolidations = ConsolidationStore(config.cognition_db_path).recent(limit=limit)
        curations = CurationStore(config.cognition_db_path).recent(limit=limit)
        skill_evolutions = SkillEvolutionStore(config.cognition_db_path).recent(limit=limit)
        persona_evolutions = PersonaEvolutionStore(config.cognition_db_path).recent(limit=limit)
        self_reviews = SelfReviewStore(config.cognition_db_path).recent(limit=limit)
        interaction_reviews = InteractionReviewStore(config.cognition_db_path).recent(limit=limit)
        commitments = CommitmentStore(config.cognition_db_path).list(limit=limit)
        commitment_reviews = CommitmentReviewStore(config.cognition_db_path).recent(limit=limit)
        environment = EnvironmentStore(config.cognition_db_path).list(limit=limit)
        environment_reviews = EnvironmentReviewStore(config.cognition_db_path).recent(limit=limit)
        wakeups = WakeupStore(config.cognition_db_path).scheduled(limit=limit)
        payload = {
            "active_goals": [asdict(goal) for goal in snapshot.active_goals[:limit]],
            "active_tasks": [asdict(task) for task in snapshot.active_tasks[:limit]],
            "focus": asdict(snapshot.focus),
            "persona": asdict(snapshot.persona),
            "knowledge": [asdict(record) for record in snapshot.knowledge[:limit]],
            "learning": [asdict(record) for record in snapshot.learning[:limit]],
            "consolidations": [asdict(record) for record in snapshot.consolidations[:limit]],
            "wakeups": [asdict(record) for record in snapshot.wakeups[:limit]],
            "recoveries": [asdict(record) for record in snapshot.recoveries[:limit]],
            "briefings": [asdict(record) for record in snapshot.briefings[:limit]],
            "curations": [asdict(record) for record in snapshot.curations[:limit]],
            "skill_evolutions": [asdict(record) for record in snapshot.skill_evolutions[:limit]],
            "persona_evolutions": [asdict(record) for record in snapshot.persona_evolutions[:limit]],
            "self_reviews": [asdict(record) for record in snapshot.self_reviews[:limit]],
            "interaction_reviews": [asdict(record) for record in snapshot.interaction_reviews[:limit]],
            "commitments": [asdict(record) for record in snapshot.commitments[:limit]],
            "commitment_reviews": [asdict(record) for record in snapshot.commitment_reviews[:limit]],
            "environment": [asdict(record) for record in snapshot.environment[:limit]],
            "environment_reviews": [asdict(record) for record in snapshot.environment_reviews[:limit]],
            "skills": [asdict(skill) for skill in snapshot.skills[:limit]],
            "specialists": [asdict(specialist) for specialist in snapshot.specialists[:limit]],
            "recent_reflections": [asdict(reflection) for reflection in reflections],
            "recent_consolidations": [asdict(consolidation) for consolidation in consolidations],
            "recent_curations": [asdict(curation) for curation in curations],
            "recent_skill_evolutions": [asdict(record) for record in skill_evolutions],
            "recent_persona_evolutions": [asdict(record) for record in persona_evolutions],
            "recent_self_reviews": [asdict(record) for record in self_reviews],
            "recent_interaction_reviews": [asdict(record) for record in interaction_reviews],
            "recent_commitments": [asdict(record) for record in commitments],
            "recent_commitment_reviews": [asdict(record) for record in commitment_reviews],
            "recent_environment": [asdict(record) for record in environment],
            "recent_environment_reviews": [asdict(record) for record in environment_reviews],
            "scheduled_wakeups": [asdict(wakeup) for wakeup in wakeups],
        }
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Cognitive state: {len(payload['active_goals'])} active goals, {len(payload['active_tasks'])} active tasks, {len(payload['knowledge'])} knowledge records, {len(payload['skills'])} skills, {len(payload['specialists'])} specialists, {len(payload['consolidations'])} consolidations, {len(payload['wakeups'])} wakeups, {len(payload['recoveries'])} recoveries, {len(payload['briefings'])} briefings, {len(payload['curations'])} curations, {len(payload['skill_evolutions'])} skill evolutions, {len(payload['persona_evolutions'])} persona evolutions, {len(payload['self_reviews'])} self-reviews, {len(payload['interaction_reviews'])} interaction reviews, {len(payload['commitments'])} commitments, {len(payload['commitment_reviews'])} commitment reviews, {len(payload['environment'])} environment records, {len(payload['environment_reviews'])} environment reviews.",
            payload,
        )


class CognitiveBriefingPrepareTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_briefing_prepare",
            description="Prepare and store a model-led operational briefing from current focus, goals, tasks, memory, wakeups, recovery, skills, and persona.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "purpose": {"type": "string", "description": "Briefing purpose such as current, morning, handoff, review, or planning."},
                    "horizon_hours": {"type": "integer", "minimum": 1, "maximum": 720},
                    "include_state": {"type": "boolean", "description": "Attach the bounded raw cognitive state used for the briefing."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        purpose = str(tool_input.get("purpose", "current")).strip() or "current"
        horizon_hours = min(max(int(tool_input.get("horizon_hours") or 24), 1), 720)
        limit = min(int(tool_input.get("limit") or 8), 20)
        recorder = CognitiveRecorder(config)
        snapshot = recorder.snapshot()
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would prepare cognitive briefing.",
                {"purpose": purpose, "horizon_hours": horizon_hours, "state": _snapshot_payload(snapshot, limit=limit)},
            )
        engine = BriefingEngine(
            BriefingStore(config.cognition_db_path),
            provider=_build_briefing_provider(config),
        )
        briefing = engine.prepare(snapshot=snapshot, purpose=purpose, horizon_hours=horizon_hours)
        payload: dict[str, Any] = {"briefing": asdict(briefing)}
        if bool(tool_input.get("include_state", False)) or briefing.status.value == "skipped":
            payload["state"] = _snapshot_payload(snapshot, limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Cognitive briefing {briefing.status.value}: {briefing.summary}",
            payload,
        )


class CognitiveBriefingStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_briefing_status",
            description="Inspect recent current-work briefings prepared from the assistant's cognitive state.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = min(int(tool_input.get("limit") or 10), 50)
        briefings = BriefingStore(config.cognition_db_path).recent(limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(briefings)} cognitive briefing record(s).",
            {"briefings": [asdict(record) for record in briefings]},
        )


class CognitiveMemoryCurateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_memory_curate",
            description="Run a model-led memory hygiene pass over durable cognitive knowledge to retain, summarize, or archive exact records.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "purpose": {"type": "string", "description": "Curation purpose such as memory_hygiene, weekly_cleanup, duplicate_review, or privacy_review."},
                    "max_archive": {"type": "integer", "minimum": 0, "maximum": 20},
                    "max_summaries": {"type": "integer", "minimum": 0, "maximum": 10},
                    "include_state": {"type": "boolean", "description": "Attach the bounded raw cognitive state used for curation."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        purpose = str(tool_input.get("purpose", "memory_hygiene")).strip() or "memory_hygiene"
        max_archive = min(max(int(tool_input.get("max_archive") or 5), 0), 20)
        max_summaries = min(max(int(tool_input.get("max_summaries") or 3), 0), 10)
        limit = min(int(tool_input.get("limit") or 20), 50)
        recorder = CognitiveRecorder(config)
        snapshot = recorder.snapshot()
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would run cognitive memory curation.",
                {
                    "purpose": purpose,
                    "max_archive": max_archive,
                    "max_summaries": max_summaries,
                    "state": _snapshot_payload(snapshot, limit=limit),
                },
            )
        engine = CurationEngine(
            CurationStore(config.cognition_db_path),
            KnowledgeStore(config.cognition_db_path),
            provider=_build_curation_provider(config),
        )
        curation = engine.curate(snapshot=snapshot, purpose=purpose, max_archive=max_archive, max_summaries=max_summaries)
        payload: dict[str, Any] = {"curation": asdict(curation)}
        if bool(tool_input.get("include_state", False)) or curation.status.value == "skipped":
            payload["state"] = _snapshot_payload(snapshot, limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Cognitive memory curation {curation.status.value}: {curation.summary}",
            payload,
        )


class CognitiveCurationStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_curation_status",
            description="Inspect recent cognitive memory curation records.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = min(int(tool_input.get("limit") or 10), 50)
        curations = CurationStore(config.cognition_db_path).recent(limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(curations)} cognitive memory curation record(s).",
            {"curations": [asdict(record) for record in curations]},
        )


class CognitiveSkillEvolveTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_skill_evolve",
            description="Run a model-led review of reusable cognitive skills to improve, retire, create, or retain exact skill records from evidence.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "purpose": {"type": "string", "description": "Skill review purpose such as skill_review, weekly_learning, duplicate_skill_review, or workflow_upgrade."},
                    "max_updates": {"type": "integer", "minimum": 0, "maximum": 20},
                    "max_new_skills": {"type": "integer", "minimum": 0, "maximum": 10},
                    "include_state": {"type": "boolean", "description": "Attach the bounded raw cognitive state used for the review."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        purpose = str(tool_input.get("purpose", "skill_review")).strip() or "skill_review"
        max_updates = min(max(int(tool_input.get("max_updates") or 5), 0), 20)
        max_new_skills = min(max(int(tool_input.get("max_new_skills") or 3), 0), 10)
        limit = min(int(tool_input.get("limit") or 20), 50)
        recorder = CognitiveRecorder(config)
        snapshot = recorder.snapshot()
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would run cognitive skill evolution.",
                {
                    "purpose": purpose,
                    "max_updates": max_updates,
                    "max_new_skills": max_new_skills,
                    "state": _snapshot_payload(snapshot, limit=limit),
                },
            )
        engine = SkillEvolutionEngine(
            SkillEvolutionStore(config.cognition_db_path),
            SkillStore(config.skill_library_path),
            provider=_build_skill_evolution_provider(config),
        )
        evolution = engine.evolve(snapshot=snapshot, purpose=purpose, max_updates=max_updates, max_new_skills=max_new_skills)
        payload: dict[str, Any] = {"skill_evolution": asdict(evolution)}
        if bool(tool_input.get("include_state", False)) or evolution.status.value == "skipped":
            payload["state"] = _snapshot_payload(snapshot, limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Cognitive skill evolution {evolution.status.value}: {evolution.summary}",
            payload,
        )


class CognitiveSkillEvolutionStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_skill_evolution_status",
            description="Inspect recent cognitive skill evolution records.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = min(int(tool_input.get("limit") or 10), 50)
        evolutions = SkillEvolutionStore(config.cognition_db_path).recent(limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(evolutions)} cognitive skill evolution record(s).",
            {"skill_evolutions": [asdict(record) for record in evolutions]},
        )


class CognitiveGoalCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_goal_create",
            description="Create a durable assistant goal with success criteria for future or long-running work.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "title": {"type": "string", "description": "Goal title."},
                    "success_criteria": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 10,
                        "description": "Evidence that will prove this goal is complete.",
                    },
                },
                required=["title"],
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        title = str(tool_input.get("title", "")).strip()
        if not title:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Goal title is empty.")
        criteria = [str(item).strip() for item in tool_input.get("success_criteria", []) if str(item).strip()]
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would create cognitive goal.", {"title": title, "success_criteria": criteria})
        goal = GoalStore(config.cognition_db_path).create_goal(title, success_criteria=criteria, metadata={"source": "cognitive_goal_create"})
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Created cognitive goal {goal.goal_id}.", {"goal": asdict(goal)})


class CognitiveFocusUpdateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_focus_update",
            description="Update the assistant's durable current focus with explicit goal/task IDs, mode, summary, and pinned context.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "mode": {"type": "string", "enum": [mode.value for mode in FocusMode]},
                    "active_goal_id": {"type": "string"},
                    "active_task_id": {"type": "string"},
                    "summary": {"type": "string"},
                    "pinned_context": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                    "metadata": {"type": "object"},
                    "clear": {"type": "boolean"},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would update cognitive focus.", dict(tool_input))
        store = FocusStore(config.cognition_db_path)
        if bool(tool_input.get("clear", False)):
            focus = store.clear(summary=str(tool_input.get("summary", "")).strip())
        else:
            metadata = tool_input.get("metadata", {}) if "metadata" in tool_input else None
            focus = store.update(
                mode=str(tool_input.get("mode", "")).strip() or None,
                active_goal_id=str(tool_input.get("active_goal_id", "")).strip() if "active_goal_id" in tool_input else None,
                active_task_id=str(tool_input.get("active_task_id", "")).strip() if "active_task_id" in tool_input else None,
                summary=str(tool_input.get("summary", "")).strip() if "summary" in tool_input else None,
                pinned_context=[str(item) for item in tool_input.get("pinned_context", [])] if "pinned_context" in tool_input else None,
                metadata=metadata if isinstance(metadata, dict) else None,
            )
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Updated cognitive focus to {focus.mode.value}.", {"focus": asdict(focus)})


class CognitiveKnowledgeRecordTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_knowledge_record",
            description="Record a durable fact, preference, procedure, project context, or lesson with evidence references.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "kind": {"type": "string", "enum": [kind.value for kind in KnowledgeKind]},
                    "text": {"type": "string"},
                    "source": {"type": "string"},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                required=["kind", "text"],
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        text = str(tool_input.get("text", "")).strip()
        if not text:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Knowledge text is empty.")
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would record cognitive knowledge.", dict(tool_input))
        record = KnowledgeStore(config.cognition_db_path).append(
            kind=str(tool_input.get("kind", KnowledgeKind.CONTEXT.value)),
            text=text,
            source=str(tool_input.get("source", "manual")),
            evidence_refs=[str(item) for item in tool_input.get("evidence_refs", [])],
            confidence=float(tool_input.get("confidence", 0.5)),
        )
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Recorded knowledge {record.knowledge_id}.", {"knowledge": asdict(record)})


class CognitiveKnowledgeForgetTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_knowledge_forget",
            description="Archive one exact cognitive knowledge record by ID when it is stale, wrong, or no longer useful.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "knowledge_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                required=["knowledge_id"],
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        knowledge_id = str(tool_input.get("knowledge_id", "")).strip()
        if not knowledge_id:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Knowledge ID is empty.")
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would archive cognitive knowledge.", dict(tool_input))
        record = KnowledgeStore(config.cognition_db_path).archive(knowledge_id, reason=str(tool_input.get("reason", "")))
        if record is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Knowledge record was not found: {knowledge_id}")
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Archived knowledge {knowledge_id}.", {"knowledge": asdict(record)})


class CognitiveLearningStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_learning_status",
            description="Inspect recent execution-learning records or the experience history for one cognitive task.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "task_id": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = min(int(tool_input.get("limit") or 10), 50)
        task_id = str(tool_input.get("task_id", "")).strip()
        store = LearningStore(config.cognition_db_path)
        records = store.for_task(task_id, limit=limit) if task_id else store.recent(limit=limit)
        scope = f"task {task_id}" if task_id else "recent tasks"
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(records)} learning record(s) for {scope}.",
            {"learning": [asdict(record) for record in records]},
        )


class CognitiveConsolidationStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_consolidation_status",
            description="Inspect recent model-led experience consolidations or consolidation history for one cognitive task.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "task_id": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = min(int(tool_input.get("limit") or 10), 50)
        task_id = str(tool_input.get("task_id", "")).strip()
        store = ConsolidationStore(config.cognition_db_path)
        records = store.for_task(task_id, limit=limit) if task_id else store.recent(limit=limit)
        scope = f"task {task_id}" if task_id else "recent tasks"
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(records)} consolidation record(s) for {scope}.",
            {"consolidations": [asdict(record) for record in records]},
        )


class CognitiveRecoveryStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_recovery_status",
            description="Inspect recent adaptive recovery records or recovery history for one cognitive task.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "task_id": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = min(int(tool_input.get("limit") or 10), 50)
        task_id = str(tool_input.get("task_id", "")).strip()
        store = RecoveryStore(config.cognition_db_path)
        records = store.for_task(task_id, limit=limit) if task_id else store.recent(limit=limit)
        scope = f"task {task_id}" if task_id else "recent tasks"
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(records)} recovery record(s) for {scope}.",
            {"recoveries": [asdict(record) for record in records]},
        )


class CognitiveWakeupScheduleTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_wakeup_schedule",
            description="Schedule a future autonomous stimulus using an absolute ISO timestamp or a numeric delay.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "scheduled_for": {"type": "string", "description": "ISO-8601 timestamp. UTC is assumed if no timezone is present."},
                    "delay_seconds": {"type": "integer", "minimum": 1, "maximum": 31536000},
                    "event_type": {"type": "string", "enum": ["STIMULUS", "PASSIVE_STIMULUS", "USER_REQUEST", "VOICE_REQUEST"]},
                    "text": {"type": "string"},
                    "source": {"type": "string"},
                    "priority": {"type": "string", "enum": [priority.value for priority in CognitivePriority]},
                    "metadata": {"type": "object"},
                    "response_mode": {"type": "string", "enum": ["text", "voice_prepare", "voice_speak", "silent"]},
                    "goal_id": {"type": "string"},
                    "task_id": {"type": "string"},
                    "reason": {"type": "string"},
                    "should_run_agent": {"type": "boolean"},
                },
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        scheduled_for = _scheduled_for_from_input(tool_input)
        if not scheduled_for:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Wakeup requires delay_seconds or a valid ISO scheduled_for timestamp.")
        text = str(tool_input.get("text", "")).strip()
        if not text:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Wakeup text is empty.")
        metadata = tool_input.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        metadata = dict(metadata)
        if "should_run_agent" in tool_input:
            metadata["should_run_agent"] = bool(tool_input.get("should_run_agent"))
        else:
            metadata.setdefault("should_run_agent", True)
        metadata.setdefault("intent", "task")
        payload: dict[str, Any] = {
            "text": text,
            "source": str(tool_input.get("source", "wakeup")).strip() or "wakeup",
            "metadata": metadata,
        }
        response_mode = str(tool_input.get("response_mode", "")).strip()
        if response_mode:
            payload["response_mode"] = response_mode
        priority = CognitivePriority(str(tool_input.get("priority", CognitivePriority.NORMAL.value)).strip().lower() or CognitivePriority.NORMAL.value)
        event_type = str(tool_input.get("event_type", "STIMULUS")).strip().upper() or "STIMULUS"
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would schedule cognitive wakeup.",
                {"scheduled_for": scheduled_for, "event_type": event_type, "payload": payload},
            )
        wakeup = WakeupStore(config.cognition_db_path).schedule(
            scheduled_for=scheduled_for,
            event_type=event_type,
            payload=payload,
            priority=priority,
            source=payload["source"],
            goal_id=str(tool_input.get("goal_id", "")).strip(),
            task_id=str(tool_input.get("task_id", "")).strip(),
            reason=str(tool_input.get("reason", "")).strip(),
        )
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Scheduled wakeup {wakeup.wakeup_id}.", {"wakeup": asdict(wakeup)})


class CognitiveWakeupStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_wakeup_status",
            description="Inspect scheduled or recent future wakeups for proactive autonomous work.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "status": {"type": "string", "enum": [status.value for status in WakeupStatus]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = min(int(tool_input.get("limit") or 10), 50)
        status = str(tool_input.get("status", "")).strip().lower()
        store = WakeupStore(config.cognition_db_path)
        if status == WakeupStatus.SCHEDULED.value:
            records = store.scheduled(limit=limit)
        else:
            records = store.recent(limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(records)} wakeup record(s).",
            {"wakeups": [asdict(record) for record in records]},
        )


class CognitiveWakeupCancelTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_wakeup_cancel",
            description="Cancel one exact scheduled cognitive wakeup by ID.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "wakeup_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                required=["wakeup_id"],
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        wakeup_id = str(tool_input.get("wakeup_id", "")).strip()
        if not wakeup_id:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Wakeup ID is empty.")
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would cancel cognitive wakeup.", {"wakeup_id": wakeup_id})
        record = WakeupStore(config.cognition_db_path).cancel(wakeup_id, reason=str(tool_input.get("reason", "")))
        if record is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Wakeup was not found: {wakeup_id}")
        if record.status != WakeupStatus.CANCELLED:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Wakeup is not cancellable because it is {record.status.value}.", {"wakeup": asdict(record)})
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Cancelled wakeup {wakeup_id}.", {"wakeup": asdict(record)})


class CognitiveSkillRecordTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_skill_record",
            description="Record or update a reusable assistant skill with tools, verification steps, and failure modes.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "name": {"type": "string"},
                    "purpose": {"type": "string"},
                    "when_to_use": {"type": "string"},
                    "tools": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                    "verification_steps": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                    "failure_modes": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                required=["name", "purpose", "when_to_use"],
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would record cognitive skill.", dict(tool_input))
        skill = SkillStore(config.skill_library_path).upsert(
            name=str(tool_input.get("name", "")),
            purpose=str(tool_input.get("purpose", "")),
            when_to_use=str(tool_input.get("when_to_use", "")),
            tools=[str(item) for item in tool_input.get("tools", [])],
            verification_steps=[str(item) for item in tool_input.get("verification_steps", [])],
            failure_modes=[str(item) for item in tool_input.get("failure_modes", [])],
            confidence=float(tool_input.get("confidence", 0.5)),
        )
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Recorded skill {skill.name}.", {"skill": asdict(skill)})


class CognitiveSpecialistRecordTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_specialist_record",
            description="Record or update a specialist contract that model-led task graphs can explicitly delegate to.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "name": {"type": "string"},
                    "purpose": {"type": "string"},
                    "contract": {"type": "string"},
                    "tools": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
                    "success_criteria": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                    "permission_notes": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                required=["name", "purpose", "contract"],
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        name = str(tool_input.get("name", "")).strip()
        purpose = str(tool_input.get("purpose", "")).strip()
        contract = str(tool_input.get("contract", "")).strip()
        if not name or not purpose or not contract:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Specialist name, purpose, and contract are required.")
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would record cognitive specialist.", dict(tool_input))
        specialist = SpecialistStore(config.specialist_registry_path).upsert(
            name=name,
            purpose=purpose,
            contract=contract,
            tools=[str(item) for item in tool_input.get("tools", [])],
            success_criteria=[str(item) for item in tool_input.get("success_criteria", [])],
            permission_notes=[str(item) for item in tool_input.get("permission_notes", [])],
            confidence=float(tool_input.get("confidence", 0.5)),
        )
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Recorded specialist {specialist.name}.", {"specialist": asdict(specialist)})


class CognitivePersonaUpdateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_persona_update",
            description="Update the assistant's durable persona with an explicit user preference or stable fact.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "kind": {"type": "string", "enum": ["preference", "fact"]},
                    "text": {"type": "string"},
                },
                required=["kind", "text"],
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        kind = str(tool_input.get("kind", "preference")).strip().lower()
        text = str(tool_input.get("text", "")).strip()
        if not text:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Persona update text is empty.")
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would update persona.", {"kind": kind, "text": text})
        store = PersonaStore(config.persona_path)
        profile = store.add_fact(text) if kind == "fact" else store.add_preference(text)
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, "Updated assistant persona.", {"persona": asdict(profile)})


class CognitivePersonaEvolveTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_persona_evolve",
            description="Run a model-led review of assistant persona, user preferences, stable facts, boundaries, identity, and communication style from durable evidence.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "purpose": {"type": "string", "description": "Persona review purpose such as persona_review, communication_tuning, preference_review, or boundary_review."},
                    "include_state": {"type": "boolean", "description": "Attach the bounded raw cognitive state used for the review."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        purpose = str(tool_input.get("purpose", "persona_review")).strip() or "persona_review"
        limit = min(int(tool_input.get("limit") or 20), 50)
        recorder = CognitiveRecorder(config)
        snapshot = recorder.snapshot()
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would run cognitive persona evolution.",
                {"purpose": purpose, "state": _snapshot_payload(snapshot, limit=limit)},
            )
        engine = PersonaEvolutionEngine(
            PersonaEvolutionStore(config.cognition_db_path),
            PersonaStore(config.persona_path),
            provider=_build_persona_evolution_provider(config),
        )
        evolution = engine.evolve(snapshot=snapshot, purpose=purpose)
        payload: dict[str, Any] = {"persona_evolution": asdict(evolution)}
        if bool(tool_input.get("include_state", False)) or evolution.status.value == "skipped":
            payload["state"] = _snapshot_payload(snapshot, limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Cognitive persona evolution {evolution.status.value}: {evolution.summary}",
            payload,
        )


class CognitivePersonaEvolutionStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_persona_evolution_status",
            description="Inspect recent cognitive persona evolution records.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = min(int(tool_input.get("limit") or 10), 50)
        evolutions = PersonaEvolutionStore(config.cognition_db_path).recent(limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(evolutions)} cognitive persona evolution record(s).",
            {"persona_evolutions": [asdict(record) for record in evolutions]},
        )


class CognitiveSelfReviewTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_self_review",
            description="Run a model-led metacognitive self-review of uncertainty, risks, autonomy posture, open questions, and recommended next actions from current cognitive evidence.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "purpose": {"type": "string", "description": "Self-review purpose such as current_work, before_response, autonomy_check, risk_review, or uncertainty_review."},
                    "include_state": {"type": "boolean", "description": "Attach the bounded raw cognitive state used for the review."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        purpose = str(tool_input.get("purpose", "self_review")).strip() or "self_review"
        limit = min(int(tool_input.get("limit") or 20), 50)
        recorder = CognitiveRecorder(config)
        snapshot = recorder.snapshot()
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would run cognitive self-review.",
                {"purpose": purpose, "state": _snapshot_payload(snapshot, limit=limit)},
            )
        engine = SelfReviewEngine(
            SelfReviewStore(config.cognition_db_path),
            provider=_build_self_review_provider(config),
        )
        review = engine.review(snapshot=snapshot, purpose=purpose)
        payload: dict[str, Any] = {"self_review": asdict(review)}
        if bool(tool_input.get("include_state", False)) or review.status.value == "skipped":
            payload["state"] = _snapshot_payload(snapshot, limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Cognitive self-review {review.status.value}: {review.summary}",
            payload,
        )


class CognitiveSelfReviewStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_self_review_status",
            description="Inspect recent cognitive metacognitive self-review records.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = min(int(tool_input.get("limit") or 10), 50)
        reviews = SelfReviewStore(config.cognition_db_path).recent(limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(reviews)} cognitive self-review record(s).",
            {"self_reviews": [asdict(record) for record in reviews]},
        )


class CognitiveInteractionReviewTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_interaction_review",
            description="Run a model-led review of conversation state, collaboration posture, user-state hypotheses, unresolved commitments, response recommendations, and caution flags from current cognitive evidence.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "purpose": {"type": "string", "description": "Interaction review purpose such as relationship_review, before_response, collaboration_check, commitment_review, or conversation_state."},
                    "include_state": {"type": "boolean", "description": "Attach the bounded raw cognitive state used for the review."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        purpose = str(tool_input.get("purpose", "interaction_review")).strip() or "interaction_review"
        limit = min(int(tool_input.get("limit") or 20), 50)
        recorder = CognitiveRecorder(config)
        snapshot = recorder.snapshot()
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would run cognitive interaction review.",
                {"purpose": purpose, "state": _snapshot_payload(snapshot, limit=limit)},
            )
        engine = InteractionReviewEngine(
            InteractionReviewStore(config.cognition_db_path),
            provider=_build_interaction_review_provider(config),
        )
        review = engine.review(snapshot=snapshot, purpose=purpose)
        payload: dict[str, Any] = {"interaction_review": asdict(review)}
        if bool(tool_input.get("include_state", False)) or review.status.value == "skipped":
            payload["state"] = _snapshot_payload(snapshot, limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Cognitive interaction review {review.status.value}: {review.summary}",
            payload,
        )


class CognitiveInteractionReviewStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_interaction_review_status",
            description="Inspect recent cognitive conversation-state and collaboration reviews.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = min(int(tool_input.get("limit") or 10), 50)
        reviews = InteractionReviewStore(config.cognition_db_path).recent(limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(reviews)} cognitive interaction review record(s).",
            {"interaction_reviews": [asdict(record) for record in reviews]},
        )


class CognitiveCommitmentRecordTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_commitment_record",
            description="Record an explicit user-visible commitment or follow-up from structured evidence without inferring broad natural-language intent.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "title": {"type": "string", "description": "Specific owed action, promise, or follow-up."},
                    "owner": {"type": "string", "description": "Responsible owner, such as assistant, user, or a named specialist."},
                    "source": {"type": "string", "description": "Source of this commitment record."},
                    "due_at": {"type": "string", "description": "Optional due timestamp or user-visible timing note."},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                required=["title"],
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        title = str(tool_input.get("title", "")).strip()
        if not title:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Commitment title is empty.")
        evidence_refs = [str(item).strip() for item in tool_input.get("evidence_refs", []) if str(item).strip()]
        confidence = max(0.0, min(float(tool_input.get("confidence", 0.5) or 0.5), 1.0))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would record cognitive commitment.",
                {
                    "title": title,
                    "owner": str(tool_input.get("owner", "assistant")).strip() or "assistant",
                    "source": str(tool_input.get("source", "")).strip(),
                    "due_at": str(tool_input.get("due_at", "")).strip(),
                    "evidence_refs": evidence_refs,
                    "confidence": confidence,
                },
            )
        commitment = CommitmentStore(config.cognition_db_path).create(
            title=title,
            owner=str(tool_input.get("owner", "assistant")).strip() or "assistant",
            source=str(tool_input.get("source", "")).strip(),
            due_at=str(tool_input.get("due_at", "")).strip(),
            evidence_refs=evidence_refs,
            confidence=confidence,
        )
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Recorded cognitive commitment {commitment.commitment_id}.",
            {"commitment": asdict(commitment)},
        )


class CognitiveCommitmentUpdateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_commitment_update",
            description="Update one exact cognitive commitment by ID, including status, title, due note, evidence references, or confidence.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "commitment_id": {"type": "string"},
                    "title": {"type": "string"},
                    "status": {"type": "string", "enum": [status.value for status in CommitmentStatus]},
                    "due_at": {"type": "string"},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                required=["commitment_id"],
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        commitment_id = str(tool_input.get("commitment_id", "")).strip()
        if not commitment_id:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Commitment ID is empty.")
        status = None
        if "status" in tool_input and str(tool_input.get("status", "")).strip():
            try:
                status = CommitmentStatus(str(tool_input.get("status")).strip())
            except ValueError:
                return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Commitment status is invalid.")
        evidence_refs = [str(item).strip() for item in tool_input.get("evidence_refs", []) if str(item).strip()]
        confidence = None
        if "confidence" in tool_input:
            confidence = max(0.0, min(float(tool_input.get("confidence", 0.5) or 0.5), 1.0))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would update cognitive commitment.",
                dict(tool_input),
            )
        title = str(tool_input.get("title", "")).strip() if "title" in tool_input else None
        due_at = str(tool_input.get("due_at", "")).strip() if "due_at" in tool_input else None
        commitment = CommitmentStore(config.cognition_db_path).update(
            commitment_id,
            title=title,
            status=status,
            due_at=due_at,
            evidence_refs=evidence_refs,
            confidence=confidence,
        )
        if commitment is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Commitment {commitment_id} was not found.")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Updated cognitive commitment {commitment.commitment_id}.",
            {"commitment": asdict(commitment)},
        )


class CognitiveCommitmentReviewTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_commitment_review",
            description="Run a model-led review of durable evidence to create, update, resolve, or retain exact user-visible commitments and follow-ups.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "purpose": {"type": "string", "description": "Commitment review purpose such as commitment_review, handoff, follow_up_review, or before_response."},
                    "max_new_commitments": {"type": "integer", "minimum": 0, "maximum": 20},
                    "max_updates": {"type": "integer", "minimum": 0, "maximum": 40},
                    "include_state": {"type": "boolean", "description": "Attach the bounded raw cognitive state used for the review."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        purpose = str(tool_input.get("purpose", "commitment_review")).strip() or "commitment_review"
        max_new = min(max(int(tool_input.get("max_new_commitments") or 5), 0), 20)
        max_updates = min(max(int(tool_input.get("max_updates") or 10), 0), 40)
        limit = min(int(tool_input.get("limit") or 20), 50)
        recorder = CognitiveRecorder(config)
        snapshot = recorder.snapshot()
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would run cognitive commitment review.",
                {
                    "purpose": purpose,
                    "max_new_commitments": max_new,
                    "max_updates": max_updates,
                    "state": _snapshot_payload(snapshot, limit=limit),
                },
            )
        store = CommitmentStore(config.cognition_db_path)
        engine = CommitmentReviewEngine(
            CommitmentReviewStore(config.cognition_db_path),
            store,
            provider=_build_commitment_review_provider(config),
        )
        review = engine.review(
            snapshot=snapshot,
            purpose=purpose,
            max_new_commitments=max_new,
            max_updates=max_updates,
        )
        payload: dict[str, Any] = {
            "commitment_review": asdict(review),
            "commitments": [asdict(record) for record in store.list(limit=limit, include_closed=True)],
        }
        if bool(tool_input.get("include_state", False)) or review.status.value == "skipped":
            payload["state"] = _snapshot_payload(snapshot, limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Cognitive commitment review {review.status.value}: {review.summary}",
            payload,
        )


class CognitiveCommitmentStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_commitment_status",
            description="Inspect open or historical commitments and recent commitment review records.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "include_closed": {"type": "boolean"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = min(int(tool_input.get("limit") or 10), 50)
        include_closed = bool(tool_input.get("include_closed", False))
        commitments = CommitmentStore(config.cognition_db_path).list(limit=limit, include_closed=include_closed)
        reviews = CommitmentReviewStore(config.cognition_db_path).recent(limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(commitments)} cognitive commitment record(s) and {len(reviews)} review record(s).",
            {
                "commitments": [asdict(record) for record in commitments],
                "commitment_reviews": [asdict(record) for record in reviews],
            },
        )


class CognitiveEnvironmentRecordTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_environment_record",
            description="Record an explicit operating-environment fact, constraint, resource, risk, opportunity, or signal from structured evidence.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "kind": {"type": "string", "enum": [kind.value for kind in EnvironmentKind]},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "source": {"type": "string"},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                required=["kind", "title", "summary"],
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        title = str(tool_input.get("title", "")).strip()
        summary = str(tool_input.get("summary", "")).strip()
        if not title or not summary:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Environment title and summary are required.")
        try:
            kind = EnvironmentKind(str(tool_input.get("kind", "signal")).strip())
        except ValueError:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Environment kind is invalid.")
        evidence_refs = [str(item).strip() for item in tool_input.get("evidence_refs", []) if str(item).strip()]
        confidence = max(0.0, min(float(tool_input.get("confidence", 0.5) or 0.5), 1.0))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would record cognitive environment fact.",
                {
                    "kind": kind.value,
                    "title": title,
                    "summary": summary,
                    "source": str(tool_input.get("source", "")).strip(),
                    "evidence_refs": evidence_refs,
                    "confidence": confidence,
                },
            )
        record = EnvironmentStore(config.cognition_db_path).create(
            kind=kind,
            title=title,
            summary=summary,
            source=str(tool_input.get("source", "")).strip(),
            evidence_refs=evidence_refs,
            confidence=confidence,
        )
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Recorded cognitive environment fact {record.environment_id}.",
            {"environment": asdict(record)},
        )


class CognitiveEnvironmentUpdateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_environment_update",
            description="Update or archive one exact cognitive environment record by ID.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "environment_id": {"type": "string"},
                    "kind": {"type": "string", "enum": [kind.value for kind in EnvironmentKind]},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "archive_reason": {"type": "string"},
                },
                required=["environment_id"],
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        environment_id = str(tool_input.get("environment_id", "")).strip()
        if not environment_id:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Environment ID is empty.")
        kind = None
        if "kind" in tool_input and str(tool_input.get("kind", "")).strip():
            try:
                kind = EnvironmentKind(str(tool_input.get("kind")).strip())
            except ValueError:
                return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Environment kind is invalid.")
        evidence_refs = [str(item).strip() for item in tool_input.get("evidence_refs", []) if str(item).strip()]
        confidence = None
        if "confidence" in tool_input:
            confidence = max(0.0, min(float(tool_input.get("confidence", 0.5) or 0.5), 1.0))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would update cognitive environment record.",
                dict(tool_input),
            )
        store = EnvironmentStore(config.cognition_db_path)
        archive_reason = str(tool_input.get("archive_reason", "")).strip()
        if archive_reason:
            record = store.archive(environment_id, reason=archive_reason)
        else:
            title = str(tool_input.get("title", "")).strip() if "title" in tool_input else None
            summary = str(tool_input.get("summary", "")).strip() if "summary" in tool_input else None
            record = store.update(
                environment_id,
                kind=kind,
                title=title,
                summary=summary,
                evidence_refs=evidence_refs,
                confidence=confidence,
            )
        if record is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Environment record {environment_id} was not found.")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Updated cognitive environment record {record.environment_id}.",
            {"environment": asdict(record)},
        )


class CognitiveEnvironmentReviewTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_environment_review",
            description="Run a model-led review of durable evidence to create, update, archive, or retain exact operating-environment records.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "purpose": {"type": "string", "description": "Environment review purpose such as environment_review, workspace_review, system_context, risk_review, or handoff."},
                    "max_new_records": {"type": "integer", "minimum": 0, "maximum": 20},
                    "max_updates": {"type": "integer", "minimum": 0, "maximum": 40},
                    "include_state": {"type": "boolean", "description": "Attach the bounded raw cognitive state used for the review."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        purpose = str(tool_input.get("purpose", "environment_review")).strip() or "environment_review"
        max_new = min(max(int(tool_input.get("max_new_records") or 5), 0), 20)
        max_updates = min(max(int(tool_input.get("max_updates") or 10), 0), 40)
        limit = min(int(tool_input.get("limit") or 20), 50)
        recorder = CognitiveRecorder(config)
        snapshot = recorder.snapshot()
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would run cognitive environment review.",
                {
                    "purpose": purpose,
                    "max_new_records": max_new,
                    "max_updates": max_updates,
                    "state": _snapshot_payload(snapshot, limit=limit),
                },
            )
        store = EnvironmentStore(config.cognition_db_path)
        engine = EnvironmentReviewEngine(
            EnvironmentReviewStore(config.cognition_db_path),
            store,
            provider=_build_environment_review_provider(config),
        )
        review = engine.review(snapshot=snapshot, purpose=purpose, max_new_records=max_new, max_updates=max_updates)
        payload: dict[str, Any] = {
            "environment_review": asdict(review),
            "environment": [asdict(record) for record in store.list(limit=limit, include_archived=True)],
        }
        if bool(tool_input.get("include_state", False)) or review.status.value == "skipped":
            payload["state"] = _snapshot_payload(snapshot, limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Cognitive environment review {review.status.value}: {review.summary}",
            payload,
        )


class CognitiveEnvironmentStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_environment_status",
            description="Inspect current or historical operating-environment records and recent environment review history.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "include_archived": {"type": "boolean"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = min(int(tool_input.get("limit") or 10), 50)
        include_archived = bool(tool_input.get("include_archived", False))
        environment = EnvironmentStore(config.cognition_db_path).list(limit=limit, include_archived=include_archived)
        reviews = EnvironmentReviewStore(config.cognition_db_path).recent(limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(environment)} cognitive environment record(s) and {len(reviews)} review record(s).",
            {
                "environment": [asdict(record) for record in environment],
                "environment_reviews": [asdict(record) for record in reviews],
            },
        )


class CognitiveReflectionStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cognitive_reflection_status",
            description="Inspect recent completion reflections or the reflection history for one cognitive task.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "task_id": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = min(int(tool_input.get("limit") or 10), 50)
        task_id = str(tool_input.get("task_id", "")).strip()
        store = ReflectionStore(config.cognition_db_path)
        reflections = store.for_task(task_id, limit=limit) if task_id else store.recent(limit=limit)
        scope = f"task {task_id}" if task_id else "recent tasks"
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(reflections)} reflection record(s) for {scope}.",
            {"reflections": [asdict(reflection) for reflection in reflections]},
        )


class AutonomousEventSubmitTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="autonomous_event_submit",
            description="Queue a durable autonomous runtime event for later one-cycle processing.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "event_type": {
                        "type": "string",
                        "enum": ["USER_REQUEST", "VOICE_REQUEST", "STIMULUS", "PASSIVE_STIMULUS", "INTERRUPT", "PAUSE", "RESUME"],
                    },
                    "text": {"type": "string", "description": "Optional user/stimulus text for request events."},
                    "source": {"type": "string", "description": "Stimulus source such as user_text, voice_transcript, activity, browser, or system."},
                    "priority": {"type": "string", "enum": ["critical", "high", "normal", "low"]},
                    "metadata": {"type": "object", "description": "Structured event metadata."},
                    "response_mode": {"type": "string", "enum": ["text", "voice_prepare", "voice_speak", "silent"]},
                },
                required=["event_type"],
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        event_type = str(tool_input.get("event_type", "")).strip().upper()
        source = str(tool_input.get("source", "runtime")).strip() or "runtime"
        priority = CognitivePriority(str(tool_input.get("priority", "normal")).strip().lower() or "normal")
        metadata = tool_input.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        payload = {
            "text": str(tool_input.get("text", "")).strip(),
            "source": source,
            "metadata": metadata,
        }
        response_mode = str(tool_input.get("response_mode", "")).strip()
        if response_mode:
            payload["response_mode"] = response_mode
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would queue autonomous event.", {"event_type": event_type, "payload": payload})
        event = RuntimeEventQueue(config.cognition_db_path).push(event_type, payload=payload, priority=priority, source=source)
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Queued autonomous event {event.event_id}.", {"event": asdict(event)})


class AutonomousQueueStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="autonomous_queue_status",
            description="Inspect queued autonomous events and ready cognitive task-graph work.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"limit": {"type": "integer", "minimum": 1, "maximum": 20}}),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = min(int(tool_input.get("limit") or 8), 20)
        queue = RuntimeEventQueue(config.cognition_db_path)
        goals = GoalStore(config.cognition_db_path)
        queued = queue.queued(limit=limit)
        ready = goals.ready_tasks(limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Autonomous queue: {len(queued)} queued events, {len(ready)} ready tasks.",
            {
                "queued_events": [asdict(event) for event in queued],
                "ready_tasks": [asdict(task) for task in ready],
                "active_goals": [asdict(goal) for goal in goals.active_goals(limit=limit)],
            },
        )


class AutonomousTaskGraphCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="autonomous_task_graph_create",
            description="Create a durable goal with a dependency-aware task graph for complex autonomous work.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "goal_title": {"type": "string"},
                    "success_criteria": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
                    "tasks": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 20,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "task_id": {"type": "string"},
                                "title": {"type": "string"},
                                "request": {"type": "string"},
                                "owner": {"type": "string"},
                                "success_criteria": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
                                "depends_on": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                            },
                            "required": ["title"],
                        },
                    },
                },
                required=["goal_title", "tasks"],
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        title = str(tool_input.get("goal_title", "")).strip()
        raw_tasks = tool_input.get("tasks", [])
        if not title:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Goal title is empty.")
        if not isinstance(raw_tasks, list) or not raw_tasks:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Task graph has no tasks.")
        criteria = [str(item).strip() for item in tool_input.get("success_criteria", []) if str(item).strip()]
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would create autonomous task graph.", dict(tool_input))
        store = GoalStore(config.cognition_db_path)
        goal = store.create_goal(title, success_criteria=criteria, metadata={"source": "autonomous_task_graph_create"})
        id_map: dict[str, str] = {}
        created = []
        for index, raw in enumerate(raw_tasks, start=1):
            if not isinstance(raw, dict):
                continue
            local_id = _safe_local_id(str(raw.get("task_id") or f"task-{index}"))
            task_id = f"{goal.goal_id}-{local_id}"[:120]
            id_map[local_id] = task_id
        for index, raw in enumerate(raw_tasks, start=1):
            if not isinstance(raw, dict):
                continue
            local_id = _safe_local_id(str(raw.get("task_id") or f"task-{index}"))
            depends_on = [
                id_map[_safe_local_id(str(dep))]
                for dep in raw.get("depends_on", [])
                if _safe_local_id(str(dep)) in id_map
            ]
            task = store.add_task(
                goal.goal_id,
                str(raw.get("title", f"Task {index}")),
                owner=str(raw.get("owner", "master")),
                depends_on=depends_on,
                metadata={
                    "request": str(raw.get("request") or raw.get("title", "")),
                    "local_task_id": local_id,
                    "success_criteria": [
                        str(item).strip()
                        for item in raw.get("success_criteria", [])
                        if str(item).strip()
                    ],
                },
                task_id=id_map[local_id],
            )
            created.append(task)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created autonomous task graph {goal.goal_id} with {len(created)} tasks.",
            {"goal": asdict(goal), "tasks": [asdict(task) for task in created]},
        )


class AutonomousCycleRunTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="autonomous_cycle_run",
            description="Run a bounded number of autonomous cycles over queued events or ready tasks. Mutating actions remain governed by normal tool approvals.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "max_cycles": {"type": "integer", "minimum": 1, "maximum": 5},
                    "approve_inner_high_risk": {"type": "boolean"},
                }
            ),
            capability_group="cognition",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        max_cycles = min(int(tool_input.get("max_cycles") or 1), 5)
        approve_inner = bool(tool_input.get("approve_inner_high_risk", False))
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would run autonomous cycle.", {"max_cycles": max_cycles})
        from humungousaur.cognition.autonomous import AutonomousRuntime

        runtime = AutonomousRuntime(config)
        results = [runtime.run_once(approve_high_risk=approve_inner) for _ in range(max_cycles)]
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Ran {len(results)} autonomous cycle(s).",
            {"cycles": [asdict(result) for result in results]},
        )


def default_cognition_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        CognitiveStateTool(),
        CognitiveBriefingPrepareTool(),
        CognitiveBriefingStatusTool(),
        CognitiveMemoryCurateTool(),
        CognitiveCurationStatusTool(),
        CognitiveSkillEvolveTool(),
        CognitiveSkillEvolutionStatusTool(),
        CognitiveGoalCreateTool(),
        CognitiveFocusUpdateTool(),
        CognitiveKnowledgeRecordTool(),
        CognitiveKnowledgeForgetTool(),
        CognitiveLearningStatusTool(),
        CognitiveConsolidationStatusTool(),
        CognitiveRecoveryStatusTool(),
        CognitiveWakeupScheduleTool(),
        CognitiveWakeupStatusTool(),
        CognitiveWakeupCancelTool(),
        CognitiveSkillRecordTool(),
        CognitiveSpecialistRecordTool(),
        CognitivePersonaUpdateTool(),
        CognitivePersonaEvolveTool(),
        CognitivePersonaEvolutionStatusTool(),
        CognitiveSelfReviewTool(),
        CognitiveSelfReviewStatusTool(),
        CognitiveInteractionReviewTool(),
        CognitiveInteractionReviewStatusTool(),
        CognitiveCommitmentRecordTool(),
        CognitiveCommitmentUpdateTool(),
        CognitiveCommitmentReviewTool(),
        CognitiveCommitmentStatusTool(),
        CognitiveEnvironmentRecordTool(),
        CognitiveEnvironmentUpdateTool(),
        CognitiveEnvironmentReviewTool(),
        CognitiveEnvironmentStatusTool(),
        CognitiveReflectionStatusTool(),
        AutonomousEventSubmitTool(),
        AutonomousQueueStatusTool(),
        AutonomousTaskGraphCreateTool(),
        AutonomousCycleRunTool(),
    ]
    return {tool.name: tool for tool in tools}


def _safe_local_id(value: str) -> str:
    cleaned = "-".join(str(value or "task").strip().lower().split())
    cleaned = "".join(char for char in cleaned if char.isalnum() or char in {"-", "_"})
    return cleaned[:40] or "task"


def _build_briefing_provider(config: AgentConfig) -> EvidenceBriefingProvider | ModelBriefingProvider:
    fallback = EvidenceBriefingProvider()
    if config.planner_provider != "model":
        return fallback
    return ModelBriefingProvider(build_model_client(config), fallback=fallback)


def _build_curation_provider(config: AgentConfig) -> EvidenceCurationProvider | ModelCurationProvider:
    fallback = EvidenceCurationProvider()
    if config.planner_provider != "model":
        return fallback
    return ModelCurationProvider(build_model_client(config), fallback=fallback)


def _build_skill_evolution_provider(config: AgentConfig) -> EvidenceSkillEvolutionProvider | ModelSkillEvolutionProvider:
    fallback = EvidenceSkillEvolutionProvider()
    if config.planner_provider != "model":
        return fallback
    return ModelSkillEvolutionProvider(build_model_client(config), fallback=fallback)


def _build_persona_evolution_provider(config: AgentConfig) -> EvidencePersonaEvolutionProvider | ModelPersonaEvolutionProvider:
    fallback = EvidencePersonaEvolutionProvider()
    if config.planner_provider != "model":
        return fallback
    return ModelPersonaEvolutionProvider(build_model_client(config), fallback=fallback)


def _build_self_review_provider(config: AgentConfig) -> EvidenceSelfReviewProvider | ModelSelfReviewProvider:
    fallback = EvidenceSelfReviewProvider()
    if config.planner_provider != "model":
        return fallback
    return ModelSelfReviewProvider(build_model_client(config), fallback=fallback)


def _build_interaction_review_provider(config: AgentConfig) -> EvidenceInteractionReviewProvider | ModelInteractionReviewProvider:
    fallback = EvidenceInteractionReviewProvider()
    if config.planner_provider != "model":
        return fallback
    return ModelInteractionReviewProvider(build_model_client(config), fallback=fallback)


def _build_commitment_review_provider(config: AgentConfig) -> EvidenceCommitmentReviewProvider | ModelCommitmentReviewProvider:
    fallback = EvidenceCommitmentReviewProvider()
    if config.planner_provider != "model":
        return fallback
    return ModelCommitmentReviewProvider(build_model_client(config), fallback=fallback)


def _build_environment_review_provider(config: AgentConfig) -> EvidenceEnvironmentReviewProvider | ModelEnvironmentReviewProvider:
    fallback = EvidenceEnvironmentReviewProvider()
    if config.planner_provider != "model":
        return fallback
    return ModelEnvironmentReviewProvider(build_model_client(config), fallback=fallback)


def _snapshot_payload(snapshot: Any, *, limit: int) -> dict[str, Any]:
    return {
        "active_goals": [asdict(goal) for goal in snapshot.active_goals[:limit]],
        "active_tasks": [asdict(task) for task in snapshot.active_tasks[:limit]],
        "focus": asdict(snapshot.focus),
        "persona": asdict(snapshot.persona),
        "knowledge": [asdict(record) for record in snapshot.knowledge[:limit]],
        "learning": [asdict(record) for record in snapshot.learning[:limit]],
        "consolidations": [asdict(record) for record in snapshot.consolidations[:limit]],
        "wakeups": [asdict(record) for record in snapshot.wakeups[:limit]],
        "recoveries": [asdict(record) for record in snapshot.recoveries[:limit]],
        "briefings": [asdict(record) for record in snapshot.briefings[:limit]],
        "curations": [asdict(record) for record in snapshot.curations[:limit]],
        "skill_evolutions": [asdict(record) for record in snapshot.skill_evolutions[:limit]],
        "persona_evolutions": [asdict(record) for record in snapshot.persona_evolutions[:limit]],
        "self_reviews": [asdict(record) for record in snapshot.self_reviews[:limit]],
        "interaction_reviews": [asdict(record) for record in snapshot.interaction_reviews[:limit]],
        "commitments": [asdict(record) for record in snapshot.commitments[:limit]],
        "commitment_reviews": [asdict(record) for record in snapshot.commitment_reviews[:limit]],
        "environment": [asdict(record) for record in snapshot.environment[:limit]],
        "environment_reviews": [asdict(record) for record in snapshot.environment_reviews[:limit]],
        "skills": [asdict(record) for record in snapshot.skills[:limit]],
        "specialists": [asdict(record) for record in snapshot.specialists[:limit]],
    }


def _scheduled_for_from_input(tool_input: dict[str, Any]) -> str | None:
    if "delay_seconds" in tool_input and tool_input.get("delay_seconds") not in {None, ""}:
        try:
            return scheduled_for_from_delay(int(tool_input.get("delay_seconds")))
        except (TypeError, ValueError):
            return None
    scheduled_for = str(tool_input.get("scheduled_for", "")).strip()
    if not scheduled_for:
        return None
    return try_normalize_scheduled_for(scheduled_for)
