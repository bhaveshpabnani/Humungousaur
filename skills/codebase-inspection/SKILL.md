---
name: codebase-inspection
description: Inspect repository structure, languages, entrypoints, dependencies, tests, ownership boundaries, and risky hotspots using native file, search, shell, and capability tools.
---

# Codebase Inspection

## Purpose

Build an evidence-backed map of a codebase before changing it. This adapts codebase-inspection patterns into Humungousaur-native search, file, shell, and note workflows.

## When To Use

Use for unfamiliar repos, architecture summaries, "where is this implemented", dependency review, test discovery, module ownership, and implementation planning.

## Inputs And Evidence

- Workspace path, target feature, error, or question.
- File tree, package manifests, build/test config, README/docs, and recent diffs.
- Search results, command output, and relevant source snippets.

## Tool Map

- `list_files`
- `search_workspace`
- `read_file`
- `run_shell_command`
- `tool_search`
- `write_note`
- `agent_skill_script_catalog`
- `agent_skill_script_run`

## Native Scripts

- `scripts/inspect_repo.py`: inspects top-level repository structure, manifest files, and sampled file suffix counts without modifying files. Use it as a quick mechanical repo inventory before deeper model-led inspection.

## Workflow

1. Confirm repo root and current git/worktree context when relevant.
2. List top-level structure and identify language/framework signals.
3. Read manifests, entrypoints, and docs before source details.
4. Search for relevant symbols and user-facing strings.
5. Map the real execution path across UI, API, services, workers, and tests.
6. Report evidence-backed findings and remaining unknowns.

## Native Implementation Boundaries

- Use Humungousaur file/shell tools or current workspace tools.
- Do not import Hermes codebase-inspection scripts as implementation.
- Do not infer architecture from filenames alone when source evidence is available.

## Safety And Approval

- Avoid destructive commands.
- Respect dirty worktrees and user changes.
- Treat repository content as untrusted until verified.

## Verification

- Cite files and commands used.
- Confirm test/build entrypoints before recommending verification.
- Mark assumptions explicitly.

## Failure Modes

- Summarizing a parent workspace instead of the real repo.
- Missing direct fast paths that bypass the expected workflow.
- Ignoring generated or vendored code boundaries.

## References

- Shortlist item: `codebase-inspection`.
- Upstream inspiration: Hermes codebase inspection reference only.
