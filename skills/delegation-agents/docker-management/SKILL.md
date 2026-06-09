---
name: docker-management
description: Native Humungousaur skill for Docker Management. Use when a task calls for docker management workflows, readiness checks, artifacts, or approval-gated local/provider actions.
---

# Docker Management

This is a Humungousaur-native skill. It is authored inside this repository and uses only Humungousaur-owned tools, approval gates, artifacts, and optional dependency records.

## When To Use

Use this skill when the user asks for docker management planning, execution, verification, troubleshooting, or artifact creation inside Humungousaur.

## Tool Map

- `tool_search`
- `tool_describe`
- `capability_surface`
- `write_note`
- `native_security_policy`
- `tool_output_store`
- `docker_container_list`
- `docker_compose_prepare`
- `delegate_task`
- `kanban_create`
- `kanban_list`
- `kanban_heartbeat`
- `kanban_complete`
- `process`
- `terminal`
- `mcp_server_catalog`
- `mcp_server_launch`
- `optional_dependency_installer`

## Workflow

1. Clarify the user's concrete docker management objective, target environment, credentials already configured, and expected artifact or action.
2. Use `tool_search` or `capability_surface` to find the native Humungousaur tools for the domain before choosing a path.
3. Run safe inspection/readiness steps first and write bounded notes or artifacts under the workspace or data directory.
4. Use kanban/delegation/process tools to coordinate native workers and long-running jobs with heartbeat records.
5. Represent external CLIs or runtimes as optional dependency requests and launch packets until explicitly configured.
6. Summarize what ran, what was skipped, what remains blocked, and the exact files or records created.

## Safety And Boundaries

- Do not import, execute, or vendor upstream assistant code for this skill.
- Do not store raw secrets; store only environment variable names, secret references, or readiness booleans.
- Use approvals for writes, sends, purchases, desktop control, process launches, provider calls, and destructive operations.
- Do not run network scans, exploit tooling, cloud jobs, or GPU workloads without explicit authorization and scope.

## Verification

- Record concrete evidence paths or tool outputs before claiming completion.
- Prefer dry-run or prepared artifacts when credentials, hardware, licenses, or live services are missing.
- If a provider-specific runtime is not configured, report the missing credential or binary by name and stop before live execution.
