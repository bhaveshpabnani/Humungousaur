#!/usr/bin/env python3
"""Verify the repository state is ready for an open-source release push."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEBSITE_ROOT = ROOT.parent / "Humungousaur-Website"
GIT_STATUS_COMMAND_DISPLAY = "status --porcelain=v1 --untracked-files=all"
WEBSITE_PUBLICATION_COMMAND = ["npm", "run", "check:publication"]

REQUIRED_TRACKED_PATHS = [
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    "CONTRIBUTING.md",
    "AGENTS.md",
    "LICENSE",
    "SECURITY.md",
    "README.md",
    "docs/OPEN_SOURCE_RELEASE_GOAL.md",
    "docs/GLOBAL_AGENT_INSTRUCTIONS.md",
    "docs/COGNITIVE_AGENT_ARCHITECTURE.md",
    "docs/AGENT_SKILL_AUTHORING_STANDARD.md",
    "docs/RELEASE_CHECKLIST.md",
    "docs/RELEASE_RUNBOOK.md",
    "humungousaur/planning/prompt_templates.py",
    "humungousaur/resources/prompts/planning.yaml",
    "humungousaur/resources/prompts/cognition.yaml",
    "humungousaur/resources/prompts/codex.yaml",
    "humungousaur/resources/prompts/workflow.yaml",
    "humungousaur/resources/prompts/response.yaml",
    "script/build_and_run.sh",
    "script/collect_release_artifacts.py",
    "script/generate_release_report.py",
    "script/package_macos.sh",
    "script/package_windows.ps1",
    "script/verify_desktop_parity.py",
    "script/verify_desktop_runtime_smoke.py",
    "script/verify_macos_package.sh",
    "script/verify_open_source_hygiene.py",
    "script/verify_release_readiness.py",
    "script/verify_release_report.py",
    "script/verify_windows_package.ps1",
    "scripts/smoke_real_world_tasks.py",
    "apps/macos/Package.swift",
    "apps/macos/README.md",
    "apps/macos/Sources/AgentAPIClient.swift",
    "apps/macos/Sources/AppSettings.swift",
    "apps/macos/Sources/AppViewModel.swift",
    "apps/windows/Humungousaur.App/Humungousaur.App.csproj",
    "tests/test_release_readiness.py",
]


@dataclass(frozen=True)
class StatusEntry:
    code: str
    path: str


def parse_status(output: str) -> list[StatusEntry]:
    entries: list[StatusEntry] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        code = line[:2]
        path = line[3:] if len(line) > 3 else ""
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        entries.append(StatusEntry(code=code, path=path))
    return entries


def run_git(args: list[str], root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)


def tracked_files(root: Path) -> set[str]:
    result = run_git(["ls-files"], root)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def macos_swift_sources(root: Path) -> list[str]:
    source_dir = root / "apps/macos/Sources"
    if not source_dir.is_dir():
        return []
    return sorted(path.relative_to(root).as_posix() for path in source_dir.glob("*.swift"))


def windows_app_sources(root: Path) -> list[str]:
    source_dir = root / "apps/windows/Humungousaur.App"
    if not source_dir.is_dir():
        return []
    patterns = ["*.cs", "*.xaml", "*.csproj", "*.targets", "*.manifest"]
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(source_dir.rglob(pattern))
    generated_dirs = {"bin", "obj"}
    return sorted(
        path.relative_to(root).as_posix()
        for path in paths
        if path.is_file() and not generated_dirs.intersection(path.relative_to(source_dir).parts)
    )


def required_tracked_paths(root: Path) -> list[str]:
    return list(dict.fromkeys([*REQUIRED_TRACKED_PATHS, *macos_swift_sources(root), *windows_app_sources(root)]))


def website_publication_errors(website_root: Path, require_clean: bool = True) -> list[str]:
    if not website_root.exists():
        return [f"website: missing website root {website_root}"]
    command = [*WEBSITE_PUBLICATION_COMMAND]
    if not require_clean:
        command.extend(["--", "--allow-dirty"])
    try:
        result = subprocess.run(command, cwd=website_root, text=True, capture_output=True, check=False)
    except FileNotFoundError as exc:
        return [f"website: npm publication gate could not run: {exc}"]
    if result.returncode == 0:
        return []
    output = "\n".join(part for part in [result.stdout, result.stderr] if part).strip()
    failures = [line.removeprefix("FAIL ").strip() for line in output.splitlines() if line.startswith("FAIL ")]
    if not failures:
        failures = [output or f"{' '.join(command)} failed with exit code {result.returncode}"]
    return [f"website: {failure}" for failure in failures]


def publication_errors(root: Path, require_clean: bool = True, website_root: Path | None = None) -> list[str]:
    errors: list[str] = []
    tracked = tracked_files(root)
    missing = [path for path in required_tracked_paths(root) if path not in tracked]
    for path in missing:
        errors.append(f"{path}: required release/publication file is not tracked by git")

    if require_clean:
        status = run_git(GIT_STATUS_COMMAND_DISPLAY.split(), root)
        if status.returncode != 0:
            raise RuntimeError(status.stderr.strip() or status.stdout.strip())
        dirty = parse_status(status.stdout)
        for entry in dirty:
            errors.append(f"{entry.path}: working tree has pending status {entry.code!r}")
    if website_root is not None:
        errors.extend(website_publication_errors(website_root, require_clean=require_clean))
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--website-root", type=Path, default=DEFAULT_WEBSITE_ROOT)
    parser.add_argument("--require-website", action="store_true", help="Also run the sibling website publication gate.")
    parser.add_argument("--allow-dirty", action="store_true", help="Only check required release files are tracked.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    website_root = args.website_root.resolve() if args.require_website else None
    try:
        errors = publication_errors(root, require_clean=not args.allow_dirty, website_root=website_root)
    except Exception as exc:
        print(f"FAIL {exc}")
        return 1
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        print(f"\nPublication state: 0 passed, {len(errors)} failures")
        return 1
    if args.require_website:
        print("Publication state: required release and website files are tracked and both working trees are clean")
    else:
        print("Publication state: required release files are tracked and working tree is clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
