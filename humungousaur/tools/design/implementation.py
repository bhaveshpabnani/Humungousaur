from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


MAX_DESIGN_ITEMS = 200
MAX_TEXT_CHARS = 20_000


class BrandGuidelinesCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="brand_guidelines_create",
            description=(
                "Create a local brand-guidelines artifact with colors, typography, tone, layout rules, logo usage, "
                "accessibility notes, source refs, and official/proposed status. Does not claim proposed rules are official."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/design/brand_guidelines."},
                    "brand_name": {"type": "string"},
                    "status": {"type": "string", "enum": ["official", "proposed", "draft"]},
                    "colors": {"type": "array", "items": {"type": "object"}},
                    "typography": {"type": "array", "items": {"type": "object"}},
                    "tone": {"type": "array", "items": {"type": "string"}},
                    "logo_rules": {"type": "array", "items": {"type": "string"}},
                    "layout_rules": {"type": "array", "items": {"type": "string"}},
                    "accessibility_notes": {"type": "array", "items": {"type": "string"}},
                    "prohibited_uses": {"type": "array", "items": {"type": "string"}},
                    "source_refs": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                required=["brand_name", "reason"],
            ),
            capability_group="design",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        brand_name = " ".join(str(tool_input.get("brand_name") or "").split())
        reason = str(tool_input.get("reason") or "").strip()
        if not brand_name or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Brand name and reason are required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"brand-guidelines-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "design" / "brand_guidelines" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Brand guidelines path is outside allowed write roots.")
        artifact = _brand_artifact(tool_input, brand_name=brand_name, reason=reason, markdown_path=markdown_path)
        markdown = _render_brand_guidelines(artifact)
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would create brand guidelines {markdown_path}.", {"path": str(markdown_path), "artifact": artifact})
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        metadata_path = markdown_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created brand guidelines artifact {markdown_path}.",
            {
                "path": str(markdown_path),
                "metadata_path": str(metadata_path),
                "brand_guidelines_id": artifact["brand_guidelines_id"],
                "brand_name": artifact["brand_name"],
                "status": artifact["status"],
                "color_count": len(artifact["colors"]),
                "source": "brand_guidelines_create",
            },
        )


class BrandGuidelinesInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="brand_guidelines_inspect",
            description="Inspect a local brand-guidelines artifact for status, colors, typography, accessibility notes, and preview text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string", "description": "Workspace-relative or allowed absolute brand guidelines markdown path."}}, required=["path"]),
            capability_group="design",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_allowed_path(normalized, str(tool_input.get("path") or ""), subdir="design/brand_guidelines", suffix=".md")
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Brand guidelines path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".md":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Brand guidelines file does not exist.")
        metadata = _load_sidecar(path.with_suffix(".json"))
        text = path.read_text(encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected brand guidelines artifact {path}.",
            {
                "path": str(path),
                "metadata_path": str(path.with_suffix(".json")) if path.with_suffix(".json").exists() else "",
                "brand_guidelines_id": metadata.get("brand_guidelines_id", ""),
                "brand_name": metadata.get("brand_name", ""),
                "status": metadata.get("status", ""),
                "color_count": len(metadata.get("colors", [])) if isinstance(metadata.get("colors"), list) else 0,
                "typography_count": len(metadata.get("typography", [])) if isinstance(metadata.get("typography"), list) else 0,
                "accessibility_note_count": len(metadata.get("accessibility_notes", [])) if isinstance(metadata.get("accessibility_notes"), list) else 0,
                "preview": text[:4000],
                "source": "brand_guidelines_inspect",
            },
        )


class ThemePackCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="theme_pack_create",
            description=(
                "Create a local theme token artifact with palette, typography, spacing, radii, component states, "
                "contrast notes, and generated CSS variables. Does not edit app code by itself."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/design/theme_packs."},
                    "theme_name": {"type": "string"},
                    "mode": {"type": "string", "enum": ["light", "dark", "adaptive"]},
                    "tokens": {"type": "object"},
                    "palette": {"type": "array", "items": {"type": "object"}},
                    "typography": {"type": "object"},
                    "spacing": {"type": "object"},
                    "radii": {"type": "object"},
                    "component_states": {"type": "array", "items": {"type": "object"}},
                    "contrast_checks": {"type": "array", "items": {"type": "object"}},
                    "source_refs": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                required=["theme_name", "reason"],
            ),
            capability_group="design",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        theme_name = " ".join(str(tool_input.get("theme_name") or "").split())
        reason = str(tool_input.get("reason") or "").strip()
        if not theme_name or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Theme name and reason are required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"theme-pack-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "design" / "theme_packs" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Theme pack path is outside allowed write roots.")
        artifact = _theme_artifact(tool_input, theme_name=theme_name, reason=reason, markdown_path=markdown_path)
        markdown = _render_theme_pack(artifact)
        css = _render_theme_css(artifact)
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would create theme pack {markdown_path}.", {"path": str(markdown_path), "artifact": artifact})
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        metadata_path = markdown_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        css_path = markdown_path.with_suffix(".css")
        css_path.write_text(css, encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created theme pack artifact {markdown_path}.",
            {
                "path": str(markdown_path),
                "metadata_path": str(metadata_path),
                "css_path": str(css_path),
                "theme_pack_id": artifact["theme_pack_id"],
                "theme_name": artifact["theme_name"],
                "mode": artifact["mode"],
                "token_count": len(artifact["tokens"]),
                "source": "theme_pack_create",
            },
        )


class ThemePackInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="theme_pack_inspect",
            description="Inspect a local theme-pack artifact for token counts, CSS sidecar, contrast checks, component states, and preview text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string", "description": "Workspace-relative or allowed absolute theme pack markdown path."}}, required=["path"]),
            capability_group="design",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_allowed_path(normalized, str(tool_input.get("path") or ""), subdir="design/theme_packs", suffix=".md")
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Theme pack path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".md":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Theme pack file does not exist.")
        metadata = _load_sidecar(path.with_suffix(".json"))
        text = path.read_text(encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected theme pack artifact {path}.",
            {
                "path": str(path),
                "metadata_path": str(path.with_suffix(".json")) if path.with_suffix(".json").exists() else "",
                "css_path": str(path.with_suffix(".css")) if path.with_suffix(".css").exists() else "",
                "theme_pack_id": metadata.get("theme_pack_id", ""),
                "theme_name": metadata.get("theme_name", ""),
                "mode": metadata.get("mode", ""),
                "token_count": len(metadata.get("tokens", {})) if isinstance(metadata.get("tokens"), dict) else 0,
                "contrast_check_count": len(metadata.get("contrast_checks", [])) if isinstance(metadata.get("contrast_checks"), list) else 0,
                "preview": text[:4000],
                "source": "theme_pack_inspect",
            },
        )


def default_design_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        BrandGuidelinesCreateTool(),
        BrandGuidelinesInspectTool(),
        ThemePackCreateTool(),
        ThemePackInspectTool(),
    ]
    return {tool.name: tool for tool in tools}


def _brand_artifact(tool_input: dict[str, Any], *, brand_name: str, reason: str, markdown_path: Path) -> dict[str, Any]:
    status = str(tool_input.get("status") or "proposed").strip().lower()
    if status not in {"official", "proposed", "draft"}:
        status = "proposed"
    return {
        "brand_guidelines_id": f"brand-guidelines-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "brand_name": brand_name,
        "status": status,
        "colors": _colors(tool_input.get("colors")),
        "typography": _typography_list(tool_input.get("typography")),
        "tone": _string_list(tool_input.get("tone"), limit=MAX_DESIGN_ITEMS),
        "logo_rules": _string_list(tool_input.get("logo_rules"), limit=MAX_DESIGN_ITEMS),
        "layout_rules": _string_list(tool_input.get("layout_rules"), limit=MAX_DESIGN_ITEMS),
        "accessibility_notes": _string_list(tool_input.get("accessibility_notes"), limit=MAX_DESIGN_ITEMS),
        "prohibited_uses": _string_list(tool_input.get("prohibited_uses"), limit=MAX_DESIGN_ITEMS),
        "source_refs": _string_list(tool_input.get("source_refs"), limit=MAX_DESIGN_ITEMS),
        "reason": reason,
        "path": str(markdown_path),
        "safety_note": "Proposed or draft guidelines are not official brand rules unless source evidence says so.",
    }


def _theme_artifact(tool_input: dict[str, Any], *, theme_name: str, reason: str, markdown_path: Path) -> dict[str, Any]:
    mode = str(tool_input.get("mode") or "adaptive").strip().lower()
    if mode not in {"light", "dark", "adaptive"}:
        mode = "adaptive"
    palette = _colors(tool_input.get("palette"))
    tokens = _tokens(tool_input.get("tokens"), palette=palette)
    return {
        "theme_pack_id": f"theme-pack-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "theme_name": theme_name,
        "mode": mode,
        "tokens": tokens,
        "palette": palette,
        "typography": _object_map(tool_input.get("typography")),
        "spacing": _object_map(tool_input.get("spacing")),
        "radii": _object_map(tool_input.get("radii")),
        "component_states": _component_states(tool_input.get("component_states")),
        "contrast_checks": _contrast_checks(tool_input.get("contrast_checks")),
        "source_refs": _string_list(tool_input.get("source_refs"), limit=MAX_DESIGN_ITEMS),
        "reason": reason,
        "path": str(markdown_path),
        "application_status": "artifact_only_not_applied",
        "safety_note": "Theme pack was created locally. It has not been applied to app code or verified in browser unless separate tools prove it.",
    }


def _render_brand_guidelines(artifact: dict[str, Any]) -> str:
    lines = [f"# {artifact['brand_name']} Brand Guidelines", "", f"Status: {artifact['status']}", ""]
    if artifact["colors"]:
        lines.extend(["## Colors", "", "| Name | Value | Usage | Accessibility |", "| --- | --- | --- | --- |"])
        for color in artifact["colors"]:
            lines.append(f"| {color['name']} | `{color['value']}` | {color['usage']} | {color['accessibility']} |")
        lines.append("")
    if artifact["typography"]:
        lines.extend(["## Typography", "", "| Role | Family | Size | Weight | Notes |", "| --- | --- | --- | --- | --- |"])
        for item in artifact["typography"]:
            lines.append(f"| {item['role']} | {item['family']} | {item['size']} | {item['weight']} | {item['notes']} |")
        lines.append("")
    _append_list(lines, "Tone", artifact["tone"])
    _append_list(lines, "Logo Rules", artifact["logo_rules"])
    _append_list(lines, "Layout Rules", artifact["layout_rules"])
    _append_list(lines, "Accessibility Notes", artifact["accessibility_notes"])
    _append_list(lines, "Prohibited Uses", artifact["prohibited_uses"])
    _append_list(lines, "Source References", artifact["source_refs"])
    lines.extend(["## Safety Note", "", artifact["safety_note"], "", f"Created: {artifact['created_at']}"])
    return "\n".join(lines) + "\n"


def _render_theme_pack(artifact: dict[str, Any]) -> str:
    lines = [f"# {artifact['theme_name']} Theme Pack", "", f"Mode: {artifact['mode']}", f"Application status: {artifact['application_status']}", ""]
    if artifact["palette"]:
        lines.extend(["## Palette", "", "| Name | Value | Usage | Accessibility |", "| --- | --- | --- | --- |"])
        for color in artifact["palette"]:
            lines.append(f"| {color['name']} | `{color['value']}` | {color['usage']} | {color['accessibility']} |")
        lines.append("")
    if artifact["tokens"]:
        lines.extend(["## Tokens", ""])
        for key, value in artifact["tokens"].items():
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")
    _append_mapping(lines, "Typography", artifact["typography"])
    _append_mapping(lines, "Spacing", artifact["spacing"])
    _append_mapping(lines, "Radii", artifact["radii"])
    if artifact["component_states"]:
        lines.extend(["## Component States", "", "| Component | State | Token | Notes |", "| --- | --- | --- | --- |"])
        for state in artifact["component_states"]:
            lines.append(f"| {state['component']} | {state['state']} | `{state['token']}` | {state['notes']} |")
        lines.append("")
    if artifact["contrast_checks"]:
        lines.extend(["## Contrast Checks", "", "| Foreground | Background | Ratio | Status | Notes |", "| --- | --- | --- | --- | --- |"])
        for check in artifact["contrast_checks"]:
            lines.append(f"| `{check['foreground']}` | `{check['background']}` | {check['ratio']} | {check['status']} | {check['notes']} |")
        lines.append("")
    _append_list(lines, "Source References", artifact["source_refs"])
    lines.extend(["## Safety Note", "", artifact["safety_note"], "", f"Created: {artifact['created_at']}"])
    return "\n".join(lines) + "\n"


def _render_theme_css(artifact: dict[str, Any]) -> str:
    selector = ".humungousaur-theme"
    lines = [f"{selector} {{"]
    for key, value in artifact["tokens"].items():
        css_name = "--" + "".join(char if char.isalnum() else "-" for char in key.strip().lower()).strip("-")
        lines.append(f"  {css_name}: {value};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _colors(value: Any) -> list[dict[str, str]]:
    colors = []
    for raw in _bounded_list(value, MAX_DESIGN_ITEMS):
        if isinstance(raw, str):
            color = raw.strip()
            if color:
                colors.append({"name": color, "value": color, "usage": "", "accessibility": ""})
            continue
        if not isinstance(raw, dict):
            continue
        name = _bounded_text(raw.get("name") or raw.get("token") or raw.get("value"))
        value_text = _bounded_text(raw.get("value") or raw.get("hex"))
        if name and value_text:
            colors.append({"name": name, "value": value_text, "usage": _bounded_text(raw.get("usage")), "accessibility": _bounded_text(raw.get("accessibility"))})
    return colors


def _typography_list(value: Any) -> list[dict[str, str]]:
    items = []
    for raw in _bounded_list(value, MAX_DESIGN_ITEMS):
        if not isinstance(raw, dict):
            continue
        role = _bounded_text(raw.get("role") or raw.get("name"))
        if role:
            items.append({"role": role, "family": _bounded_text(raw.get("family")), "size": _bounded_text(raw.get("size")), "weight": _bounded_text(raw.get("weight")), "notes": _bounded_text(raw.get("notes"))})
    return items


def _tokens(value: Any, *, palette: list[dict[str, str]]) -> dict[str, str]:
    tokens = {str(key).strip(): _bounded_text(raw) for key, raw in _object_map(value).items() if str(key).strip() and _bounded_text(raw)}
    for color in palette:
        tokens.setdefault(f"color-{color['name']}", color["value"])
    return dict(list(tokens.items())[:MAX_DESIGN_ITEMS])


def _component_states(value: Any) -> list[dict[str, str]]:
    states = []
    for raw in _bounded_list(value, MAX_DESIGN_ITEMS):
        if not isinstance(raw, dict):
            continue
        component = _bounded_text(raw.get("component"))
        state = _bounded_text(raw.get("state"))
        if component and state:
            states.append({"component": component, "state": state, "token": _bounded_text(raw.get("token")), "notes": _bounded_text(raw.get("notes"))})
    return states


def _contrast_checks(value: Any) -> list[dict[str, str]]:
    checks = []
    for raw in _bounded_list(value, MAX_DESIGN_ITEMS):
        if not isinstance(raw, dict):
            continue
        fg = _bounded_text(raw.get("foreground"))
        bg = _bounded_text(raw.get("background"))
        if fg and bg:
            checks.append({"foreground": fg, "background": bg, "ratio": _bounded_text(raw.get("ratio")), "status": _bounded_text(raw.get("status")), "notes": _bounded_text(raw.get("notes"))})
    return checks


def _append_mapping(lines: list[str], title: str, mapping: dict[str, Any]) -> None:
    if not mapping:
        return
    lines.extend([f"## {title}", ""])
    for key, value in mapping.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")


def _append_list(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines.extend([f"## {title}", ""])
    for item in items:
        lines.append(f"- {item}")
    lines.append("")


def _object_map(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _bounded_text(value: Any) -> str:
    return " ".join(str(value or "").split())[:MAX_TEXT_CHARS]


def _bounded_list(value: Any, limit: int) -> list[Any]:
    if not isinstance(value, list):
        return []
    return value[: max(0, limit)]


def _string_list(value: Any, *, limit: int) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value[:limit] if str(item).strip()]


def _resolve_allowed_path(config: AgentConfig, raw_path: str, *, subdir: str, suffix: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = config.workspace / path
        if not path.exists():
            data_path = config.data_dir / raw_path
            if data_path.exists():
                path = data_path
            else:
                artifact_path = config.data_dir / subdir / Path(raw_path).name
                if artifact_path.exists():
                    path = artifact_path
    if not path.suffix:
        path = path.with_suffix(suffix)
    return path.resolve()


def _load_sidecar(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _safe_filename(value: str, suffix: str) -> str:
    name = Path(value).name.strip() or f"artifact{suffix}"
    if not name.lower().endswith(suffix):
        name += suffix
    stem = "".join(char if char.isalnum() or char in ("-", "_", ".") else "-" for char in Path(name).stem).strip(".-")
    return f"{stem or 'artifact'}{suffix}"


def _is_within(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)
