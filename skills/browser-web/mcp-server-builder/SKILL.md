---
name: mcp-server-builder
description: Design, implement, and review MCP server tools with clear schemas, auth boundaries, approval modes, tests, and Humungousaur-native integration plans.
---

# MCP Server Builder

## Purpose

Build or plan Model Context Protocol servers as explicit tool surfaces. This skill emphasizes schema clarity, auth, least privilege, and verification.

## When To Use

Use when the user asks to build an MCP server, expose tools, wrap an API, add OAuth/auth, deploy a remote MCP service, or review MCP server code.

## Inputs And Evidence

- Desired tools/resources, auth model, host/runtime, deployment target, and client integration needs.
- Existing code, API docs, schemas, and tests.

## Tool Map

- `read_file`
- `search_workspace`
- `write_note`
- `run_shell_command`
- `tool_search`
- `agent-api-integration`

## Workflow

1. Define tool/resource contracts and user-visible capability boundaries.
2. Choose runtime and auth model.
3. Implement small typed tools with clear schemas and errors.
4. Add tests for schema validation, auth, and failure cases.
5. Document setup and secrets.
6. Verify with local or deployed smoke tests.

## Native Implementation Boundaries

- Implement MCP code inside the user's project or Humungousaur-owned adapters.
- Do not import Anthropic MCP builder skill code as implementation.
- Do not expose broad filesystem/network access without explicit policy.

## Safety And Approval

- Auth, secrets, and external APIs require careful setup.
- Tools that mutate external state need approval modes.
- Avoid logging tokens or private payloads.

## Verification

- Validate tool schemas.
- Run local tests and an MCP client smoke where feasible.
- Confirm auth failure behavior.

## Failure Modes

- Tools with vague inputs.
- No error contract.
- Overpowered server access.

## References

- Shortlist item: `mcp-server-builder`.
- Upstream inspiration: Anthropic MCP builder reference only.
