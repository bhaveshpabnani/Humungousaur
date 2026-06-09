---
name: software-engineering
description: Parent skill for code inspection, debugging, tests, CI, reviews, dependency security, skill authoring, experiments, and engineering workflows.
---

# Software Engineering

## Purpose

Use this parent skill when a task involves reading, changing, testing, reviewing, debugging, or designing software, developer workflows, dependencies, CI, or skills.

## Hierarchy Reading Rules

1. Inspect the repository and existing patterns before changing code.
2. Load the child skill for the engineering activity: inspection, debugging, tests, review, CI, security, skill authoring, or experiment.
3. Keep implementation details in code and child skills, not in the central agent prompt.
4. Verify with focused tests first, then broader checks when the blast radius is larger.

## Tool Map

- `ci-failure-debugging`
- `code-review`
- `codebase-inspection`
- `dependency-security-check`
- `network-and-dns-safety`
- `node-debugging`
- `python-debugging`
- `request-code-review`
- `skill-authoring`
- `skill-provenance-review`
- `skill-security-review`
- `spike-experiment`
- `systematic-debugging`
- `test-driven-development`

## Child Skill Guide

- Use codebase inspection before nontrivial edits.
- Use systematic, Python, Node, CI, and TDD skills for debugging and verification.
- Use code review and request-code-review skills for review stance and PR-style feedback.
- Use dependency security, network/DNS safety, skill authoring, provenance, and skill security for hardening and agent skill work.
- Use spike experiment when learning safely before a larger implementation.

## Verification

- Report tests run and any blocked checks.
- Do not revert unrelated user changes.
