---
name: pinecone
description: Native Humungousaur skill for Pinecone. Use when a task calls for pinecone workflows, readiness checks, artifacts, or approval-gated local/provider actions.
---

# Pinecone

This is a Humungousaur-native skill. It is authored inside this repository and uses only Humungousaur-owned tools, approval gates, artifacts, and optional dependency records.

## When To Use

Use this skill when the user asks for pinecone planning, execution, verification, troubleshooting, or artifact creation inside Humungousaur.

## Tool Map

- `tool_search`
- `tool_describe`
- `capability_surface`
- `write_note`
- `native_security_policy`
- `tool_output_store`
- `pinecone_index_prepare`
- `execute_code`
- `python_interpreter`
- `process`
- `terminal`
- `provider_registry`
- `mcp_server_catalog`
- `mcp_tool_call`
- `optional_dependency_installer`

## Workflow

1. Clarify the user's concrete pinecone objective, target environment, credentials already configured, and expected artifact or action.
2. Use `tool_search` or `capability_surface` to find the native Humungousaur tools for the domain before choosing a path.
3. Run safe inspection/readiness steps first and write bounded notes or artifacts under the workspace or data directory.
4. Create reproducible scripts, notebooks, benchmark commands, model cards, or vector-store plans using bounded local code execution.
5. Gate GPU/cloud/provider work behind `provider_registry`, credential readiness, and explicit approval.
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
