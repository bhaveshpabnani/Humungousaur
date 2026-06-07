---
name: dependency-security-check
description: Review package installs, dependency changes, scripts, manifests, and supply-chain risk before execution or integration.
---

# Dependency Security Check

## Purpose

Reduce supply-chain risk when adding or running dependencies. This skill reviews manifests, install commands, package scripts, and trust signals.

## When To Use

Use before installing packages, running unfamiliar scripts, adding plugins, updating lockfiles, or executing community skill code.

## Inputs And Evidence

- Package names, manifest diffs, lockfiles, scripts, source repo, version, and requested command.
- Known vulnerability or audit output when available.

## Tool Map

- `dependency_inventory_create`
- `secret_scan_report_create`
- `approval_policy_review_create`
- `security_review_inspect`
- `read_file`
- `search_workspace`
- `run_shell_command`
- `skill-security-review`
- `secrets-handling`

## Workflow

1. Inspect package manifest and scripts.
2. Use `dependency_inventory_create` to preserve package, script, trust, and risk evidence.
3. Use `secret_scan_report_create` on explicitly provided manifest/config snippets or files when secret leakage risk exists.
4. Use `approval_policy_review_create` before install, script execution, or package-manager network actions.
5. Use `security_review_inspect` before reporting findings.
6. Prefer existing dependencies and native implementations.
7. Request approval before install/network actions.
8. Verify lockfile and test impact.

## Native Implementation Boundaries

- Do not import OpenClaw audit/Snyk skill code.
- External scanners require native wrapper or approved shell path.
- Do not execute package scripts just to inspect them.
- Native security artifacts are local review documents and do not install packages or run scanners.

## Safety And Approval

- Installs can run code and require approval.
- Avoid packages with unclear provenance for core agent tools.
- Do not leak tokens into package manager configs.

## Verification

- Cite manifest/script evidence.
- Inspect native security artifacts for risk findings and action counts.
- Report audit/scanner output if run.
- Confirm no unexpected files changed.

## Failure Modes

- Blind `npm install`.
- Ignoring postinstall scripts.
- Adding dependency for trivial functionality.

## References

- Shortlist item: `dependency-security-check`.
