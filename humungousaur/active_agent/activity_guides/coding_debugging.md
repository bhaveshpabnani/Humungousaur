# Activity Skill Pack: Coding And Debugging

## Summary

Use when the user is implementing, reviewing, running, testing, debugging, or
validating software. Optimize for failure continuity, safe evidence, and
non-disruptive next-step support.

## Signals

- IDE/editor saves, diagnostics, searches, refactors, debugger state, or focused
  source navigation.
- Terminal, build, package-manager, test, lint, deployment, or runtime events.
- Repeated fail/fix/run loops or the same error category appearing across tools.
- Git branch, diff, conflict, commit, pull request, issue, or CI activity.

## Helpful Moments

- A command, test, build, or check fails repeatedly.
- The user returns to a dirty tree, paused debugging session, or unresolved PR.
- Validation passes and a concise summary or handoff may help.
- The user explicitly asks for analysis, implementation, review, or next steps.

## Stay Silent When

- File changes are background watcher noise or generated output without user
  intent.
- Assistance would require reading source, logs, stack traces, secrets, tokens,
  proprietary data, or cloud-console details without approval.
- The user is typing or stepping through code without a natural pause.
- The event concerns credentials, keys, billing, or restricted infrastructure.

## Deep Dive Triggers

- Inspecting source files, diffs, logs, stack traces, test output, CI output, or
  dependency metadata.
- Running commands, editing code, creating commits, or opening PR/release actions.
- Reading linked issues, design docs, incidents, or private repository context.

## Memory Guidance

- Store repo/project hashes, branch or issue hashes, safe failure category,
  command class, validation outcome, blocked/fixed state, and user-declared goal.
- Keep short safe summaries of attempted fixes and last known verification.
- Do not retain code snippets, secrets, full paths with sensitive names, logs, or
  stack traces without approval.

## Privacy Notes

- Treat code, logs, environment variables, and repository metadata as sensitive.
- Ask before inspecting or acting on source-controlled content.
- Prefer summaries of categories and outcomes over raw technical content.
