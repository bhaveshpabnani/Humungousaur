---
name: pdf-operations
description: List, read, summarize, save browser PDFs, and plan richer PDF work using Humungousaur-native PDF, browser, file, and approved interpreter tools.
---

# PDF Operations

## Purpose

Handle PDF knowledge work with clear evidence. Humungousaur has native PDF listing, reading, summarization, merge, page extraction, live-browser PDF save, and OCR readiness checks.

## When To Use

Use for reading PDFs, summarizing document sets, extracting key points, saving browser pages as PDFs, or planning PDF creation/editing.

## Inputs And Evidence

- PDF path or directory, requested summary depth, page limits, extraction target, and output format.
- Browser session ID for saving pages as PDF.

## Tool Map

- `list_pdfs`
- `read_pdf`
- `summarize_pdfs`
- `pdf_merge`
- `pdf_extract_pages`
- `ocr_provider_status`
- `browser_live_save_pdf`
- `python_interpreter`
- `write_note`

## Workflow

1. Confirm the PDF path is inside allowed roots.
2. Use `read_pdf` for a specific PDF or `summarize_pdfs` for a folder.
3. Preserve page/source references where possible.
4. Use `pdf_merge` when the user wants a combined local PDF artifact.
5. Use `pdf_extract_pages` for split/extract page-range workflows.
6. Use `ocr_provider_status` before OCR claims; if OCR is not ready, report the exact local provider gap.
7. Use browser PDF save for live pages only after approval.
8. Save summaries or notes when requested.

## Native Implementation Boundaries

- Use Humungousaur PDF/browser tools.
- Do not import Anthropic PDF or external reference nano-pdf scripts directly.
- Add future fill/OCR extraction operations as native tools with tests before claiming support.

## Safety And Approval

- Do not read PDFs outside allowed roots.
- Avoid reproducing long copyrighted text.
- Treat scanned/OCR results as uncertain.

## Verification

- Report PDF path, page count/limits when available, and extraction errors.
- Generated PDFs require output path verification.
- Unsupported operations should be labeled clearly; OCR readiness is not the same as OCR extraction.

## Failure Modes

- Treating a scanned PDF as successfully read text.
- Missing extraction errors.
- Claiming fill or OCR extraction support when no native tool ran.

## References

- Shortlist item: `pdf-operations`.
