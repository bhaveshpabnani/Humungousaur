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
- `read_pdf`
- `summarize_pdfs`
- `web-data-extraction`
- `write_note`

## Workflow

1. Define search question and inclusion criteria.
2. Use current web evidence for changing paper lists.
3. Extract title, authors, venue/date, abstract, link, and relevance.
4. Read/summarize PDFs when provided and accessible.
5. Group papers by theme/method and note gaps.
6. Save a literature note when requested.

## Native Implementation Boundaries

- Do not import Hermes arXiv or OpenClaw academic plugins.
- Add scholarly API adapters natively when needed.
- Avoid fabricating citations.

## Safety And Approval

- Respect copyright and do not reproduce long paper text.
- Distinguish abstract-level review from full-paper reading.
- Mark uncertain metadata.

## Verification

- Cite source URLs and dates where possible.
- Confirm PDF extraction succeeded before summarizing details.
- Note search limitations.

## Failure Modes

- Hallucinating paper titles.
- Missing recent work due to stale knowledge.
- Overstating findings from abstracts alone.

## References

- Shortlist item: `research-paper-search`.
