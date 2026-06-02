from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path, override: bool = False) -> dict[str, str]:
    """Load simple KEY=VALUE pairs from a local .env file."""
    loaded: dict[str, str] = {}
    if not path.exists() or not path.is_file():
        return loaded

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = _clean_value(value.strip())
        if not key or not _valid_key(key):
            continue
        if override or key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded


def load_workspace_environment(workspace: Path) -> dict[str, str]:
    loaded: dict[str, str] = {}
    workspace_env = workspace.expanduser().resolve() / ".env"
    for candidate in _env_candidates(workspace):
        loaded.update(load_dotenv(candidate, override=candidate == workspace_env))
    return loaded


def _env_candidates(workspace: Path) -> list[Path]:
    workspace = workspace.expanduser().resolve()
    candidates = [workspace / ".env"]
    cwd_env = Path.cwd().expanduser().resolve() / ".env"
    if cwd_env not in candidates:
        candidates.append(cwd_env)
    return candidates


def _clean_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value


def _valid_key(key: str) -> bool:
    return all(char == "_" or char.isalnum() for char in key)
