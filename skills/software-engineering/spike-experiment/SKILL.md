---
name: spike-experiment
description: Run bounded throwaway experiments to reduce uncertainty before implementation, then preserve only conclusions and intentional code.
---

# Spike Experiment

## Purpose

Use small experiments to answer uncertain technical questions without letting exploratory code leak into production. A spike is evidence gathering, not the final architecture.

## When To Use

Use for unfamiliar APIs, performance questions, parsing approaches, provider behavior, browser/OS feasibility, and risky design choices.

## Inputs And Evidence

- Question to answer, time/step budget, success criteria, and allowed workspace.
- Experiment code/output, artifacts, and conclusion.

## Tool Map

- `python_interpreter`
- `run_shell_command`
- `read_file`
- `write_note`
- `browser_live_open`
- `tool_search`

## Workflow

1. State the narrow question and stop condition.
2. Choose a safe sandbox/profile.
3. Run the smallest experiment that can answer the question.
4. Record results, surprises, and limitations.
5. Discard throwaway code unless the user asks to keep it.
6. Convert the learning into a production plan or scoped patch.

## Native Implementation Boundaries

- Use Humungousaur interpreter/shell/browser tools.
- Do not import external reference spike scripts.
- Do not call external services unless explicitly approved and necessary.

## Safety And Approval

- Experiments that execute code or contact networks require the relevant approval.
- Keep writes inside approved workspace/data directories.
- Avoid using secrets in exploratory code.

## Verification

- A spike must answer the stated question or explain why it did not.
- Preserve output or notes when useful.
- Do not claim production readiness from a spike alone.

## Failure Modes

- Letting spike code become unreviewed production code.
- Running an unbounded experiment.
- Optimizing for interesting results instead of the user's decision.

## References

- Shortlist item: `spike-experiment`.
- Upstream inspiration: external reference spike reference only.
