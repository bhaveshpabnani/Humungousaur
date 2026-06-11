from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


PYTHON_CODE_LIMIT_CHARS = 20_000
PYTHON_TIMEOUT_SECONDS = 30
PYTHON_OUTPUT_LIMIT_CHARS = 8_000
PYTHON_ARTIFACT_TEXT_LIMIT = 12_000
PYTHON_SESSION_REPLAY_LIMIT_CHARS = 80_000
PYTHON_INTERPRETER_DIRNAME = "python-interpreter"
PYTHON_SESSION_DIRNAME = "python-interpreter-sessions"
PYTHON_IMPORT_MODES = ("stdlib", "allowlist", "all")
PYTHON_SANDBOX_PROFILES = ("read_only", "data_write", "workspace_write", "trusted_dev")
PYTHON_INTERNAL_RUN_FILES = {"runner.py", "user_code.py", "current_code.py", "policy.json", "manifest.json"}
PYTHON_TEXT_ARTIFACT_SUFFIXES = {
    ".csv",
    ".css",
    ".html",
    ".ini",
    ".json",
    ".js",
    ".log",
    ".md",
    ".py",
    ".toml",
    ".tsv",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


class PythonInterpreterTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="python_interpreter",
            description=(
                "Run bounded Python analysis code in a child process with audit-hook filesystem, subprocess, "
                "and network controls. Use this for Open Interpreter-style local data analysis after approval."
            ),
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "code": {"type": "string", "description": "Python code to execute."},
                    "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": PYTHON_TIMEOUT_SECONDS},
                    "network_enabled": {
                        "type": "boolean",
                        "description": "Allow network socket events in the child process when explicitly approved.",
                    },
                    "import_mode": {
                        "type": "string",
                        "enum": list(PYTHON_IMPORT_MODES),
                        "description": "Import policy: stdlib only, stdlib plus allowed_imports, or all imports.",
                    },
                    "allowed_imports": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 50,
                        "description": "Top-level third-party or local package names allowed when import_mode is allowlist.",
                    },
                    "sandbox_profile": {
                        "type": "string",
                        "enum": list(PYTHON_SANDBOX_PROFILES),
                        "description": (
                            "Filesystem write profile: read_only only writes run artifacts, data_write writes configured "
                            "data roots, workspace_write can edit the workspace, and trusted_dev can write allowed roots."
                        ),
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Optional Python interpreter session id to attach this run to.",
                    },
                    "session_label": {
                        "type": "string",
                        "description": "Optional label used when creating or updating a Python interpreter session.",
                    },
                    "replay_session": {
                        "type": "boolean",
                        "description": "Replay prior successful session cells before the current code for variable continuity.",
                    },
                    "reason": {"type": "string", "description": "Why local Python execution is needed."},
                },
                required=["code", "reason"],
            ),
            capability_group="code",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        code = str(tool_input.get("code", ""))
        if not code.strip():
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Python code is required.")
        if len(code) > PYTHON_CODE_LIMIT_CHARS:
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Python code exceeds configured limit.")
        timeout_seconds = max(1, min(int(tool_input.get("timeout_seconds") or 10), PYTHON_TIMEOUT_SECONDS))
        network_enabled = bool(tool_input.get("network_enabled", False))
        import_mode = str(tool_input.get("import_mode") or "stdlib")
        if import_mode not in PYTHON_IMPORT_MODES:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unsupported import mode: {import_mode}.")
        sandbox_profile = str(tool_input.get("sandbox_profile") or "data_write")
        if sandbox_profile not in PYTHON_SANDBOX_PROFILES:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unsupported sandbox profile: {sandbox_profile}.")
        try:
            allowed_imports = _normalize_import_names(tool_input.get("allowed_imports") or [])
        except ValueError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Invalid allowed import name.", error=str(exc))
        session_id = str(tool_input.get("session_id") or "").strip()
        session_label = str(tool_input.get("session_label") or "").strip()
        replay_session = bool(tool_input.get("replay_session", False))
        session: dict[str, Any] | None = None
        replayed_run_ids: list[str] = []
        if session_id:
            session = _read_session(config, session_id)
            if session is None:
                return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Python interpreter session not found: {session_id}")
        elif session_label:
            session_id = _new_session_id()
            session = _new_session(session_id, session_label)
        if session is not None and session_label:
            session["label"] = session_label[:120]
        execution_code = code
        if session is not None and replay_session:
            execution_code, replayed_run_ids = _session_replay_code(config, session, code)
            if len(execution_code) > PYTHON_SESSION_REPLAY_LIMIT_CHARS:
                return ToolResult(
                    self.name,
                    ActionStatus.BLOCKED,
                    self.risk_level,
                    "Python session replay exceeds configured code limit.",
                    {"session_id": session_id, "replay_code_chars": len(execution_code)},
                )
        created_at = datetime.now().astimezone().isoformat()
        reason = str(tool_input.get("reason", "")).strip()
        run_id = f"python-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        run_dir = (python_interpreter_root(config) / run_id).resolve()
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would execute bounded Python code after approval.",
                {
                    "run_id": run_id,
                    "run_dir": str(run_dir),
                    "timeout_seconds": timeout_seconds,
                    "network_enabled": network_enabled,
                    "import_mode": import_mode,
                    "allowed_imports": sorted(allowed_imports),
                    "sandbox_profile": sandbox_profile,
                    "session_id": session_id or None,
                    "session_label": session.get("label") if session else None,
                    "replay_session": replay_session,
                    "replayed_run_ids": replayed_run_ids,
                    "code_not_executed": True,
                },
            )
        run_dir.mkdir(parents=True, exist_ok=True)
        code_path = run_dir / "user_code.py"
        current_code_path = run_dir / "current_code.py"
        policy_path = run_dir / "policy.json"
        wrapper_path = run_dir / "runner.py"
        code_path.write_text(execution_code, encoding="utf-8")
        current_code_path.write_text(code, encoding="utf-8")
        read_roots = _unique_paths([*config.allowed_read_roots, run_dir])
        write_roots = _write_roots_for_sandbox_profile(config, run_dir, sandbox_profile)
        policy = {
            "read_roots": [str(path) for path in read_roots],
            "write_roots": [str(path) for path in write_roots],
            "sandbox_profile": sandbox_profile,
            "network_enabled": network_enabled,
            "subprocess_enabled": False,
            "import_mode": import_mode,
            "allowed_imports": sorted(allowed_imports),
        }
        policy_path.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        wrapper_path.write_text(_runner_source(), encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["UMANG_RUN_DIR"] = str(run_dir)
        env["UMANG_WORKSPACE"] = str(config.workspace)
        env["UMANG_DATA_DIR"] = str(config.data_dir)
        try:
            completed = subprocess.run(
                [sys.executable, str(wrapper_path), str(policy_path), str(code_path)],
                cwd=config.workspace,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=False,
                check=False,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
            manifest = _write_run_manifest(
                config=config,
                run_id=run_id,
                run_dir=run_dir,
                created_at=created_at,
                code_path=code_path,
                policy_path=policy_path,
                wrapper_path=wrapper_path,
                status=ActionStatus.FAILED,
                returncode=None,
                timeout_seconds=timeout_seconds,
                timed_out=True,
                network_enabled=network_enabled,
                import_mode=import_mode,
                allowed_imports=allowed_imports,
                sandbox_profile=sandbox_profile,
                read_roots=read_roots,
                write_roots=write_roots,
                session_id=session_id or None,
                session_label=session.get("label") if session else None,
                replay_session=replay_session,
                replayed_run_ids=replayed_run_ids,
                reason=reason,
                stdout=stdout,
                stderr=stderr,
            )
            if session is not None:
                _append_session_run(
                    config,
                    session,
                    {
                        "run_id": run_id,
                        "status": ActionStatus.FAILED.value,
                        "created_at": created_at,
                        "reason": reason,
                        "manifest_path": manifest["manifest_path"],
                        "artifact_count": len(manifest["artifacts"]),
                        "returncode": None,
                        "timed_out": True,
                        "code_chars": len(code),
                        "execution_code_chars": len(execution_code),
                        "replay_session": replay_session,
                        "replayed_run_ids": replayed_run_ids,
                    },
                )
            return ToolResult(
                self.name,
                ActionStatus.FAILED,
                self.risk_level,
                f"Python execution timed out after {timeout_seconds} second(s).",
                {
                    "run_id": run_id,
                    "run_dir": str(run_dir),
                    "timeout_seconds": timeout_seconds,
                    "timed_out": True,
                    "stdout": stdout[-PYTHON_OUTPUT_LIMIT_CHARS:],
                    "stderr": stderr[-PYTHON_OUTPUT_LIMIT_CHARS:],
                    "import_mode": import_mode,
                    "allowed_imports": sorted(allowed_imports),
                    "sandbox_profile": sandbox_profile,
                    "session_id": session_id or None,
                    "session_label": session.get("label") if session else None,
                    "replay_session": replay_session,
                    "replayed_run_ids": replayed_run_ids,
                    "manifest_path": manifest["manifest_path"],
                    "artifact_count": len(manifest["artifacts"]),
                },
                error="Python execution timed out.",
            )
        status = ActionStatus.SUCCEEDED if completed.returncode == 0 else ActionStatus.FAILED
        manifest = _write_run_manifest(
            config=config,
            run_id=run_id,
            run_dir=run_dir,
            created_at=created_at,
            code_path=code_path,
            policy_path=policy_path,
            wrapper_path=wrapper_path,
            status=status,
            returncode=completed.returncode,
            timeout_seconds=timeout_seconds,
            timed_out=False,
            network_enabled=network_enabled,
            import_mode=import_mode,
            allowed_imports=allowed_imports,
            sandbox_profile=sandbox_profile,
            read_roots=read_roots,
            write_roots=write_roots,
            session_id=session_id or None,
            session_label=session.get("label") if session else None,
            replay_session=replay_session,
            replayed_run_ids=replayed_run_ids,
            reason=reason,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        if session is not None:
            _append_session_run(
                config,
                session,
                {
                    "run_id": run_id,
                    "status": status.value,
                    "created_at": created_at,
                    "reason": reason,
                    "manifest_path": manifest["manifest_path"],
                    "artifact_count": len(manifest["artifacts"]),
                    "returncode": completed.returncode,
                    "code_chars": len(code),
                    "execution_code_chars": len(execution_code),
                    "replay_session": replay_session,
                    "replayed_run_ids": replayed_run_ids,
                },
            )
        return ToolResult(
            self.name,
            status,
            self.risk_level,
            f"Python execution exited with code {completed.returncode}.",
            {
                "run_id": run_id,
                "run_dir": str(run_dir),
                "returncode": completed.returncode,
                "timeout_seconds": timeout_seconds,
                "network_enabled": network_enabled,
                "import_mode": import_mode,
                "allowed_imports": sorted(allowed_imports),
                "sandbox_profile": sandbox_profile,
                "session_id": session_id or None,
                "session_label": session.get("label") if session else None,
                "replay_session": replay_session,
                "replayed_run_ids": replayed_run_ids,
                "stdout": completed.stdout[-PYTHON_OUTPUT_LIMIT_CHARS:],
                "stderr": completed.stderr[-PYTHON_OUTPUT_LIMIT_CHARS:],
                "reason": reason,
                "manifest_path": manifest["manifest_path"],
                "artifact_count": len(manifest["artifacts"]),
                "source": "python_interpreter",
            },
            None if status == ActionStatus.SUCCEEDED else completed.stderr[-1000:],
        )


class PythonInterpreterRunsTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="python_interpreter_runs",
            description=(
                "List recent bounded Python interpreter run manifests, including status and artifact metadata "
                "without returning full code, stdout, stderr, or artifact contents."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
            ),
            capability_group="code",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = max(1, min(int(tool_input.get("limit") or 10), 50))
        runs = _list_run_manifests(config, limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(runs)} Python interpreter run manifest(s).",
            {"runs": runs, "root": str(python_interpreter_root(config)), "limit": limit},
        )


class PythonInterpreterRunTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="python_interpreter_run",
            description=(
                "Read one bounded Python interpreter run manifest by run id, including artifact names and "
                "bounded stdout/stderr tails but not full artifact contents."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {"run_id": {"type": "string", "description": "Interpreter run id returned by python_interpreter."}},
                required=["run_id"],
            ),
            capability_group="code",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        run_id = str(tool_input.get("run_id", "")).strip()
        manifest = _read_run_manifest(config, run_id)
        if manifest is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Python run not found: {run_id}")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Loaded Python interpreter run {manifest.get('run_id')}.",
            {"run": manifest},
        )


class PythonInterpreterArtifactTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="python_interpreter_artifact",
            description=(
                "Read a text artifact from a bounded Python interpreter run by manifest-listed filename. "
                "Only text artifacts from that run directory are returned, with a strict character limit."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "run_id": {"type": "string", "description": "Interpreter run id returned by python_interpreter."},
                    "filename": {"type": "string", "description": "Manifest-listed artifact filename to read."},
                    "max_chars": {"type": "integer", "minimum": 1, "maximum": PYTHON_ARTIFACT_TEXT_LIMIT},
                },
                required=["run_id", "filename"],
            ),
            capability_group="code",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        run_id = str(tool_input.get("run_id", "")).strip()
        filename = str(tool_input.get("filename", "")).strip()
        max_chars = max(1, min(int(tool_input.get("max_chars") or PYTHON_ARTIFACT_TEXT_LIMIT), PYTHON_ARTIFACT_TEXT_LIMIT))
        manifest = _read_run_manifest(config, run_id)
        if manifest is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Python run not found: {run_id}")
        artifact, path = _artifact_from_manifest(manifest, filename)
        if artifact is None or path is None:
            return ToolResult(
                self.name,
                ActionStatus.BLOCKED,
                self.risk_level,
                "Artifact access is limited to files listed in the interpreter run manifest.",
            )
        if artifact.get("kind") != "text":
            return ToolResult(
                self.name,
                ActionStatus.BLOCKED,
                self.risk_level,
                "Only text interpreter artifacts can be read inline.",
                {"artifact": artifact},
            )
        if not path.exists() or not path.is_file():
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Artifact no longer exists: {filename}")
        text = path.read_text(encoding="utf-8", errors="replace")
        truncated = len(text) > max_chars
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Read text artifact {filename} from Python interpreter run {run_id}.",
            {
                "run_id": run_id,
                "filename": filename,
                "content": text[:max_chars],
                "truncated": truncated,
                "max_chars": max_chars,
                "size_bytes": artifact.get("size_bytes"),
            },
        )


class PythonInterpreterSessionsTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="python_interpreter_sessions",
            description=(
                "List Python interpreter sessions with run counts and latest status, without returning code, "
                "stdout, stderr, or artifact contents."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
            ),
            capability_group="code",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = max(1, min(int(tool_input.get("limit") or 10), 50))
        sessions = _list_sessions(config, limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(sessions)} Python interpreter session(s).",
            {"sessions": sessions, "root": str(python_interpreter_sessions_root(config)), "limit": limit},
        )


class PythonInterpreterSessionTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="python_interpreter_session",
            description=(
                "Read one Python interpreter session manifest by session id, including bounded run metadata "
                "and replay lineage without returning code bodies or artifacts."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {"session_id": {"type": "string", "description": "Interpreter session id."}},
                required=["session_id"],
            ),
            capability_group="code",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        session_id = str(tool_input.get("session_id", "")).strip()
        session = _read_session(config, session_id)
        if session is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Python interpreter session not found: {session_id}")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Loaded Python interpreter session {session.get('session_id')}.",
            {"session": _summarize_session(session, include_runs=True)},
        )


def default_code_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        PythonInterpreterTool(),
        PythonInterpreterRunsTool(),
        PythonInterpreterRunTool(),
        PythonInterpreterArtifactTool(),
        PythonInterpreterSessionsTool(),
        PythonInterpreterSessionTool(),
    ]
    return {tool.name: tool for tool in tools}


def python_interpreter_root(config: AgentConfig) -> Path:
    return (config.data_dir / PYTHON_INTERPRETER_DIRNAME).resolve()


def python_interpreter_sessions_root(config: AgentConfig) -> Path:
    return (config.data_dir / PYTHON_SESSION_DIRNAME).resolve()


def _write_run_manifest(
    *,
    config: AgentConfig,
    run_id: str,
    run_dir: Path,
    created_at: str,
    code_path: Path,
    policy_path: Path,
    wrapper_path: Path,
    status: ActionStatus,
    returncode: int | None,
    timeout_seconds: int,
    timed_out: bool,
    network_enabled: bool,
    import_mode: str,
    allowed_imports: set[str],
    sandbox_profile: str,
    read_roots: list[Path],
    write_roots: list[Path],
    session_id: str | None,
    session_label: str | None,
    replay_session: bool,
    replayed_run_ids: list[str],
    reason: str,
    stdout: str,
    stderr: str,
) -> dict[str, Any]:
    artifacts = _scan_run_artifacts(run_dir)
    manifest = {
        "run_id": run_id,
        "created_at": created_at,
        "updated_at": datetime.now().astimezone().isoformat(),
        "workspace": str(config.workspace),
        "data_dir": str(config.data_dir),
        "run_dir": str(run_dir),
        "code_path": str(code_path),
        "policy_path": str(policy_path),
        "wrapper_path": str(wrapper_path),
        "returncode": returncode,
        "status": status.value,
        "timeout_seconds": timeout_seconds,
        "timed_out": timed_out,
        "network_enabled": network_enabled,
        "import_mode": import_mode,
        "allowed_imports": sorted(allowed_imports),
        "sandbox_profile": sandbox_profile,
        "read_roots": [str(path) for path in read_roots],
        "write_roots": [str(path) for path in write_roots],
        "session_id": session_id,
        "session_label": session_label,
        "replay_session": replay_session,
        "replayed_run_ids": replayed_run_ids,
        "reason": reason,
        "stdout_tail": stdout[-PYTHON_OUTPUT_LIMIT_CHARS:],
        "stderr_tail": stderr[-PYTHON_OUTPUT_LIMIT_CHARS:],
        "stdout_chars": len(stdout),
        "stderr_chars": len(stderr),
        "artifacts": artifacts,
        "artifact_bytes_served": False,
        "source": "python_interpreter",
    }
    manifest_path = run_dir / "manifest.json"
    manifest["manifest_path"] = str(manifest_path)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _scan_run_artifacts(run_dir: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file() or path.name in PYTHON_INTERNAL_RUN_FILES:
            continue
        relative = path.relative_to(run_dir).as_posix()
        stat = path.stat()
        artifacts.append(
            {
                "name": relative,
                "path": str(path),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
                "kind": "text" if path.suffix.lower() in PYTHON_TEXT_ARTIFACT_SUFFIXES else "binary",
                "returned_inline": False,
            }
        )
    return artifacts


def _list_run_manifests(config: AgentConfig, limit: int) -> list[dict[str, Any]]:
    root = python_interpreter_root(config)
    if not root.exists():
        return []
    manifests: list[dict[str, Any]] = []
    for manifest_path in sorted(root.glob("python-*/manifest.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        manifest = _load_manifest_file(manifest_path)
        if manifest is None:
            continue
        manifests.append(_summarize_manifest(manifest))
        if len(manifests) >= limit:
            break
    return manifests


def _read_run_manifest(config: AgentConfig, run_id: str) -> dict[str, Any] | None:
    safe_run_id = _safe_run_id(run_id)
    if safe_run_id is None:
        return None
    manifest_path = python_interpreter_root(config) / safe_run_id / "manifest.json"
    manifest = _load_manifest_file(manifest_path)
    if manifest is None:
        return None
    run_dir = Path(str(manifest.get("run_dir", ""))).resolve()
    root = python_interpreter_root(config)
    if not _path_within(run_dir, root):
        return None
    return manifest


def _safe_run_id(run_id: str) -> str | None:
    candidate = run_id.strip()
    if not candidate or candidate != Path(candidate).name or not candidate.startswith("python-"):
        return None
    if not all(char.isalnum() or char in {"-", "_"} for char in candidate):
        return None
    return candidate


def _load_manifest_file(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists() or not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _summarize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    artifacts = manifest.get("artifacts", [])
    return {
        "run_id": manifest.get("run_id"),
        "created_at": manifest.get("created_at"),
        "updated_at": manifest.get("updated_at"),
        "status": manifest.get("status"),
        "returncode": manifest.get("returncode"),
        "timed_out": manifest.get("timed_out", False),
        "timeout_seconds": manifest.get("timeout_seconds"),
        "network_enabled": manifest.get("network_enabled", False),
        "import_mode": manifest.get("import_mode", "unknown"),
        "allowed_imports": manifest.get("allowed_imports", []),
        "sandbox_profile": manifest.get("sandbox_profile", "unknown"),
        "session_id": manifest.get("session_id"),
        "session_label": manifest.get("session_label"),
        "replay_session": manifest.get("replay_session", False),
        "replayed_run_ids": manifest.get("replayed_run_ids", []),
        "reason": manifest.get("reason", ""),
        "run_dir": manifest.get("run_dir"),
        "manifest_path": manifest.get("manifest_path"),
        "artifact_count": len(artifacts) if isinstance(artifacts, list) else 0,
        "artifacts": [
            {
                "name": item.get("name"),
                "size_bytes": item.get("size_bytes"),
                "kind": item.get("kind"),
                "modified_at": item.get("modified_at"),
            }
            for item in artifacts
            if isinstance(item, dict)
        ],
        "stdout_tail": manifest.get("stdout_tail", ""),
        "stderr_tail": manifest.get("stderr_tail", ""),
        "artifact_bytes_served": False,
    }


def _new_session_id() -> str:
    return f"py-session-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"


def _new_session(session_id: str, label: str) -> dict[str, Any]:
    now = datetime.now().astimezone().isoformat()
    return {
        "session_id": session_id,
        "label": label[:120] or session_id,
        "created_at": now,
        "updated_at": now,
        "runs": [],
        "source": "python_interpreter_session",
    }


def _safe_session_id(session_id: str) -> str | None:
    candidate = session_id.strip()
    if not candidate or candidate != Path(candidate).name or not candidate.startswith("py-session-"):
        return None
    if not all(char.isalnum() or char in {"-", "_"} for char in candidate):
        return None
    return candidate


def _session_path(config: AgentConfig, session_id: str) -> Path | None:
    safe_session_id = _safe_session_id(session_id)
    if safe_session_id is None:
        return None
    return python_interpreter_sessions_root(config) / f"{safe_session_id}.json"


def _read_session(config: AgentConfig, session_id: str) -> dict[str, Any] | None:
    path = _session_path(config, session_id)
    if path is None:
        return None
    try:
        if not path.exists() or not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("session_id") != _safe_session_id(session_id):
        return None
    return payload


def _write_session(config: AgentConfig, session: dict[str, Any]) -> None:
    session_id = str(session.get("session_id", ""))
    path = _session_path(config, session_id)
    if path is None:
        raise ValueError("Invalid Python interpreter session id.")
    path.parent.mkdir(parents=True, exist_ok=True)
    session["updated_at"] = datetime.now().astimezone().isoformat()
    path.write_text(json.dumps(session, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_session_run(config: AgentConfig, session: dict[str, Any], run: dict[str, Any]) -> None:
    runs = session.get("runs")
    if not isinstance(runs, list):
        runs = []
    runs.append(run)
    session["runs"] = runs[-200:]
    _write_session(config, session)


def _list_sessions(config: AgentConfig, limit: int) -> list[dict[str, Any]]:
    root = python_interpreter_sessions_root(config)
    if not root.exists():
        return []
    sessions: list[dict[str, Any]] = []
    for path in sorted(root.glob("py-session-*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        session = _load_session_file(path)
        if session is None:
            continue
        sessions.append(_summarize_session(session, include_runs=False))
        if len(sessions) >= limit:
            break
    return sessions


def _load_session_file(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _summarize_session(session: dict[str, Any], include_runs: bool) -> dict[str, Any]:
    runs = [run for run in session.get("runs", []) if isinstance(run, dict)]
    latest = runs[-1] if runs else {}
    summary = {
        "session_id": session.get("session_id"),
        "label": session.get("label", ""),
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
        "run_count": len(runs),
        "latest_run_id": latest.get("run_id"),
        "latest_status": latest.get("status"),
        "latest_reason": latest.get("reason", ""),
        "code_bodies_served": False,
        "artifact_bytes_served": False,
    }
    if include_runs:
        summary["runs"] = [
            {
                "run_id": run.get("run_id"),
                "status": run.get("status"),
                "created_at": run.get("created_at"),
                "reason": run.get("reason", ""),
                "manifest_path": run.get("manifest_path"),
                "artifact_count": run.get("artifact_count", 0),
                "returncode": run.get("returncode"),
                "timed_out": run.get("timed_out", False),
                "code_chars": run.get("code_chars", 0),
                "execution_code_chars": run.get("execution_code_chars", 0),
                "replay_session": run.get("replay_session", False),
                "replayed_run_ids": run.get("replayed_run_ids", []),
            }
            for run in runs
        ]
    return summary


def _session_replay_code(config: AgentConfig, session: dict[str, Any], current_code: str) -> tuple[str, list[str]]:
    cells: list[str] = []
    replayed_run_ids: list[str] = []
    for run in session.get("runs", []):
        if not isinstance(run, dict) or run.get("status") != ActionStatus.SUCCEEDED.value:
            continue
        manifest_path = Path(str(run.get("manifest_path", ""))).resolve()
        if not _path_within(manifest_path, python_interpreter_root(config)):
            continue
        manifest = _load_manifest_file(manifest_path)
        if manifest is None:
            continue
        run_dir = Path(str(manifest.get("run_dir", ""))).resolve()
        if not _path_within(run_dir, python_interpreter_root(config)):
            continue
        current_code_path = (run_dir / "current_code.py").resolve()
        if not _path_within(current_code_path, run_dir) or not current_code_path.exists():
            continue
        try:
            cell = current_code_path.read_text(encoding="utf-8")
        except OSError:
            continue
        run_id = str(run.get("run_id", "unknown"))
        cells.append(f"\n# --- Janus replay cell: {run_id} ---\n{cell}\n")
        replayed_run_ids.append(run_id)
    cells.append(f"\n# --- Janus current cell ---\n{current_code}\n")
    return "".join(cells), replayed_run_ids


def _artifact_from_manifest(manifest: dict[str, Any], filename: str) -> tuple[dict[str, Any] | None, Path | None]:
    if not filename or filename != filename.replace("\\", "/").strip("/"):
        return None, None
    if any(part in {"", ".", ".."} for part in filename.split("/")):
        return None, None
    run_dir = Path(str(manifest.get("run_dir", ""))).resolve()
    for item in manifest.get("artifacts", []):
        if not isinstance(item, dict) or item.get("name") != filename:
            continue
        artifact_path = (run_dir / filename).resolve()
        if not _path_within(artifact_path, run_dir):
            return None, None
        return item, artifact_path
    return None, None


def _path_within(path: Path, root: Path) -> bool:
    root = root.resolve()
    path = path.resolve()
    return path == root or root in path.parents


def _normalize_import_names(values: Any) -> set[str]:
    if not isinstance(values, list):
        raise ValueError("allowed_imports must be an array of package names.")
    normalized: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise ValueError("allowed_imports entries must be strings.")
        package = value.strip()
        if not package:
            continue
        parts = package.split(".")
        if not all(part.isidentifier() for part in parts):
            raise ValueError(f"Invalid import name: {package}.")
        normalized.add(parts[0])
    return normalized


def _write_roots_for_sandbox_profile(config: AgentConfig, run_dir: Path, sandbox_profile: str) -> list[Path]:
    if sandbox_profile == "read_only":
        return _unique_paths([run_dir])
    if sandbox_profile == "workspace_write":
        return _unique_paths([*config.allowed_write_roots, config.workspace, run_dir])
    if sandbox_profile == "trusted_dev":
        return _unique_paths([*config.allowed_write_roots, *config.allowed_read_roots, config.workspace, config.data_dir, run_dir])
    return _unique_paths([*config.allowed_write_roots, run_dir])


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


def _runner_source() -> str:
    return r'''
from __future__ import annotations

import builtins
import json
import os
import runpy
import sys
import sysconfig
from pathlib import Path


policy = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
code_path = Path(sys.argv[2]).resolve()
stdlib_roots = tuple(
    Path(value).resolve()
    for value in {
        sys.prefix,
        sys.base_prefix,
        sys.exec_prefix,
        sysconfig.get_paths().get("stdlib", ""),
        sysconfig.get_paths().get("purelib", ""),
        sysconfig.get_paths().get("platlib", ""),
    }
    if value
)
read_roots = tuple(Path(path).resolve() for path in policy["read_roots"]) + stdlib_roots
write_roots = tuple(Path(path).resolve() for path in policy["write_roots"])
network_enabled = bool(policy.get("network_enabled", False))
subprocess_enabled = bool(policy.get("subprocess_enabled", False))
import_mode = str(policy.get("import_mode", "stdlib"))
allowed_imports = set(policy.get("allowed_imports", []))
stdlib_modules = set(getattr(sys, "stdlib_module_names", set())) | set(sys.builtin_module_names)
workspace_path = str(Path.cwd())
if workspace_path not in sys.path:
    sys.path.insert(0, workspace_path)


def is_within(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def resolve_path(value) -> Path | None:
    if value is None or isinstance(value, int):
        return None
    try:
        path = Path(os.fspath(value)).expanduser()
    except TypeError:
        return None
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def flags_write(flags: int | None) -> bool:
    if flags is None:
        return False
    write_bits = (
        getattr(os, "O_WRONLY", 0)
        | getattr(os, "O_RDWR", 0)
        | getattr(os, "O_CREAT", 0)
        | getattr(os, "O_TRUNC", 0)
        | getattr(os, "O_APPEND", 0)
    )
    return bool(flags & write_bits)


def mode_write(mode: str | None) -> bool:
    return bool(mode and any(marker in mode for marker in ("w", "a", "x", "+")))


def assert_read_allowed(path: Path) -> None:
    if not is_within(path, read_roots):
        raise PermissionError(f"Python sandbox blocked read outside allowed roots: {path}")


def assert_write_allowed(path: Path) -> None:
    if not is_within(path, write_roots):
        raise PermissionError(f"Python sandbox blocked write outside allowed roots: {path}")


def top_level_import(name: str) -> str:
    return str(name).split(".", 1)[0]


def assert_import_allowed(name: str) -> None:
    top_level = top_level_import(name)
    if not top_level or import_mode == "all":
        return
    if top_level in stdlib_modules or top_level.startswith("_"):
        return
    if import_mode == "allowlist" and top_level in allowed_imports:
        return
    raise PermissionError(f"Python sandbox blocked import outside allowed packages: {top_level}")


def audit_hook(event: str, args) -> None:
    if event.startswith("socket.") and not network_enabled:
        raise PermissionError(f"Python sandbox blocked network event: {event}")
    if event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.spawn"} and not subprocess_enabled:
        raise PermissionError(f"Python sandbox blocked subprocess event: {event}")
    if event == "open":
        path = resolve_path(args[0] if args else None)
        if path is None:
            return
        mode = args[1] if len(args) > 1 and isinstance(args[1], str) else None
        flags = args[2] if len(args) > 2 and isinstance(args[2], int) else None
        if mode_write(mode) or flags_write(flags):
            assert_write_allowed(path)
        else:
            assert_read_allowed(path)
    if event in {"os.remove", "os.unlink", "os.rmdir"}:
        path = resolve_path(args[0] if args else None)
        if path is not None:
            assert_write_allowed(path)
    if event in {"os.rename", "os.replace"}:
        for value in args[:2]:
            path = resolve_path(value)
            if path is not None:
                assert_write_allowed(path)


def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level == 0:
        assert_import_allowed(str(name))
    return original_import(name, globals, locals, fromlist, level)


def guarded_open(file, mode="r", *args, **kwargs):
    path = resolve_path(file)
    if path is not None:
        if mode_write(str(mode)):
            assert_write_allowed(path)
        else:
            assert_read_allowed(path)
    return original_open(file, mode, *args, **kwargs)


original_open = builtins.open
original_import = builtins.__import__
builtins.open = guarded_open
builtins.__import__ = guarded_import
sys.addaudithook(audit_hook)
runpy.run_path(str(code_path), run_name="__main__")
'''
