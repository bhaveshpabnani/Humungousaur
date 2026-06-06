---
name: ocr-document-extraction
description: Extract text or tables from scanned documents only through native OCR-capable tools or approved implementation plans, with uncertainty and privacy controls.
---

# OCR Document Extraction

## Purpose

Handle scanned documents carefully. OCR is error-prone and sensitive, so the assistant must use native OCR support when available or clearly report the implementation gap.

## When To Use

Use for scans, images of documents, receipts, screenshots, forms, and PDFs where normal text extraction fails.

## Inputs And Evidence

- Image/PDF path, target fields, language, table requirements, and confidence needs.
- Existing extraction errors or screenshot metadata.

## Tool Map

- `read_pdf`
- `screenshot_capture`
- `screen_captures`
- `python_interpreter`
- `tool_search`
- `write_note`

## Workflow

1. Try native text extraction when the input is a PDF.
2. Check for native OCR capability before claiming OCR.
3. If OCR is missing, describe the adapter/tool needed or use approved interpreter packages if available.
4. Extract fields with confidence/uncertainty labels.
5. Preserve source page/image references.
6. Verify critical numbers manually where possible.

## Native Implementation Boundaries

- Do not import Hermes OCR or upstream document scripts directly.
- OCR adapters must be Humungousaur-owned and tested.
- Upstream OCR workflows are reference only.

## Safety And Approval

- Documents may include IDs, financials, or private data.
- Do not send images to cloud OCR without explicit user approval.
- Avoid storing sensitive extractions as memory unless requested.

## Verification

- Distinguish native text extraction from OCR.
- Report confidence and uncertain fields.
- Confirm output notes/artifacts.

## Failure Modes

- Treating OCR output as exact.
- Missing table structure.
- Claiming OCR ran when only PDF text extraction ran.

## References

- Shortlist item: `ocr-document-extraction`.
