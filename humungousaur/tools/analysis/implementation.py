from __future__ import annotations

import csv
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
from statistics import mean
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


CSV_PROFILE_MAX_ROWS = 100_000
CSV_PROFILE_MAX_SAMPLE_ROWS = 25
CHART_MAX_POINTS = 500
REPORT_MAX_SECTIONS = 40


class CsvDatasetProfileTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="csv_dataset_profile",
            description=(
                "Profile a local CSV dataset with columns, row count, sample rows, missing counts, "
                "unique samples, and numeric min/max/mean. Use for bounded data analysis before reporting."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "path": {"type": "string", "description": "Workspace-relative or allowed absolute CSV path."},
                    "max_rows": {"type": "integer", "minimum": 1, "maximum": CSV_PROFILE_MAX_ROWS},
                    "sample_rows": {"type": "integer", "minimum": 1, "maximum": CSV_PROFILE_MAX_SAMPLE_ROWS},
                },
                required=["path"],
            ),
            capability_group="analysis",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_allowed_path(normalized, str(tool_input.get("path") or ""), suffix=".csv")
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "CSV path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".csv":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "CSV file does not exist.")
        max_rows = max(1, min(int(tool_input.get("max_rows") or 10_000), CSV_PROFILE_MAX_ROWS))
        sample_limit = max(1, min(int(tool_input.get("sample_rows") or 5), CSV_PROFILE_MAX_SAMPLE_ROWS))
        try:
            profile = _profile_csv(path, max_rows=max_rows, sample_rows=sample_limit)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "CSV profile failed.", error=str(exc))
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Profiled CSV dataset {path} with {profile['row_count']} sampled row(s).",
            {"path": str(path), **profile, "source": "csv_dataset_profile"},
        )


class ChartArtifactCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="chart_artifact_create",
            description=(
                "Create a local SVG chart artifact from structured data. Supports bar and line charts with labels, "
                "source note, and a machine-readable metadata sidecar."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output SVG filename under data_dir/charts."},
                    "title": {"type": "string"},
                    "chart_type": {"type": "string", "enum": ["bar", "line"]},
                    "x_label": {"type": "string"},
                    "y_label": {"type": "string"},
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Point objects with label and value.",
                    },
                    "source_note": {"type": "string"},
                    "reason": {"type": "string"},
                },
                required=["title", "chart_type", "data", "reason"],
            ),
            capability_group="analysis",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        title = " ".join(str(tool_input.get("title") or "").split())
        chart_type = str(tool_input.get("chart_type") or "").strip().lower()
        points = _chart_points(tool_input.get("data"))
        if not title:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Chart title is required.")
        if chart_type not in {"bar", "line"}:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Unsupported chart type.")
        if not points:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "At least one chart data point is required.")
        filename = _safe_filename(str(tool_input.get("filename") or "humungousaur-chart.svg"), ".svg")
        path = (normalized.data_dir / "charts" / filename).resolve()
        if not _is_within(path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Chart path is outside allowed write roots.")
        metadata = {
            "title": title,
            "chart_type": chart_type,
            "x_label": str(tool_input.get("x_label") or ""),
            "y_label": str(tool_input.get("y_label") or ""),
            "source_note": str(tool_input.get("source_note") or ""),
            "point_count": len(points),
            "data": points,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reason": str(tool_input.get("reason") or ""),
        }
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would create chart {path}.", {"path": str(path), "metadata": metadata})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_render_svg_chart(metadata), encoding="utf-8")
        sidecar = path.with_suffix(".json")
        sidecar.write_text(json.dumps(metadata, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created {chart_type} chart artifact {path}.",
            {"path": str(path), "metadata_path": str(sidecar), "metadata": metadata, "source": "chart_artifact_create"},
        )


class ChartArtifactInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="chart_artifact_inspect",
            description="Inspect a local chart SVG artifact and metadata sidecar for title, chart type, point count, and source note.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string", "description": "Workspace-relative or allowed absolute SVG chart path."}}, required=["path"]),
            capability_group="analysis",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_allowed_path(normalized, str(tool_input.get("path") or ""), subdir="charts", suffix=".svg")
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Chart path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".svg":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Chart SVG file does not exist.")
        sidecar = path.with_suffix(".json")
        metadata: dict[str, Any] = {}
        if sidecar.exists():
            try:
                metadata = json.loads(sidecar.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                metadata = {}
        svg = path.read_text(encoding="utf-8")[:4000]
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected chart artifact {path}.",
            {
                "path": str(path),
                "metadata_path": str(sidecar) if sidecar.exists() else "",
                "title": metadata.get("title", ""),
                "chart_type": metadata.get("chart_type", ""),
                "point_count": metadata.get("point_count", 0),
                "source_note": metadata.get("source_note", ""),
                "svg_preview": svg,
                "source": "chart_artifact_inspect",
            },
        )


class BusinessReportCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="business_report_create",
            description=(
                "Create a local markdown business report from structured summary, metrics, findings, recommendations, "
                "and artifact references. Does not publish or send."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/reports."},
                    "title": {"type": "string"},
                    "audience": {"type": "string"},
                    "period": {"type": "string"},
                    "summary": {"type": "string"},
                    "metrics": {"type": "array", "items": {"type": "object"}},
                    "findings": {"type": "array", "items": {"type": "string"}},
                    "recommendations": {"type": "array", "items": {"type": "string"}},
                    "artifact_paths": {"type": "array", "items": {"type": "string"}},
                    "assumptions": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                required=["title", "summary", "reason"],
            ),
            capability_group="analysis",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        title = " ".join(str(tool_input.get("title") or "").split())
        summary = str(tool_input.get("summary") or "").strip()
        if not title or not summary:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Report title and summary are required.")
        filename = _safe_filename(str(tool_input.get("filename") or "humungousaur-report.md"), ".md")
        path = (normalized.data_dir / "reports" / filename).resolve()
        if not _is_within(path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Report path is outside allowed write roots.")
        report = _render_business_report(tool_input, title=title, summary=summary)
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would create report {path}.", {"path": str(path), "preview": report[:1200]})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created business report {path}.",
            {"path": str(path), "title": title, "summary_length": len(summary), "artifact_count": len(_string_list(tool_input.get("artifact_paths"))), "source": "business_report_create"},
        )


def default_analysis_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        CsvDatasetProfileTool(),
        ChartArtifactCreateTool(),
        ChartArtifactInspectTool(),
        BusinessReportCreateTool(),
    ]
    return {tool.name: tool for tool in tools}


def _profile_csv(path: Path, *, max_rows: int, sample_rows: int) -> dict[str, Any]:
    row_count = 0
    samples: list[dict[str, str]] = []
    missing: dict[str, int] = {}
    numeric: dict[str, list[float]] = {}
    unique_samples: dict[str, set[str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        missing = {column: 0 for column in columns}
        numeric = {column: [] for column in columns}
        unique_samples = {column: set() for column in columns}
        for row in reader:
            row_count += 1
            if len(samples) < sample_rows:
                samples.append({column: str(row.get(column, "")) for column in columns})
            for column in columns:
                raw = str(row.get(column, "")).strip()
                if not raw:
                    missing[column] += 1
                    continue
                if len(unique_samples[column]) < 10:
                    unique_samples[column].add(raw)
                try:
                    numeric[column].append(float(raw.replace(",", "")))
                except ValueError:
                    pass
            if row_count >= max_rows:
                break
    numeric_summary = {
        column: {"min": min(values), "max": max(values), "mean": mean(values), "count": len(values)}
        for column, values in numeric.items()
        if values
    }
    return {
        "columns": columns,
        "row_count": row_count,
        "truncated": row_count >= max_rows,
        "sample_rows": samples,
        "missing_counts": missing,
        "numeric_summary": numeric_summary,
        "unique_samples": {column: sorted(values) for column, values in unique_samples.items()},
    }


def _render_svg_chart(metadata: dict[str, Any]) -> str:
    points = metadata["data"][:CHART_MAX_POINTS]
    width = 760
    height = 420
    margin_left = 70
    margin_bottom = 70
    plot_width = width - margin_left - 40
    plot_height = height - 100 - margin_bottom
    values = [float(point["value"]) for point in points]
    max_value = max(values) if values else 1.0
    min_value = min(0.0, min(values) if values else 0.0)
    span = max(max_value - min_value, 1.0)
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        f"<title>{escape(metadata['title'])}</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width / 2}" y="34" text-anchor="middle" font-family="Arial" font-size="22" font-weight="700">{escape(metadata["title"])}</text>',
        f'<line x1="{margin_left}" y1="{height - margin_bottom}" x2="{width - 30}" y2="{height - margin_bottom}" stroke="#273043" stroke-width="1.5"/>',
        f'<line x1="{margin_left}" y1="70" x2="{margin_left}" y2="{height - margin_bottom}" stroke="#273043" stroke-width="1.5"/>',
    ]
    if metadata["chart_type"] == "bar":
        slot = plot_width / max(len(points), 1)
        bar_width = max(8, min(46, slot * 0.62))
        for index, point in enumerate(points):
            value = float(point["value"])
            bar_height = (value - min_value) / span * plot_height
            x = margin_left + index * slot + (slot - bar_width) / 2
            y = height - margin_bottom - bar_height
            elements.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" height="{bar_height:.2f}" fill="#1f77b4"/>')
            elements.append(f'<text x="{x + bar_width / 2:.2f}" y="{height - margin_bottom + 18}" text-anchor="middle" font-family="Arial" font-size="11">{escape(point["label"][:14])}</text>')
            elements.append(f'<text x="{x + bar_width / 2:.2f}" y="{y - 6:.2f}" text-anchor="middle" font-family="Arial" font-size="11">{value:g}</text>')
    else:
        coords = []
        for index, point in enumerate(points):
            value = float(point["value"])
            x = margin_left + (index / max(len(points) - 1, 1)) * plot_width
            y = height - margin_bottom - ((value - min_value) / span * plot_height)
            coords.append((x, y, point, value))
        if coords:
            elements.append('<polyline fill="none" stroke="#2ca02c" stroke-width="3" points="' + " ".join(f"{x:.2f},{y:.2f}" for x, y, _, _ in coords) + '"/>')
        for x, y, point, value in coords:
            elements.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="#2ca02c"/>')
            elements.append(f'<text x="{x:.2f}" y="{height - margin_bottom + 18}" text-anchor="middle" font-family="Arial" font-size="11">{escape(point["label"][:14])}</text>')
            elements.append(f'<text x="{x:.2f}" y="{y - 8:.2f}" text-anchor="middle" font-family="Arial" font-size="11">{value:g}</text>')
    if metadata.get("x_label"):
        elements.append(f'<text x="{width / 2}" y="{height - 18}" text-anchor="middle" font-family="Arial" font-size="13">{escape(metadata["x_label"])}</text>')
    if metadata.get("y_label"):
        elements.append(f'<text x="18" y="{height / 2}" transform="rotate(-90 18 {height / 2})" text-anchor="middle" font-family="Arial" font-size="13">{escape(metadata["y_label"])}</text>')
    if metadata.get("source_note"):
        elements.append(f'<text x="{margin_left}" y="{height - 44}" font-family="Arial" font-size="11" fill="#555">{escape(metadata["source_note"][:120])}</text>')
    elements.append("</svg>")
    return "\n".join(elements)


def _render_business_report(tool_input: dict[str, Any], *, title: str, summary: str) -> str:
    lines = [f"# {title}", ""]
    audience = str(tool_input.get("audience") or "").strip()
    period = str(tool_input.get("period") or "").strip()
    if audience or period:
        lines.append(f"Audience: {audience or 'unspecified'}")
        lines.append(f"Period: {period or 'unspecified'}")
        lines.append("")
    lines.extend(["## Executive Summary", "", summary, ""])
    metrics = [item for item in tool_input.get("metrics", []) if isinstance(item, dict)]
    if metrics:
        lines.extend(["## Metrics", "", "| Metric | Value | Note |", "| --- | ---: | --- |"])
        for metric in metrics[:100]:
            lines.append(f"| {str(metric.get('name', '')).strip()} | {str(metric.get('value', '')).strip()} | {str(metric.get('note', '')).strip()} |")
        lines.append("")
    _append_list_section(lines, "Findings", _string_list(tool_input.get("findings")))
    _append_list_section(lines, "Recommendations", _string_list(tool_input.get("recommendations")))
    _append_list_section(lines, "Assumptions And Caveats", _string_list(tool_input.get("assumptions")))
    artifacts = _string_list(tool_input.get("artifact_paths"))
    if artifacts:
        lines.extend(["## Artifacts", ""])
        for artifact in artifacts:
            lines.append(f"- `{artifact}`")
        lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    return "\n".join(lines) + "\n"


def _append_list_section(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines.extend([f"## {title}", ""])
    for item in items[:REPORT_MAX_SECTIONS]:
        lines.append(f"- {item}")
    lines.append("")


def _chart_points(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    points = []
    for item in value[:CHART_MAX_POINTS]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("x") or "").strip()
        raw_value = item.get("value", item.get("y"))
        try:
            numeric = float(str(raw_value).replace(",", ""))
        except (TypeError, ValueError):
            continue
        if label:
            points.append({"label": label, "value": numeric})
    return points


def _safe_filename(value: str, suffix: str) -> str:
    name = Path(value).name.strip() or f"artifact{suffix}"
    if not name.lower().endswith(suffix):
        name += suffix
    stem = "".join(char if char.isalnum() or char in ("-", "_", ".") else "-" for char in Path(name).stem).strip(".-")
    return f"{stem or 'artifact'}{suffix}"


def _resolve_allowed_path(config: AgentConfig, raw_path: str, *, subdir: str = "", suffix: str = "") -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = config.workspace / path
        if not path.exists():
            data_path = config.data_dir / raw_path
            if data_path.exists():
                path = data_path
            elif subdir:
                artifact_path = config.data_dir / subdir / Path(raw_path).name
                if artifact_path.exists():
                    path = artifact_path
    if suffix and not path.suffix:
        path = path.with_suffix(suffix)
    return path.resolve()


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _is_within(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)
