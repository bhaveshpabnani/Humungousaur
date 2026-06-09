---
name: skill-authoring
description: Create, update, validate, and improve Humungousaur SKILL.md packs with complete descriptions, workflows, tool maps, scripts, references, safety, and verification. Use when adding or evolving agent skills.
---

# Skill Authoring

## Purpose

Author high-quality Humungousaur skills that follow the project standard and can be selected by model-led planning. This adapts Hermes skill authoring and Anthropic skill-creator guidance.

## When To Use

Use when creating new skills, improving existing skills, integrating upstream skill ideas, adding scripts/references, or validating the skill library.

## Inputs And Evidence

- `docs/AGENT_SKILL_AUTHORING_STANDARD.md`.
- Source skill text or catalog entries from trusted local references.
- Current tool catalog and capability surface.
- Existing skills to avoid duplication.
- User's requested domain and scope.

## Tool Map

- `agent_skill_catalog`
- `agent_skill_read`
- `agent_skill_script_catalog`
- `agent_skill_script_read`
- `agent_skill_script_run`
- `skill_forge_draft`
- `skill_forge_packs`
- `cognitive_skill_evolve`
- `read_file`
- `search_workspace`
- `run_shell_command`

## Workflow

1. Read the authoring standard before editing or generating skills.
2. Search existing skills for overlap and decide whether to update or create.
3. Use upstream material only as reference evidence; write Humungousaur-owned guidance.
4. Ensure every required tool, script, adapter, or helper is native to Humungousaur or already exposed through a trusted Humungousaur platform tool.
5. If upstream material implies a missing tool, record the gap or implement a Humungousaur-owned tool; do not depend on Hermes, OpenClaw, Anthropic Skills, ClawHub, or Codex plugin code directly.
6. Create valid frontmatter: lowercase hyphenated `name`, description under 1024 chars, optional compatibility/license/metadata.
7. Include purpose, when-to-use, evidence, tool map, workflow, safety, verification, failure modes, and references.
8. Add `scripts/`, `references/`, or `assets/` only when they improve execution or progressive disclosure and are Humungousaur-owned.
9. For each native script, add first-line metadata, enforce allowed root boundaries, accept the standard JSON envelope, emit bounded JSON output when possible, and list it under `Native Scripts`.
10. Run the workspace skill format and skill-tool tests.

## Safety

- Do not copy third-party code or instructions blindly.
- Do not import, execute, or rely on third-party skill implementation code as the native implementation of a Humungousaur skill.
- Do not include secrets, tokens, or private paths unless they are user-provided repo-local references.
- Do not create skills that implement brittle keyword routing.

## Native Implementation Boundaries

- Use `skill_forge_draft`, skill catalog/read/script tools, filesystem tools, and tests as the native authoring path.
- Upstream skills, OpenClaw extensions, Hermes tools, Codex plugin skills, and Anthropic skills are references only unless reimplemented as Humungousaur-owned tools/scripts.
- Scripts must be repo-local, schema-bounded, and safe under configured workspace roots before they are advertised as capability.

## Verification

- Run `tests/test_workspace_skill_format.py`.
- Run `tests/test_skill_tools.py` after adding scripts.
- Confirm `agent_skill_catalog` discovers the new skill.
- Confirm `agent_skill_script_catalog` discovers native scripts and `agent_skill_script_run` can run an approved smoke case.
- Check names match parent directories.

## Failure Modes

- Adding a short vague skill that cannot guide execution.
- Violating name/description/frontmatter constraints.
- Creating duplicate skills instead of improving a broader existing one.

## References

- Shortlist item: `skill-authoring`.
- Upstream inspiration: Hermes skill authoring, Anthropic `skill-creator`.
- Required standard: `docs/AGENT_SKILL_AUTHORING_STANDARD.md`.
