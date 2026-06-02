# Engineering Principles

## Model-Led Capability Handoffs

Humungousaur should grow through schema-driven tools and model-led planning, not broad natural-language keyword routing.

- Add capabilities as permissioned tools with descriptions, JSON input schemas, risk levels, and capability groups.
- Let the GenAI planner choose tools from the catalog using user intent, runtime context, permissions, and tool contracts.
- Keep rule-based safeguards limited to explicit command-shaped fallbacks, safety validation, offline recovery, and tests that need no model/API key.
- Avoid regex intent maps and long keyword lists for broad product behavior. They are brittle, hard to extend, and age badly as the assistant becomes more capable.
- Prefer intelligent handoffs: user intent -> planner -> capability tool -> policy/executor -> observation/audit -> next step.
