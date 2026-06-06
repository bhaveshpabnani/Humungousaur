---
name: openai-api-development
description: Build and debug OpenAI or OpenAI-compatible clients, Responses/chat/tool schemas, Groq/Ollama-compatible routing, and provider smoke tests with current docs when needed.
---

# OpenAI API Development

## Purpose

Implement robust OpenAI and OpenAI-compatible integrations. This skill supports OpenAI, Groq-compatible endpoints, Ollama local OpenAI-compatible endpoints, and other configured clients through generalized adapters.

## When To Use

Use for model client bugs, Responses/chat completions, tool calling, JSON schema outputs, streaming, embeddings, provider fallback, Groq/Ollama/OpenAI-compatible setup, and smoke tests.

## Inputs And Evidence

- Provider config, env keys, model, base URL, error output, request/response logs, and current code.
- Tool schemas, prompt requirements, and verification case.

## Tool Map

- `read_file`
- `search_workspace`
- `run_shell_command`
- `python_interpreter`
- `system_status`
- `capability_surface`

## Workflow

1. Inspect existing provider abstraction and environment loading.
2. Use official docs when OpenAI API details are current/unstable.
3. Keep clients generalized around base URL, API key, model, timeout, and schema.
4. Preserve full prompts when required; do not over-compress task-critical prompts.
5. Add tests for request shape, parsing, errors, and provider selection.
6. Run mocked or approved live smoke and report exact provider/model.

## Native Implementation Boundaries

- Implement clients in Humungousaur or the target project.
- Do not import upstream provider wrappers as implementation.
- Avoid regex/keyword routing for provider choice or user intent.

## Safety And Approval

- Redact API keys.
- Live calls may cost money and require user intent.
- Do not log private prompts unnecessarily.

## Verification

- Provider smoke should prove request reached the intended endpoint when possible.
- 401/403/network errors should be reported with code and likely boundary, not hidden.
- Tests should cover parser behavior.

## Failure Modes

- Treating OpenAI, Groq, and Ollama as identical beyond compatible request shape.
- Swallowing provider error details.
- Hardcoding one model across all tasks.

## References

- Shortlist item: `openai-api-development`.
- Existing Humungousaur model-client requirement.
