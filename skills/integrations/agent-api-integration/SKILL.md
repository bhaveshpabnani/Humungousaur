---
name: agent-api-integration
description: Discover, design, and implement external API integrations as Humungousaur-owned tools with schemas, auth, approvals, tests, and capability documentation.
---

# Agent API Integration

## Purpose

Turn external APIs into reliable agent tools. This skill makes integrations native: explicit schemas, auth handling, error contracts, risk levels, approvals, tests, and capability catalog entries.

## When To Use

Use when the user wants to integrate a SaaS API, channel, data service, automation endpoint, plugin-like capability, or a missing upstream-inspired tool.

## Inputs And Evidence

- API docs, auth method, desired operations, rate limits, data sensitivity, and expected workflows.
- Current tool registry, capability surface, tests, and existing adapters.

## Tool Map

- `tool_search`
- `tool_describe`
- `capability_surface`
- `read_file`
- `search_workspace`
- `run_shell_command`
- `write_note`

## Workflow

1. Define the user workflows the API should support.
2. Read current project adapter patterns and tool schemas.
3. Design minimal native tools with typed inputs, risk levels, and approval needs.
4. Implement auth through env/secret references, not raw secrets in files.
5. Add tests for happy path, missing auth, bad inputs, and API errors.
6. Register/document the capability and run smoke tests.

## Native Implementation Boundaries

- Build Humungousaur-owned adapters and tools.
- Do not import external reference AgentAPI plugins, external reference scripts, or other upstream runtime code directly.
- Upstream repos are reference evidence only.

## Safety And Approval

- Mutating external APIs need approval.
- Redact tokens and sensitive payloads.
- Respect rate limits and terms.

## Verification

- Tool schema appears in `tool_search` or capability surface.
- Tests prove validation and error handling.
- Live smoke, when approved, proves endpoint behavior.

## Failure Modes

- Wrapping too many operations in one vague tool.
- Missing auth failure handling.
- Claiming integration complete when only docs were written.

## References

- Shortlist item: `agent-api-integration`.
- Upstream inspiration: external reference AgentAPI entries as reference only.
