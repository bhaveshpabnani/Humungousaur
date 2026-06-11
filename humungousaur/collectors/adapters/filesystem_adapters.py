from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile, utc_now


FILESYSTEM_STIMULUS_TYPES = {"file_created", "file_modified", "file_deleted", "file_changed"}


def collect_filesystem(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    events = read_bridge_events(config, state, "filesystem", FILESYSTEM_STIMULUS_TYPES, source="activity", max_events=max(1, profile.max_file_events))
    paths = profile.watch_paths or [str(config.workspace)]
    current: dict[str, dict[str, Any]] = {}
    for path_text in paths:
        root = Path(path_text).expanduser()
        if not root.is_absolute():
            root = config.workspace / root
        if not root.exists():
            continue
        candidates = _recent_files(root, limit=max(profile.max_file_events * 4, profile.max_file_events), ignored_roots=[config.data_dir])
        for candidate in candidates:
            rel = _safe_relative(candidate, config.workspace)
            try:
                stat = candidate.stat()
                resolved = str(candidate.resolve())
            except OSError:
                continue
            current[resolved] = {
                "relative_path": rel,
                "root": str(root),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "signature": f"{stat.st_mtime_ns}:{stat.st_size}",
            }
    filesystem_state = state.setdefault("filesystem", {})
    initialized = bool(filesystem_state.get("initialized", False))
    previous = filesystem_state.get("files", {})
    filesystem_state["files"] = current
    filesystem_state["initialized"] = True
    filesystem_state["last_seen_at"] = utc_now()
    if not initialized or not isinstance(previous, dict):
        return events[: profile.max_file_events]
    for path_text, info in sorted(current.items(), key=lambda item: str(item[1].get("modified_at", "")), reverse=True):
        previous_info = previous.get(path_text)
        if isinstance(previous_info, dict) and previous_info.get("signature") == info.get("signature"):
            continue
        stimulus_type = "file_created" if previous_info is None else "file_modified"
        events.append(_filesystem_event(path_text, info, stimulus_type))
        if len(events) >= profile.max_file_events:
            return events
    for path_text, info in previous.items():
        if path_text in current or not isinstance(info, dict):
            continue
        events.append(_filesystem_event(path_text, info, "file_deleted"))
        if len(events) >= profile.max_file_events:
            break
    return events[: profile.max_file_events]


def _filesystem_event(path_text: str, info: dict[str, Any], stimulus_type: str) -> CollectorEvent:
    rel = str(info.get("relative_path") or Path(path_text).name)
    path_digest = hashlib.sha256(str(path_text).encode("utf-8")).hexdigest()[:16]
    verb = {
        "file_created": "File created",
        "file_modified": "File modified",
        "file_deleted": "File deleted",
    }.get(stimulus_type, "File changed")
    return CollectorEvent(
        collector="filesystem",
        source="activity",
        stimulus_type=stimulus_type,
        text=f"{verb}: {rel}",
        metadata={
            "path": rel,
            "root": str(info.get("root") or ""),
            "size_bytes": int(info.get("size_bytes") or 0),
            "modified_at": str(info.get("modified_at") or ""),
        },
        payload={
            "relative_path": rel,
            "modified_at": str(info.get("modified_at") or ""),
            "path_digest": path_digest,
        },
        signature=f"filesystem:{stimulus_type}:{path_digest}:{info.get('signature', '')}",
    )


def _recent_files(root: Path, *, limit: int, ignored_roots: list[Path] | None = None) -> list[Path]:
    if root.is_file():
        return [] if _ignored_file_path(root) else [root]
    candidates: list[Path] = []
    resolved_ignored_roots = [item.resolve() for item in (ignored_roots or [])]
    try:
        for path in root.rglob("*"):
            if len(candidates) >= max(limit * 10, limit):
                break
            if _ignored_file_path(path):
                continue
            resolved = path.resolve()
            if any(resolved == ignored_root or ignored_root in resolved.parents for ignored_root in resolved_ignored_roots):
                continue
            if path.is_file():
                candidates.append(path)
    except OSError:
        return []
    return sorted(candidates, key=lambda item: item.stat().st_mtime_ns, reverse=True)[:limit]


def _ignored_file_path(path: Path) -> bool:
    ignored_parts = {".git", ".venv", "node_modules", ".build", "__pycache__", "artifacts", ".codex"}
    if any(part in ignored_parts for part in path.parts):
        return True
    name = path.name.lower()
    if name == ".env" or name.startswith(".env."):
        return True
    return name.endswith((".pem", ".key", ".p12", ".pfx", ".crt"))


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)
