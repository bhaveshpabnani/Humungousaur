# Open-Source Release Notes

Use this note when preparing the repository for public visibility.

## Public Readiness Checklist

- Root README explains real user capabilities before internals.
- `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md`, `CODE_OF_CONDUCT.md`, `GOVERNANCE.md`, `AGENTS.md`, and GitHub issue/PR templates are present.
- `.env.example` contains placeholders only.
- `python3 script/verify_open_source_hygiene.py` passes.
- `python3 script/verify_release_readiness.py --require-website --release-tag v0.1.0` passes for source readiness.
- Any remaining release blockers are named directly in `CHANGELOG.md`, release notes, or final maintainer status.

## Public Claim Rule

Only claim a capability as end-to-end when it has current evidence from code, tests, smoke scripts, desktop verification, credentialed live validation, or release artifacts. Otherwise call it prepared, local-only, source-ready, or pending live validation.
