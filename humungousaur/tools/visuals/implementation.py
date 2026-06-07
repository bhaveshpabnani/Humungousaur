from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


MAX_VISUAL_ITEMS = 200
MAX_TEXT_CHARS = 20_000


class DiagramArtifactCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="diagram_artifact_create",
            description=(
                "Create a local diagram artifact with typed nodes, edges, diagram status, evidence refs, "
                "Markdown explanation, JSON metadata, and a Mermaid sidecar when possible."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/visuals/diagrams."},
                    "title": {"type": "string"},
                    "diagram_type": {"type": "string", "enum": ["component", "sequence", "data_flow", "deployment", "state", "infographic", "concept"]},
                    "status": {"type": "string", "enum": ["current", "proposed", "draft"]},
                    "nodes": {"type": "array", "items": {"type": "object"}},
                    "edges": {"type": "array", "items": {"type": "object"}},
                    "sections": {"type": "array", "items": {"type": "object"}},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}},
                    "unknowns": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                required=["title", "reason"],
            ),
            capability_group="visuals",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        title = " ".join(str(tool_input.get("title") or "").split())
        reason = str(tool_input.get("reason") or "").strip()
        if not title or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Title and reason are required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"diagram-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "visuals" / "diagrams" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Diagram path is outside allowed write roots.")
        artifact = _diagram_artifact(tool_input, title=title, reason=reason, markdown_path=markdown_path)
        markdown = _render_diagram_markdown(artifact)
        mermaid = _render_mermaid(artifact)
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would create diagram {markdown_path}.", {"path": str(markdown_path), "artifact": artifact})
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        metadata_path = markdown_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        mermaid_path = markdown_path.with_suffix(".mmd")
        mermaid_path.write_text(mermaid, encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created diagram artifact {markdown_path}.",
            {
                "path": str(markdown_path),
                "metadata_path": str(metadata_path),
                "mermaid_path": str(mermaid_path),
                "diagram_id": artifact["diagram_id"],
                "diagram_type": artifact["diagram_type"],
                "status": artifact["status"],
                "node_count": len(artifact["nodes"]),
                "edge_count": len(artifact["edges"]),
                "source": "diagram_artifact_create",
            },
        )


class DiagramArtifactInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="diagram_artifact_inspect",
            description="Inspect a local diagram artifact for type, status, node/edge counts, evidence refs, Mermaid sidecar, and preview text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string", "description": "Workspace-relative or allowed absolute diagram markdown path."}}, required=["path"]),
            capability_group="visuals",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_allowed_path(normalized, str(tool_input.get("path") or ""), subdir="visuals/diagrams", suffix=".md")
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Diagram path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".md":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Diagram file does not exist.")
        metadata = _load_sidecar(path.with_suffix(".json"))
        text = path.read_text(encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected diagram artifact {path}.",
            {
                "path": str(path),
                "metadata_path": str(path.with_suffix(".json")) if path.with_suffix(".json").exists() else "",
                "mermaid_path": str(path.with_suffix(".mmd")) if path.with_suffix(".mmd").exists() else "",
                "diagram_id": metadata.get("diagram_id", ""),
                "diagram_type": metadata.get("diagram_type", ""),
                "status": metadata.get("status", ""),
                "node_count": len(metadata.get("nodes", [])) if isinstance(metadata.get("nodes"), list) else 0,
                "edge_count": len(metadata.get("edges", [])) if isinstance(metadata.get("edges"), list) else 0,
                "evidence_ref_count": len(metadata.get("evidence_refs", [])) if isinstance(metadata.get("evidence_refs"), list) else 0,
                "unknown_count": len(metadata.get("unknowns", [])) if isinstance(metadata.get("unknowns"), list) else 0,
                "preview": text[:4000],
                "source": "diagram_artifact_inspect",
            },
        )


class ExcalidrawDiagramCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="excalidraw_diagram_create",
            description="Create a Humungousaur-owned Excalidraw-compatible JSON file from typed nodes and edges.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output .excalidraw filename under data_dir/visuals/excalidraw."},
                    "title": {"type": "string"},
                    "nodes": {"type": "array", "items": {"type": "object"}},
                    "edges": {"type": "array", "items": {"type": "object"}},
                    "status": {"type": "string", "enum": ["current", "proposed", "draft"]},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                required=["title", "nodes", "reason"],
            ),
            capability_group="visuals",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        title = " ".join(str(tool_input.get("title") or "").split())
        reason = str(tool_input.get("reason") or "").strip()
        nodes = _nodes(tool_input.get("nodes"))
        if not title or not reason or not nodes:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Title, nodes, and reason are required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"diagram-{uuid4().hex[:8]}.excalidraw"), ".excalidraw")
        path = (normalized.data_dir / "visuals" / "excalidraw" / filename).resolve()
        if not _is_within(path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Excalidraw path is outside allowed write roots.")
        artifact = _excalidraw_file(title=title, nodes=nodes, edges=_edges(tool_input.get("edges")), tool_input=tool_input, reason=reason)
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would create Excalidraw file {path}.", {"path": str(path), "artifact": artifact})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created Excalidraw-compatible file {path}.",
            {
                "path": str(path),
                "title": title,
                "status": artifact["humungousaur_metadata"]["status"],
                "element_count": len(artifact["elements"]),
                "node_count": len(nodes),
                "edge_count": len(_edges(tool_input.get("edges"))),
                "source": "excalidraw_diagram_create",
            },
        )


class InfographicPlanCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="infographic_plan_create",
            description="Create a local infographic plan with message hierarchy, metrics, sections, chart ideas, accessibility notes, and source refs.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/visuals/infographics."},
                    "title": {"type": "string"},
                    "audience": {"type": "string"},
                    "key_message": {"type": "string"},
                    "status": {"type": "string", "enum": ["draft", "ready_for_review", "final"]},
                    "metrics": {"type": "array", "items": {"type": "object"}},
                    "sections": {"type": "array", "items": {"type": "object"}},
                    "visual_marks": {"type": "array", "items": {"type": "string"}},
                    "accessibility_notes": {"type": "array", "items": {"type": "string"}},
                    "source_refs": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                required=["title", "key_message", "reason"],
            ),
            capability_group="visuals",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        title = " ".join(str(tool_input.get("title") or "").split())
        key_message = str(tool_input.get("key_message") or "").strip()
        reason = str(tool_input.get("reason") or "").strip()
        if not title or not key_message or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Title, key_message, and reason are required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"infographic-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "visuals" / "infographics" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Infographic path is outside allowed write roots.")
        artifact = _infographic_artifact(tool_input, title=title, key_message=key_message, reason=reason, markdown_path=markdown_path)
        markdown = _render_infographic_markdown(artifact)
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would create infographic plan {markdown_path}.", {"path": str(markdown_path), "artifact": artifact})
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        metadata_path = markdown_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created infographic plan {markdown_path}.",
            {
                "path": str(markdown_path),
                "metadata_path": str(metadata_path),
                "infographic_id": artifact["infographic_id"],
                "status": artifact["status"],
                "metric_count": len(artifact["metrics"]),
                "section_count": len(artifact["sections"]),
                "source": "infographic_plan_create",
            },
        )


class InfographicPlanInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="infographic_plan_inspect",
            description="Inspect a local infographic plan for status, key message, metric count, sections, accessibility notes, and source refs.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string", "description": "Workspace-relative or allowed absolute infographic markdown path."}}, required=["path"]),
            capability_group="visuals",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_allowed_path(normalized, str(tool_input.get("path") or ""), subdir="visuals/infographics", suffix=".md")
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Infographic path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".md":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Infographic plan file does not exist.")
        metadata = _load_sidecar(path.with_suffix(".json"))
        text = path.read_text(encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected infographic plan {path}.",
            {
                "path": str(path),
                "metadata_path": str(path.with_suffix(".json")) if path.with_suffix(".json").exists() else "",
                "infographic_id": metadata.get("infographic_id", ""),
                "status": metadata.get("status", ""),
                "key_message": metadata.get("key_message", ""),
                "metric_count": len(metadata.get("metrics", [])) if isinstance(metadata.get("metrics"), list) else 0,
                "section_count": len(metadata.get("sections", [])) if isinstance(metadata.get("sections"), list) else 0,
                "accessibility_note_count": len(metadata.get("accessibility_notes", [])) if isinstance(metadata.get("accessibility_notes"), list) else 0,
                "preview": text[:4000],
                "source": "infographic_plan_inspect",
            },
        )


def default_visual_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        DiagramArtifactCreateTool(),
        DiagramArtifactInspectTool(),
        ExcalidrawDiagramCreateTool(),
        InfographicPlanCreateTool(),
        InfographicPlanInspectTool(),
    ]
    return {tool.name: tool for tool in tools}


def _diagram_artifact(tool_input: dict[str, Any], *, title: str, reason: str, markdown_path: Path) -> dict[str, Any]:
    diagram_type = str(tool_input.get("diagram_type") or "component").strip().lower()
    if diagram_type not in {"component", "sequence", "data_flow", "deployment", "state", "infographic", "concept"}:
        diagram_type = "component"
    status = str(tool_input.get("status") or "draft").strip().lower()
    if status not in {"current", "proposed", "draft"}:
        status = "draft"
    return {
        "diagram_id": f"diagram-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "diagram_type": diagram_type,
        "status": status,
        "nodes": _nodes(tool_input.get("nodes")),
        "edges": _edges(tool_input.get("edges")),
        "sections": _sections(tool_input.get("sections")),
        "evidence_refs": _string_list(tool_input.get("evidence_refs"), limit=MAX_VISUAL_ITEMS),
        "unknowns": _string_list(tool_input.get("unknowns"), limit=MAX_VISUAL_ITEMS),
        "reason": reason,
        "path": str(markdown_path),
        "safety_note": "Current diagrams require source evidence. Proposed or draft diagrams must not be presented as verified current architecture.",
    }


def _infographic_artifact(tool_input: dict[str, Any], *, title: str, key_message: str, reason: str, markdown_path: Path) -> dict[str, Any]:
    status = str(tool_input.get("status") or "draft").strip().lower()
    if status not in {"draft", "ready_for_review", "final"}:
        status = "draft"
    return {
        "infographic_id": f"infographic-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "audience": _bounded_text(tool_input.get("audience")),
        "key_message": key_message[:MAX_TEXT_CHARS],
        "status": status,
        "metrics": _metrics(tool_input.get("metrics")),
        "sections": _sections(tool_input.get("sections")),
        "visual_marks": _string_list(tool_input.get("visual_marks"), limit=MAX_VISUAL_ITEMS),
        "accessibility_notes": _string_list(tool_input.get("accessibility_notes"), limit=MAX_VISUAL_ITEMS),
        "source_refs": _string_list(tool_input.get("source_refs"), limit=MAX_VISUAL_ITEMS),
        "reason": reason,
        "path": str(markdown_path),
        "safety_note": "Infographic metrics must trace to source refs. Draft plans are not publication approvals.",
    }


def _render_diagram_markdown(artifact: dict[str, Any]) -> str:
    lines = [f"# {artifact['title']}", "", f"Type: {artifact['diagram_type']}", f"Status: {artifact['status']}", ""]
    if artifact["nodes"]:
        lines.extend(["## Nodes", "", "| ID | Label | Kind | Notes |", "| --- | --- | --- | --- |"])
        for node in artifact["nodes"]:
            lines.append(f"| `{node['id']}` | {node['label']} | {node['kind']} | {node['notes']} |")
        lines.append("")
    if artifact["edges"]:
        lines.extend(["## Edges", "", "| From | To | Label | Evidence |", "| --- | --- | --- | --- |"])
        for edge in artifact["edges"]:
            lines.append(f"| `{edge['from']}` | `{edge['to']}` | {edge['label']} | {edge['evidence']} |")
        lines.append("")
    _append_sections(lines, artifact["sections"])
    _append_list(lines, "Evidence References", artifact["evidence_refs"])
    _append_list(lines, "Unknowns", artifact["unknowns"])
    lines.extend(["## Mermaid", "", "```mermaid", _render_mermaid(artifact).strip(), "```", ""])
    lines.extend(["## Safety Note", "", artifact["safety_note"], "", f"Created: {artifact['created_at']}"])
    return "\n".join(lines) + "\n"


def _render_infographic_markdown(artifact: dict[str, Any]) -> str:
    lines = [f"# {artifact['title']}", "", f"Audience: {artifact['audience']}", f"Status: {artifact['status']}", "", "## Key Message", "", artifact["key_message"], ""]
    if artifact["metrics"]:
        lines.extend(["## Metrics", "", "| Label | Value | Unit | Source | Notes |", "| --- | --- | --- | --- | --- |"])
        for metric in artifact["metrics"]:
            lines.append(f"| {metric['label']} | {metric['value']} | {metric['unit']} | {metric['source']} | {metric['notes']} |")
        lines.append("")
    _append_sections(lines, artifact["sections"])
    _append_list(lines, "Visual Marks", artifact["visual_marks"])
    _append_list(lines, "Accessibility Notes", artifact["accessibility_notes"])
    _append_list(lines, "Source References", artifact["source_refs"])
    lines.extend(["## Safety Note", "", artifact["safety_note"], "", f"Created: {artifact['created_at']}"])
    return "\n".join(lines) + "\n"


def _render_mermaid(artifact: dict[str, Any]) -> str:
    if artifact["diagram_type"] == "sequence":
        lines = ["sequenceDiagram"]
        for node in artifact["nodes"]:
            lines.append(f"    participant {_mermaid_id(node['id'])} as {node['label']}")
        for edge in artifact["edges"]:
            label = edge["label"] or "interacts"
            lines.append(f"    {_mermaid_id(edge['from'])}->>+{_mermaid_id(edge['to'])}: {label}")
        return "\n".join(lines) + "\n"
    lines = ["flowchart LR"]
    for node in artifact["nodes"]:
        lines.append(f"    {_mermaid_id(node['id'])}[\"{_escape_mermaid_label(node['label'])}\"]")
    for edge in artifact["edges"]:
        label = edge["label"]
        label_text = f"|{_escape_mermaid_label(label)}|" if label else ""
        lines.append(f"    {_mermaid_id(edge['from'])} -->{label_text} {_mermaid_id(edge['to'])}")
    return "\n".join(lines) + "\n"


def _excalidraw_file(*, title: str, nodes: list[dict[str, str]], edges: list[dict[str, str]], tool_input: dict[str, Any], reason: str) -> dict[str, Any]:
    status = str(tool_input.get("status") or "draft").strip().lower()
    if status not in {"current", "proposed", "draft"}:
        status = "draft"
    elements: list[dict[str, Any]] = []
    node_positions: dict[str, tuple[int, int]] = {}
    for index, node in enumerate(nodes):
        x = _bounded_int(node.get("x"), default=80 + (index % 3) * 280, low=0, high=4000)
        y = _bounded_int(node.get("y"), default=80 + (index // 3) * 180, low=0, high=4000)
        width = _bounded_int(node.get("width"), default=180, low=40, high=800)
        height = _bounded_int(node.get("height"), default=80, low=30, high=500)
        node_positions[node["id"]] = (x + width // 2, y + height // 2)
        rect_id = f"rect-{node['id']}-{uuid4().hex[:6]}"
        text_id = f"text-{node['id']}-{uuid4().hex[:6]}"
        elements.append(_excalidraw_element(rect_id, "rectangle", x=x, y=y, width=width, height=height))
        elements.append(_excalidraw_text(text_id, node["label"], x=x + 12, y=y + 18, width=max(40, width - 24), height=max(24, height - 24)))
    for edge in edges:
        start = node_positions.get(edge["from"])
        end = node_positions.get(edge["to"])
        if not start or not end:
            continue
        arrow_id = f"arrow-{edge['from']}-{edge['to']}-{uuid4().hex[:6]}"
        elements.append(_excalidraw_arrow(arrow_id, start=start, end=end))
        if edge["label"]:
            mid_x = int((start[0] + end[0]) / 2)
            mid_y = int((start[1] + end[1]) / 2)
            elements.append(_excalidraw_text(f"label-{arrow_id}", edge["label"], x=mid_x, y=mid_y - 24, width=160, height=28, font_size=16))
    return {
        "type": "excalidraw",
        "version": 2,
        "source": "humungousaur_native_excalidraw_diagram_create",
        "elements": elements,
        "appState": {"viewBackgroundColor": "#ffffff", "name": title},
        "files": {},
        "humungousaur_metadata": {
            "title": title,
            "status": status,
            "reason": reason,
            "evidence_refs": _string_list(tool_input.get("evidence_refs"), limit=MAX_VISUAL_ITEMS),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "safety_note": "This is a local Excalidraw-compatible draft generated by Humungousaur native code.",
        },
    }


def _nodes(value: Any) -> list[dict[str, Any]]:
    nodes = []
    for index, raw in enumerate(_bounded_list(value, MAX_VISUAL_ITEMS)):
        if not isinstance(raw, dict):
            continue
        node_id = _slug(raw.get("id") or raw.get("label") or f"node-{index + 1}")
        label = _bounded_text(raw.get("label") or raw.get("name") or node_id)
        if node_id and label:
            nodes.append(
                {
                    "id": node_id,
                    "label": label,
                    "kind": _bounded_text(raw.get("kind") or raw.get("type")),
                    "notes": _bounded_text(raw.get("notes")),
                    "x": raw.get("x"),
                    "y": raw.get("y"),
                    "width": raw.get("width"),
                    "height": raw.get("height"),
                }
            )
    return nodes


def _edges(value: Any) -> list[dict[str, str]]:
    edges = []
    for raw in _bounded_list(value, MAX_VISUAL_ITEMS):
        if not isinstance(raw, dict):
            continue
        source = _slug(raw.get("from") or raw.get("source"))
        target = _slug(raw.get("to") or raw.get("target"))
        if source and target:
            edges.append({"from": source, "to": target, "label": _bounded_text(raw.get("label")), "evidence": _bounded_text(raw.get("evidence"))})
    return edges


def _sections(value: Any) -> list[dict[str, str]]:
    sections = []
    for raw in _bounded_list(value, MAX_VISUAL_ITEMS):
        if not isinstance(raw, dict):
            continue
        title = _bounded_text(raw.get("title") or raw.get("heading"))
        body = _bounded_text(raw.get("body") or raw.get("description"))
        if title or body:
            sections.append({"title": title, "body": body})
    return sections


def _metrics(value: Any) -> list[dict[str, str]]:
    metrics = []
    for raw in _bounded_list(value, MAX_VISUAL_ITEMS):
        if not isinstance(raw, dict):
            continue
        label = _bounded_text(raw.get("label") or raw.get("name"))
        metric_value = _bounded_text(raw.get("value"))
        if label and metric_value:
            metrics.append({"label": label, "value": metric_value, "unit": _bounded_text(raw.get("unit")), "source": _bounded_text(raw.get("source")), "notes": _bounded_text(raw.get("notes"))})
    return metrics


def _append_sections(lines: list[str], sections: list[dict[str, str]]) -> None:
    if not sections:
        return
    lines.extend(["## Sections", ""])
    for section in sections:
        heading = section["title"] or "Section"
        lines.extend([f"### {heading}", "", section["body"], ""])


def _append_list(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines.extend([f"## {title}", ""])
    for item in items:
        lines.append(f"- {item}")
    lines.append("")


def _excalidraw_element(element_id: str, element_type: str, *, x: int, y: int, width: int, height: int) -> dict[str, Any]:
    return {
        "id": element_id,
        "type": element_type,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "angle": 0,
        "strokeColor": "#1f2937",
        "backgroundColor": "#f8fafc",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": {"type": 3},
        "seed": 1,
        "versionNonce": 1,
        "isDeleted": False,
        "boundElements": [],
        "updated": 1,
        "link": None,
        "locked": False,
    }


def _excalidraw_text(element_id: str, text: str, *, x: int, y: int, width: int, height: int, font_size: int = 18) -> dict[str, Any]:
    element = _excalidraw_element(element_id, "text", x=x, y=y, width=width, height=height)
    element.update(
        {
            "text": text,
            "fontSize": font_size,
            "fontFamily": 5,
            "textAlign": "left",
            "verticalAlign": "top",
            "containerId": None,
            "originalText": text,
            "lineHeight": 1.25,
            "backgroundColor": "transparent",
            "strokeColor": "#111827",
        }
    )
    return element


def _excalidraw_arrow(element_id: str, *, start: tuple[int, int], end: tuple[int, int]) -> dict[str, Any]:
    x = start[0]
    y = start[1]
    width = end[0] - start[0]
    height = end[1] - start[1]
    element = _excalidraw_element(element_id, "arrow", x=x, y=y, width=width, height=height)
    element.update(
        {
            "backgroundColor": "transparent",
            "points": [[0, 0], [width, height]],
            "lastCommittedPoint": None,
            "startBinding": None,
            "endBinding": None,
            "startArrowhead": None,
            "endArrowhead": "arrow",
        }
    )
    return element


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


def _bounded_text(value: Any) -> str:
    return " ".join(str(value or "").split())[:MAX_TEXT_CHARS]


def _bounded_int(value: Any, *, default: int, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(low, min(number, high))


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


def _slug(value: Any) -> str:
    text = _bounded_text(value).lower()
    slug = "".join(char if char.isalnum() else "-" for char in text).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:80]


def _mermaid_id(value: str) -> str:
    ident = "".join(char if char.isalnum() else "_" for char in value)
    if not ident or ident[0].isdigit():
        ident = f"n_{ident}"
    return ident


def _escape_mermaid_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _is_within(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)
