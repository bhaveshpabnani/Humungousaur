from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from humungousaur.cognition.skills import SkillStore
from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


SKILL_FILE_LIMIT = 300
SKILL_READ_LIMIT = 80_000


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


class WorkspaceSkillRef:
    def __init__(self, *, skill_id: str, name: str, description: str, path: Path, relative_path: str) -> None:
        self.skill_id = skill_id
        self.name = name
        self.description = description
        self.path = path
        self.relative_path = relative_path

    def summary(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "path": str(self.path),
            "relative_path": self.relative_path,
            "source": "workspace",
        }


def default_skill_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        AgentSkillCatalogTool(),
        AgentSkillReadTool(),
        AgentSkillImportTool(),
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
