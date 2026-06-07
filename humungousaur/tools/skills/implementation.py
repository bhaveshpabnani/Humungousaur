from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from humungousaur.cognition.skills import SkillStore
from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


SKILL_FILE_LIMIT = 300
SKILL_READ_LIMIT = 80_000
SKILL_SCRIPT_READ_LIMIT = 200_000
SKILL_SCRIPT_OUTPUT_LIMIT = 20_000
SKILL_SCRIPT_TIMEOUT_SECONDS = 60
SKILL_SCRIPT_METADATA_PREFIX = "# humungousaur-skill-script:"
SKILL_AUDIT_LIMIT = 300


class AgentSkillCatalogTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="agent_skill_catalog",
            description=(
                "List workspace SKILL.md instruction packs and durable cognitive skills. "
                "Use this to discover reusable workflows without using keyword routing."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "source": {"type": "string", "enum": ["all", "workspace", "memory"], "description": "Skill source to inspect."},
                    "include_retired": {"type": "boolean", "description": "Include retired durable skills from memory."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 300},
                }
            ),
            capability_group="skills",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        source = str(tool_input.get("source") or "all").strip().lower()
        if source not in {"all", "workspace", "memory"}:
            source = "all"
        limit = max(1, min(int(tool_input.get("limit") or 50), SKILL_FILE_LIMIT))
        payload: dict[str, Any] = {"workspace_skills": [], "memory_skills": [], "source": source}
        if source in {"all", "workspace"}:
            payload["workspace_skills"] = [skill.summary() for skill in discover_workspace_skills(config)[:limit]]
        if source in {"all", "memory"}:
            store = SkillStore(config.normalized().skill_library_path)
            payload["memory_skills"] = [
                asdict(skill) for skill in store.list(limit=limit, include_retired=bool(tool_input.get("include_retired", False)))
            ]
        count = len(payload["workspace_skills"]) + len(payload["memory_skills"])
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {count} agent skill record(s).",
            payload,
        )


class AgentSkillReadTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="agent_skill_read",
            description="Read a bounded workspace SKILL.md pack by exact skill_id from agent_skill_catalog.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {"skill_id": {"type": "string", "description": "Exact workspace skill id."}},
                required=["skill_id"],
            ),
            capability_group="skills",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        skill_id = str(tool_input.get("skill_id") or "").strip()
        skill = workspace_skill_by_id(config, skill_id)
        if skill is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown workspace skill_id: {skill_id}")
        if skill.path.stat().st_size > min(config.max_file_bytes, SKILL_READ_LIMIT):
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Skill file exceeds configured read limit.")
        content = skill.path.read_text(encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Read workspace skill {skill.name}.",
            {"skill": skill.summary(), "content": content},
        )


class AgentSkillImportTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="agent_skill_import",
            description=(
                "Import exact workspace SKILL.md packs into the durable cognitive skill store. "
                "This preserves the skill as reusable evidence; it does not create deterministic task routes."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "skill_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                    "reason": {"type": "string", "description": "Why these skills should be imported."},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                required=["skill_ids", "reason"],
            ),
            capability_group="skills",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        skill_ids = [str(item).strip() for item in tool_input.get("skill_ids", []) if str(item).strip()]
        if not skill_ids:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "At least one exact skill_id is required.")
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would import workspace skills.", dict(tool_input))
        imported = []
        missing = []
        store = SkillStore(config.normalized().skill_library_path)
        for skill_id in skill_ids[:20]:
            skill = workspace_skill_by_id(config, skill_id)
            if skill is None:
                missing.append(skill_id)
                continue
            record = store.upsert(
                name=f"Workspace: {skill.name}",
                purpose=skill.description or f"Reusable workflow from {skill.relative_path}",
                when_to_use=skill.description or "Use when model reasoning selects this reusable workflow from structured context.",
                tools=[],
                verification_steps=["Read the source SKILL.md before applying specialized workflow details."],
                failure_modes=["Using the skill as an intent router instead of evidence-guided reusable workflow knowledge."],
                evidence_refs=[f"workspace_skill:{skill.skill_id}", f"path:{skill.relative_path}"],
                confidence=float(tool_input.get("confidence", 0.7)),
            )
            imported.append(asdict(record))
        status = ActionStatus.SUCCEEDED if imported else ActionStatus.FAILED
        return ToolResult(
            self.name,
            status,
            self.risk_level,
            f"Imported {len(imported)} workspace skill(s).",
            {"imported_skills": imported, "missing_skill_ids": missing},
        )


class AgentSkillScriptCatalogTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="agent_skill_script_catalog",
            description=(
                "List Humungousaur-owned executable scripts bundled under workspace skill scripts/ directories. "
                "Scripts are model-selected capability helpers, not deterministic intent routes."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "skill_id": {"type": "string", "description": "Optional exact workspace skill id from agent_skill_catalog."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 300},
                }
            ),
            capability_group="skills",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        skill_id = str(tool_input.get("skill_id") or "").strip()
        if skill_id and workspace_skill_by_id(config, skill_id) is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown workspace skill_id: {skill_id}")
        limit = max(1, min(int(tool_input.get("limit") or 100), SKILL_FILE_LIMIT))
        scripts = discover_workspace_skill_scripts(config, skill_id=skill_id)[:limit]
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(scripts)} skill script(s).",
            {"scripts": [script.summary() for script in scripts], "source": "workspace_skill_scripts"},
        )


class AgentSkillScriptReadTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="agent_skill_script_read",
            description="Read a bounded Humungousaur-owned skill script by exact script_id from agent_skill_script_catalog.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {"script_id": {"type": "string", "description": "Exact script id returned by agent_skill_script_catalog."}},
                required=["script_id"],
            ),
            capability_group="skills",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        script = workspace_skill_script_by_id(config, str(tool_input.get("script_id") or ""))
        if script is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Unknown skill script_id.")
        if script.path.stat().st_size > min(config.max_file_bytes, SKILL_SCRIPT_READ_LIMIT):
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Skill script exceeds configured read limit.")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Read skill script {script.name}.",
            {"script": script.summary(), "content": script.path.read_text(encoding="utf-8")},
        )


class AgentSkillScriptRunTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="agent_skill_script_run",
            description=(
                "Run one exact Humungousaur-owned Python skill script after approval. "
                "The script receives JSON on stdin and returns bounded stdout/stderr."
            ),
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "script_id": {"type": "string", "description": "Exact script id returned by agent_skill_script_catalog."},
                    "input": {"type": "object", "description": "JSON object passed to the script on stdin."},
                    "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 120},
                    "reason": {"type": "string", "description": "Why this skill script should run."},
                },
                required=["script_id", "reason"],
            ),
            capability_group="skills",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        script = workspace_skill_script_by_id(normalized, str(tool_input.get("script_id") or ""))
        if script is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Unknown skill script_id.")
        if script.path.suffix.lower() != ".py":
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Only Python skill scripts can run natively.")
        payload = tool_input.get("input", {})
        if not isinstance(payload, dict):
            payload = {}
        envelope = {
            "input": payload,
            "workspace": str(normalized.workspace),
            "data_dir": str(normalized.data_dir),
            "allowed_read_roots": [str(path) for path in normalized.allowed_read_roots],
            "allowed_write_roots": [str(path) for path in normalized.allowed_write_roots],
        }
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would execute approved skill script.",
                {"script": script.summary(), "envelope": envelope, "reason": str(tool_input.get("reason") or "")},
            )
        timeout = max(1, min(int(tool_input.get("timeout_seconds") or SKILL_SCRIPT_TIMEOUT_SECONDS), 120))
        completed = subprocess.run(
            [sys.executable, str(script.path)],
            cwd=normalized.workspace,
            input=json.dumps(envelope, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            check=False,
            env={**_safe_script_env(), "PYTHONDONTWRITEBYTECODE": "1"},
        )
        stdout = completed.stdout[-SKILL_SCRIPT_OUTPUT_LIMIT:]
        stderr = completed.stderr[-SKILL_SCRIPT_OUTPUT_LIMIT:]
        output: dict[str, Any] = {
            "script": script.summary(),
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
        parsed_stdout = _json_object(stdout)
        if parsed_stdout is not None:
            output["json"] = parsed_stdout
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED if completed.returncode == 0 else ActionStatus.FAILED,
            self.risk_level,
            f"Skill script exited with code {completed.returncode}.",
            output,
            None if completed.returncode == 0 else stderr[-1000:],
        )


class AgentSkillCapabilityAuditTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="agent_skill_capability_audit",
            description=(
                "Create a per-skill capability audit matrix for workspace SKILL.md packs. "
                "The audit checks exact Tool Map entries, native tool coverage, skill references, bundled scripts, "
                "safety/verification sections, and implementation status evidence."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "skill_id": {"type": "string", "description": "Optional exact workspace skill id to audit."},
                    "filename": {"type": "string", "description": "Optional Markdown filename for the audit artifact."},
                    "reason": {"type": "string", "description": "Why the skill capability matrix is being generated."},
                }
            ),
            capability_group="skills",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        skill_id = str(tool_input.get("skill_id") or "").strip()
        skills = discover_workspace_skills(normalized)
        if skill_id:
            skills = [skill for skill in skills if skill.skill_id == skill_id]
            if not skills:
                return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown workspace skill_id: {skill_id}")
        from humungousaur.tools import default_tools

        tool_names = set(default_tools(normalized))
        skill_names = {skill.name for skill in discover_workspace_skills(normalized)}
        rows = [_skill_audit_row(skill, tool_names, skill_names) for skill in skills[:SKILL_AUDIT_LIMIT]]
        summary = _skill_audit_summary(rows)
        audit_dir = normalized.data_dir / "skill_audits"
        audit_dir.mkdir(parents=True, exist_ok=True)
        filename = _safe_audit_filename(str(tool_input.get("filename") or "skill-capability-audit.md"))
        markdown_path = audit_dir / filename
        json_path = markdown_path.with_suffix(".json")
        payload = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reason": str(tool_input.get("reason") or ""),
            "source": "workspace_skill_capability_audit",
            "workspace": str(normalized.workspace),
            "summary": summary,
            "skills": rows,
        }
        markdown_path.write_text(_render_skill_audit_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Audited {len(rows)} workspace skill(s); {summary['needs_attention_count']} need attention.",
            {
                "path": str(markdown_path),
                "json_path": str(json_path),
                "summary": summary,
                "skills": rows,
            },
        )


class WorkspaceSkillRef:
    def __init__(self, *, skill_id: str, name: str, description: str, path: Path, relative_path: str) -> None:
        self.skill_id = skill_id
        self.name = name
        self.description = description
        self.path = path
        self.relative_path = relative_path

    def summary(self) -> dict[str, Any]:
        script_count = len(discover_scripts_for_skill(self))
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "path": str(self.path),
            "relative_path": self.relative_path,
            "source": "workspace",
            "script_count": script_count,
        }


class WorkspaceSkillScriptRef:
    def __init__(
        self,
        *,
        script_id: str,
        skill: WorkspaceSkillRef,
        name: str,
        description: str,
        path: Path,
        relative_path: str,
        metadata: dict[str, Any],
    ) -> None:
        self.script_id = script_id
        self.skill = skill
        self.name = name
        self.description = description
        self.path = path
        self.relative_path = relative_path
        self.metadata = metadata

    def summary(self) -> dict[str, Any]:
        return {
            "script_id": self.script_id,
            "skill_id": self.skill.skill_id,
            "skill_name": self.skill.name,
            "name": self.name,
            "description": self.description,
            "path": str(self.path),
            "relative_path": self.relative_path,
            "runtime": "python",
            "requires_approval": True,
            "input_schema": self.metadata.get("input_schema", {"type": "object", "additionalProperties": True}),
        }


def default_skill_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        AgentSkillCatalogTool(),
        AgentSkillReadTool(),
        AgentSkillImportTool(),
        AgentSkillScriptCatalogTool(),
        AgentSkillScriptReadTool(),
        AgentSkillScriptRunTool(),
        AgentSkillCapabilityAuditTool(),
    ]
    return {tool.name: tool for tool in tools}


def discover_workspace_skills(config: AgentConfig) -> list[WorkspaceSkillRef]:
    normalized = config.normalized()
    roots = [normalized.workspace / "skills", normalized.workspace / ".umang" / "skills"]
    skills: list[WorkspaceSkillRef] = []
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(root.rglob("SKILL.md")):
            if not path.is_file() or path.stat().st_size > min(normalized.max_file_bytes, SKILL_READ_LIMIT):
                continue
            relative = path.relative_to(normalized.workspace).as_posix()
            metadata = _skill_metadata(path)
            name = metadata.get("name") or path.parent.name
            description = metadata.get("description", "")
            skills.append(
                WorkspaceSkillRef(
                    skill_id=f"workspace:{relative}",
                    name=name,
                    description=description,
                    path=path.resolve(),
                    relative_path=relative,
                )
            )
            if len(skills) >= SKILL_FILE_LIMIT:
                return skills
    return skills


def workspace_skill_by_id(config: AgentConfig, skill_id: str) -> WorkspaceSkillRef | None:
    return next((skill for skill in discover_workspace_skills(config) if skill.skill_id == skill_id), None)


def discover_workspace_skill_scripts(config: AgentConfig, *, skill_id: str = "") -> list[WorkspaceSkillScriptRef]:
    selected = [skill for skill in discover_workspace_skills(config) if not skill_id or skill.skill_id == skill_id]
    scripts: list[WorkspaceSkillScriptRef] = []
    for skill in selected:
        scripts.extend(discover_scripts_for_skill(skill))
        if len(scripts) >= SKILL_FILE_LIMIT:
            return scripts
    return scripts


def workspace_skill_script_by_id(config: AgentConfig, script_id: str) -> WorkspaceSkillScriptRef | None:
    cleaned = str(script_id or "").strip()
    if not cleaned:
        return None
    return next((script for script in discover_workspace_skill_scripts(config) if script.script_id == cleaned), None)


def discover_scripts_for_skill(skill: WorkspaceSkillRef) -> list[WorkspaceSkillScriptRef]:
    scripts_dir = skill.path.parent / "scripts"
    if not scripts_dir.exists() or not scripts_dir.is_dir():
        return []
    scripts: list[WorkspaceSkillScriptRef] = []
    for path in sorted(scripts_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() != ".py":
            continue
        if path.stat().st_size > SKILL_SCRIPT_READ_LIMIT:
            continue
        metadata = _script_metadata(path)
        name = str(metadata.get("name") or path.stem).strip() or path.stem
        description = str(metadata.get("description") or f"Run {path.name} for {skill.name}.").strip()
        relative = (Path(skill.relative_path).parent / "scripts" / path.name).as_posix()
        scripts.append(
            WorkspaceSkillScriptRef(
                script_id=f"workspace:{relative}",
                skill=skill,
                name=name,
                description=description,
                path=path.resolve(),
                relative_path=relative,
                metadata=metadata,
            )
        )
    return scripts


def _skill_audit_row(skill: WorkspaceSkillRef, tool_names: set[str], skill_names: set[str]) -> dict[str, Any]:
    content = skill.path.read_text(encoding="utf-8")
    tool_map = _section_list_entries(content, "tool map")
    native_tools = [entry for entry in tool_map if entry in tool_names]
    skill_refs = [entry for entry in tool_map if entry in skill_names]
    unresolved = [entry for entry in tool_map if entry not in tool_names and entry not in skill_names]
    sections = _section_names(content)
    scripts = [script.summary() for script in discover_scripts_for_skill(skill)]
    has_safety = any(name in sections for name in {"safety and approval", "safety", "approval"})
    has_verification = "verification" in sections
    has_workflow = any(name in sections for name in {"workflow", "procedure", "operating model", "setup workflow", "testing a channel"})
    has_boundaries = any(name in sections for name in {"native implementation boundaries", "implementation boundaries", "delivery truth"})
    implementation_status = _skill_implementation_status(
        native_tools=native_tools,
        skill_refs=skill_refs,
        unresolved=unresolved,
        script_count=len(scripts),
        has_safety=has_safety,
        has_verification=has_verification,
        has_workflow=has_workflow,
    )
    needs_attention = bool(unresolved) or not tool_map or implementation_status in {"prompt_only", "thin_tool_map"} or not has_verification
    return {
        "skill_id": skill.skill_id,
        "name": skill.name,
        "relative_path": skill.relative_path,
        "description": skill.description,
        "tool_map_count": len(tool_map),
        "native_tool_count": len(native_tools),
        "skill_ref_count": len(skill_refs),
        "script_count": len(scripts),
        "unresolved_tool_count": len(unresolved),
        "implementation_status": implementation_status,
        "has_workflow": has_workflow,
        "has_safety": has_safety,
        "has_verification": has_verification,
        "has_boundaries": has_boundaries,
        "needs_attention": needs_attention,
        "tool_map": tool_map,
        "native_tools": native_tools,
        "skill_refs": skill_refs,
        "unresolved_entries": unresolved,
        "scripts": scripts,
        "recommended_next_action": _recommended_skill_action(implementation_status, unresolved, has_verification),
    }


def _section_names(content: str) -> set[str]:
    names: set[str] = set()
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("## "):
            continue
        names.add(stripped.lstrip("#").strip().lower())
    return names


def _section_list_entries(content: str, section_name: str) -> list[str]:
    entries: list[str] = []
    in_section = False
    wanted = section_name.strip().lower()
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            current = stripped.lstrip("#").strip().lower()
            in_section = current == wanted
            continue
        if in_section and stripped.startswith("#"):
            break
        if not in_section or not stripped.startswith("-"):
            continue
        entry = _backtick_value(stripped)
        if entry:
            entries.append(entry)
    return entries


def _backtick_value(text: str) -> str:
    start = text.find("`")
    if start < 0:
        return ""
    end = text.find("`", start + 1)
    if end < 0:
        return ""
    return text[start + 1 : end].strip()


def _skill_implementation_status(
    *,
    native_tools: list[str],
    skill_refs: list[str],
    unresolved: list[str],
    script_count: int,
    has_safety: bool,
    has_verification: bool,
    has_workflow: bool,
) -> str:
    if unresolved:
        return "unresolved_tool_map"
    if not native_tools and not script_count:
        return "prompt_only" if not skill_refs else "skill_ref_only"
    if script_count and native_tools:
        return "native_tools_and_scripts"
    if script_count:
        return "native_script_capable"
    if native_tools and has_workflow and has_safety and has_verification:
        return "native_capable"
    if native_tools:
        return "thin_tool_map"
    return "unknown"


def _recommended_skill_action(implementation_status: str, unresolved: list[str], has_verification: bool) -> str:
    if unresolved:
        return "Resolve Tool Map entries to native tools, scripts, or explicit referenced skills."
    if implementation_status == "prompt_only":
        return "Add native tools, scripts, operation packets, or concrete artifact creation for this skill."
    if implementation_status == "skill_ref_only":
        return "Add a direct native capability path or explain why this skill is only a composition wrapper."
    if not has_verification:
        return "Add a Verification section and representative smoke coverage."
    if implementation_status == "thin_tool_map":
        return "Add workflow, safety, boundary, and verification detail around the native tools."
    return "Keep current native path and add live/credentialed smoke when external setup is available."


def _skill_audit_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("implementation_status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "skill_count": len(rows),
        "native_capable_count": sum(1 for row in rows if str(row.get("implementation_status", "")).startswith("native")),
        "script_capable_count": sum(1 for row in rows if int(row.get("script_count", 0) or 0) > 0),
        "prompt_only_count": status_counts.get("prompt_only", 0),
        "unresolved_tool_map_count": status_counts.get("unresolved_tool_map", 0),
        "needs_attention_count": sum(1 for row in rows if row.get("needs_attention")),
        "status_counts": status_counts,
    }


def _safe_audit_filename(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_", "."} else "-" for char in value.strip())
    if not cleaned:
        cleaned = "skill-capability-audit.md"
    if not cleaned.endswith(".md"):
        cleaned += ".md"
    return cleaned[:120]


def _render_skill_audit_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Skill Capability Audit",
        "",
        f"Created: {payload['created_at']}",
        f"Workspace: `{payload['workspace']}`",
        f"Reason: {payload.get('reason', '')}",
        "",
        "## Summary",
        "",
        f"- Skills audited: {summary['skill_count']}",
        f"- Native capable: {summary['native_capable_count']}",
        f"- Script capable: {summary['script_capable_count']}",
        f"- Prompt only: {summary['prompt_only_count']}",
        f"- Unresolved Tool Maps: {summary['unresolved_tool_map_count']}",
        f"- Needs attention: {summary['needs_attention_count']}",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in sorted(summary["status_counts"].items()):
        lines.append(f"- {status}: {count}")
    lines.extend(
        [
            "",
            "## Matrix",
            "",
            "| Skill | Status | Native Tools | Scripts | Unresolved | Attention | Next Action |",
            "| --- | --- | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for row in payload["skills"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(str(row["name"])),
                    _md_cell(str(row["implementation_status"])),
                    str(row["native_tool_count"]),
                    str(row["script_count"]),
                    str(row["unresolved_tool_count"]),
                    "yes" if row["needs_attention"] else "no",
                    _md_cell(str(row["recommended_next_action"])),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Attention Items", ""])
    for row in [item for item in payload["skills"] if item.get("needs_attention")]:
        lines.append(f"- `{row['name']}`: {row['recommended_next_action']}")
    if not any(item.get("needs_attention") for item in payload["skills"]):
        lines.append("- None.")
    lines.append("")
    return "\n".join(lines)


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")[:240]


def _skill_metadata(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    if not lines or lines[0].strip() != "---":
        return _heading_metadata(lines)
    metadata: dict[str, str] = {}
    for line in lines[1:80]:
        stripped = line.strip()
        if stripped == "---":
            break
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip().lower()
        if key in {"name", "description"}:
            metadata[key] = value.strip().strip("'\"")[:500]
    return metadata or _heading_metadata(lines)


def _heading_metadata(lines: list[str]) -> dict[str, str]:
    for line in lines[:80]:
        stripped = line.strip()
        if stripped.startswith("# "):
            name = stripped[2:].strip()
            return {"name": name, "description": ""}
    return {}


def _script_metadata(path: Path) -> dict[str, Any]:
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[:20]:
            stripped = line.strip()
            if stripped.startswith(SKILL_SCRIPT_METADATA_PREFIX):
                parsed = json.loads(stripped[len(SKILL_SCRIPT_METADATA_PREFIX) :].strip())
                return parsed if isinstance(parsed, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}
    return {}


def _json_object(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _safe_script_env() -> dict[str, str]:
    allowed_names = {
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "USERNAME",
        "USERPROFILE",
        "PROGRAMDATA",
        "APPDATA",
        "LOCALAPPDATA",
        "PYTHONPATH",
    }
    return {name: value for name, value in os.environ.items() if name.upper() in allowed_names}
