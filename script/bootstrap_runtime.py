#!/usr/bin/env python3
"""Install or repair the local Humungousaur Python runtime for desktop apps."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import venv
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIN_PYTHON = (3, 12)
DEFAULT_EXTRAS = "browser,pdf,ocr,office"


def default_data_root() -> Path:
    system = platform.system().lower()
    if system == "windows":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "Humungousaur"
    if system == "darwin":
        return Path.home() / "Library" / "Application Support" / "Humungousaur"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "humungousaur"


def python_bin(venv_dir: Path) -> Path:
    if platform.system().lower() == "windows":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def run(command: list[str], *, quiet: bool) -> None:
    if not quiet:
        print("+ " + " ".join(command))
    subprocess.run(command, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT, help="Humungousaur source tree to install from.")
    parser.add_argument("--data-root", type=Path, default=default_data_root(), help="Per-user runtime data root.")
    parser.add_argument("--extras", default=DEFAULT_EXTRAS, help="Python extras to install from pyproject.toml.")
    parser.add_argument("--skip-playwright", action="store_true", help="Do not install the Playwright Chromium browser.")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def require_python_version() -> None:
    if sys.version_info < MIN_PYTHON:
        version = ".".join(str(part) for part in sys.version_info[:3])
        required = ".".join(str(part) for part in MIN_PYTHON)
        raise RuntimeError(
            f"Humungousaur requires Python {required}+ for the desktop runtime; "
            f"this installer is running with Python {version}."
        )


def validate_source(source: Path) -> Path:
    source = source.resolve()
    if not (source / "pyproject.toml").is_file() or not (source / "humungousaur" / "__main__.py").is_file():
        raise RuntimeError(f"{source} is not a Humungousaur runtime source tree")
    return source


def write_status(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    try:
        require_python_version()
        source = validate_source(args.source)
        data_root = args.data_root.expanduser().resolve()
        runtime_dir = data_root / "runtime"
        venv_dir = runtime_dir / ".venv"
        runtime_dir.mkdir(parents=True, exist_ok=True)

        builder = venv.EnvBuilder(with_pip=True, upgrade_deps=False)
        builder.create(venv_dir)
        runtime_python = python_bin(venv_dir)
        if not runtime_python.is_file():
            raise RuntimeError(f"virtual environment did not create {runtime_python}")

        run([str(runtime_python), "-m", "pip", "install", "--upgrade", "pip", "wheel"], quiet=args.quiet)
        install_target = f"{source}[{args.extras}]" if args.extras else str(source)
        run([str(runtime_python), "-m", "pip", "install", "--upgrade", "-e", install_target], quiet=args.quiet)
        if not args.skip_playwright:
            run([str(runtime_python), "-m", "playwright", "install", "chromium"], quiet=args.quiet)

        status = {
            "ok": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": str(source),
            "data_root": str(data_root),
            "python": str(runtime_python),
            "extras": args.extras,
            "playwright": not args.skip_playwright,
        }
        write_status(runtime_dir / "install-status.json", status)
        if not args.quiet:
            print(f"Humungousaur runtime ready: {runtime_python}")
        return 0
    except Exception as exc:
        data_root = args.data_root.expanduser()
        write_status(
            data_root / "runtime" / "install-status.json",
            {
                "ok": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
                "python": sys.executable,
            },
        )
        print(f"Humungousaur runtime bootstrap failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
