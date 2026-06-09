---
name: citation-and-bib-cleanup
description: Clean citations, bibliography entries, paper metadata, and reference lists using source verification and clear uncertainty labels.
---

# Citation And Bib Cleanup

## Purpose

Improve citations and bibliographies without inventing metadata. This skill checks titles, authors, venues, years, URLs, and BibTeX-like fields from evidence.

## When To Use

Use for BibTeX cleanup, citation lists, related-work references, DOI/arXiv metadata checks, and bibliography formatting.

## Inputs And Evidence

- Existing citation entries, paper links, PDFs, DOIs, arXiv IDs, and target style.
- Source metadata from web/PDF evidence.

## Tool Map

- `research_webpages`
- `fetch_webpage`
- `read_pdf`
- `research-paper-search`
- `citation_bibliography_create`
- `citation_bibliography_inspect`
- `write_note`

## Workflow

1. Parse existing entries and identify missing fields.
2. Verify metadata from source pages or PDFs.
3. Normalize authors, titles, venues, dates, URLs, identifiers, source references, and uncertainty labels in structured fields.
4. Use `citation_bibliography_create` to produce Markdown, JSON metadata, and BibTeX artifacts from explicit evidence.
5. Use `citation_bibliography_inspect` to verify entry counts, uncertainty counts, and preview text before responding.
6. Do not fabricate unavailable metadata.

## Native Implementation Boundaries

- Use Humungousaur web/PDF/search tools.
- Do not import external reference abstract searcher or citation scripts.
- Dedicated DOI/arXiv adapters must be native.
- Bibliography creation is artifact-only; it does not claim live DOI/arXiv verification unless source evidence is provided.

## Safety And Approval

- Avoid plagiarism and fake citations.
- Respect source access limits.
- Do not over-normalize names without evidence.

## Verification

- Each cleaned entry should have source evidence.
- Unverified fields should be marked.
- Inspect the bibliography artifact and BibTeX sidecar.
- Formatting should match requested style.

## Failure Modes

- Hallucinating DOI/venue.
- Changing title casing incorrectly for proper nouns.
- Losing URLs or access dates.

## References

- Shortlist item: `citation-and-bib-cleanup`.
