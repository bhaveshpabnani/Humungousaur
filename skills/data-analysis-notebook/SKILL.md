---
name: data-analysis-notebook
description: Run bounded local data analysis through Humungousaur's approval-gated Python interpreter, saved artifacts, and reproducible notes.
---

# Data Analysis Notebook

## Purpose

Use the native Python interpreter as a notebook-like analysis environment. The goal is reproducible, bounded analysis with artifacts and clear assumptions.

## When To Use

Use for data exploration, CSV/JSON analysis, calculations, simulations, small plots, file parsing, and technical experiments.

## Inputs And Evidence

- Data path, question, allowed imports, output artifacts, and success criteria.
- Interpreter run IDs, manifests, stdout/stderr, and artifacts.

## Tool Map

- `python_interpreter`
- `python_interpreter_runs`
- `python_interpreter_run`
- `python_interpreter_artifact`
- `read_file`
- `write_note`

## Workflow

1. Define the analysis question and data boundaries.
2. Choose the least-privilege interpreter sandbox/import mode.
3. Run small, readable analysis code.
4. Inspect stdout, errors, and artifacts.
5. Iterate only as needed.
6. Summarize methods, results, assumptions, and reproducibility.

## Native Implementation Boundaries

- Use Humungousaur `python_interpreter` tools.
- Do not import Hermes Jupyter live-kernel code.
- Notebook/live-kernel support beyond this requires native implementation.

## Safety And Approval

- Interpreter execution is approval-gated.
- Keep network/subprocess/import permissions minimal.
- Do not expose sensitive data in outputs.

## Verification

- Report run IDs and artifacts.
- Validate calculations with sanity checks.
- Note if packages were unavailable.

## Failure Modes

- Running code without a clear question.
- Trusting a single output without sanity checks.
- Losing reproducibility.

## References

- Shortlist item: `data-analysis-notebook`.
