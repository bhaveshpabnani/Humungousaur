---
name: research-paper-search
description: Search, collect, and summarize research-paper evidence from web or provided sources, with citation discipline and current-source verification.
---

# Research Paper Search

## Purpose

Help build literature sets and understand papers from evidence. Current search uses native web/research tools unless a dedicated scholarly API adapter is implemented.

## When To Use

Use for arXiv-style searches, paper lists, related work, literature reviews, methods comparison, and reading provided paper links/PDFs.

## Inputs And Evidence

- Topic, constraints, date range, venues, authors, links, PDFs, and output format.
- Source URLs, titles, abstracts, and citation metadata.

## Tool Map

- `research_webpages`
- `fetch_webpage`
- `rss_feed_read`
- `read_pdf`
- `summarize_pdfs`
- `literature_set_create`
- `literature_set_inspect`
- `citation_bibliography_create`
- `web-data-extraction`
- `write_note`

## Workflow

1. Define search question and inclusion criteria.
2. Use current web evidence for changing paper lists.
3. Extract title, authors, venue/date, abstract, link, source references, evidence level, and relevance.
4. Read/summarize PDFs when provided and accessible.
5. Use `literature_set_create` to preserve papers, themes, gaps, limitations, and source references as an inspectable artifact.
6. Use `literature_set_inspect` and optionally `citation_bibliography_create` before reporting or drafting a literature note.

## Native Implementation Boundaries

- Do not import external reference arXiv or external reference academic plugins.
- Add scholarly API adapters natively when needed.
- Avoid fabricating citations.
- Literature-set artifacts are local evidence organization, not proof of live scholarly search by themselves.

## Safety And Approval

- Respect copyright and do not reproduce long paper text.
- Distinguish abstract-level review from full-paper reading.
- Mark uncertain metadata.

## Verification

- Cite source URLs and dates where possible.
- Confirm PDF extraction succeeded before summarizing details.
- Inspect literature-set artifacts for paper/theme/gap counts.
- Note search limitations.

## Failure Modes

- Hallucinating paper titles.
- Missing recent work due to stale knowledge.
- Overstating findings from abstracts alone.

## References

- Shortlist item: `research-paper-search`.
