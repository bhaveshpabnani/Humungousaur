---
name: node-debugging
description: Debug Node.js applications using native shell, file, browser, and inspector-compatible workflows with evidence-backed reproduction and verification.
---

# Node Debugging

## Purpose

Diagnose Node.js and frontend/backend JavaScript problems with repository-native commands and browser evidence. Inspector or DevTools workflows are used only through configured native tools or approved shell commands.

## When To Use

Use for Node runtime errors, npm scripts, bundler issues, frontend bugs, server logs, inspector workflows, and browser/Node integration problems.

## Inputs And Evidence

- Error output, package scripts, lockfiles, source files, browser state, and reproduction steps.
- Node/npm versions and test/build commands.

## Tool Map

- `read_file`
- `search_workspace`
- `run_shell_command`
- `browser_live_open`
- `browser_live_observe`
- `systematic-debugging`

## Workflow

1. Inspect package scripts and runtime versions.
2. Reproduce with the smallest relevant command.
3. Trace stack frames to source and tests.
4. Use browser tools for UI-visible bugs.
5. Patch narrowly and run targeted verification.
6. Report version/tooling blockers explicitly.

## Native Implementation Boundaries

- Use repo commands through Humungousaur shell/browser tools.
- Do not import external reference node-inspector scripts.
- Do not install packages without user approval.

## Safety And Approval

- Network/package installs require approval.
- Do not kill or restart services without checking user impact.
- Avoid logging secrets from env or browser storage.

## Verification

- Test/build/dev-server output or browser observation should prove the result.
- If a server remains running, track and stop/report it as appropriate.
- Note local-only vs CI verification.

## Failure Modes

- Fixing minified/generated output instead of source.
- Ignoring lockfile/package-manager conventions.
- Treating browser symptoms as pure frontend without checking API responses.

## References

- Shortlist item: `node-debugging`.
- Upstream inspiration: external reference node debugging references only.
