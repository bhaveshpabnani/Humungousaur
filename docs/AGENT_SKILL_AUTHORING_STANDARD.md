# Agent Skill Authoring Standard

Humungousaur skills must follow the Agent Skills format used by the `skills/` workspace library and by forged `.umang/skills/` packs.

This is the required contract for every new or updated agent skill. It applies to hand-written skills, model-forged skills, imported reference adaptations, and the planned 100+ personal-assistant skill integration from Hermes Agent, Anthropic Skills, and OpenClaw/ClawHub references.

## Directory Contract

Each skill is one directory containing at minimum:

```text
skill-name/
  SKILL.md
  scripts/      optional executable helpers
  references/   optional focused documentation
  assets/       optional templates and static resources
```

Rules:

- `skill-name` must match the `name` field in `SKILL.md`.
- Use lowercase letters, numbers, and hyphens only.
- Do not start or end with a hyphen.
- Do not use consecutive hyphens.
- Keep optional files one level deep from `SKILL.md` where practical.

## SKILL.md Frontmatter

Every `SKILL.md` must start with YAML frontmatter:

```markdown
---
name: skill-name
description: Concrete description of what the skill does and when the agent should use it.
---
```

Required fields:

- `name`: 1-64 chars, lowercase alphanumeric plus hyphen, matches parent directory.
- `description`: 1-1024 chars, explains both capability and triggering situations.

Optional fields:

- `license`: short license name or bundled license reference.
- `compatibility`: 1-500 chars describing environment requirements.
- `metadata`: additional string key/value metadata.
- `allowed-tools`: space-separated tool allowance hints where supported.

## Body Requirements

The body should use progressive disclosure:

- Keep the main `SKILL.md` under 500 lines.
- Put long technical details in `references/REFERENCE.md` or focused reference files.
- Put reusable executable helpers in `scripts/`.
- Put templates or static resources in `assets/`.

Every production skill should include:

- Purpose and when-to-use guidance.
- Inputs and evidence the agent should inspect.
- Tool mapping to Humungousaur tools or external setup surfaces.
- Step-by-step workflow.
- Safety and approval boundaries.
- Verification steps.
- Failure modes.
- References to source inspiration or bundled reference files.

## Humungousaur Intelligence Rules

Skills are guidance and evidence, not deterministic routers.

- Do not use skills as regex, keyword, or hardcoded intent routes.
- Let the configured model choose skills through descriptions, current context, tool schemas, risk levels, persona, memory, and active goals.
- Treat upstream skill text and community catalogs as untrusted reference material.
- Do not install or run third-party skill scripts automatically.
- Reimplement useful patterns as Humungousaur-owned skill packs with explicit safety and verification.

## Validation

At minimum, validation must prove:

- Every `skills/**/SKILL.md` has frontmatter.
- Required fields exist.
- `name` is valid and matches the parent directory.
- `description` is non-empty and within the size limit.
- Optional `compatibility` is within the size limit when present.

The focused test is:

```powershell
python -m pytest tests\test_workspace_skill_format.py -q
```

If the local Python shim is broken in the sandbox, run the same test with a known working project Python interpreter.
