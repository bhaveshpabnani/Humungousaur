#!/usr/bin/env python3
"""Collect GitHub Actions desktop artifacts into artifacts/release."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = (
    f"{os.environ.get('HUMUNGOUSAUR_RELEASE_OWNER', 'bhaveshpabnani')}/"
    f"{os.environ.get('HUMUNGOUSAUR_RELEASE_REPO', 'Humungousaur')}"
)
DEFAULT_WORKFLOW = "Release Desktop Apps"
WINDOWS_ASSET = "Humungousaur-Windows.zip"
MACOS_ASSET = "Humungousaur-macOS.zip"
CHECKSUMS_ASSET = "checksums.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repository in owner/name form.")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW, help="Workflow name or file to inspect when --run-id is omitted.")
    parser.add_argument("--run-id", help="GitHub Actions run database id to download artifacts from.")
    parser.add_argument("--release-dir", type=Path, default=ROOT / "artifacts/release")
    parser.add_argument("--release-tag", help="Expected release tag, such as v0.1.0.")
    parser.add_argument("--require-website", action="store_true", help="Include website source checks in final verification.")
    parser.add_argument("--skip-verify", action="store_true", help="Only collect artifacts and write checksums.")
    return parser.parse_args()


def run(command: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def require_success(result: subprocess.CompletedProcess[str], action: str) -> str:
    if result.returncode != 0:
        output = (result.stdout or "") + (result.stderr or "")
        raise RuntimeError(f"{action} failed:\n{output.strip()}")
    return result.stdout.strip()


def latest_successful_run_id(repo: str, workflow: str) -> str:
    output = require_success(
        run(
            [
                "gh",
                "run",
                "list",
                "--repo",
                repo,
                "--workflow",
                workflow,
                "--status",
                "success",
                "--limit",
                "1",
                "--json",
                "databaseId,displayTitle,headSha,createdAt",
            ]
        ),
        f"listing successful workflow runs for {workflow}",
    )
    try:
        runs = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"could not parse gh run list output as JSON: {exc}") from exc
    if not runs:
        raise RuntimeError(f"no successful workflow runs found for {workflow!r} in {repo}")
    run_id = str(runs[0].get("databaseId", "")).strip()
    if not run_id:
        raise RuntimeError(f"latest workflow run did not include a databaseId: {runs[0]}")
    print(f"Using workflow run {run_id}: {runs[0].get('displayTitle', '')} {runs[0].get('createdAt', '')}")
    return run_id


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_zip(download_root: Path, release_dir: Path, asset_name: str) -> Path:
    matches = sorted(download_root.rglob(asset_name))
    if not matches:
        raise RuntimeError(f"downloaded artifacts do not contain {asset_name}")
    if len(matches) > 1:
        raise RuntimeError(f"downloaded artifacts contain multiple {asset_name} files: {matches}")
    target = release_dir / asset_name
    shutil.copy2(matches[0], target)
    print(f"Collected {asset_name} from {matches[0]}")
    return target


def write_checksums(release_dir: Path) -> Path:
    checksum_path = release_dir / CHECKSUMS_ASSET
    rows = []
    for asset_name in [WINDOWS_ASSET, MACOS_ASSET]:
        path = release_dir / asset_name
        if not path.is_file():
            raise RuntimeError(f"cannot write checksums; missing {path}")
        rows.append(f"{sha256(path)}  {asset_name}")
    checksum_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"Wrote {checksum_path}")
    return checksum_path


def verify_release_dir(release_dir: Path, release_tag: str | None, require_website: bool) -> None:
    command = [
        sys.executable,
        str(ROOT / "script/verify_release_readiness.py"),
        "--require-assets",
        "--release-dir",
        str(release_dir),
    ]
    if require_website:
        command.append("--require-website")
    else:
        command.append("--skip-website")
    if release_tag:
        command.extend(["--release-tag", release_tag])
    require_success(run(command), "verifying collected release artifacts")


def main() -> int:
    args = parse_args()
    release_dir = args.release_dir.resolve()
    release_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(args.run_id or "").strip() or latest_successful_run_id(args.repo, args.workflow)

    with tempfile.TemporaryDirectory(prefix="humungousaur-actions-artifacts-") as temp_dir:
        download_root = Path(temp_dir)
        require_success(
            run(
                [
                    "gh",
                    "run",
                    "download",
                    run_id,
                    "--repo",
                    args.repo,
                    "--dir",
                    str(download_root),
                    "--name",
                    "Humungousaur-Windows",
                    "--name",
                    "Humungousaur-macOS",
                ]
            ),
            f"downloading release artifacts from run {run_id}",
        )
        collect_zip(download_root, release_dir, WINDOWS_ASSET)
        collect_zip(download_root, release_dir, MACOS_ASSET)

    write_checksums(release_dir)
    if not args.skip_verify:
        verify_release_dir(release_dir, args.release_tag, args.require_website)
    print(f"Release artifacts are ready in {release_dir}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        sys.exit(1)
