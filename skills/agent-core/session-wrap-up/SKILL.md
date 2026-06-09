---
name: session-wrap-up
description: End a work session by summarizing completed work, blockers, tests, pending commitments, memory lessons, and optional git status. Use when the user asks to wrap up, checkpoint, commit, or preserve learnings.
---

# Session Wrap Up

## Purpose

Create a reliable end-of-session checkpoint. This skill adapts OpenClaw session wrap-up and Hermes GitHub workflow patterns into Humungousaur's notes, memory, commitments, and optional git surfaces.

## When To Use

Use when the user asks to wrap up, summarize the session, checkpoint progress, persist lessons, prepare a handoff, or commit eligible changes.

## Inputs And Evidence

- Git status and recent commits when working in a repo.
- Recent run notes and test output.
- Active commitments, follow-ups, blockers, and user requests.
- Memory lessons and skill changes that should be retained.

## Tool Map

- `memory_summary`
- `memory_write`
- `cognitive_commitment_status`
- `cognitive_commitment_review`
- `cognitive_self_review`
- `run_shell_command`
- `write_note`
- `codex_cli_plan`

## Workflow

1. Inspect current workspace state and recent work evidence.
2. Summarize completed work, tests, failures, current branch status, and uncommitted changes.
3. Identify pending commitments and blockers without marking them complete unless evidence proves it.
4. Record durable lessons only when useful for future work.
5. If the user requested commit, stage only intended files and commit after verification.
6. Produce a concise handoff with next actions.

## Safety

- Never push, deploy, or send external updates unless explicitly requested.
- Do not include secrets in summaries or commits.
- Do not claim tests passed unless command output proves it.

## Native Implementation Boundaries

- Use memory, commitment, self-review, shell, note, and Codex planning tools as the native wrap-up path.
- Treat git and test output as evidence; do not infer clean status or passing checks from prior intent.
- Use `write_note` or `memory_write` only for useful durable state, not for every transient thought.

## Verification

- Check git status before and after any commit.
- Link each blocker to evidence.
- Ensure generated notes are saved under the configured data directory.

## Failure Modes

- Committing generated artifacts accidentally.
- Summarizing intentions as completed work.
- Losing untracked follow-ups.

## References

- Shortlist item: `session-wrap-up`.
- Upstream inspiration: OpenClaw `alex-session-wrap-up`, Hermes GitHub skills.
- Existing guidance: `docs/GLOBAL_AGENT_INSTRUCTIONS.md`.
