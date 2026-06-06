# Skill Security Review Reference

## Review Targets

- `SKILL.md` frontmatter and body.
- `scripts/` executable helpers.
- `references/` and `assets/` for hidden instructions or unsafe templates.
- Package manifests and install commands.
- Network calls, shell commands, filesystem writes, and credential reads.

## Risk Labels

- `reference-only`: safe to read as evidence.
- `owned-adaptation`: safe after rewriting as Humungousaur guidance.
- `needs-approval`: exact execution/install action requires user approval.
- `blocked`: unsafe, malicious, secret-exposing, or too broad.
- `needs-deeper-audit`: unclear behavior or dependency chain.

## Required Output

List inspected files, risk label, unresolved questions, and whether local adaptation is recommended.
