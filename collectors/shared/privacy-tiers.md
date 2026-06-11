# Collector Privacy Tiers

- `metadata`: safe local metadata such as app names, event kinds, coarse states,
  and redacted paths.
- `sensitive_metadata`: metadata that can reveal private context and must require
  explicit collector enablement or rich-capture opt-in before Humungousaur accepts
  it.
- `rich_capture`: screenshots, OCR, transcript text, clipboard values, document
  contents, or similar high-risk payloads. These should be avoided unless the user
  explicitly opts in.
- `blocked`: platform collector observed a signal but intentionally suppressed the
  payload. Blocked observations may be useful for health/status but must not enter
  attention batches.

Platform collectors should redact before writing. Humungousaur will still run its
own privacy policy, dwell, dedupe, rate limit, and attention compaction gates.
