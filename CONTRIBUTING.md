# Contributing to Humungousaur

Humungousaur is a local-first agent runtime with governed tools, explicit schemas, approvals, audit logs, skills, memory, channels, and native desktop shells.

## Ground Rules

- Keep cognition model-led and schema-driven. Do not add keyword routing, regex intent maps, static natural-language dispatch, or hardcoded task decomposition.
- Every new capability must be a tool, adapter, or skill with an explicit contract, risk level, policy behavior, and verification path.
- High-risk actions must stay approval-gated and auditable.
- Treat external project code as reference material unless the license and integration plan explicitly allow reuse.
- Keep secrets out of git, logs, screenshots, fixtures, docs examples, and test output.

## Local Setup

```bash
python -m pip install -e ".[browser,pdf,ocr,office,test]"
playwright install chromium
python -m unittest discover -v
```

The PDF/browser tests skip when optional runtime dependencies are unavailable. Do not weaken tests to hide real failures.

## Desktop Apps

- Windows app changes should preserve the shared REST API contract and approval model.
- macOS app changes should use the same backend surfaces as Windows unless the capability is genuinely platform-specific.
- Desktop clients should hydrate runtime secrets from platform storage and avoid writing plaintext secrets to repo files.

## Pull Requests

Before opening a PR:

- Run the relevant unit tests and smoke scripts.
- Build any touched desktop app or website.
- Update docs when behavior, commands, setup, or public surfaces change.
- Include evidence for cross-platform behavior when touching tools, channels, approvals, runtime startup, or model/provider settings.
