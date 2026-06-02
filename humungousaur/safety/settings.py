from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig


class PermissionSettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def effective_config(self, base_config: AgentConfig) -> AgentConfig:
        base = base_config.normalized()
        settings = self.load()
        read_roots = _unique_paths([*base.allowed_read_roots, *settings["extra_read_roots"]])
        return replace(base, allowed_read_roots=tuple(read_roots)).normalized()

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"extra_read_roots": []}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"extra_read_roots": []}
        roots = payload.get("extra_read_roots", [])
        if not isinstance(roots, list):
            roots = []
        return {"extra_read_roots": [str(item) for item in roots if isinstance(item, str)]}

    def add_read_root(self, raw_path: str, base_config: AgentConfig) -> dict[str, Any]:
        path = self._resolve_user_path(raw_path, base_config)
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Read root must be an existing directory: {path}")
        settings = self.load()
        roots = _unique_strings([*settings["extra_read_roots"], str(path)])
        self._save({"extra_read_roots": roots})
        return self.load()

    def remove_read_root(self, raw_path: str, base_config: AgentConfig) -> dict[str, Any]:
        path = self._resolve_user_path(raw_path, base_config)
        settings = self.load()
        roots = [root for root in settings["extra_read_roots"] if Path(root).expanduser().resolve() != path]
        self._save({"extra_read_roots": roots})
        return self.load()

    def _resolve_user_path(self, raw_path: str, base_config: AgentConfig) -> Path:
        value = str(raw_path).strip()
        if not value:
            raise ValueError("Field 'path' is required.")
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = base_config.normalized().workspace / path
        return path.resolve()

    def _save(self, payload: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _unique_paths(paths: list[Path | str]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for value in paths:
        path = Path(value).expanduser().resolve()
        key = str(path).casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _unique_strings(values: list[str]) -> list[str]:
    return [str(path) for path in _unique_paths(values)]
