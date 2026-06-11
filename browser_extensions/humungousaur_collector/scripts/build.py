#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


BROWSERS = ("chrome", "edge", "brave", "firefox", "safari")


def build(root: Path, output: Path) -> list[Path]:
    src = root / "src"
    if not src.is_dir():
        raise SystemExit(f"missing extension source directory: {src}")
    built: list[Path] = []
    for browser in BROWSERS:
        manifest_path = root / f"manifest.{browser}.json"
        if not manifest_path.exists():
            raise SystemExit(f"missing manifest for {browser}: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        destination = output / browser
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(src, destination / "src")
        (destination / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        built.append(destination)
    return built


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Humungousaur browser collector extension directories.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output or root / "dist").resolve()
    built = build(root, output)
    for directory in built:
        print(directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
