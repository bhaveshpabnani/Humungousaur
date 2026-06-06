---
name: skill-provenance-review
description: Trace source, license, trust, scripts, permissions, and native-implementation status for skill packs before adapting them.
---

# Skill Provenance Review

## Purpose

Assess whether a skill can be safely adapted into Humungousaur. Provenance review protects against unsafe scripts, license confusion, and upstream runtime dependency.

## When To Use

Use before adapting community skills, adding scripts/assets, reviewing external repos, or deciding whether a skill belongs in the library.

## Inputs And Evidence

- Source URL/path, license, SKILL.md, scripts, package manifests, assets, and intended use.
- Native tool requirements and gaps.

## Tool Map

- `skill-security-review`
- `read_file`
- `search_workspace`
- `dependency-security-check`
- `agent-api-integration`

## Workflow

1. Identify source, version, and license.
2. Inspect skill text and optional files.
3. Review scripts/dependencies before any execution.
4. Decide whether to adapt, reject, or implement missing native tools.
5. Write Humungousaur-owned skill guidance.
6. Document source inspiration and boundaries.

## Native Implementation Boundaries

- Do not import upstream skill code as implementation.
- Adapt patterns into owned SKILL.md files.
- Missing tools must become native tools or explicit gaps.

## Safety And Approval

- Treat community skills as untrusted.
- Do not execute scripts without approval.
- Preserve license constraints.

## Verification

- Report provenance and risk classification.
- Confirm native-only implementation status.
- Validate final skill format.

## Failure Modes

- Copying unsafe scripts.
- Ignoring license.
- Hiding external runtime dependencies.

## References

- Shortlist item: `skill-provenance-review`.
