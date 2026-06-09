---
name: integrations
description: Parent skill for external APIs, GitHub, Google Workspace, Notion, Airtable, RSS, GOG, OpenAI, Claude, auth setup, and computer-use provider integrations.
---

# Integrations

## Purpose

Use this parent skill when a task depends on an external service, API, repository host, productivity platform, provider SDK, authentication setup, or integration-specific operation.

## Hierarchy Reading Rules

1. Identify the service and whether the task is read-only, write, setup, or credential-sensitive.
2. Load the service child skill before using provider-specific contracts or schemas.
3. Prefer official APIs and connectors over browser interaction when available.
4. Keep credentials, tokens, permissions, and account changes guarded by the relevant child skill.

## Tool Map

- `agent-api-integration`
- `airtable-operations`
- `claude-api-development`
- `claude-computer-use`
- `git-auth-setup`
- `github-issues`
- `github-pr-workflow`
- `github-repo-management`
- `gog`
- `google-workspace`
- `notion-operations`
- `openai-api-development`
- `openai-computer-use`
- `rss-and-blog-monitoring`
- `wacli-operations`

## Child Skill Guide

- Use GitHub children for issues, PRs, repos, and auth-sensitive repository work.
- Use Google Workspace, Notion, Airtable, RSS, GOG, and WhatsApp CLI children for service-specific operations.
- Use OpenAI, Claude, and computer-use children for AI provider and automation integrations.
- Use agent API integration when designing or consuming a general API surface.

## Verification

- Verify service identity, account/project/repo, permissions, and side-effect status.
- Do not expose secrets; cite secret presence only in redacted form.
