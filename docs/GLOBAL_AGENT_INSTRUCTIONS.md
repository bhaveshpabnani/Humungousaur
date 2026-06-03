# Global Agent Instructions

These instructions apply to Humungousaur's cognitive, planning, routing, delegation, response, and autonomy layers.

## Intelligence Must Be Model-Led

Do not implement assistant intelligence anywhere through pattern-based, regex-based, keyword-list-based, hardcoded-constant-based, broad deterministic matching, deterministic natural-language handling, or static routing tables.

This is a strict global constraint for every cognitive and agentic layer. No code path may decide user meaning, tool intent, task type, response mode, specialist delegation, completion status, memory importance, wakeup timing, skill choice, skill evolution, persona evolution, or recovery strategy by matching strings, regexes, fixed constants, command templates, keyword buckets, or brittle handcrafted cases.

This prohibition covers:

- intent detection
- tool routing
- task decomposition
- specialist selection
- response strategy
- memory decisions
- memory curation, forgetting, summarization, and retention decisions
- experience consolidation
- persona update decisions
- future wakeup and timing decisions
- skill selection
- skill evolution, improvement, retention, creation, and retirement decisions
- persona evolution, identity, communication-style, boundary, preference, and stable-fact decisions
- autonomous continuation decisions
- complex-task completion judgment
- adaptive recovery decisions
- briefing synthesis, prioritization, blocker selection, and next-action selection
- user-activity stimulus interpretation
- conversation-state interpretation
- proactive assistance decisions

For those behaviors, use model-led reasoning through the configured LLM clients and structured schemas. Supported intelligent planning transports include OpenAI, Groq's OpenAI-compatible API, Ollama's local OpenAI-compatible endpoint, Grok/xAI, and other explicitly configured OpenAI-compatible clients.

The planner should generalize from tool descriptions, risk levels, permissions, runtime context, active goals, persona, skills, and structured tool schemas. It must not rely on exact command words, intent regexes, static keyword maps, or brittle constant tables to infer broad natural-language meaning.

If a model client is unavailable, the platform may use only explicitly bounded fallback behavior: ask for clarification, preserve the stimulus for later processing, execute an explicitly selected tool command after schema validation, or stop safely. It must not silently replace model reasoning with handcrafted natural-language heuristics.

## Allowed Mechanical Determinism

Deterministic code is allowed only for non-intelligence mechanical boundaries:

- JSON/schema validation
- explicit user-selected tool commands
- safety policy and approval gates
- sandbox and filesystem boundaries
- redaction
- audit persistence
- database IDs and state transitions
- model-unavailable safe stops and evidence-boundary bookkeeping
- tests that intentionally avoid live model calls

These deterministic parts may enforce contracts, safety, durability, and reproducibility. They must not infer semantic meaning, route broad natural-language requests, decide cognitive intent, or become hidden deterministic planners.

## Engineering Rule

When adding a new assistant capability, expose a clear tool schema or specialist contract and let the model choose it from context. If a behavior starts to look like a keyword map, regex intent table, or hardcoded routing matrix, replace it with a model-led structured decision.
