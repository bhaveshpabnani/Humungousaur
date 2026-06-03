from datetime import datetime, timedelta, timezone
import json
import tempfile
import unittest
from pathlib import Path

from humungousaur.cognition import (
    BriefingEngine,
    BriefingStore,
    ConsolidationEngine,
    ConsolidationStore,
    CognitiveEventBus,
    CognitiveRecorder,
    CurationEngine,
    CurationStore,
    EvidenceBriefingProvider,
    EvidenceConsolidationProvider,
    EvidenceCurationProvider,
    EvidenceReflectionProvider,
    ExplicitCognitiveDecisionProvider,
    FocusStore,
    GoalStore,
    KnowledgeStore,
    LearningStore,
    AutonomousLoopRunner,
    autonomous_loop_result_to_dict,
    autonomous_status,
    ModelBriefingProvider,
    ModelCognitiveDecisionProvider,
    ModelConsolidationProvider,
    ModelCurationProvider,
    ModelReflectionProvider,
    PersonaStore,
    RecoveryEngine,
    RecoveryStore,
    EvidenceRecoveryProvider,
    ModelRecoveryProvider,
    ReflectionRecord,
    ReflectionEngine,
    ReflectionStore,
    EvidenceSkillEvolutionProvider,
    ModelSkillEvolutionProvider,
    SkillEvolutionEngine,
    SkillEvolutionStore,
    SkillStore,
    SpecialistStore,
    WakeupStore,
)
from humungousaur.cognition.autonomous import AutonomousRuntime
from humungousaur.cognition.models import (
    AttentionAction,
    BriefingStatus,
    ConsolidationStatus,
    CurationStatus,
    CognitiveEvent,
    CognitivePriority,
    CognitiveSnapshot,
    FocusMode,
    GoalStatus,
    KnowledgeKind,
    MemoryAction,
    ReflectionStatus,
    RuntimeCycleStatus,
    RecoveryStatus,
    SkillEvolutionStatus,
    SkillLifecycleStatus,
    StepBoundaryAction,
    TaskStatus,
    WakeupStatus,
)
from humungousaur.cognition.queue import RuntimeEventQueue
from humungousaur.cognition.step_boundary import AtomicStepBoundary
from humungousaur.config import AgentConfig
from humungousaur.interaction import InteractionHarness
from humungousaur.planning.model_clients import ModelClientError, StaticModelClient
from humungousaur.schemas import ActionStatus, AgentRunResult, ApprovalRequest, RiskLevel, ToolResult
from humungousaur.tools.cognition_tools import (
    AutonomousTaskGraphCreateTool,
    CognitiveBriefingPrepareTool,
    CognitiveBriefingStatusTool,
    CognitiveConsolidationStatusTool,
    CognitiveCurationStatusTool,
    CognitiveFocusUpdateTool,
    CognitiveGoalCreateTool,
    CognitiveKnowledgeForgetTool,
    CognitiveKnowledgeRecordTool,
    CognitiveLearningStatusTool,
    CognitiveMemoryCurateTool,
    CognitivePersonaUpdateTool,
    CognitiveReflectionStatusTool,
    CognitiveRecoveryStatusTool,
    CognitiveSkillEvolveTool,
    CognitiveSkillEvolutionStatusTool,
    CognitiveSkillRecordTool,
    CognitiveSpecialistRecordTool,
    CognitiveStateTool,
    CognitiveWakeupCancelTool,
    CognitiveWakeupScheduleTool,
    CognitiveWakeupStatusTool,
)


class CognitiveStoreTests(unittest.TestCase):
    def test_event_goal_persona_and_skill_stores_persist_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            db = root / "cognition.sqlite3"

            event = CognitiveEventBus(db).append(
                "user_text",
                "prepare tomorrow's review",
                {"channel": "test"},
                priority=CognitivePriority.HIGH,
            )
            goal_store = GoalStore(db)
            goal = goal_store.create_goal("Prepare tomorrow's review", ["Draft agenda"])
            task = goal_store.add_task(goal.goal_id, "Draft agenda")
            goal_store.update_task(task.task_id, TaskStatus.COMPLETED, "Agenda drafted.")
            goal_store.update_goal(goal.goal_id, GoalStatus.COMPLETED)

            focus = FocusStore(db).update(
                mode=FocusMode.DEEP_WORK,
                active_goal_id=goal.goal_id,
                active_task_id=task.task_id,
                summary="Drafting agenda.",
                pinned_context=["agenda"],
            )
            knowledge_store = KnowledgeStore(db)
            knowledge = knowledge_store.append(
                kind=KnowledgeKind.PROCEDURE,
                text="Use a compact agenda before review meetings.",
                source="test",
                evidence_refs=[f"task:{task.task_id}"],
                confidence=0.9,
            )
            learning = LearningStore(db).append(
                goal_id=goal.goal_id,
                task_id=task.task_id,
                outcome="completed",
                lesson="Agenda drafting completed with durable task evidence.",
                evidence_refs=[f"task:{task.task_id}"],
            )
            persona = PersonaStore(root / "persona.json").add_preference("Use short morning briefings.")
            skill = SkillStore(root / "skills.json").upsert(
                name="Morning briefing",
                purpose="Prepare a compact daily planning note.",
                when_to_use="Use before the user starts the workday.",
                tools=["memory_summary", "cognitive_state"],
                verification_steps=["Confirm active goals are included."],
                confidence=0.8,
            )
            wakeup = WakeupStore(db).schedule(
                scheduled_for=_utc_seconds_from_now(60),
                payload={"text": "review tomorrow", "metadata": {"should_run_agent": True}},
                reason="Check future work.",
            )

            self.assertEqual(CognitiveEventBus(db).recent(limit=1)[0].event_id, event.event_id)
            self.assertEqual(goal_store.recent_goals()[0].status, GoalStatus.COMPLETED)
            self.assertEqual(goal_store.recent_tasks()[0].result_summary, "Agenda drafted.")
            self.assertEqual(focus.mode, FocusMode.DEEP_WORK)
            self.assertEqual(FocusStore(db).load().active_task_id, task.task_id)
            self.assertEqual(KnowledgeStore(db).list()[0].knowledge_id, knowledge.knowledge_id)
            self.assertEqual(LearningStore(db).recent()[0].learning_id, learning.learning_id)
            archived = knowledge_store.archive(knowledge.knowledge_id, reason="obsolete test memory")
            self.assertIsNotNone(archived)
            self.assertEqual(KnowledgeStore(db).list(), [])
            self.assertIn("short morning", persona.user_preferences[0])
            self.assertEqual(skill.confidence, 0.8)
            self.assertEqual(WakeupStore(db).scheduled()[0].wakeup_id, wakeup.wakeup_id)

    def test_wakeup_store_tracks_due_fire_and_cancel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db = Path(tmp_dir) / "cognition.sqlite3"
            store = WakeupStore(db)
            due = store.schedule(
                scheduled_for=_utc_seconds_from_now(-5),
                event_type="STIMULUS",
                payload={"text": "check project", "metadata": {"should_run_agent": True}},
                reason="Due follow-up.",
            )
            future = store.schedule(
                scheduled_for=_utc_seconds_from_now(3600),
                event_type="STIMULUS",
                payload={"text": "future project check"},
                reason="Future follow-up.",
            )

            due_records = store.due()
            fired = store.mark_fired(due.wakeup_id, fired_event_id="rt-event-1")
            cancelled = store.cancel(future.wakeup_id, reason="No longer needed")

            self.assertEqual(due_records[0].wakeup_id, due.wakeup_id)
            self.assertIsNotNone(fired)
            self.assertEqual(fired.status, WakeupStatus.FIRED)
            self.assertEqual(fired.fired_event_id, "rt-event-1")
            self.assertIsNotNone(cancelled)
            self.assertEqual(cancelled.status, WakeupStatus.CANCELLED)
            self.assertEqual(store.due(), [])

    def test_model_cognitive_decision_provider_uses_structured_model_decision(self) -> None:
        client = StaticModelClient(
            '{"action":"analyze","request":"read_file {\\"path\\":\\"README.md\\"}","response_mode":"silent","reason":"Model chose to inspect the referenced file from structured context.","should_run_agent":true,"should_record_event":true,"memory_action":"remember","focus_goal_id":"","create_goal_title":"Inspect referenced README","create_task_title":"Read README","stay_warm":false,"next_wakeup_seconds":null}'
        )
        provider = ModelCognitiveDecisionProvider(client, fallback=ExplicitCognitiveDecisionProvider())
        event = CognitiveEvent(
            event_id="event-model",
            source="activity",
            text='read_file {"path":"README.md"}',
            metadata={"origin": "test"},
        )

        decision = provider.decide(event, CognitiveSnapshot(), response_mode="silent")

        self.assertEqual(decision.action, AttentionAction.ANALYZE)
        self.assertEqual(decision.request, 'read_file {"path":"README.md"}')
        self.assertEqual(decision.response_mode, "silent")
        self.assertTrue(decision.should_run_agent)
        self.assertEqual(decision.memory_action, MemoryAction.REMEMBER)
        self.assertIn("Model chose", decision.reason)

    def test_model_cognitive_decision_provider_falls_back_without_guessing_text(self) -> None:
        class FailingClient(StaticModelClient):
            def complete_json(self, prompt, schema):
                raise ModelClientError("offline")

        provider = ModelCognitiveDecisionProvider(FailingClient("{}"), fallback=ExplicitCognitiveDecisionProvider())
        event = CognitiveEvent(
            event_id="event-fallback",
            source="activity",
            text="please do this sometime",
            metadata={},
        )

        decision = provider.decide(event, CognitiveSnapshot(), response_mode="silent")

        self.assertEqual(decision.action, AttentionAction.OBSERVE)
        self.assertFalse(decision.should_run_agent)
        self.assertEqual(decision.request, "")

    def test_model_reflection_provider_uses_structured_model_judgment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run = AgentRunResult(
                run_id="run-model-reflect",
                request='read_file {"path":"README.md"}',
                final_response="README.md was read and summarized.",
                results=[
                    ToolResult(
                        "read_file",
                        ActionStatus.SUCCEEDED,
                        RiskLevel.LOW,
                        "Read README.md.",
                        {"path": "README.md", "text": "Verified evidence."},
                    )
                ],
            )
            client = StaticModelClient(
                '{"status":"passed","confidence":0.93,"summary":"The README criterion is directly proven by the read_file result.","checked_criteria":["README was read."],"missing_evidence":[]}'
            )
            engine = ReflectionEngine(
                ReflectionStore(Path(tmp_dir) / "cognition.sqlite3"),
                provider=ModelReflectionProvider(client, fallback=EvidenceReflectionProvider()),
            )

            reflection = engine.evaluate_task(
                goal_id="goal-1",
                task_id="task-1",
                run=run,
                criteria=["README was read."],
            )

            self.assertEqual(reflection.status, ReflectionStatus.PASSED)
            self.assertEqual(reflection.confidence, 0.93)
            self.assertEqual(reflection.checked_criteria, ["README was read."])
            self.assertEqual(ReflectionStore(Path(tmp_dir) / "cognition.sqlite3").recent()[0].reflection_id, reflection.reflection_id)

    def test_model_reflection_provider_falls_back_to_structured_evidence(self) -> None:
        class FailingClient(StaticModelClient):
            def complete_json(self, prompt, schema):
                raise ModelClientError("offline")

        run = AgentRunResult(
            run_id="run-fallback-reflect",
            request="noop",
            final_response="",
            results=[],
        )
        provider = ModelReflectionProvider(FailingClient("{}"), fallback=EvidenceReflectionProvider())

        reflection = provider.evaluate_task(goal_id="goal-1", task_id="task-1", run=run, criteria=["Evidence exists."])

        self.assertEqual(reflection.status, ReflectionStatus.INCONCLUSIVE)
        self.assertIn("No tool results", reflection.missing_evidence[0])

    def test_model_reflection_provider_enforces_approval_boundary(self) -> None:
        run = AgentRunResult(
            run_id="run-approval-reflect",
            request='run_shell_command {"argv":["python","-V"]}',
            final_response="Approval needed.",
            results=[],
            approvals=[
                ApprovalRequest(
                    tool_name="run_shell_command",
                    tool_input={"argv": ["python", "-V"]},
                    risk_level=RiskLevel.HIGH,
                    reason="Needs approval.",
                    approval_token="token-1",
                )
            ],
        )
        client = StaticModelClient(
            '{"status":"passed","confidence":0.99,"summary":"The model attempted to pass the task.","checked_criteria":["Command ran."],"missing_evidence":[]}'
        )
        provider = ModelReflectionProvider(client, fallback=EvidenceReflectionProvider())

        reflection = provider.evaluate_task(goal_id="goal-1", task_id="task-1", run=run, criteria=["Command ran."])

        self.assertEqual(reflection.status, ReflectionStatus.NEEDS_APPROVAL)
        self.assertIn("Runtime evidence boundary", reflection.missing_evidence[-1])

    def test_model_consolidation_provider_persists_memory_skill_and_persona(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            db = root / "cognition.sqlite3"
            run = AgentRunResult(
                run_id="run-consolidate",
                request='read_file {"path":"README.md"}',
                final_response="The README workflow was verified and summarized.",
                results=[
                    ToolResult(
                        "read_file",
                        ActionStatus.SUCCEEDED,
                        RiskLevel.LOW,
                        "Read README.md.",
                        {"path": "README.md", "text": "Use blocker-first updates."},
                    )
                ],
            )
            reflection = ReflectionRecord(
                reflection_id="reflection-consolidate",
                goal_id="goal-1",
                task_id="task-1",
                run_id=run.run_id,
                status=ReflectionStatus.PASSED,
                confidence=0.9,
                summary="README was read and summarized with evidence.",
                checked_criteria=["README was read."],
            )
            learning = LearningStore(db).append(
                goal_id="goal-1",
                task_id="task-1",
                run_id=run.run_id,
                reflection_id=reflection.reflection_id,
                outcome=ReflectionStatus.PASSED.value,
                lesson="The README workflow can become a reusable review habit.",
                evidence_refs=[f"reflection:{reflection.reflection_id}", f"run:{run.run_id}"],
            )
            client = StaticModelClient(
                '{"status":"recorded","summary":"Promoted the verified README review into durable memory.","skip_reason":"","knowledge":[{"kind":"procedure","text":"Use blocker-first updates when summarizing project status.","confidence":0.86,"evidence_refs":["reflection:reflection-consolidate"]}],"skills":[{"name":"Blocker-first project review","purpose":"Summarize project status with blockers and evidence first.","when_to_use":"Use when reviewing local project state for the user.","tools":["cognitive_state","read_file"],"verification_steps":["Confirm the relevant file or task evidence was inspected."],"failure_modes":["Claiming completion without evidence."],"confidence":0.82}],"persona":[{"kind":"preference","text":"Prefer project updates that surface blockers before completed work."}]}'
            )
            engine = ConsolidationEngine(
                ConsolidationStore(db),
                KnowledgeStore(db),
                SkillStore(root / "skills.json"),
                PersonaStore(root / "persona.json"),
                provider=ModelConsolidationProvider(client, fallback=EvidenceConsolidationProvider()),
            )

            record = engine.consolidate_task(run=run, reflection=reflection, learning=learning)

            self.assertEqual(record.status, ConsolidationStatus.RECORDED)
            self.assertEqual(len(record.knowledge_ids), 1)
            self.assertEqual(len(record.skill_ids), 1)
            self.assertEqual(len(record.persona_updates), 1)
            knowledge = KnowledgeStore(db).get(record.knowledge_ids[0])
            self.assertIsNotNone(knowledge)
            self.assertEqual(knowledge.kind, KnowledgeKind.PROCEDURE)
            self.assertIn(f"learning:{learning.learning_id}", knowledge.evidence_refs)
            self.assertEqual(SkillStore(root / "skills.json").list()[0].name, "Blocker-first project review")
            self.assertIn("blockers", PersonaStore(root / "persona.json").load().user_preferences[0])
            self.assertEqual(ConsolidationStore(db).recent()[0].consolidation_id, record.consolidation_id)

    def test_model_briefing_provider_prepares_and_stores_current_work_view(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            db = root / "cognition.sqlite3"
            goals = GoalStore(db)
            goal = goals.create_goal("Ship cognitive briefing", ["A current-work briefing exists."])
            task = goals.add_task(
                goal.goal_id,
                "Prepare briefing engine",
                metadata={"request": "prepare briefing", "success_criteria": ["Briefing record stored."]},
            )
            focus = FocusStore(db).update(
                mode=FocusMode.DEEP_WORK,
                active_goal_id=goal.goal_id,
                active_task_id=task.task_id,
                summary="Implementing a current-work briefing layer.",
                pinned_context=["briefing", "current work"],
            )
            knowledge = KnowledgeStore(db).append(
                kind=KnowledgeKind.PROCEDURE,
                text="Use evidence refs in project briefings.",
                source="test",
                evidence_refs=[f"goal:{goal.goal_id}"],
                confidence=0.8,
            )
            wakeup = WakeupStore(db).schedule(
                scheduled_for=_utc_seconds_from_now(3600),
                payload={"text": "review briefing", "metadata": {"should_run_agent": True}},
                reason="Review briefing follow-up.",
            )
            snapshot = CognitiveSnapshot(
                active_goals=[goal],
                active_tasks=[task],
                focus=focus,
                knowledge=[knowledge],
                wakeups=[wakeup],
            )
            client = StaticModelClient(
                json.dumps(
                    {
                        "status": "generated",
                        "summary": "Current work is centered on shipping the briefing layer.",
                        "current_focus": "Implementing a current-work briefing layer.",
                        "priorities": ["Finish the briefing engine and tool wiring."],
                        "blockers": [],
                        "next_actions": ["Run focused cognition tests.", "Commit the briefing iteration."],
                        "watch_items": ["Review the scheduled follow-up."],
                        "suggested_wakeups": ["Check briefing quality after tests."],
                        "evidence_refs": [f"goal:{goal.goal_id}", f"task:{task.task_id}", f"wakeup:{wakeup.wakeup_id}"],
                        "confidence": 0.82,
                    }
                )
            )
            engine = BriefingEngine(
                BriefingStore(db),
                provider=ModelBriefingProvider(client, fallback=EvidenceBriefingProvider()),
            )

            briefing = engine.prepare(snapshot=snapshot, purpose="iteration", horizon_hours=24)
            recent = BriefingStore(db).recent(limit=3)

            self.assertEqual(briefing.status, BriefingStatus.GENERATED)
            self.assertEqual(briefing.purpose, "iteration")
            self.assertIn("briefing layer", briefing.summary)
            self.assertEqual(briefing.priorities[0], "Finish the briefing engine and tool wiring.")
            self.assertEqual(briefing.evidence_refs[0], f"goal:{goal.goal_id}")
            self.assertEqual(recent[0].briefing_id, briefing.briefing_id)

    def test_model_curation_provider_archives_and_summarizes_exact_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db = Path(tmp_dir) / "cognition.sqlite3"
            store = KnowledgeStore(db)
            stale = store.append(
                kind=KnowledgeKind.CONTEXT,
                text="Temporary status: old duplicate dashboard note.",
                source="test",
                evidence_refs=["event:old"],
                confidence=0.3,
            )
            useful = store.append(
                kind=KnowledgeKind.PROCEDURE,
                text="Use blockers-first status updates when reviewing projects.",
                source="test",
                evidence_refs=["event:useful"],
                confidence=0.9,
            )
            snapshot = CognitiveSnapshot(knowledge=[stale, useful])
            client = StaticModelClient(
                json.dumps(
                    {
                        "status": "recorded",
                        "summary": "Archived a stale duplicate and kept the durable status procedure.",
                        "archive_knowledge": [{"knowledge_id": stale.knowledge_id, "reason": "Superseded temporary project status."}],
                        "summarize_knowledge": [
                            {
                                "kind": "procedure",
                                "text": "For project reviews, use blockers-first status updates.",
                                "confidence": 0.88,
                                "evidence_refs": [f"knowledge:{useful.knowledge_id}"],
                            }
                        ],
                        "retain_knowledge_ids": [useful.knowledge_id],
                        "evidence_refs": [f"knowledge:{stale.knowledge_id}", f"knowledge:{useful.knowledge_id}"],
                        "confidence": 0.84,
                    }
                )
            )
            engine = CurationEngine(
                CurationStore(db),
                store,
                provider=ModelCurationProvider(client, fallback=EvidenceCurationProvider()),
            )

            curation = engine.curate(snapshot=snapshot, purpose="test_cleanup", max_archive=3, max_summaries=2)
            remaining = KnowledgeStore(db).list(limit=10)
            archived = KnowledgeStore(db).get(stale.knowledge_id, include_archived=True)
            created = KnowledgeStore(db).get(curation.created_knowledge_ids[0])

            self.assertEqual(curation.status, CurationStatus.RECORDED)
            self.assertEqual(curation.archived_knowledge_ids, [stale.knowledge_id])
            self.assertEqual(curation.retained_knowledge_ids, [useful.knowledge_id])
            self.assertIsNotNone(archived)
            self.assertTrue(archived.archived_at)
            self.assertIsNotNone(created)
            self.assertEqual(created.source, "model_curation")
            self.assertIn(f"knowledge:{useful.knowledge_id}", created.evidence_refs)
            self.assertNotIn(stale.knowledge_id, [record.knowledge_id for record in remaining])
            self.assertEqual(CurationStore(db).recent()[0].curation_id, curation.curation_id)

    def test_model_skill_evolution_provider_updates_retires_and_creates_exact_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            db = root / "cognition.sqlite3"
            skills = SkillStore(root / "skills.json")
            status_skill = skills.upsert(
                name="Status updates",
                purpose="Summarize project progress.",
                when_to_use="Use during project reviews.",
                tools=["cognitive_state"],
                verification_steps=["Mention completed work."],
                failure_modes=["Missing blockers."],
                confidence=0.55,
            )
            duplicate_skill = skills.upsert(
                name="Old review notes",
                purpose="Prepare project review notes.",
                when_to_use="Use during project reviews.",
                tools=["memory_summary"],
                verification_steps=["List project notes."],
                failure_modes=["Duplicating the status update skill."],
                confidence=0.4,
            )
            learning = LearningStore(db).append(
                outcome="completed",
                lesson="Blockers-first status updates worked better than generic review notes.",
                evidence_refs=["run:status-review"],
            )
            snapshot = CognitiveSnapshot(skills=skills.list(limit=10), learning=[learning])
            client = StaticModelClient(
                json.dumps(
                    {
                        "status": "recorded",
                        "summary": "Improved the status skill, retired a duplicate, and created a recurring review skill.",
                        "update_skills": [
                            {
                                "skill_id": status_skill.skill_id,
                                "name": "Blockers-first status updates",
                                "purpose": "Summarize project progress with blockers and risks before completed work.",
                                "when_to_use": "Use during project reviews and implementation handoffs.",
                                "tools": ["cognitive_state", "cognitive_briefing_prepare"],
                                "verification_steps": ["Mention unresolved blockers.", "Include evidence-backed next actions."],
                                "failure_modes": ["Hiding uncertainty.", "Claiming completion without evidence."],
                                "confidence": 0.87,
                                "evidence_refs": [f"skill:{status_skill.skill_id}", f"learning:{learning.learning_id}"],
                            }
                        ],
                        "retire_skills": [
                            {
                                "skill_id": duplicate_skill.skill_id,
                                "reason": "Duplicated by the improved blockers-first status skill.",
                                "evidence_refs": [f"skill:{duplicate_skill.skill_id}", f"learning:{learning.learning_id}"],
                            }
                        ],
                        "create_skills": [
                            {
                                "name": "Recurring review follow-up",
                                "purpose": "Schedule and verify future follow-ups for long-running project reviews.",
                                "when_to_use": "Use when a review produces future work or watch items.",
                                "tools": ["cognitive_wakeup_schedule", "cognitive_briefing_prepare"],
                                "verification_steps": ["Confirm a wakeup or next action is visible."],
                                "failure_modes": ["Letting future work disappear."],
                                "confidence": 0.78,
                                "evidence_refs": [f"learning:{learning.learning_id}"],
                            }
                        ],
                        "retain_skill_ids": [],
                        "evidence_refs": [f"skill:{status_skill.skill_id}", f"skill:{duplicate_skill.skill_id}", f"learning:{learning.learning_id}"],
                        "confidence": 0.84,
                    }
                )
            )
            engine = SkillEvolutionEngine(
                SkillEvolutionStore(db),
                skills,
                provider=ModelSkillEvolutionProvider(client, fallback=EvidenceSkillEvolutionProvider()),
            )

            evolution = engine.evolve(snapshot=snapshot, purpose="test_skill_review", max_updates=3, max_new_skills=2)
            updated = skills.get(status_skill.skill_id)
            retired = skills.get(duplicate_skill.skill_id)
            active_names = [skill.name for skill in skills.list(limit=10)]

            self.assertEqual(evolution.status, SkillEvolutionStatus.RECORDED)
            self.assertEqual(evolution.updated_skill_ids, [status_skill.skill_id])
            self.assertEqual(evolution.retired_skill_ids, [duplicate_skill.skill_id])
            self.assertEqual(len(evolution.created_skill_ids), 1)
            self.assertIsNotNone(updated)
            self.assertEqual(updated.name, "Blockers-first status updates")
            self.assertIn("cognitive_briefing_prepare", updated.tools)
            self.assertIn(f"learning:{learning.learning_id}", updated.evidence_refs)
            self.assertIsNotNone(retired)
            self.assertEqual(retired.status, SkillLifecycleStatus.RETIRED)
            self.assertIn("Duplicated", retired.retirement_reason)
            self.assertNotIn("Old review notes", active_names)
            self.assertIn("Recurring review follow-up", active_names)
            self.assertEqual(SkillEvolutionStore(db).recent()[0].evolution_id, evolution.evolution_id)

    def test_model_consolidation_provider_falls_back_without_inferred_memory(self) -> None:
        class FailingClient(StaticModelClient):
            def complete_json(self, prompt, schema):
                raise ModelClientError("offline")

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            db = root / "cognition.sqlite3"
            run = AgentRunResult(run_id="run-skip-consolidate", request="noop", final_response="", results=[])
            reflection = ReflectionRecord(
                reflection_id="reflection-skip-consolidate",
                goal_id="goal-1",
                task_id="task-1",
                run_id=run.run_id,
                status=ReflectionStatus.INCONCLUSIVE,
                confidence=0.2,
                summary="No evidence was available.",
            )
            learning = LearningStore(db).append(
                goal_id="goal-1",
                task_id="task-1",
                run_id=run.run_id,
                reflection_id=reflection.reflection_id,
                outcome=ReflectionStatus.INCONCLUSIVE.value,
                lesson="No durable memory should be inferred while offline.",
            )
            engine = ConsolidationEngine(
                ConsolidationStore(db),
                KnowledgeStore(db),
                SkillStore(root / "skills.json"),
                PersonaStore(root / "persona.json"),
                provider=ModelConsolidationProvider(FailingClient("{}"), fallback=EvidenceConsolidationProvider()),
            )

            record = engine.consolidate_task(run=run, reflection=reflection, learning=learning)

            self.assertEqual(record.status, ConsolidationStatus.SKIPPED)
            self.assertEqual(record.knowledge_ids, [])
            self.assertEqual(KnowledgeStore(db).list(), [])
            self.assertEqual(SkillStore(root / "skills.json").list(), [])
            self.assertEqual(PersonaStore(root / "persona.json").load().user_preferences, [])

    def test_model_recovery_provider_creates_explicit_repair_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db = Path(tmp_dir) / "cognition.sqlite3"
            goals = GoalStore(db)
            goal = goals.create_goal("Recover failed file review", ["README is read."])
            task = goals.add_task(
                goal.goal_id,
                "Read missing file",
                metadata={"request": 'read_file {"path":"missing.md"}', "success_criteria": ["README is read."]},
            )
            run = AgentRunResult(
                run_id="run-recovery",
                request='read_file {"path":"missing.md"}',
                final_response="File not found.",
                results=[
                    ToolResult(
                        "read_file",
                        ActionStatus.FAILED,
                        RiskLevel.LOW,
                        "File was not found.",
                        {"path": "missing.md"},
                        error="missing",
                    )
                ],
            )
            reflection = ReflectionRecord(
                reflection_id="reflection-recovery",
                goal_id=goal.goal_id,
                task_id=task.task_id,
                run_id=run.run_id,
                status=ReflectionStatus.FAILED,
                confidence=0.9,
                summary="The file read failed.",
                missing_evidence=["README was not read."],
            )
            learning = LearningStore(db).append(
                goal_id=goal.goal_id,
                task_id=task.task_id,
                run_id=run.run_id,
                reflection_id=reflection.reflection_id,
                outcome=ReflectionStatus.FAILED.value,
                lesson="Recovery should inspect the available README.",
            )
            client = StaticModelClient(
                '{"status":"planned","summary":"Plan a repair task that reads the available README.","tasks":[{"local_task_id":"read-readme","title":"Read available README","request":"read_file {\\"path\\":\\"README.md\\"}","owner":"master","success_criteria":["README was read."],"depends_on":[]}]}'
            )
            engine = RecoveryEngine(
                RecoveryStore(db),
                goals,
                provider=ModelRecoveryProvider(client, fallback=EvidenceRecoveryProvider()),
            )

            recovery = engine.recover_task(goal=goal, task=task, run=run, reflection=reflection, learning=learning)
            created = goals.get_task(recovery.created_task_ids[0])

            self.assertEqual(recovery.status, RecoveryStatus.PLANNED)
            self.assertEqual(len(recovery.created_task_ids), 1)
            self.assertIsNotNone(created)
            self.assertEqual(created.metadata["recovery_parent_task_id"], task.task_id)
            self.assertEqual(created.metadata["request"], 'read_file {"path":"README.md"}')
            self.assertEqual(RecoveryStore(db).for_task(task.task_id)[0].recovery_id, recovery.recovery_id)

    def test_interaction_harness_records_cognitive_goal_and_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Cognitive Harness\n\nRuntime state.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

            result = InteractionHarness(config).handle('read_file {"path":"README.md"}')
            recorder = CognitiveRecorder(config)
            goals = recorder.goals.recent_goals(limit=5)
            tasks = recorder.goals.recent_tasks(limit=5)

            self.assertIsNotNone(result.run)
            self.assertEqual(goals[0].status, GoalStatus.COMPLETED)
            self.assertEqual(tasks[0].status, TaskStatus.COMPLETED)
            self.assertIn("README.md", tasks[0].result_summary)
            snapshot = recorder.snapshot()
            self.assertEqual(snapshot.focus.mode, FocusMode.IDLE)
            self.assertEqual(snapshot.focus.active_task_id, "")
            self.assertEqual(snapshot.learning[0].task_id, tasks[0].task_id)
            self.assertEqual(snapshot.learning[0].outcome, TaskStatus.COMPLETED.value)

    def test_cognition_tools_expose_and_update_runtime_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

            goal = CognitiveGoalCreateTool().execute(
                {"title": "Track follow-up tasks", "success_criteria": ["A follow-up goal is visible."]},
                config,
            )
            focus = CognitiveFocusUpdateTool().execute(
                {
                    "mode": "monitoring",
                    "active_goal_id": goal.output["goal"]["goal_id"],
                    "summary": "Watching follow-up work.",
                    "pinned_context": ["follow-ups"],
                },
                config,
            )
            knowledge = CognitiveKnowledgeRecordTool().execute(
                {
                    "kind": "procedure",
                    "text": "For project status, show blockers before completed work.",
                    "source": "test",
                    "evidence_refs": [f"goal:{goal.output['goal']['goal_id']}"],
                    "confidence": 0.85,
                },
                config,
            )
            persona = CognitivePersonaUpdateTool().execute(
                {"kind": "preference", "text": "Prefer progress updates with blockers first."},
                config,
            )
            learning_record = LearningStore(config.cognition_db_path).append(
                goal_id=goal.output["goal"]["goal_id"],
                outcome="observed",
                lesson="Public cognition tools expose learned state.",
            )
            learning = CognitiveLearningStatusTool().execute({"limit": 5}, config)
            consolidation = CognitiveConsolidationStatusTool().execute({"limit": 5}, config)
            recovery = CognitiveRecoveryStatusTool().execute({"limit": 5}, config)
            briefing = CognitiveBriefingPrepareTool().execute({"purpose": "status", "include_state": True, "limit": 5}, config)
            briefing_status = CognitiveBriefingStatusTool().execute({"limit": 5}, config)
            curation = CognitiveMemoryCurateTool().execute({"purpose": "cleanup", "include_state": True, "limit": 5}, config)
            curation_status = CognitiveCurationStatusTool().execute({"limit": 5}, config)
            scheduled_wakeup = CognitiveWakeupScheduleTool().execute(
                {
                    "delay_seconds": 60,
                    "text": "check pending project follow-up",
                    "response_mode": "silent",
                    "reason": "Track future follow-up.",
                },
                config,
            )
            wakeup_status = CognitiveWakeupStatusTool().execute({"status": "scheduled", "limit": 5}, config)
            cancelled_wakeup = CognitiveWakeupCancelTool().execute(
                {"wakeup_id": scheduled_wakeup.output["wakeup"]["wakeup_id"], "reason": "covered in test"},
                config,
            )
            skill = CognitiveSkillRecordTool().execute(
                {
                    "name": "Blocker-first update",
                    "purpose": "Summarize task progress with risks first.",
                    "when_to_use": "Use during project status updates.",
                    "tools": ["cognitive_state"],
                    "verification_steps": ["Mention unresolved blockers."],
                    "failure_modes": ["Hiding uncertainty."],
                    "confidence": 0.7,
                },
                config,
            )
            skill_evolution = CognitiveSkillEvolveTool().execute(
                {"purpose": "skill_review", "include_state": True, "limit": 5},
                config,
            )
            skill_evolution_status = CognitiveSkillEvolutionStatusTool().execute({"limit": 5}, config)
            specialist = CognitiveSpecialistRecordTool().execute(
                {
                    "name": "Reviewer",
                    "purpose": "Review local files and summarize evidence.",
                    "contract": "Use available file tools and report only verified file evidence.",
                    "tools": ["read_file"],
                    "success_criteria": ["The requested file was read."],
                    "permission_notes": ["Stay within the configured workspace."],
                    "confidence": 0.75,
                },
                config,
            )
            state = CognitiveStateTool().execute({"limit": 5}, config)
            forgotten = CognitiveKnowledgeForgetTool().execute(
                {"knowledge_id": knowledge.output["knowledge"]["knowledge_id"], "reason": "covered by durable preference"},
                config,
            )

            self.assertEqual(goal.status, ActionStatus.SUCCEEDED)
            self.assertEqual(focus.status, ActionStatus.SUCCEEDED)
            self.assertEqual(knowledge.status, ActionStatus.SUCCEEDED)
            self.assertEqual(persona.status, ActionStatus.SUCCEEDED)
            self.assertEqual(learning.status, ActionStatus.SUCCEEDED)
            self.assertEqual(consolidation.status, ActionStatus.SUCCEEDED)
            self.assertEqual(recovery.status, ActionStatus.SUCCEEDED)
            self.assertEqual(briefing.status, ActionStatus.SUCCEEDED)
            self.assertEqual(briefing_status.status, ActionStatus.SUCCEEDED)
            self.assertEqual(curation.status, ActionStatus.SUCCEEDED)
            self.assertEqual(curation_status.status, ActionStatus.SUCCEEDED)
            self.assertEqual(scheduled_wakeup.status, ActionStatus.SUCCEEDED)
            self.assertEqual(wakeup_status.status, ActionStatus.SUCCEEDED)
            self.assertEqual(cancelled_wakeup.status, ActionStatus.SUCCEEDED)
            self.assertEqual(skill.status, ActionStatus.SUCCEEDED)
            self.assertEqual(skill_evolution.status, ActionStatus.SUCCEEDED)
            self.assertEqual(skill_evolution_status.status, ActionStatus.SUCCEEDED)
            self.assertEqual(specialist.status, ActionStatus.SUCCEEDED)
            self.assertEqual(state.status, ActionStatus.SUCCEEDED)
            self.assertEqual(forgotten.status, ActionStatus.SUCCEEDED)
            self.assertEqual(len(state.output["active_goals"]), 1)
            self.assertEqual(state.output["focus"]["mode"], "monitoring")
            self.assertEqual(state.output["consolidations"], [])
            self.assertEqual(state.output["recoveries"], [])
            self.assertEqual(state.output["briefings"][0]["status"], BriefingStatus.SKIPPED)
            self.assertEqual(state.output["curations"][0]["status"], CurationStatus.SKIPPED)
            self.assertEqual(state.output["skill_evolutions"][0]["status"], SkillEvolutionStatus.SKIPPED)
            self.assertEqual(briefing.output["briefing"]["status"], BriefingStatus.SKIPPED)
            self.assertEqual(briefing_status.output["briefings"][0]["briefing_id"], briefing.output["briefing"]["briefing_id"])
            self.assertEqual(curation.output["curation"]["status"], CurationStatus.SKIPPED)
            self.assertEqual(curation_status.output["curations"][0]["curation_id"], curation.output["curation"]["curation_id"])
            self.assertEqual(skill_evolution.output["skill_evolution"]["status"], SkillEvolutionStatus.SKIPPED)
            self.assertEqual(
                skill_evolution_status.output["skill_evolutions"][0]["evolution_id"],
                skill_evolution.output["skill_evolution"]["evolution_id"],
            )
            self.assertEqual(wakeup_status.output["wakeups"][0]["wakeup_id"], scheduled_wakeup.output["wakeup"]["wakeup_id"])
            self.assertEqual(state.output["wakeups"], [])
            self.assertEqual(state.output["knowledge"][0]["knowledge_id"], knowledge.output["knowledge"]["knowledge_id"])
            self.assertEqual(learning.output["learning"][0]["learning_id"], learning_record.learning_id)
            self.assertEqual(state.output["persona"]["user_preferences"][0], "Prefer progress updates with blockers first.")
            self.assertEqual(state.output["skills"][0]["name"], "Blocker-first update")
            self.assertEqual(state.output["specialists"][0]["name"], "Reviewer")
            self.assertIn("forget_reason:covered by durable preference", forgotten.output["knowledge"]["evidence_refs"])
            self.assertEqual(KnowledgeStore(config.cognition_db_path).list(), [])
            self.assertEqual(cancelled_wakeup.output["wakeup"]["status"], WakeupStatus.CANCELLED)

    def test_runtime_event_queue_priority_and_step_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            queue = RuntimeEventQueue(Path(tmp_dir) / "cognition.sqlite3")

            queue.push("USER_REQUEST", {"text": "normal"}, priority=CognitivePriority.NORMAL)
            queue.push("INTERRUPT", {"reason": "user changed direction"}, priority=CognitivePriority.CRITICAL)

            boundary = AtomicStepBoundary(queue)
            self.assertEqual(boundary.check(), StepBoundaryAction.INTERRUPT)
            self.assertEqual(queue.pop_next().event_type, "INTERRUPT")
            queue.push("PAUSE", {}, priority=CognitivePriority.NORMAL)
            self.assertEqual(boundary.check(), StepBoundaryAction.PAUSE)

    def test_autonomous_task_graph_tracks_ready_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = AutonomousTaskGraphCreateTool().execute(
                {
                    "goal_title": "Prepare a two-step review",
                    "success_criteria": ["Both steps are complete."],
                    "tasks": [
                        {"task_id": "read", "title": "Read source", "request": 'read_file {"path":"README.md"}'},
                        {"task_id": "summarize", "title": "Summarize source", "request": "summarize source", "depends_on": ["read"]},
                    ],
                },
                config,
            )
            store = GoalStore(config.cognition_db_path)
            ready = store.ready_tasks()

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertEqual(len(ready), 1)
            self.assertIn("read", ready[0].task_id)
            store.update_task(ready[0].task_id, TaskStatus.COMPLETED, "Read complete.")
            next_ready = store.ready_tasks()
            self.assertEqual(len(next_ready), 1)
            self.assertIn("summarize", next_ready[0].task_id)

    def test_autonomous_runtime_processes_one_queued_user_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Autonomous Runtime\n\nOne cycle works.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()
            runtime = AutonomousRuntime(config)

            runtime.submit_user_request('read_file {"path":"README.md"}')
            result = runtime.run_once()
            goals = runtime.goals.recent_goals(limit=3)
            tasks = runtime.goals.recent_tasks(limit=3)

            self.assertEqual(result.status, RuntimeCycleStatus.RUN_FINISHED)
            self.assertIsNotNone(result.run_id)
            self.assertIn("README.md", result.final_response)
            self.assertEqual(goals[0].status, GoalStatus.COMPLETED)
            self.assertEqual(tasks[0].status, TaskStatus.COMPLETED)

    def test_autonomous_runtime_fires_due_wakeup_through_event_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Wakeup Runtime\n\nDue wakeup works.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()
            wakeup = WakeupStore(config.cognition_db_path).schedule(
                scheduled_for=_utc_seconds_from_now(-1),
                event_type="STIMULUS",
                payload={
                    "text": 'read_file {"path":"README.md"}',
                    "source": "wakeup",
                    "metadata": {"should_run_agent": True, "intent": "task"},
                    "response_mode": "silent",
                },
                reason="Resume due file review.",
            )

            result = AutonomousRuntime(config).run_once()
            fired = WakeupStore(config.cognition_db_path).get(wakeup.wakeup_id)
            tasks = GoalStore(config.cognition_db_path).recent_tasks(limit=3)

            self.assertEqual(result.status, RuntimeCycleStatus.RUN_FINISHED)
            self.assertIsNotNone(fired)
            self.assertEqual(fired.status, WakeupStatus.FIRED)
            self.assertTrue(fired.fired_event_id)
            self.assertIn("README.md", result.final_response)
            self.assertEqual(tasks[0].status, TaskStatus.COMPLETED)

    def test_autonomous_loop_runner_processes_due_wakeup_and_records_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Loop Runtime\n\nBounded loop works.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()
            WakeupStore(config.cognition_db_path).schedule(
                scheduled_for=_utc_seconds_from_now(-1),
                event_type="STIMULUS",
                payload={
                    "text": 'read_file {"path":"README.md"}',
                    "source": "wakeup",
                    "metadata": {"should_run_agent": True, "intent": "task"},
                    "response_mode": "silent",
                },
                reason="Resume due loop review.",
            )

            result = AutonomousLoopRunner(config).run(max_cycles=3, stop_after_idle_cycles=1)
            payload = autonomous_loop_result_to_dict(result)
            status = autonomous_status(config, limit=5)

            self.assertEqual(result.stopped_reason, "idle")
            self.assertEqual(payload["cycle_count"], 2)
            self.assertEqual(payload["cycles"][0]["status"], RuntimeCycleStatus.RUN_FINISHED)
            self.assertEqual(payload["cycles"][1]["status"], RuntimeCycleStatus.NO_OP)
            self.assertEqual(status["scheduled_wakeups"], [])
            self.assertEqual(status["recent_wakeups"][0]["status"], WakeupStatus.FIRED)
            self.assertEqual(status["recent_loops"][0]["payload"]["cycle_count"], 2)

    def test_autonomous_loop_runner_stops_after_idle_without_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

            result = AutonomousLoopRunner(config).run(max_cycles=5, stop_after_idle_cycles=2)

            self.assertEqual(result.stopped_reason, "idle")
            self.assertEqual(result.cycle_count, 2)
            self.assertTrue(all(cycle.status == RuntimeCycleStatus.NO_OP for cycle in result.cycles))

    def test_autonomous_runtime_plans_recovery_and_completes_repair_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Recovery Runtime\n\nRepair task evidence.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()
            graph = AutonomousTaskGraphCreateTool().execute(
                {
                    "goal_title": "Recover a failed README review",
                    "success_criteria": ["README was read."],
                    "tasks": [
                        {
                            "task_id": "missing",
                            "title": "Read source with invalid input",
                            "request": 'read_file {"path":"README.md","unexpected":true}',
                            "success_criteria": ["README was read."],
                        }
                    ],
                },
                config,
            )
            runtime = AutonomousRuntime(config)
            runtime.recovery = RecoveryEngine(
                RecoveryStore(config.cognition_db_path),
                runtime.goals,
                provider=ModelRecoveryProvider(
                    StaticModelClient(
                        '{"status":"planned","summary":"Recover by reading the available README.","tasks":[{"local_task_id":"read-readme","title":"Read available README","request":"read_file {\\"path\\":\\"README.md\\"}","owner":"master","success_criteria":["README was read."],"depends_on":[]}]}'
                    ),
                    fallback=EvidenceRecoveryProvider(),
                ),
            )

            first = runtime.run_once()
            parent_task_id = graph.output["tasks"][0]["task_id"]
            parent = GoalStore(config.cognition_db_path).get_task(parent_task_id)
            recoveries = RecoveryStore(config.cognition_db_path).for_task(parent_task_id)
            ready_after_recovery = GoalStore(config.cognition_db_path).ready_tasks()
            second = runtime.run_once()
            goal = GoalStore(config.cognition_db_path).get_goal(graph.output["goal"]["goal_id"])
            repaired = GoalStore(config.cognition_db_path).get_task(recoveries[0].created_task_ids[0])

            self.assertEqual(first.status, RuntimeCycleStatus.RECOVERY_PLANNED)
            self.assertIsNotNone(parent)
            self.assertEqual(parent.status, TaskStatus.RECOVERING)
            self.assertEqual(parent.metadata["recovery_status"], RecoveryStatus.PLANNED.value)
            self.assertEqual(ready_after_recovery[0].task_id, recoveries[0].created_task_ids[0])
            self.assertEqual(second.status, RuntimeCycleStatus.TASK_FINISHED)
            self.assertIsNotNone(repaired)
            self.assertEqual(repaired.status, TaskStatus.COMPLETED)
            self.assertIsNotNone(goal)
            self.assertEqual(goal.status, GoalStatus.COMPLETED)

    def test_autonomous_runtime_delegates_to_specialist_and_records_reflection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Specialist Runtime\n\nDelegated task evidence.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()

            specialist = CognitiveSpecialistRecordTool().execute(
                {
                    "name": "File reviewer",
                    "purpose": "Read local files and return verified evidence.",
                    "contract": "Use read-only tools for file inspection. Do not infer file contents without reading.",
                    "tools": ["read_file"],
                    "success_criteria": ["README was read."],
                    "confidence": 0.8,
                },
                config,
            )
            graph = AutonomousTaskGraphCreateTool().execute(
                {
                    "goal_title": "Review README through a specialist",
                    "success_criteria": ["Specialist evidence is stored."],
                    "tasks": [
                        {
                            "task_id": "readme",
                            "title": "Read README",
                            "owner": "File reviewer",
                            "request": 'read_file {"path":"README.md"}',
                            "success_criteria": ["README was read."],
                        }
                    ],
                },
                config,
            )

            self.assertEqual(specialist.status, ActionStatus.SUCCEEDED)
            self.assertEqual(graph.status, ActionStatus.SUCCEEDED)
            result = AutonomousRuntime(config).run_once()
            store = GoalStore(config.cognition_db_path)
            task_id = graph.output["tasks"][0]["task_id"]
            task = store.get_task(task_id)
            reflections = ReflectionStore(config.cognition_db_path).for_task(task_id)
            learning = LearningStore(config.cognition_db_path).for_task(task_id)
            consolidations = ConsolidationStore(config.cognition_db_path).for_task(task_id)
            recorded_specialist = SpecialistStore(config.specialist_registry_path).get_by_name("File reviewer")
            reflection_tool = CognitiveReflectionStatusTool().execute({"task_id": task_id}, config)
            consolidation_tool = CognitiveConsolidationStatusTool().execute({"task_id": task_id}, config)

            self.assertEqual(result.status, RuntimeCycleStatus.TASK_FINISHED)
            self.assertIsNotNone(task)
            self.assertEqual(task.status, TaskStatus.COMPLETED)
            self.assertEqual(task.metadata["specialist_id"], specialist.output["specialist"]["specialist_id"])
            self.assertEqual(task.metadata["reflection_status"], ReflectionStatus.PASSED.value)
            self.assertEqual(task.metadata["learning_id"], learning[0].learning_id)
            self.assertEqual(task.metadata["consolidation_id"], consolidations[0].consolidation_id)
            self.assertEqual(task.metadata["consolidation_status"], ConsolidationStatus.SKIPPED.value)
            self.assertEqual(reflections[0].status, ReflectionStatus.PASSED)
            self.assertEqual(reflections[0].checked_criteria, ["README was read."])
            self.assertEqual(learning[0].reflection_id, reflections[0].reflection_id)
            self.assertEqual(learning[0].outcome, ReflectionStatus.PASSED.value)
            self.assertIsNotNone(recorded_specialist)
            self.assertEqual(recorded_specialist.usage_count, 1)
            self.assertEqual(reflection_tool.status, ActionStatus.SUCCEEDED)
            self.assertEqual(reflection_tool.output["reflections"][0]["task_id"], task_id)
            self.assertEqual(consolidation_tool.status, ActionStatus.SUCCEEDED)
            self.assertEqual(consolidation_tool.output["consolidations"][0]["task_id"], task_id)


def _utc_seconds_from_now(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


if __name__ == "__main__":
    unittest.main()
