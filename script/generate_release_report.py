#!/usr/bin/env python3
"""Generate a Markdown release readiness report from local verification gates."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEBSITE_ROOT = ROOT.parent / "Humungousaur-Website"
DEFAULT_OUTPUT = ROOT / "artifacts/release/release-readiness.md"
ASSET_NAMES = [
    "Humungousaur-Windows-Setup.exe",
    "Humungousaur-macOS.pkg",
    "Humungousaur-Windows.zip",
    "Humungousaur-macOS.zip",
    "checksums.txt",
]


def run_command(args: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> tuple[int, str]:
    command_env = os.environ.copy()
    if env:
        command_env.update(env)
    result = subprocess.run(args, cwd=cwd, env=command_env, text=True, capture_output=True, check=False)
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_section(release_dir: Path) -> str:
    lines = ["## Artifact Manifest", ""]
    for name in ASSET_NAMES:
        path = release_dir / name
        if not path.exists():
            lines.append(f"- `{name}`: missing")
            continue
        size = path.stat().st_size
        if path.suffix in {".zip", ".pkg"}:
            lines.append(f"- `{name}`: {size} bytes, sha256 `{sha256(path)}`")
        if path.suffix == ".zip":
            try:
                with zipfile.ZipFile(path) as archive:
                    entries = archive.namelist()
            except zipfile.BadZipFile:
                lines.append("  - invalid zip")
                continue
            for entry in entries:
                lines.append(f"  - `{entry}`")
        else:
            lines.append(f"- `{name}`: {size} bytes")
            preview = path.read_text(encoding="utf-8", errors="replace").strip()
            if preview:
                lines.append("")
                lines.append("```text")
                lines.append(preview)
                lines.append("```")
    return "\n".join(lines)


def check_section(title: str, command: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> tuple[bool, str]:
    code, output = run_command(command, cwd=cwd, env=env)
    ok = code == 0
    status = "PASS" if ok else "FAIL"
    command_text = " ".join(command)
    if env:
        env_prefix = " ".join(f"{key}={value}" for key, value in sorted(env.items()))
        command_text = f"{env_prefix} {command_text}"
    body = [
        f"## {title}",
        "",
        f"- Status: `{status}`",
        f"- Command: `{command_text}`",
        f"- Working directory: `{cwd}`",
        "",
        "```text",
        output or "(no output)",
        "```",
    ]
    return ok, "\n".join(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--release-dir", type=Path, default=ROOT / "artifacts/release")
    parser.add_argument("--website-root", type=Path, default=DEFAULT_WEBSITE_ROOT)
    parser.add_argument("--skip-website", action="store_true")
    parser.add_argument("--require-website", action="store_true")
    parser.add_argument("--require-assets", action="store_true")
    parser.add_argument("--check-github-release", action="store_true")
    parser.add_argument("--require-github-release", action="store_true")
    parser.add_argument("--github-release-tag")
    parser.add_argument("--release-tag")
    parser.add_argument("--fail-on-check-failure", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    release_dir = args.release_dir.resolve()
    website_root = args.website_root.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = [
        "# Humungousaur Release Readiness",
        "",
        f"- Generated: `{datetime.now(timezone.utc).isoformat()}`",
        f"- Repository root: `{ROOT}`",
        f"- Git ref: `{os.environ.get('GITHUB_REF', 'local')}`",
        f"- Git SHA: `{os.environ.get('GITHUB_SHA', 'local')}`",
        "",
        artifact_section(release_dir),
    ]

    hygiene_command = [sys.executable, "script/verify_open_source_hygiene.py"]
    if args.skip_website:
        hygiene_command.append("--skip-website")

    checks: list[tuple[str, list[str], Path, dict[str, str] | None]] = [
        ("Backend Regression", [sys.executable, "-m", "unittest", "discover", "-v"], ROOT, None),
        ("Open-Source Hygiene", hygiene_command, ROOT, None),
        ("Desktop Parity", [sys.executable, "script/verify_desktop_parity.py"], ROOT, None),
        ("Desktop Runtime Smoke", [sys.executable, "script/verify_desktop_runtime_smoke.py"], ROOT, None),
    ]
    if not args.skip_website:
        if website_root.exists():
            checks.extend(
                [
                    ("Website Lint", ["npm", "run", "lint"], website_root, None),
                    ("Website Download Source Check", ["npm", "run", "check:downloads"], website_root, None),
                    ("Website Release Asset Self-Test", ["npm", "run", "check:release-assets:selftest"], website_root, None),
                    ("Website Build", ["npm", "run", "build"], website_root, None),
                    ("Website Audit", ["npm", "audit", "--audit-level=moderate"], website_root, None),
                ]
            )
            if args.check_github_release or args.require_github_release:
                release_tag = args.github_release_tag or args.release_tag
                env = {"HUMUNGOUSAUR_RELEASE_TAG": release_tag} if release_tag else None
                checks.append(("Website Live Release Asset Check", ["npm", "run", "check:release-assets"], website_root, env))
        elif args.require_website:
            checks.append(("Website Repository", ["test", "-d", str(website_root)], ROOT, None))
    release_command = [sys.executable, "script/verify_release_readiness.py"]
    if args.skip_website:
        release_command.append("--skip-website")
    if args.require_website:
        release_command.append("--require-website")
    if args.require_assets:
        release_command.append("--require-assets")
    release_command.extend(["--release-dir", str(release_dir)])
    if args.check_github_release:
        release_command.append("--check-github-release")
    if args.require_github_release:
        release_command.append("--require-github-release")
    if args.github_release_tag:
        release_command.extend(["--github-release-tag", args.github_release_tag])
    if args.release_tag:
        release_command.extend(["--release-tag", args.release_tag])
    checks.append(("Release Preflight", release_command, ROOT, None))

    all_ok = True
    for title, command, cwd, env in checks:
        ok, section = check_section(title, command, cwd=cwd, env=env)
        all_ok = all_ok and ok
        sections.extend(["", section])

    output.write_text("\n".join(sections) + "\n", encoding="utf-8")
    print(f"Wrote {output}")
    return 1 if args.fail_on_check_failure and not all_ok else 0


if __name__ == "__main__":
    sys.exit(main())
