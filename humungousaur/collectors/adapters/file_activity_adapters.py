from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import platform
import shutil
import subprocess
from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile, utc_now


FILE_SOURCE_CONTRACTS: dict[str, dict[str, Any]] = {
    "darwin": {
        "directory_changes": {
            "recommended_emitter": "macos_fsevents_helper",
            "api": "FSEvents",
            "implemented": True,
            "implementation": "native_collectors/macos product HumungousaurMacCollectorHost",
            "covers": ["file_saved", "file_renamed", "file_moved", "folder_changed", "folder_created", "folder_renamed", "folder_moved"],
        },
        "file_open_close": {
            "recommended_emitter": "macos_endpoint_security_helper",
            "api": "EndpointSecurity",
            "covers": ["file_opened", "file_closed"],
            "requires_privileged_helper": True,
        },
        "file_manager_ui": {
            "recommended_emitter": "macos_finder_accessibility_helper",
            "api": "Accessibility/NSWorkspace/Finder scripting",
            "implemented": True,
            "implementation": "native_collectors/macos product HumungousaurMacCollectorHost best-effort Finder/Quick Look metadata",
            "covers": ["quick_look_opened", "folder_opened"],
        },
    },
    "windows": {
        "directory_changes": {
            "recommended_emitter": "windows_read_directory_changes_helper",
            "api": "ReadDirectoryChangesW",
            "implemented": False,
            "covers": ["file_saved", "file_renamed", "file_moved", "folder_changed", "folder_created", "folder_renamed", "folder_moved"],
        },
        "file_open_close": {
            "recommended_emitter": "windows_file_audit_or_etw_helper",
            "api": "File auditing/ETW",
            "covers": ["file_opened", "file_closed"],
            "requires_privileged_helper": True,
        },
        "file_manager_ui": {
            "recommended_emitter": "windows_explorer_uia_helper",
            "api": "UI Automation/Shell notifications",
            "covers": ["file_tagged", "file_shared_from_manager", "quick_look_opened", "folder_opened", "path_bar_used", "trash_opened", "trash_item_restored", "trash_emptied"],
        },
    },
    "linux": {
        "directory_changes": {
            "recommended_emitter": "linux_inotify_helper",
            "api": "inotify",
            "implemented": False,
            "covers": ["file_saved", "file_renamed", "file_moved", "folder_changed", "folder_created", "folder_renamed", "folder_moved"],
        },
        "file_open_close": {
            "recommended_emitter": "linux_fanotify_helper",
            "api": "fanotify",
            "covers": ["file_opened", "file_closed"],
            "requires_privileged_helper": True,
        },
        "file_manager_ui": {
            "recommended_emitter": "linux_file_manager_extension_or_accessibility_helper",
            "api": "file-manager extension/accessibility bridge",
            "covers": ["file_shared_from_manager", "quick_look_opened", "folder_opened", "path_bar_used", "trash_opened", "trash_item_restored", "trash_emptied"],
        },
    },
}

FILE_OPERATION_ACTIVITY_STIMULUS_TYPES = {
    "file_opened",
    "file_closed",
    "file_saved",
    "file_renamed",
    "file_moved",
    "file_duplicated",
    "file_tagged",
    "file_shared_from_manager",
}
FOLDER_NAVIGATION_ACTIVITY_STIMULUS_TYPES = {
    "folder_opened",
    "folder_changed",
    "folder_created",
    "folder_renamed",
    "folder_moved",
    "folder_view_changed",
    "path_bar_used",
}
FILE_PREVIEW_ACTIVITY_STIMULUS_TYPES = {
    "quick_look_opened",
    "preview_pane_opened",
    "preview_next_file",
    "preview_previous_file",
    "file_metadata_inspected",
    "file_info_panel_opened",
}
TRASH_ACTIVITY_STIMULUS_TYPES = {
    "file_moved_to_trash",
    "folder_moved_to_trash",
    "trash_opened",
    "trash_item_restored",
    "trash_item_deleted",
    "trash_emptied",
}


def file_activity_source_status() -> dict[str, Any]:
    platform_key = platform.system().lower()
    contract = FILE_SOURCE_CONTRACTS.get(platform_key, {})
    return {
        "platform": platform.system(),
        "implemented_native_emitters": {
            key: value
            for key, value in contract.items()
            if isinstance(value, dict) and value.get("implemented")
        },
        "local_fallbacks": {
            "directory_metadata_polling": {
                "available": True,
                "covers": ["file_saved", "file_renamed", "file_moved", "folder_created", "folder_changed", "folder_renamed", "folder_moved"],
                "limitations": "Poll-based, not realtime; cannot see Finder/Explorer-only UI actions such as preview, tag, share, path bar, restore.",
            },
            "open_handle_polling": {
                "available": _open_handle_supported(),
                "covers": ["file_opened", "file_closed"],
                "limitations": "Best-effort lsof scan over watched candidates; misses short-lived opens and unsupported platforms.",
            },
            "trash_folder_polling": {
                "available": bool(_trash_roots()),
                "covers": ["file_moved_to_trash", "folder_moved_to_trash", "trash_item_deleted", "trash_emptied"],
                "limitations": "Poll-based and user-trash scoped; restore/open actions need a file-manager UI helper.",
            },
        },
        "recommended_native_emitters": contract,
        "bridge_only_until_emitter_exists": {
            "file_operation_activity": ["file_duplicated", "file_tagged", "file_shared_from_manager"],
            "folder_navigation_activity": ["folder_view_changed", "path_bar_used"],
            "file_preview_activity": sorted(FILE_PREVIEW_ACTIVITY_STIMULUS_TYPES - {"quick_look_opened"}),
            "trash_activity": ["trash_opened", "trash_item_restored"],
        },
    }


def collect_file_operation_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    events = read_bridge_events(config, state, "file_operation_activity", FILE_OPERATION_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)
    remaining = max(0, min(20, profile.max_file_events) - len(events))
    if remaining <= 0:
        return events
    events.extend(_collect_native_file_operations(config, profile, state, max_events=remaining))
    return events


def collect_folder_navigation_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    events = read_bridge_events(config, state, "folder_navigation_activity", FOLDER_NAVIGATION_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)
    remaining = max(0, min(20, profile.max_file_events) - len(events))
    if remaining <= 0:
        return events
    events.extend(_collect_native_folder_navigation(config, profile, state, max_events=remaining))
    return events


def collect_file_preview_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "file_preview_activity", FILE_PREVIEW_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_trash_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    events = read_bridge_events(config, state, "trash_activity", TRASH_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)
    remaining = max(0, min(20, profile.max_file_events) - len(events))
    if remaining <= 0:
        return events
    events.extend(_collect_native_trash_activity(config, profile, state, max_events=remaining))
    return events


def _collect_native_file_operations(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any], *, max_events: int) -> list[CollectorEvent]:
    roots = _watch_roots(config, profile)
    files = _recent_file_infos(roots, config=config, limit=max(profile.max_file_events * 8, 40))
    current_signatures = {path_text: info["signature"] for path_text, info in files.items()}
    current_identities = {path_text: info["identity"] for path_text, info in files.items() if info.get("identity")}
    current_open_paths = _open_file_paths(set(files.keys()))

    file_state = state.setdefault("file_operation_activity", {})
    initialized = bool(file_state.get("initialized", False))
    previous_signatures = file_state.get("file_signatures", {})
    previous_identities = file_state.get("file_identities", {})
    previous_open_paths = set(file_state.get("open_paths", [])) if isinstance(file_state.get("open_paths", []), list) else set()
    file_state["file_signatures"] = current_signatures
    file_state["file_identities"] = current_identities
    file_state["open_paths"] = sorted(current_open_paths)
    file_state["initialized"] = True
    file_state["last_seen_at"] = utc_now()
    file_state["native_source"] = {
        "open_handle_supported": _open_handle_supported(),
        "platform": platform.system(),
    }
    if not initialized or not isinstance(previous_signatures, dict):
        return []

    events: list[CollectorEvent] = []
    moved_current_paths: set[str] = set()
    if isinstance(previous_identities, dict):
        current_by_identity = {
            identity: path_text
            for path_text, identity in current_identities.items()
            if path_text not in previous_signatures
        }
        for previous_path in sorted(set(previous_signatures) - set(current_signatures)):
            identity = previous_identities.get(previous_path)
            current_path = current_by_identity.get(identity) if identity else None
            if not current_path:
                continue
            stimulus_type = "file_renamed" if Path(previous_path).parent == Path(current_path).parent else "file_moved"
            events.append(_file_operation_event(current_path, files[current_path], stimulus_type, previous_path_text=previous_path))
            moved_current_paths.add(current_path)
            if len(events) >= max_events:
                return events
    for path_text in sorted(current_open_paths - previous_open_paths):
        info = files.get(path_text)
        if info is not None:
            events.append(_file_operation_event(path_text, info, "file_opened"))
            if len(events) >= max_events:
                return events
    for path_text in sorted(previous_open_paths - current_open_paths):
        info = files.get(path_text) or {"relative_path": Path(path_text).name, "size_bytes": 0, "modified_at": "", "signature": ""}
        events.append(_file_operation_event(path_text, info, "file_closed"))
        if len(events) >= max_events:
            return events
    for path_text, signature in sorted(current_signatures.items(), key=lambda item: str(files[item[0]].get("modified_at", "")), reverse=True):
        if path_text in moved_current_paths:
            continue
        if previous_signatures.get(path_text) == signature or path_text not in previous_signatures:
            continue
        events.append(_file_operation_event(path_text, files[path_text], "file_saved"))
        if len(events) >= max_events:
            break
    return events


def _watch_roots(config: AgentConfig, profile: CollectorProfile) -> list[Path]:
    roots: list[Path] = []
    for path_text in profile.watch_paths or [str(config.workspace)]:
        root = Path(path_text).expanduser()
        if not root.is_absolute():
            root = config.workspace / root
        if root.exists():
            roots.append(root)
    return roots


def _recent_file_infos(roots: list[Path], *, config: AgentConfig, limit: int) -> dict[str, dict[str, Any]]:
    infos: dict[str, dict[str, Any]] = {}
    for root in roots:
        for path in _recent_files(root, limit=limit, ignored_roots=[config.data_dir]):
            try:
                stat = path.stat()
                resolved = str(path.resolve())
            except OSError:
                continue
            infos[resolved] = {
                "relative_path": _safe_relative(path, config.workspace),
                "root": str(root),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "signature": f"{stat.st_mtime_ns}:{stat.st_size}",
                "identity": _stat_identity(stat),
            }
    return infos


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


def _open_file_paths(candidate_paths: set[str]) -> set[str]:
    if not candidate_paths or not _open_handle_supported():
        return set()
    open_paths: set[str] = set()
    for path_text in sorted(candidate_paths):
        try:
            result = subprocess.run(["lsof", "-w", "-F", "n", "--", path_text], capture_output=True, text=True, timeout=0.5)
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            if line.startswith("n"):
                opened = line[1:]
                try:
                    opened = str(Path(opened).resolve())
                except OSError:
                    pass
                if opened == path_text:
                    open_paths.add(path_text)
                    break
    return open_paths


def _open_handle_supported() -> bool:
    return shutil.which("lsof") is not None and platform.system().lower() in {"darwin", "linux"}


def _file_operation_event(path_text: str, info: dict[str, Any], stimulus_type: str, *, previous_path_text: str | None = None) -> CollectorEvent:
    path_digest = hashlib.sha256(str(path_text).encode("utf-8")).hexdigest()[:16]
    previous_path_digest = hashlib.sha256(previous_path_text.encode("utf-8")).hexdigest()[:16] if previous_path_text else None
    action = stimulus_type.removeprefix("file_")
    payload: dict[str, Any] = {
        "relative_path": str(info.get("relative_path") or Path(path_text).name),
        "modified_at": str(info.get("modified_at") or ""),
        "size_bytes": int(info.get("size_bytes") or 0),
        "path_digest": path_digest,
    }
    if previous_path_text:
        payload["previous_relative_path"] = str(info.get("previous_relative_path") or Path(previous_path_text).name)
        payload["previous_path_digest"] = previous_path_digest
    return CollectorEvent(
        collector="file_operation_activity",
        source="activity",
        stimulus_type=stimulus_type,
        text=stimulus_type.replace("_", " ").capitalize(),
        metadata={
            "file_action": action,
            "path_digest": path_digest,
            "privacy_level": "redacted",
            "platform": platform.system(),
            "native_source": "file_metadata_polling_and_open_handles",
            "open_handle_supported": _open_handle_supported(),
            "previous_path_digest": previous_path_digest,
        },
        payload=payload,
        signature=f"file_operation_activity:{stimulus_type}:{previous_path_digest or ''}:{path_digest}:{info.get('signature', '')}",
    )


def _collect_native_folder_navigation(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any], *, max_events: int) -> list[CollectorEvent]:
    folders = _recent_folder_infos(_watch_roots(config, profile), config=config, limit=max(profile.max_file_events * 8, 40))
    current_signatures = {path_text: info["signature"] for path_text, info in folders.items()}
    current_identities = {path_text: info["identity"] for path_text, info in folders.items() if info.get("identity")}
    folder_state = state.setdefault("folder_navigation_activity", {})
    initialized = bool(folder_state.get("initialized", False))
    previous_signatures = folder_state.get("folder_signatures", {})
    previous_identities = folder_state.get("folder_identities", {})
    folder_state["folder_signatures"] = current_signatures
    folder_state["folder_identities"] = current_identities
    folder_state["initialized"] = True
    folder_state["last_seen_at"] = utc_now()
    folder_state["native_source"] = {"kind": "directory_metadata_polling", "platform": platform.system()}
    if not initialized or not isinstance(previous_signatures, dict):
        return []
    events: list[CollectorEvent] = []
    moved_current_paths: set[str] = set()
    if isinstance(previous_identities, dict):
        current_by_identity = {
            identity: path_text
            for path_text, identity in current_identities.items()
            if path_text not in previous_signatures
        }
        for previous_path in sorted(set(previous_signatures) - set(current_signatures)):
            identity = previous_identities.get(previous_path)
            current_path = current_by_identity.get(identity) if identity else None
            if not current_path:
                continue
            stimulus_type = "folder_renamed" if Path(previous_path).parent == Path(current_path).parent else "folder_moved"
            events.append(_folder_navigation_event(current_path, folders[current_path], stimulus_type, previous_path_text=previous_path))
            moved_current_paths.add(current_path)
            if len(events) >= max_events:
                return events
    for path_text, signature in sorted(current_signatures.items(), key=lambda item: str(folders[item[0]].get("modified_at", "")), reverse=True):
        if path_text in moved_current_paths:
            continue
        previous = previous_signatures.get(path_text)
        if previous == signature:
            continue
        stimulus_type = "folder_created" if previous is None else "folder_changed"
        events.append(_folder_navigation_event(path_text, folders[path_text], stimulus_type))
        if len(events) >= max_events:
            break
    return events


def _recent_folder_infos(roots: list[Path], *, config: AgentConfig, limit: int) -> dict[str, dict[str, Any]]:
    infos: dict[str, dict[str, Any]] = {}
    for root in roots:
        for folder in _recent_folders(root, limit=limit, ignored_roots=[config.data_dir]):
            try:
                stat = folder.stat()
                resolved = str(folder.resolve())
                child_count = sum(1 for _ in folder.iterdir())
            except OSError:
                continue
            infos[resolved] = {
                "relative_path": _safe_relative(folder, config.workspace),
                "root": str(root),
                "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "signature": f"{stat.st_mtime_ns}:{child_count}",
                "identity": _stat_identity(stat),
            }
    return infos


def _recent_folders(root: Path, *, limit: int, ignored_roots: list[Path] | None = None) -> list[Path]:
    if not root.is_dir():
        return []
    candidates: list[Path] = [root]
    resolved_ignored_roots = [item.resolve() for item in (ignored_roots or [])]
    try:
        for path in root.rglob("*"):
            if len(candidates) >= max(limit * 10, limit):
                break
            if not path.is_dir():
                continue
            if _ignored_folder_path(path):
                continue
            resolved = path.resolve()
            if any(resolved == ignored_root or ignored_root in resolved.parents for ignored_root in resolved_ignored_roots):
                continue
            candidates.append(path)
    except OSError:
        return []
    return sorted(candidates, key=lambda item: item.stat().st_mtime_ns, reverse=True)[:limit]


def _folder_navigation_event(path_text: str, info: dict[str, Any], stimulus_type: str, *, previous_path_text: str | None = None) -> CollectorEvent:
    path_digest = hashlib.sha256(str(path_text).encode("utf-8")).hexdigest()[:16]
    previous_path_digest = hashlib.sha256(previous_path_text.encode("utf-8")).hexdigest()[:16] if previous_path_text else None
    payload: dict[str, Any] = {
        "relative_path": str(info.get("relative_path") or Path(path_text).name),
        "modified_at": str(info.get("modified_at") or ""),
        "path_digest": path_digest,
    }
    if previous_path_text:
        payload["previous_relative_path"] = str(info.get("previous_relative_path") or Path(previous_path_text).name)
        payload["previous_path_digest"] = previous_path_digest
    return CollectorEvent(
        collector="folder_navigation_activity",
        source="activity",
        stimulus_type=stimulus_type,
        text=stimulus_type.replace("_", " ").capitalize(),
        metadata={
            "folder_action": stimulus_type.removeprefix("folder_"),
            "path_digest": path_digest,
            "privacy_level": "redacted",
            "platform": platform.system(),
            "native_source": "directory_metadata_polling",
            "previous_path_digest": previous_path_digest,
        },
        payload=payload,
        signature=f"folder_navigation_activity:{stimulus_type}:{previous_path_digest or ''}:{path_digest}:{info.get('signature', '')}",
    )


def _collect_native_trash_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any], *, max_events: int) -> list[CollectorEvent]:
    del config
    items = _trash_item_infos(_trash_roots(), limit=max(profile.max_file_events * 8, 40))
    current_signatures = {path_text: info["signature"] for path_text, info in items.items()}
    trash_state = state.setdefault("trash_activity", {})
    initialized = bool(trash_state.get("initialized", False))
    previous_signatures = trash_state.get("trash_signatures", {})
    trash_state["trash_signatures"] = current_signatures
    trash_state["initialized"] = True
    trash_state["last_seen_at"] = utc_now()
    trash_state["native_source"] = {"kind": "trash_folder_polling", "platform": platform.system()}
    if not initialized or not isinstance(previous_signatures, dict):
        return []
    events: list[CollectorEvent] = []
    for path_text in sorted(set(current_signatures) - set(previous_signatures)):
        stimulus_type = "folder_moved_to_trash" if items[path_text].get("kind") == "folder" else "file_moved_to_trash"
        events.append(_trash_event(path_text, items[path_text], stimulus_type))
        if len(events) >= max_events:
            return events
    if len(previous_signatures) > 1 and not current_signatures:
        events.append(_trash_event("trash", {"relative_path": "trash", "modified_at": "", "signature": ""}, "trash_emptied"))
        return events[:max_events]
    for path_text in sorted(set(previous_signatures) - set(current_signatures)):
        info = {"relative_path": Path(path_text).name, "modified_at": "", "signature": previous_signatures.get(path_text, "")}
        events.append(_trash_event(path_text, info, "trash_item_deleted"))
        if len(events) >= max_events:
            break
    return events


def _trash_roots() -> list[Path]:
    roots: list[Path] = []
    home = Path.home()
    if platform.system().lower() == "darwin":
        roots.append(home / ".Trash")
    elif platform.system().lower() == "windows":
        roots.append(home / "$Recycle.Bin")
    else:
        roots.extend([home / ".local/share/Trash/files", home / ".Trash"])
    return [root for root in roots if root.exists() and root.is_dir()]


def _trash_item_infos(roots: list[Path], *, limit: int) -> dict[str, dict[str, Any]]:
    infos: dict[str, dict[str, Any]] = {}
    for root in roots:
        for path in _recent_trash_items(root, limit=limit):
            try:
                stat = path.stat()
                resolved = str(path.resolve())
            except OSError:
                continue
            infos[resolved] = {
                "relative_path": path.name,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "signature": f"{stat.st_mtime_ns}:{stat.st_size if path.is_file() else 0}",
                "kind": "folder" if path.is_dir() else "file",
            }
    return infos


def _recent_trash_items(root: Path, *, limit: int) -> list[Path]:
    try:
        candidates = [path for path in root.iterdir() if not _ignored_file_path(path) and not _ignored_folder_path(path)]
    except OSError:
        return []
    return sorted(candidates, key=lambda item: item.stat().st_mtime_ns, reverse=True)[:limit]


def _trash_event(path_text: str, info: dict[str, Any], stimulus_type: str) -> CollectorEvent:
    path_digest = hashlib.sha256(str(path_text).encode("utf-8")).hexdigest()[:16]
    action = {
        "file_moved_to_trash": "move_file_to_trash",
        "folder_moved_to_trash": "move_folder_to_trash",
        "trash_item_deleted": "delete",
        "trash_emptied": "empty",
    }.get(stimulus_type, stimulus_type)
    return CollectorEvent(
        collector="trash_activity",
        source="activity",
        stimulus_type=stimulus_type,
        text=stimulus_type.replace("_", " ").capitalize(),
        metadata={
            "trash_action": action,
            "path_digest": path_digest,
            "privacy_level": "redacted",
            "platform": platform.system(),
            "native_source": "trash_folder_polling",
        },
        payload={
            "relative_path": str(info.get("relative_path") or Path(path_text).name),
            "modified_at": str(info.get("modified_at") or ""),
            "path_digest": path_digest,
        },
        signature=f"trash_activity:{stimulus_type}:{path_digest}:{info.get('signature', '')}",
    )


def _ignored_file_path(path: Path) -> bool:
    ignored_parts = {".git", ".venv", "node_modules", ".build", "__pycache__", "artifacts", ".codex"}
    if any(part in ignored_parts for part in path.parts):
        return True
    name = path.name.lower()
    if name == ".env" or name.startswith(".env."):
        return True
    return name.endswith((".pem", ".key", ".p12", ".pfx", ".crt"))


def _ignored_folder_path(path: Path) -> bool:
    ignored_parts = {".git", ".venv", "node_modules", ".build", "__pycache__", "artifacts", ".codex"}
    return any(part in ignored_parts for part in path.parts)


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _stat_identity(stat: Any) -> str:
    device = getattr(stat, "st_dev", None)
    inode = getattr(stat, "st_ino", None)
    if device is None or inode is None or int(inode) == 0:
        return ""
    return f"{device}:{inode}"
