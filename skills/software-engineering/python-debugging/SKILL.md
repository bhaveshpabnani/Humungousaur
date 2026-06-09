---
name: python-debugging
description: Debug Python code with native tests, py_compile, bounded python_interpreter analysis, pdb/debugpy planning, and evidence-backed fixes.
---

# Python Debugging

## Purpose

Diagnose Python failures through tests, stack traces, imports, environment, and small safe experiments. Use `python_interpreter` for bounded analysis when useful.

## When To Use

Use for pytest failures, import errors, scripts, API bugs, data processing issues, virtualenv confusion, and Python runtime behavior questions.

## Inputs And Evidence

- Traceback, failing command, source files, tests, pyproject/requirements, interpreter path, and environment.
- Interpreter run manifests and artifacts when used.

## Tool Map

- `read_file`
- `search_workspace`
- `run_shell_command`
- `python_interpreter`
- `python_interpreter_runs`
- `python_interpreter_run`
- `systematic-debugging`

## Workflow

1. Identify interpreter and environment.
2. Reproduce the failure or inspect current traceback.
3. Trace through source, imports, and tests.
4. Use `python_interpreter` for isolated analysis when approved.
5. Patch the root cause.
6. Run targeted tests, py_compile, or broader suites as risk requires.

## Native Implementation Boundaries

- Use Humungousaur Python interpreter and native shell tools.
- Do not import external reference debugpy scripts as implementation.
- Do not execute untrusted Python without sandbox/profile awareness.

## Safety And Approval

- `python_interpreter` is approval-gated.
- Keep network/subprocess/import permissions minimal.
- Do not leak env secrets in trace/log summaries.

## Verification

- Show exact command outcomes.
- Inspect interpreter artifacts only through native artifact tools.
- State if local Python shim or virtualenv issues block a check.

## Failure Modes

- Running tests with the wrong interpreter.
- Fixing import paths in a way that masks packaging problems.
- Over-broad exception swallowing.

## References

- Shortlist item: `python-debugging`.
- Native tools: Humungousaur Python interpreter and shell tools.
