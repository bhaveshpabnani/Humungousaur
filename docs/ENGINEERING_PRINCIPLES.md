# Engineering Principles

## Model-Led Capability Handoffs

Humungousaur should grow through schema-driven tools and model-led planning, not broad natural-language keyword routing.

- `docs/GLOBAL_AGENT_INSTRUCTIONS.md` is the controlling instruction for intelligence design: broad cognition, routing, delegation, memory decisions, memory curation, forgetting, summarization, retention decisions, experience consolidation, skill evolution decisions, persona update decisions, future wakeup/timing decisions, adaptive recovery decisions, briefing synthesis, task decomposition, completion judgment, proactive assistance, and response strategy must be model-led through OpenAI, Groq, Ollama, Grok, or another configured OpenAI-compatible client. Do not implement those behaviors with pattern matching, regex intent maps, keyword lists, hardcoded constant routing, static routing tables, command templates, brittle handcrafted cases, or deterministic natural-language inference.
- Add capabilities as permissioned tools with descriptions, JSON input schemas, risk levels, and capability groups.
- Let the GenAI planner choose tools from the catalog using user intent, runtime context, permissions, and tool contracts.
- Keep deterministic safeguards limited to explicit command-shaped fallbacks, safety validation, schema validation, audit persistence, evidence-boundary enforcement, and tests that need no model/API key.
- Avoid regex intent maps and long keyword lists for broad product behavior. They are brittle, hard to extend, and age badly as the assistant becomes more capable.
- Prefer intelligent handoffs: user intent -> planner -> capability tool -> policy/executor -> observation/audit -> next step.
