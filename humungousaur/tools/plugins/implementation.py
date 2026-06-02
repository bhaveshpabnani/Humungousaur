from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


PLUGIN_MANIFEST_FILENAMES = ("plugin.json",)
PLUGIN_MANIFEST_SUFFIX = ".plugin.json"
PLUGIN_MANIFEST_LIMIT = 100
PLUGIN_MANIFEST_TOOL_LIMIT = 50
PLUGIN_NAME_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-")
PLUGIN_TOOL_NAME_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
PLUGIN_ALLOWED_SCHEMA_TYPES = {"object", "array", "string", "integer", "number", "boolean"}


@dataclass(slots=True)
class PluginToolDeclaration:
    name: str
    description: str
    declared_risk_level: str = "blocked"
    requires_approval: bool = False
    input_schema: dict[str, Any] = field(default_factory=lambda: object_input_schema())
    valid: bool = True


@dataclass(slots=True)
class PluginManifest:
    name: str
    path: Path
    version: str = ""
    description: str = ""
    capability_group: str = "plugins"
    enabled: bool = False
    tools: list[PluginToolDeclaration] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "capability_group": self.capability_group,
            "enabled": self.enabled,
            "path": str(self.path),
            "tool_count": len(self.tools),
            "errors": list(self.errors),
        }

    def detail(self) -> dict[str, Any]:
        payload = self.summary()
        payload["tools"] = [
            {
                "name": tool.name,
                "description": tool.description,
                "declared_risk_level": tool.declared_risk_level,
                "requires_approval": tool.requires_approval,
                "input_schema": tool.input_schema,
                "execution_status": "blocked_until_trusted_runtime",
                "valid": tool.valid,
            }
            for tool in self.tools
        ]
        return payload


class PluginManifestsTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="plugin_manifests",
            description="List local Umang plugin manifests and their declared blocked tools.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "include_errors": {
                        "type": "boolean",
                        "description": "Include invalid manifest records and parser errors.",
                    }
                }
            ),
            capability_group="plugins",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        include_errors = bool(tool_input.get("include_errors", True))
        manifests = discover_plugin_manifests(config)
        items = [manifest.summary() for manifest in manifests if include_errors or not manifest.errors]
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(items)} local plugin manifest(s).",
            {
                "manifests": items,
                "roots": [str(path) for path in plugin_manifest_roots(config)],
                "execution": "manifest-declared tools are visible but blocked until a trusted runtime is installed",
            },
        )


class PluginManifestTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="plugin_manifest",
            description="Read one local Umang plugin manifest by name.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {"name": {"type": "string", "description": "Plugin manifest name."}},
                required=["name"],
            ),
            capability_group="plugins",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        name = str(tool_input.get("name") or "").strip()
        for manifest in discover_plugin_manifests(config):
            if manifest.name == name:
                return ToolResult(
                    self.name,
                    ActionStatus.SUCCEEDED,
                    self.risk_level,
                    f"Read plugin manifest {name}.",
                    {"manifest": manifest.detail()},
                )
        return ToolResult(
            self.name,
            ActionStatus.FAILED,
            self.risk_level,
            f"Unknown plugin manifest: {name}",
        )


class DeclaredPluginTool(Tool):
    def __init__(self, manifest: PluginManifest, declaration: PluginToolDeclaration) -> None:
        self.manifest_name = manifest.name
        self.declared_risk_level = declaration.declared_risk_level
        super().__init__(
            name=declaration.name,
            description=(
                f"{declaration.description} Declared by local plugin manifest '{manifest.name}', "
                "but execution is blocked until a trusted plugin runtime is installed."
            ),
            risk_level=RiskLevel.BLOCKED,
            requires_approval=False,
            input_schema=declaration.input_schema,
            capability_group=manifest.capability_group or "plugins",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        return ToolResult(
            self.name,
            ActionStatus.BLOCKED,
            self.risk_level,
            "Plugin-declared tools cannot execute until a trusted plugin runtime is installed.",
            {
                "manifest": self.manifest_name,
                "declared_risk_level": self.declared_risk_level,
                "execution_status": "blocked_until_trusted_runtime",
            },
        )


def default_plugin_tools(config: AgentConfig | None = None, existing_tool_names: set[str] | None = None) -> dict[str, Tool]:
    tools: dict[str, Tool] = {
        "plugin_manifests": PluginManifestsTool(),
        "plugin_manifest": PluginManifestTool(),
    }
    if config is None:
        return tools
    blocked_names = set(tools) | set(existing_tool_names or set())
    for manifest in discover_plugin_manifests(config):
        for declaration in manifest.tools:
            if not declaration.valid:
                continue
            if declaration.name in blocked_names:
                continue
            blocked_names.add(declaration.name)
            tools[declaration.name] = DeclaredPluginTool(manifest, declaration)
    return tools


def plugin_manifest_roots(config: AgentConfig) -> list[Path]:
    normalized = config.normalized()
    return [
        normalized.workspace / ".umang" / "plugins",
        normalized.data_dir / "plugins",
    ]


def discover_plugin_manifests(config: AgentConfig) -> list[PluginManifest]:
    manifests: list[PluginManifest] = []
    seen_paths: set[Path] = set()
    for root in plugin_manifest_roots(config):
        if not root.exists() or not root.is_dir():
            continue
        for path in _iter_manifest_paths(root, config.max_file_bytes):
            if path in seen_paths:
                continue
            seen_paths.add(path)
            manifests.append(load_plugin_manifest(path, config.max_file_bytes))
            if len(manifests) >= PLUGIN_MANIFEST_LIMIT:
                return sorted(manifests, key=lambda item: item.name)
    return sorted(manifests, key=lambda item: item.name)


def load_plugin_manifest(path: Path, max_bytes: int = 200_000) -> PluginManifest:
    errors: list[str] = []
    fallback_name = path.stem.removesuffix(".plugin")
    if path.stat().st_size > max_bytes:
        return PluginManifest(name=fallback_name, path=path, errors=["Manifest exceeds configured file-size limit."])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return PluginManifest(name=fallback_name, path=path, errors=[f"Invalid JSON: {exc.msg}."])
    if not isinstance(payload, dict):
        return PluginManifest(name=fallback_name, path=path, errors=["Manifest root must be a JSON object."])

    name = _clean_string(payload.get("name"), fallback_name)
    if not _valid_plugin_name(name):
        errors.append("Plugin name must use letters, numbers, underscores, hyphens, or dots.")
        name = fallback_name
    version = _clean_string(payload.get("version"), "")
    description = _clean_string(payload.get("description"), "")
    capability_group = _clean_string(payload.get("capability_group"), "plugins") or "plugins"
    if not _valid_plugin_name(capability_group):
        errors.append("Capability group must use letters, numbers, underscores, hyphens, or dots.")
        capability_group = "plugins"
    enabled = bool(payload.get("enabled", False))

    tools_payload = payload.get("tools", [])
    tools: list[PluginToolDeclaration] = []
    if not isinstance(tools_payload, list):
        errors.append("Manifest tools must be an array.")
    else:
        for item in tools_payload[:PLUGIN_MANIFEST_TOOL_LIMIT]:
            declaration, declaration_errors = _parse_tool_declaration(item)
            errors.extend(declaration_errors)
            if declaration is not None:
                tools.append(declaration)
        if len(tools_payload) > PLUGIN_MANIFEST_TOOL_LIMIT:
            errors.append(f"Manifest tool list was truncated at {PLUGIN_MANIFEST_TOOL_LIMIT} declaration(s).")

    return PluginManifest(
        name=name,
        path=path,
        version=version,
        description=description,
        capability_group=capability_group,
        enabled=enabled,
        tools=tools,
        errors=errors,
    )


def _iter_manifest_paths(root: Path, max_bytes: int) -> list[Path]:
    paths: list[Path] = []
    for path in root.rglob("*.json"):
        if not path.is_file():
            continue
        if path.name not in PLUGIN_MANIFEST_FILENAMES and not path.name.endswith(PLUGIN_MANIFEST_SUFFIX):
            continue
        if path.stat().st_size <= max_bytes:
            paths.append(path.resolve())
        else:
            paths.append(path.resolve())
    return sorted(paths)


def _parse_tool_declaration(payload: Any) -> tuple[PluginToolDeclaration | None, list[str]]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return None, ["Tool declarations must be JSON objects."]
    name = _clean_string(payload.get("name"), "")
    if not _valid_tool_name(name):
        return None, [f"Invalid plugin tool name: {name or '<empty>'}."]
    description = _clean_string(payload.get("description"), "")
    if not description:
        errors.append(f"Plugin tool {name} is missing a description.")
    declared_risk_level = _clean_string(payload.get("risk_level"), "blocked")
    if declared_risk_level not in {item.value for item in RiskLevel}:
        errors.append(f"Plugin tool {name} has unsupported risk level: {declared_risk_level}.")
        declared_risk_level = "blocked"
    requires_approval = bool(payload.get("requires_approval", declared_risk_level in {"high", "blocked"}))
    input_schema = payload.get("input_schema", object_input_schema())
    schema_errors = _validate_manifest_schema(input_schema)
    errors.extend(f"Plugin tool {name} input_schema: {error}" for error in schema_errors)
    if schema_errors:
        input_schema = object_input_schema()
    return (
        PluginToolDeclaration(
            name=name,
            description=description,
            declared_risk_level=declared_risk_level,
            requires_approval=requires_approval,
            input_schema=input_schema,
            valid=not schema_errors,
        ),
        errors,
    )


def _validate_manifest_schema(schema: Any, depth: int = 0) -> list[str]:
    if not isinstance(schema, dict):
        return ["must be a JSON object."]
    if depth > 4:
        return ["is nested too deeply."]
    errors: list[str] = []
    schema_type = schema.get("type")
    if schema_type is not None and schema_type not in PLUGIN_ALLOWED_SCHEMA_TYPES:
        errors.append(f"has unsupported type: {schema_type}.")
    properties = schema.get("properties")
    if properties is not None:
        if not isinstance(properties, dict):
            errors.append("properties must be an object.")
        else:
            for key, child in properties.items():
                if not isinstance(key, str) or not _valid_tool_name(key):
                    errors.append(f"property has invalid name: {key}.")
                    continue
                errors.extend(_validate_manifest_schema(child, depth + 1))
    items = schema.get("items")
    if items is not None:
        errors.extend(_validate_manifest_schema(items, depth + 1))
    required = schema.get("required")
    if required is not None and not (isinstance(required, list) and all(isinstance(item, str) for item in required)):
        errors.append("required must be an array of strings.")
    additional = schema.get("additionalProperties")
    if additional is not None and not isinstance(additional, (bool, dict)):
        errors.append("additionalProperties must be a boolean or schema object.")
    if isinstance(additional, dict):
        errors.extend(_validate_manifest_schema(additional, depth + 1))
    enum = schema.get("enum")
    if enum is not None and not isinstance(enum, list):
        errors.append("enum must be an array.")
    return errors


def _clean_string(value: Any, default: str) -> str:
    if not isinstance(value, str):
        return default
    return value.strip()[:500]


def _valid_plugin_name(value: str) -> bool:
    return bool(value) and len(value) <= 120 and all(char in PLUGIN_NAME_CHARS for char in value)


def _valid_tool_name(value: str) -> bool:
    return bool(value) and len(value) <= 120 and all(char in PLUGIN_TOOL_NAME_CHARS for char in value)
