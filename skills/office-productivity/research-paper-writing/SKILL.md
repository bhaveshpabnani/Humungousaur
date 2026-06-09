---
name: research-paper-writing
description: Structure, draft, revise, and check research papers using evidence, citations, experiment records, and clear contribution claims.
---

# Research Paper Writing

## Purpose

Help write research papers with a disciplined structure: problem, related work, method, experiments, results, limitations, and contribution claims grounded in evidence.

## When To Use

Use for ML/research papers, abstracts, related-work sections, experiment narratives, rebuttals, and submission polishing.

## Inputs And Evidence

- Research question, method, results, tables, figures, citations, venue style, and draft text.
- Experiment logs or source documents.

## Tool Map

- `read_file`
- `search_workspace`
- `research-paper-search`
- `doc-coauthoring`
- `citation-and-bib-cleanup`
- `literature_set_create`
- `literature_set_inspect`
- `citation_bibliography_inspect`
- `write_note`

## Workflow

1. Clarify contribution and target venue.
2. Build outline before prose.
3. Separate claims from evidence and speculation.
4. Integrate citations with accurate positioning and inspect bibliography/literature artifacts when available.
5. Draft sections and revise for clarity, limitations, and reproducibility.
6. Check consistency across abstract, method, results, conclusion, citations, and evidence artifacts.

## Native Implementation Boundaries

- Use Humungousaur writing/search/file tools.
- Do not import external reference research-paper-writing scripts.
- Do not invent experiments or citations.
- Treat `literature_set_create` and `citation_bibliography_create` outputs as evidence artifacts, not as permission to fabricate missing results.

## Safety And Approval

- Avoid plagiarism and unsupported claims.
- Preserve limitations and negative results.
- Do not submit externally without approval.

## Verification

- Contribution claims should map to evidence.
- Citations should be backed by sources.
- Results should match tables/logs.
- Literature and bibliography artifacts should inspect successfully before final paper claims rely on them.

## Failure Modes

- Overclaiming novelty.
- Writing generic related work.
- Misaligning abstract and actual results.

## References

- Shortlist item: `research-paper-writing`.
