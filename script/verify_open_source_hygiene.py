#!/usr/bin/env python3
"""Check publish-candidate files for local state, signing material, and likely secrets."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEBSITE_ROOT = ROOT.parent / "Humungousaur-Website"
MAX_PUBLISH_CANDIDATE_BYTES = 2 * 1024 * 1024

FORBIDDEN_FILENAMES = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
}
FORBIDDEN_SUFFIXES = {
    ".pem",
    ".p12",
    ".pfx",
    ".key",
}
SKIP_TEXT_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".zip",
    ".sqlite3",
    ".db",
    ".pyc",
}

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private key block", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |)PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{30,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b")),
    ("OpenAI project key", re.compile(r"\bsk-proj-[A-Za-z0-9_-]{20,}\b")),
    ("OpenAI API key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("Slack bot token", re.compile(r"\bxoxb-[A-Za-z0-9-]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
]


def git_paths(root: Path, args: list[str]) -> set[Path]:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return {root / line for line in result.stdout.splitlines() if line.strip()}


def publish_candidates(root: Path) -> list[Path]:
    tracked = git_paths(root, ["ls-files"])
    untracked = git_paths(root, ["ls-files", "--others", "--exclude-standard"])
    return sorted(path for path in tracked | untracked if path.is_file())


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def check_path(path: Path, root: Path, errors: list[str]) -> None:
    name = path.name
    suffix = path.suffix.lower()
    relative = rel(path, root)
    if name != ".env.example" and (name in FORBIDDEN_FILENAMES or name.startswith(".env.")):
        errors.append(f"{relative}: local environment file is a publish candidate")
    if suffix in FORBIDDEN_SUFFIXES:
        errors.append(f"{relative}: signing/private key material is a publish candidate")
    if "/.codex/" in f"/{relative}/" or relative.startswith(".codex/"):
        errors.append(f"{relative}: generated Codex local state is a publish candidate")
    size = path.stat().st_size
    if size > MAX_PUBLISH_CANDIDATE_BYTES:
        max_mib = MAX_PUBLISH_CANDIDATE_BYTES / (1024 * 1024)
        actual_mib = size / (1024 * 1024)
        errors.append(f"{relative}: publish candidate is {actual_mib:.1f} MiB, above the {max_mib:.1f} MiB source-size limit")


def check_text(path: Path, root: Path, errors: list[str]) -> None:
    if path.suffix.lower() in SKIP_TEXT_SUFFIXES:
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    relative = rel(path, root)
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            errors.append(f"{relative}: likely {label}")


def check_root(root: Path, label: str) -> tuple[int, list[str]]:
    if not root.exists():
        return 0, [f"{label}: missing root {root}"]
    errors: list[str] = []
    candidates = publish_candidates(root)
    for path in candidates:
        check_path(path, root, errors)
        check_text(path, root, errors)
    return len(candidates), errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--website-root", type=Path, default=DEFAULT_WEBSITE_ROOT)
    parser.add_argument("--skip-website", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    roots = [("agent", ROOT)]
    if not args.skip_website:
        roots.append(("website", args.website_root.resolve()))

    total = 0
    errors: list[str] = []
    for label, root in roots:
        count, root_errors = check_root(root, label)
        total += count
        errors.extend(f"{label}: {error}" for error in root_errors)

    if errors:
        for error in errors:
            print(f"FAIL {error}")
        print(f"\nOpen-source hygiene: scanned {total} publish candidates, {len(errors)} failures")
        return 1

    print(f"Open-source hygiene: scanned {total} publish candidates, 0 failures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
