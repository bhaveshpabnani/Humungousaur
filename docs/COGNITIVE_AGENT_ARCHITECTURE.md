# Cognitive Agent Architecture

Humungousaur's target architecture is a local-first personal cognitive runtime: a persistent assistant that observes context, keeps goals, learns stable preferences and workflows, delegates work to specialists, verifies progress, and interacts with the user at human-appropriate moments.

## North Star

The assistant should behave like a daily collaborator:

- know the current focus and active goals
- remember useful preferences, facts, workflows, and outcomes
- develop a durable persona and user model from evidence
- maintain interaction posture, user-state hypotheses, and unresolved commitments from evidence
- forget or summarize stale noise
- practice, improve, and retire reusable skills from evidence
- keep future tasks and blocked work in view
- track explicit promises, obligations, and follow-ups as durable commitments
- maintain an evidence-backed model of the operating environment, constraints, resources, risks, opportunities, and live signals
- arbitrate priorities and initiative from current goals, tasks, commitments, environment, risks, and memory
- monitor its own uncertainty, risks, and autonomy posture
- prepare concise current-work briefings for handoffs, mornings, reviews, and interruptions
- use specialist capabilities instead of one overloaded prompt
- act only through explicit tools and policy gates
- observe results before claiming completion
- ask for judgment when needed
- stay silent when observation is enough

The system is not a chatbot wrapped around tools. It is a durable control loop around perception, attention, memory, planning, execution, reflection, and response.

## Runtime Loop

```text
event/wakeup -> perception -> attention -> cognitive decision -> goal/task update
      -> specialist/tool execution -> observation -> reflection
      -> recovery/learning/consolidation/curation/skill-evolution/persona-evolution/self-review/interaction-review/commitment-review/environment-review/priority-review -> briefing/response/schedule/sleep/continue
```

Codex skill integration adds a reference-to-memory bridge:

```text
local .codex and Codex app plugins/skills -> codex catalog/read tools -> codex skill sync -> reusable cognitive skill records -> planner-visible skill context
Codex manual / CLI surface -> codex_cli_status / codex_cli_run -> approval-gated codex exec delegation -> verified task output
```

This bridge reads OpenAI/Codex `SKILL.md`, plugin metadata, and documented Codex CLI behavior as evidence, then writes relevant reusable Humungousaur skill records or delegates an approved task through `codex exec`. It does not create deterministic natural-language routes.

## Layers

1. Event bus
   - Normalizes user text, voice, activity, screen, browser, app, file, schedule, and system stimuli into durable events.
   - Supports priorities so interrupts and approvals can preempt background work.

2. Perception and context
   - Converts raw signals into compact observations.
   - Separates retrieved/environment content from instructions.

3. Attention manager
   - Decides whether an event should be ignored, observed, analyzed, acted on, or answered.
   - Direct user and voice inputs are explicit; passive inputs require structured action metadata.

4. Cognitive controller
   - Maintains focus, active goals, working memory, and response mode.
   - Produces structured decisions instead of keyword routing.

5. Goal and task graph manager
   - Persists active goals, task dependencies, success criteria, blockers, results, and next wake-up conditions.
   - Complex work becomes a graph, not a one-shot plan.

6. Memory system
   - Working memory: current task state.
   - Episodic memory: events, actions, outcomes.
- Semantic memory: stable facts and preferences.
   - Procedural memory: learned workflows.
   - Skill memory: reusable capability instructions and verification steps.
   - Curation memory: exact-ID retention, summarization, and forgetting decisions with audit evidence.
   - Skill evolution memory: exact-ID skill improvement, retention, creation, and retirement decisions.
   - Persona evolution memory: assistant identity, communication style, boundaries, preferences, and stable facts updated from evidence.
   - Self-review memory: uncertainty, confidence, risks, open questions, autonomy posture, and recommended next actions.
   - Interaction-review memory: conversation state, collaboration posture, user-state hypotheses, unresolved commitments, response recommendations, and caution flags.
   - Commitment memory: explicit promises, follow-ups, owed actions, owner, status, due note, evidence refs, and model-led review history.
   - Environment memory: workspace, system, browser, application, constraint, resource, risk, opportunity, and signal records with evidence refs.
   - Priority memory: ranked goals, tasks, commitments, next actions, deferrals, escalations, and focus recommendations.

7. Persona and user model
   - Stores assistant identity, tone, boundaries, and user preferences.
   - Evolves from explicit user memories, repeated successful workflows, and model-led persona review.

8. Persona evolution
   - Reviews durable evidence to tune assistant identity, communication style, boundaries, user preferences, and stable facts.
   - Uses model-led review when configured and skips rather than inferring user model changes without a model.

9. Specialist agents
   - Browser, OS, code/interpreter, memory, research, document, voice, scheduler, and critic agents.
   - Each specialist gets scoped context, tools, permissions, and success criteria.

10. Tool executor and policy
   - All actions pass through schemas, risk levels, approvals, sandboxing, redaction, audit logs, and cancellation checkpoints.

11. Reflection and verification
    - Checks outputs against success criteria before final answers.
    - Retries, adapts, asks for clarification, or reports blockers when evidence is insufficient.

12. Adaptive recovery
    - Converts failed, blocked, or inconclusive reflected work into explicit repair tasks when model evidence supports it.
    - Preserves parent/repair task links so goals can continue without pretending the failed attempt succeeded.

13. Cognitive briefing
    - Synthesizes current focus, active goals, blockers, next actions, future wakeups, learning, and persona into an actionable work view.
    - Uses model-led synthesis when configured and stores skipped raw-state briefings rather than inferring priorities without a model.

14. Memory curation
    - Reviews durable knowledge for exact-ID retention, summarization, and archival.
    - Uses model-led curation when configured and skips rather than guessing what should be forgotten.

15. Skill evolution
    - Reviews reusable skills for exact-ID improvement, retention, creation, and retirement.
    - Uses model-led evidence review when configured and skips rather than rewriting skills without a model.

16. Metacognitive self-review
    - Reviews current cognitive state for uncertainty, risks, autonomy posture, open questions, and whether to ask the user.
    - Uses model-led review when configured and skips rather than inferring self-confidence without a model.

17. Interaction and relationship review
    - Reviews recent interaction evidence for collaboration posture, user-state hypotheses, unresolved commitments, response recommendations, and caution flags.
    - Uses model-led review when configured and skips rather than inferring user state, relationship context, or conversation posture without a model.

18. Commitment manager
    - Tracks explicit user-visible promises, follow-ups, owed actions, owner, status, due note, and evidence.
    - Uses model-led review to create, update, resolve, or retain commitments from evidence; deterministic explicit tools can update exact IDs only.

19. Environment/world-context manager
    - Tracks durable facts about the workspace, system, browser state, applications, constraints, resources, risks, opportunities, and live signals.
    - Uses model-led review to create, update, archive, or retain environment records from evidence; deterministic explicit tools can update exact IDs only.

20. Priority and initiative manager
    - Ranks active goals, tasks, and commitments; recommends focus, next actions, deferrals, and escalations.
    - Uses model-led review over durable evidence and exact IDs rather than deterministic urgency heuristics.

21. Human interaction manager
    - Chooses text, voice preparation, spoken response, notification, progress update, approval request, or silence.
    - Supports interruption, pause/resume, and long-running progress.

## Implementation Principles

- `docs/GLOBAL_AGENT_INSTRUCTIONS.md` is the strict global rule for intelligence: do not use pattern-based, regex-based, keyword-list-based, hardcoded-constant-based, deterministic natural-language handling, broad deterministic matching, or static routing tables for cognition, planning, routing, delegation, memory decisions, experience consolidation, skill evolution decisions, persona evolution decisions, metacognitive self-review, interaction review, commitment extraction, commitment resolution, environment modeling, constraint/resource/risk/opportunity detection, priority ranking, initiative decisions, focus selection, relationship-state decisions, user-state hypotheses, conversation-state decisions, persona update decisions, future wakeup/timing decisions, task decomposition, response strategy, recovery strategy, or completion judgment.
- Model-led cognition chooses strategy from schemas, context, permissions, and goals.
- Deterministic code enforces safety, persistence, validation, explicit fallback commands, and evidence boundaries only.
- Every capability is a tool or specialist with a bounded contract.
- Every durable action creates inspectable evidence.
- No passive observation becomes action without explicit upstream metadata or user intent.
- Completion is a verified state, not a generated sentence.

## Implemented Milestones

The first implementation milestone adds durable cognitive primitives:

- cognitive event bus
- goal/task store
- persona store
- skill store
- cognitive decision model
- interaction recorder
- cognitive state tools

This gives the existing agent core a memory-bearing control layer without replacing the already working tool executor.

The second implementation milestone adds a stepwise autonomous runtime:

- queued runtime events with priority
- atomic step boundary for pause and interrupt
- dependency-aware ready tasks
- one-cycle autonomous runner
- high-risk bounded cycle tool
- queue/status and task-graph tools

Autonomy remains deliberately stepwise. Long-running operation should repeatedly call the one-cycle runner from a daemon, scheduler, or UI loop so every action has a checkpoint, audit event, and opportunity for interruption.

The third implementation milestone adds explicit delegation and reflection:

- durable specialist contracts
- model-visible specialist registry in planning context
- task graph owner assignments for explicit delegation
- task-level success criteria
- reflection records for completed, blocked, failed, inconclusive, or approval-waiting task runs
- public tools for recording specialists and inspecting reflection status

Delegation is intentionally contract-driven. The runtime does not infer a specialist from natural language; model-led planning must assign an owner in the task graph, and the runtime executes that explicit assignment through the specialist contract.

The fourth implementation milestone adds focus and learning:

- durable current-focus state with active goal, active task, mode, summary, and pinned context
- semantic/procedural knowledge records with exact-ID forgetting
- execution-learning records tied to run, task, reflection, and note evidence
- planner-visible focus, knowledge, and recent learning context
- public tools for focus updates, knowledge recording, knowledge forgetting, and learning inspection

Learning is intentionally evidence-shaped. The runtime records outcomes from structured run and reflection state. Higher-level meaning, memory selection, and future use remain model-led through the tool schemas and planning context.

The fifth implementation milestone adds model-led attention:

- schema-driven cognitive decision provider using the same configured model clients as the planner
- OpenAI, Groq, Ollama, Grok/xAI, and OpenAI-compatible transports shared through one model-client factory
- explicit fallback limited to source type, response mode, and structured metadata
- no natural-language guessing when the model is unavailable
- planner-visible decisions still flow through the same goal/task, focus, memory, learning, and audit stores

Attention is the activation gate. It decides whether an event should be answered, analyzed, observed, ignored, or monitored before planning and execution. The model provider owns generalized event interpretation; deterministic fallback exists only so direct commands, structured passive action metadata, and model-unavailable safe stops continue to work safely.

The sixth implementation milestone adds model-led reflection:

- schema-driven task completion evaluator using the same configured model clients as planning and attention
- success criteria, tool results, final response, approvals, and note evidence are passed as structured data
- deterministic reflection fallback is limited to explicit runtime statuses and evidence-boundary bookkeeping
- evidence-boundary enforcement prevents claims of completion when approvals are pending or tools failed/blocked
- autonomous task status, learning records, and focus updates now consume the model reflection record

Reflection is the completion gate. It decides whether the assistant can claim that a task passed, needs approval, failed, was blocked, or is inconclusive. The model owns generalized completion judgment; deterministic status checks only enforce non-negotiable runtime evidence boundaries.

The seventh implementation milestone adds model-led consolidation:

- schema-driven experience consolidation using the same configured model clients as planning, attention, and reflection
- run results, reflection records, and learning records are passed as structured evidence
- durable consolidation records track what was recorded, skipped, or failed
- accepted proposals write through the existing knowledge, skill, and persona stores
- public tools expose recent consolidation history for inspection
- autonomous task metadata records the consolidation ID and status

Consolidation is the learning gate. It decides whether an experience is worth promoting into stable knowledge, reusable skill, or persona memory. The model owns generalized memory selection; deterministic code only validates schemas, caps output volume, attaches evidence references, persists records, and skips rather than guessing when the model is unavailable.

The eighth implementation milestone adds proactive wakeups:

- durable wakeup records with scheduled, fired, and cancelled states
- exact timestamp and delay scheduling tools for future autonomous stimuli
- status and exact-ID cancellation tools for user-visible follow-up control
- due wakeups are converted into normal queued runtime events before each autonomous cycle
- attention decisions can request a future wakeup through `next_wakeup_seconds`
- planning context includes scheduled wakeups so future work remains visible

Wakeups are the continuation gate. The model decides whether future attention is useful and why; deterministic code persists exact times, fires due records, preserves evidence metadata, and routes the resulting stimulus through the same attention, tool, policy, and audit path as any other event.

The ninth implementation milestone adds a bounded autonomous loop:

- shared loop runner for daemon, CLI, API, and tests
- bounded cycle batches over queued events, due wakeups, and ready tasks
- configurable idle stopping so the runtime can sleep cleanly when no work is ready
- cycle summaries recorded into memory for inspection
- CLI commands for autonomous status and loop execution
- API endpoints for autonomous status and cycle ticking

The loop is the runtime heartbeat. It does not bypass attention, planning, tool policy, approvals, reflection, learning, consolidation, or wakeup gates. It only repeats the already-audited one-cycle runtime with explicit bounds and visible stop reasons.

The tenth implementation milestone adds adaptive recovery:

- schema-driven recovery provider using the same configured model clients as planning, attention, reflection, and consolidation
- failed, blocked, or inconclusive reflected task runs can produce explicit repair task nodes
- durable recovery records preserve run, reflection, learning, parent task, and created repair task IDs
- parent tasks can enter a `recovering` status while repair tasks run through the normal autonomous loop
- goal terminal logic treats recovery chains as part of completion instead of prematurely blocking or passing
- public tools expose recent recovery history for inspection

Recovery is the repair gate. The model decides whether there is a justified next repair task from structured goal, task, run, reflection, and learning evidence. Deterministic code only validates the recovery schema, persists records, creates explicit task nodes, and skips rather than inventing semantic repair work when the model is unavailable.

The eleventh implementation milestone adds cognitive briefing:

- durable briefing records with generated, skipped, and failed states
- schema-driven briefing provider using the same configured model clients as planning, attention, reflection, consolidation, and recovery
- current focus, goals, tasks, knowledge, learning, wakeups, recoveries, briefings, skills, specialists, and persona are passed as structured evidence
- public tools prepare a current-work briefing and inspect briefing history
- planning context includes recent briefings so the assistant can carry a compact work view across future turns
- model-unavailable fallback records a skipped briefing and bounded raw state without semantic prioritization

Briefing is the situational-awareness gate. The model decides priorities, blockers, next actions, and watch items from durable evidence. Deterministic code only gathers bounded state, validates the schema, persists the briefing record, and exposes raw state when no model is available.

The twelfth implementation milestone adds memory curation:

- durable curation records with recorded, skipped, and failed states
- schema-driven curation provider using the same configured model clients as planning, attention, reflection, consolidation, recovery, and briefing
- current knowledge, focus, active goals, tasks, learning, consolidations, recoveries, briefings, wakeups, and persona are passed as structured evidence
- curation proposals can archive only exact active knowledge IDs that are present in the input
- curation proposals can create summarized knowledge records with evidence references
- public tools run a bounded memory hygiene pass and inspect curation history
- planning context includes recent curations so future memory decisions can see what was kept, summarized, or forgotten
- model-unavailable fallback records a skipped curation without semantic forgetting or summarization

Curation is the forgetting gate. The model decides what durable knowledge is stale, duplicate, superseded, low-value, or worth compressing. Deterministic code only validates IDs, archives exact records, creates evidence-backed summaries, persists the curation record, and skips when model reasoning is unavailable.

The thirteenth implementation milestone adds skill evolution:

- durable skill evolution records with recorded, skipped, and failed states
- reusable skills have active/retired lifecycle state, evidence references, retirement reasons, and exact-ID update operations
- schema-driven skill evolution provider using the same configured model clients as planning, attention, reflection, consolidation, recovery, briefing, and curation
- current skills, focus, active goals, tasks, learning, consolidations, curations, recoveries, briefings, knowledge, specialists, and persona are passed as structured evidence
- evolution proposals can update or retire only exact active skill IDs that are present in the input
- evolution proposals can create new skills only when evidence shows a reusable workflow gap
- public tools run a bounded skill review pass and inspect skill evolution history
- planning context includes recent skill evolution records so future tool and skill choices can see what was improved, retained, created, or retired
- model-unavailable fallback records a skipped skill review without semantic skill updates

Skill evolution is the practice gate. The model decides when reusable workflows should improve, merge, retire, or become new skills. Deterministic code only validates exact IDs, applies bounded store updates, preserves retired skill history, persists audit records, and skips when model reasoning is unavailable.

The fourteenth implementation milestone adds persona evolution:

- durable persona evolution records with recorded, skipped, and failed states
- persona profiles include evidence references for durable identity, style, boundary, preference, and stable-fact changes
- schema-driven persona evolution provider using the same configured model clients as planning, attention, reflection, consolidation, recovery, briefing, curation, and skill evolution
- current persona, focus, active goals, tasks, knowledge, learning, consolidations, curations, skill evolutions, previous persona evolutions, recoveries, briefings, wakeups, skills, and specialists are passed as structured evidence
- proposals can update assistant identity and communication style only when evidence supports a stable long-term improvement
- proposals can add boundaries, user preferences, and stable facts without removing existing safety boundaries
- public tools run a bounded persona review pass and inspect persona evolution history
- planning context includes recent persona evolution records so future responses can see how the assistant-user relationship model has changed
- model-unavailable fallback records a skipped persona review without semantic user-model inference

Persona evolution is the identity gate. The model decides whether evidence supports a durable change in how the assistant presents itself, communicates, preserves boundaries, or remembers user preferences. Deterministic code only validates schema output, merges bounded additions, preserves safety boundaries, persists audit records, and skips when model reasoning is unavailable.

The fifteenth implementation milestone adds metacognitive self-review:

- durable self-review records with generated, skipped, and failed states
- schema-driven self-review provider using the same configured model clients as planning, attention, reflection, consolidation, recovery, briefing, curation, skill evolution, and persona evolution
- current focus, goals, tasks, persona, memory, learning, consolidations, curations, skill evolutions, persona evolutions, previous self-reviews, recoveries, briefings, wakeups, skills, and specialists are passed as structured evidence
- self-reviews record autonomy posture, confidence, uncertainty, risks, open questions, recommended actions, and whether to ask the user
- public tools run a bounded self-review pass and inspect self-review history
- planning context includes recent self-review records so future planning can see the assistant's own uncertainty and risk posture
- model-unavailable fallback records a skipped self-review without inferred confidence, risk, or autonomy judgment

Self-review is the metacognitive gate. The model decides whether the assistant should continue, observe, ask the user, delegate, recover, or pause from structured evidence. Deterministic code only validates schema output, bounds lists, persists audit records, and skips when model reasoning is unavailable.

The sixteenth implementation milestone adds interaction review:

- durable interaction-review records with generated, skipped, and failed states
- schema-driven interaction-review provider using the same configured model clients as planning, attention, reflection, consolidation, recovery, briefing, curation, skill evolution, persona evolution, and self-review
- current focus, goals, tasks, persona, memory, learning, consolidations, curations, skill evolutions, persona evolutions, self-reviews, previous interaction reviews, recoveries, briefings, wakeups, skills, and specialists are passed as structured evidence
- interaction reviews record conversation summary, interaction posture, user-state hypotheses, collaboration notes, unresolved commitments, recommended responses, caution flags, evidence references, and confidence
- public tools run a bounded interaction review pass and inspect interaction-review history
- planning context includes recent interaction-review records so future planning can see collaboration posture and unresolved commitments
- model-unavailable fallback records a skipped interaction review without inferred user state, relationship judgment, or response posture

Interaction review is the relationship-context gate. The model decides what interaction posture and response recommendations are justified by evidence. Deterministic code only validates schema output, bounds lists, persists audit records, and skips when model reasoning is unavailable.

The seventeenth implementation milestone adds commitment tracking:

- durable commitment records with open, satisfied, blocked, and dropped states
- durable commitment-review records with recorded, skipped, and failed states
- schema-driven commitment review provider using the same configured model clients as planning, attention, reflection, consolidation, recovery, briefing, curation, skill evolution, persona evolution, self-review, and interaction review
- current focus, goals, tasks, persona, memory, learning, consolidations, curations, skill evolutions, persona evolutions, self-reviews, interaction reviews, existing commitments, previous commitment reviews, recoveries, briefings, wakeups, skills, and specialists are passed as structured evidence
- commitment reviews can create new commitments only when evidence supports a specific owed action, promise, follow-up, check-in, or user-visible obligation
- commitment reviews can update or resolve only exact existing commitment IDs that are present in the input
- explicit tools record, update, inspect, and review commitments without broad natural-language inference
- planning context includes open commitments and recent commitment reviews so future planning can honor outstanding promises
- model-unavailable fallback records a skipped commitment review without inferred promises or follow-ups

Commitment tracking is the promise ledger. The model decides which commitments are real, still open, satisfied, blocked, or dropped from evidence. Deterministic code only validates exact IDs, persists explicit structured updates, records audit history, and skips when model reasoning is unavailable.

The eighteenth implementation milestone adds environment/world-context modeling:

- durable environment records for workspace, system, browser, application, constraint, resource, risk, opportunity, and signal facts
- durable environment-review records with recorded, skipped, and failed states
- schema-driven environment review provider using the same configured model clients as planning, attention, reflection, consolidation, recovery, briefing, curation, skill evolution, persona evolution, self-review, interaction review, and commitment review
- current focus, goals, tasks, persona, memory, learning, consolidations, curations, skill evolutions, persona evolutions, self-reviews, interaction reviews, commitments, existing environment records, previous environment reviews, recoveries, briefings, wakeups, skills, and specialists are passed as structured evidence
- environment reviews can create new records only for stable or currently important workspace, system, browser, application, constraint, resource, risk, opportunity, or signal facts that help future decisions
- environment reviews can update or archive only exact existing environment IDs that are present in the input
- explicit tools record, update, inspect, and review environment facts without broad natural-language inference
- planning context includes current environment records and recent environment reviews so future planning can reason about constraints and resources
- model-unavailable fallback records a skipped environment review without inferred environment facts

Environment modeling is the world-context ledger. The model decides which environment facts matter for future action from evidence. Deterministic code only validates exact IDs, persists explicit structured updates, archives exact records, records audit history, and skips when model reasoning is unavailable.

The nineteenth implementation milestone adds priority and initiative review:

- durable priority-review records with generated, skipped, and failed states
- schema-driven priority provider using the same configured model clients as planning, attention, reflection, consolidation, recovery, briefing, curation, skill evolution, persona evolution, self-review, interaction review, commitment review, and environment review
- current focus, goals, tasks, persona, memory, learning, commitments, environment records, previous priority reviews, recoveries, briefings, wakeups, skills, and specialists are passed as structured evidence
- priority reviews rank only exact active goal, task, and commitment IDs supplied in the input
- priority reviews record focus recommendation, next actions, deferred items, escalations, evidence refs, and confidence
- public tools run a bounded priority review and inspect priority history
- planning context includes recent priority reviews so future planning can use durable initiative evidence
- model-unavailable fallback records a skipped priority review without inferred urgency, importance, or initiative

Priority review is the initiative ledger. The model decides what matters next from evidence. Deterministic code only validates exact IDs, bounds lists, persists audit records, and skips when model reasoning is unavailable.
