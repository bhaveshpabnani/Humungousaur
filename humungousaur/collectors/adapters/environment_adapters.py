from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import subprocess
from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile


DEVICE_STATE_STIMULUS_TYPES = {
    "user_idle_state_changed",
    "screen_locked",
    "screen_unlocked",
    "sleep_started",
    "wake_started",
    "battery_low",
    "charger_connected",
    "network_changed",
    "vpn_changed",
    "focus_mode_enabled",
}
VISUAL_STATE_STIMULUS_TYPES = {
    "error_banner_visible",
    "toast_visible",
    "modal_visible",
    "loading_spinner_stuck",
}
SHARE_ACTIVITY_STIMULUS_TYPES = {
    "clipboard_file_changed",
    "clipboard_image_changed",
    "clipboard_url_changed",
    "share_sheet_opened",
    "drag_drop_file",
    "drag_drop_text",
}
DOWNLOADS_STIMULUS_TYPES = {
    "downloaded_file",
    "exported_file",
    "mounted_volume_changed",
}
GIT_ACTIVITY_STIMULUS_TYPES = {
    "git_branch_changed",
    "commit_created",
    "merge_conflict_detected",
    "stash_created",
    "rebase_started",
    "rebase_conflict_detected",
    "merge_completed",
    "working_tree_dirty",
    "working_tree_clean",
}
GITHUB_ACTIVITY_STIMULUS_TYPES = {
    "pr_opened",
    "pr_review_requested",
    "ci_failed",
    "ci_passed",
    "issue_assigned",
    "comment_received",
    "merge_ready",
}


def collect_device_state(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "device_state", DEVICE_STATE_STIMULUS_TYPES, source="system", max_events=20)


def collect_visual_state(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "visual_state", VISUAL_STATE_STIMULUS_TYPES, source="screen_ocr", max_events=20)


def collect_share_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "share_activity", SHARE_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_downloads(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    events = read_bridge_events(config, state, "downloads", DOWNLOADS_STIMULUS_TYPES, source="activity", max_events=20)
    events.extend(_download_poll_events(config, profile, state))
    return events[: max(1, profile.max_file_events)]


def collect_git_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    events = read_bridge_events(config, state, "git_activity", GIT_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)
    events.extend(_git_poll_events(config, state))
    return events[:20]


def collect_github_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "github_activity", GITHUB_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def _download_poll_events(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    roots = _download_roots(config, profile)
    if not roots:
        return []
    current: dict[str, dict[str, Any]] = {}
    for root in roots:
        for path in _recent_download_files(root, limit=max(profile.max_file_events * 4, 20), ignored_roots=[config.data_dir]):
            try:
                stat = path.stat()
            except OSError:
                continue
            current[str(path.resolve())] = {
                "signature": f"{stat.st_mtime_ns}:{stat.st_size}",
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "root": str(root),
                "filename": path.name,
            }
    download_state = state.setdefault("downloads", {})
    previous = download_state.get("files", {})
    download_state["files"] = current
    if not isinstance(previous, dict) or not previous:
        return []
    events: list[CollectorEvent] = []
    for path_text, info in sorted(current.items(), key=lambda item: str(item[1].get("modified_at", "")), reverse=True):
        previous_info = previous.get(path_text)
        if isinstance(previous_info, dict) and previous_info.get("signature") == info.get("signature"):
            continue
        path = Path(path_text)
        path_digest = hashlib.sha256(path_text.encode("utf-8")).hexdigest()[:16]
        events.append(
            CollectorEvent(
                collector="downloads",
                source="activity",
                stimulus_type="downloaded_file",
                text=f"Downloaded or exported file changed: {path.name}",
                metadata={
                    "filename": path.name,
                    "root": str(info.get("root", "")),
                    "size_bytes": int(info.get("size_bytes") or 0),
                    "modified_at": str(info.get("modified_at", "")),
                },
                payload={"path": str(path), "filename": path.name},
                signature=f"downloads:{path_digest}:{info.get('signature', '')}",
            )
        )
        if len(events) >= profile.max_file_events:
            break
    return events


def _download_roots(config: AgentConfig, profile: CollectorProfile) -> list[Path]:
    raw_paths = profile.watch_paths or [str(Path.home() / "Downloads")]
    roots: list[Path] = []
    for item in raw_paths:
        path = Path(str(item)).expanduser()
        if not path.is_absolute():
            path = config.workspace / path
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved.exists() and resolved.is_dir() and resolved not in roots:
            roots.append(resolved)
    return roots[:10]


def _recent_download_files(root: Path, *, limit: int, ignored_roots: list[Path]) -> list[Path]:
    ignored = []
    for path in ignored_roots:
        try:
            ignored.append(path.resolve())
        except OSError:
            continue
    candidates: list[Path] = []
    try:
        children = list(root.iterdir())
    except OSError:
        return []
    for path in children:
        if len(candidates) >= max(limit * 4, limit):
            break
        try:
            resolved = path.resolve()
            if any(resolved == ignored_root or ignored_root in resolved.parents for ignored_root in ignored):
                continue
            if path.is_file() and not path.name.startswith("."):
                candidates.append(path)
        except OSError:
            continue
    return sorted(candidates, key=lambda item: item.stat().st_mtime if item.exists() else 0.0, reverse=True)[:limit]


def _git_poll_events(config: AgentConfig, state: dict[str, Any]) -> list[CollectorEvent]:
    snapshot = _git_snapshot(config.workspace)
    if snapshot is None:
        return []
    git_state = state.setdefault("git_activity", {})
    previous = git_state.get("snapshot", {})
    git_state["snapshot"] = snapshot
    if not isinstance(previous, dict) or not previous:
        return []
    events: list[CollectorEvent] = []
    if str(previous.get("branch") or "") != str(snapshot.get("branch") or ""):
        events.append(_git_event("git_branch_changed", "Git branch changed.", snapshot))
    if str(previous.get("head") or "") != str(snapshot.get("head") or ""):
        events.append(_git_event("commit_created", "Git HEAD changed.", snapshot))
    if int(snapshot.get("conflict_count") or 0) > 0 and int(previous.get("conflict_count") or 0) != int(snapshot.get("conflict_count") or 0):
        events.append(_git_event("merge_conflict_detected", "Git merge conflict detected.", snapshot))
    previous_dirty = bool(previous.get("dirty", False))
    current_dirty = bool(snapshot.get("dirty", False))
    if previous_dirty != current_dirty:
        events.append(
            _git_event(
                "working_tree_dirty" if current_dirty else "working_tree_clean",
                "Git working tree became dirty." if current_dirty else "Git working tree became clean.",
                snapshot,
            )
        )
    return events


def _git_event(stimulus_type: str, text: str, snapshot: dict[str, Any]) -> CollectorEvent:
    repository_digest = hashlib.sha256(str(snapshot.get("repository", "")).encode("utf-8")).hexdigest()[:16]
    return CollectorEvent(
        collector="git_activity",
        source="activity",
        stimulus_type=stimulus_type,
        text=text,
        metadata={
            "repository": str(snapshot.get("repository", "")),
            "branch": str(snapshot.get("branch", "")),
            "dirty": bool(snapshot.get("dirty", False)),
            "conflict_count": int(snapshot.get("conflict_count") or 0),
        },
        payload={
            "head": str(snapshot.get("head", ""))[:40],
            "status_counts": snapshot.get("status_counts", {}),
        },
        signature=f"git:{stimulus_type}:{repository_digest}:{snapshot.get('branch', '')}:{snapshot.get('head', '')}:{snapshot.get('dirty', False)}:{snapshot.get('conflict_count', 0)}",
    )


def _git_snapshot(workspace: Path) -> dict[str, Any] | None:
    root = _git(["rev-parse", "--show-toplevel"], workspace)
    if root is None:
        return None
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], workspace) or ""
    head = _git(["rev-parse", "HEAD"], workspace) or ""
    status = _git(["status", "--porcelain"], workspace) or ""
    status_counts: dict[str, int] = {}
    conflict_count = 0
    for line in status.splitlines():
        code = line[:2]
        status_counts[code] = status_counts.get(code, 0) + 1
        if "U" in code or code in {"AA", "DD"}:
            conflict_count += 1
    return {
        "repository": root,
        "branch": branch,
        "head": head,
        "dirty": bool(status.strip()),
        "conflict_count": conflict_count,
        "status_counts": status_counts,
    }


def _git(args: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()
