#!/usr/bin/env python3
"""Validate the generated release-readiness Markdown report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "artifacts/release/release-readiness.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--skip-website", action="store_true")
    parser.add_argument("--require-website", action="store_true")
    parser.add_argument("--require-assets", action="store_true")
    parser.add_argument("--check-github-release", action="store_true")
    parser.add_argument("--require-pass-status", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = args.report.resolve()
    errors: list[str] = []

    if not report.is_file():
        errors.append(f"missing release readiness report: {report}")
    else:
        text = report.read_text(encoding="utf-8", errors="replace")
        required = [
            "# Humungousaur Release Readiness",
            "## Artifact Manifest",
            "## Backend Regression",
            "## Open-Source Hygiene",
            "## Desktop Parity",
            "## Desktop Runtime Smoke",
            "## Release Preflight",
            "python -m unittest discover -v",
            "verify_open_source_hygiene.py",
            "verify_desktop_parity.py",
            "verify_desktop_runtime_smoke.py",
            "verify_release_readiness.py",
        ]
        if args.require_assets:
            required.extend(
                [
                    "Humungousaur-Windows.zip",
                    "Humungousaur-macOS.zip",
                    "Humungousaur-Windows-Setup.exe",
                    "Humungousaur-macOS.pkg",
                    "checksums.txt",
                    "sha256",
                    "--require-assets",
                ]
            )
        if not args.skip_website or args.require_website:
            required.extend(
                [
                    "## Website Lint",
                    "## Website Download Source Check",
                    "## Website Release Asset Self-Test",
                    "## Website Build",
                    "## Website Audit",
                    "npm run lint",
                    "npm run check:downloads",
                    "npm run check:release-assets:selftest",
                    "npm run build",
                    "npm audit --audit-level=moderate",
                ]
            )
        if args.check_github_release and not args.skip_website:
            required.extend(["## Website Live Release Asset Check", "npm run check:release-assets"])
        missing = [needle for needle in required if needle not in text]
        if missing:
            errors.append(f"release readiness report is missing required evidence {missing}")
        if args.require_pass_status and "- Status: `FAIL`" in text:
            errors.append("release readiness report contains a failing check section")
        if "```text" not in text:
            errors.append("release readiness report does not include captured command output blocks")

    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print(f"Verified {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
