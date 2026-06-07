from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


MAX_TRAVEL_ITEMS = 200
MAX_TEXT_CHARS = 20_000


class TravelPlanCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="travel_plan_create",
            description=(
                "Create a local travel, route, commute, or itinerary planning artifact from explicit evidence. "
                "Stores places, route options, itinerary days, constraints, source refs, uncertainties, and approval boundaries. "
                "This does not book, pay, cancel, contact venues, or claim live routing without evidence."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/travel/plans."},
                    "title": {"type": "string"},
                    "origin": {"type": "string"},
                    "destination": {"type": "string"},
                    "date_range": {"type": "string"},
                    "travelers": {"type": "string"},
                    "budget": {"type": "string"},
                    "preferences": {"type": "array", "items": {"type": "string"}},
                    "constraints": {"type": "array", "items": {"type": "string"}},
                    "places": {"type": "array", "items": {"type": "object"}},
                    "route_options": {"type": "array", "items": {"type": "object"}},
                    "itinerary_days": {"type": "array", "items": {"type": "object"}},
                    "source_refs": {"type": "array", "items": {"type": "string"}},
                    "evidence_checked_at": {"type": "string"},
                    "uncertainties": {"type": "array", "items": {"type": "string"}},
                    "approval_boundaries": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                required=["title", "reason"],
            ),
            capability_group="travel",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        title = " ".join(str(tool_input.get("title") or "").split())
        reason = str(tool_input.get("reason") or "").strip()
        if not title or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Travel plan title and reason are required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"travel-plan-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "travel" / "plans" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Travel plan path is outside allowed write roots.")
        artifact = _travel_plan(tool_input, title=title, reason=reason, markdown_path=markdown_path)
        markdown = _render_travel_plan(artifact)
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would create travel plan {markdown_path}.", {"path": str(markdown_path), "artifact": artifact})
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        metadata_path = markdown_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created travel plan artifact {markdown_path}.",
            {
                "path": str(markdown_path),
                "metadata_path": str(metadata_path),
                "travel_plan_id": artifact["travel_plan_id"],
                "place_count": len(artifact["places"]),
                "route_option_count": len(artifact["route_options"]),
                "itinerary_day_count": len(artifact["itinerary_days"]),
                "approval_status": artifact["approval_status"],
                "source": "travel_plan_create",
            },
        )


class TravelPlanInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="travel_plan_inspect",
            description="Inspect a local travel plan artifact for routes, places, itinerary days, evidence refs, approval boundaries, and preview text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string", "description": "Workspace-relative or allowed absolute travel plan markdown path."}}, required=["path"]),
            capability_group="travel",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_allowed_path(normalized, str(tool_input.get("path") or ""), subdir="travel/plans", suffix=".md")
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Travel plan path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".md":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Travel plan file does not exist.")
        metadata = _load_sidecar(path.with_suffix(".json"))
        text = path.read_text(encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected travel plan artifact {path}.",
            {
                "path": str(path),
                "metadata_path": str(path.with_suffix(".json")) if path.with_suffix(".json").exists() else "",
                "travel_plan_id": metadata.get("travel_plan_id", ""),
                "title": metadata.get("title", ""),
                "origin": metadata.get("origin", ""),
                "destination": metadata.get("destination", ""),
                "place_count": len(metadata.get("places", [])) if isinstance(metadata.get("places"), list) else 0,
                "route_option_count": len(metadata.get("route_options", [])) if isinstance(metadata.get("route_options"), list) else 0,
                "itinerary_day_count": len(metadata.get("itinerary_days", [])) if isinstance(metadata.get("itinerary_days"), list) else 0,
                "uncertainty_count": len(metadata.get("uncertainties", [])) if isinstance(metadata.get("uncertainties"), list) else 0,
                "approval_status": metadata.get("approval_status", ""),
                "preview": text[:4000],
                "source": "travel_plan_inspect",
            },
        )


def default_travel_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        TravelPlanCreateTool(),
        TravelPlanInspectTool(),
    ]
    return {tool.name: tool for tool in tools}


def _travel_plan(tool_input: dict[str, Any], *, title: str, reason: str, markdown_path: Path) -> dict[str, Any]:
    approval_boundaries = _string_list(tool_input.get("approval_boundaries"), limit=MAX_TRAVEL_ITEMS)
    if not approval_boundaries:
        approval_boundaries = [
            "No bookings, payments, cancellations, or venue contacts were performed.",
            "Changing travel facts require current source verification before action.",
        ]
    return {
        "travel_plan_id": f"travel-plan-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "origin": _bounded_text(tool_input.get("origin")),
        "destination": _bounded_text(tool_input.get("destination")),
        "date_range": _bounded_text(tool_input.get("date_range")),
        "travelers": _bounded_text(tool_input.get("travelers")),
        "budget": _bounded_text(tool_input.get("budget")),
        "preferences": _string_list(tool_input.get("preferences"), limit=MAX_TRAVEL_ITEMS),
        "constraints": _string_list(tool_input.get("constraints"), limit=MAX_TRAVEL_ITEMS),
        "places": _places(tool_input.get("places")),
        "route_options": _routes(tool_input.get("route_options")),
        "itinerary_days": _itinerary_days(tool_input.get("itinerary_days")),
        "source_refs": _string_list(tool_input.get("source_refs"), limit=MAX_TRAVEL_ITEMS),
        "evidence_checked_at": _bounded_text(tool_input.get("evidence_checked_at")) or datetime.now(timezone.utc).isoformat(),
        "uncertainties": _string_list(tool_input.get("uncertainties"), limit=MAX_TRAVEL_ITEMS),
        "approval_boundaries": approval_boundaries,
        "approval_status": "planning_only_not_booked",
        "reason": reason,
        "path": str(markdown_path),
        "status": "prepared_not_booked",
    }


def _places(value: Any) -> list[dict[str, str]]:
    places = []
    for raw in _bounded_list(value, MAX_TRAVEL_ITEMS):
        if not isinstance(raw, dict):
            continue
        name = _bounded_text(raw.get("name"))
        if not name:
            continue
        places.append(
            {
                "name": name,
                "kind": _bounded_text(raw.get("kind")),
                "location": _bounded_text(raw.get("location")),
                "hours": _bounded_text(raw.get("hours")),
                "cost": _bounded_text(raw.get("cost")),
                "notes": _bounded_text(raw.get("notes")),
                "source_ref": _bounded_text(raw.get("source_ref")),
            }
        )
    return places


def _routes(value: Any) -> list[dict[str, str]]:
    routes = []
    for raw in _bounded_list(value, MAX_TRAVEL_ITEMS):
        if not isinstance(raw, dict):
            continue
        label = _bounded_text(raw.get("label") or raw.get("name"))
        if not label:
            continue
        routes.append(
            {
                "label": label,
                "mode": _bounded_text(raw.get("mode")),
                "estimated_duration": _bounded_text(raw.get("estimated_duration")),
                "estimated_cost": _bounded_text(raw.get("estimated_cost")),
                "reliability": _bounded_text(raw.get("reliability")),
                "accessibility": _bounded_text(raw.get("accessibility")),
                "tradeoffs": _bounded_text(raw.get("tradeoffs")),
                "source_ref": _bounded_text(raw.get("source_ref")),
            }
        )
    return routes


def _itinerary_days(value: Any) -> list[dict[str, Any]]:
    days = []
    for raw in _bounded_list(value, MAX_TRAVEL_ITEMS):
        if not isinstance(raw, dict):
            continue
        label = _bounded_text(raw.get("label") or raw.get("date"))
        if not label:
            continue
        items = []
        for item in _bounded_list(raw.get("items"), MAX_TRAVEL_ITEMS):
            if not isinstance(item, dict):
                continue
            activity = _bounded_text(item.get("activity"))
            if activity:
                items.append(
                    {
                        "time": _bounded_text(item.get("time")),
                        "activity": activity,
                        "location": _bounded_text(item.get("location")),
                        "notes": _bounded_text(item.get("notes")),
                    }
                )
        days.append({"label": label, "summary": _bounded_text(raw.get("summary")), "items": items})
    return days


def _render_travel_plan(plan: dict[str, Any]) -> str:
    lines = [f"# {plan['title']}", "", f"Status: {plan['status']}", f"Approval status: {plan['approval_status']}", ""]
    for key in ("origin", "destination", "date_range", "travelers", "budget", "evidence_checked_at"):
        if plan[key]:
            lines.append(f"{key.replace('_', ' ').title()}: {plan[key]}")
    lines.append("")
    _append_list(lines, "Preferences", plan["preferences"])
    _append_list(lines, "Constraints", plan["constraints"])
    if plan["route_options"]:
        lines.extend(["## Route Options", "", "| Label | Mode | Duration | Cost | Reliability | Accessibility | Tradeoffs | Source |", "| --- | --- | --- | --- | --- | --- | --- | --- |"])
        for route in plan["route_options"]:
            lines.append(
                f"| {route['label']} | {route['mode']} | {route['estimated_duration']} | {route['estimated_cost']} | {route['reliability']} | {route['accessibility']} | {route['tradeoffs']} | {route['source_ref']} |"
            )
        lines.append("")
    if plan["places"]:
        lines.extend(["## Places", "", "| Name | Kind | Location | Hours | Cost | Notes | Source |", "| --- | --- | --- | --- | --- | --- | --- |"])
        for place in plan["places"]:
            lines.append(f"| {place['name']} | {place['kind']} | {place['location']} | {place['hours']} | {place['cost']} | {place['notes']} | {place['source_ref']} |")
        lines.append("")
    if plan["itinerary_days"]:
        lines.extend(["## Itinerary", ""])
        for day in plan["itinerary_days"]:
            lines.extend([f"### {day['label']}", "", day["summary"], ""])
            for item in day["items"]:
                prefix = f"{item['time']} - " if item["time"] else ""
                location = f" ({item['location']})" if item["location"] else ""
                notes = f": {item['notes']}" if item["notes"] else ""
                lines.append(f"- {prefix}{item['activity']}{location}{notes}")
            lines.append("")
    _append_list(lines, "Source References", plan["source_refs"])
    _append_list(lines, "Uncertainties", plan["uncertainties"])
    _append_list(lines, "Approval Boundaries", plan["approval_boundaries"])
    lines.append(f"Created: {plan['created_at']}")
    return "\n".join(lines) + "\n"


def _append_list(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines.extend([f"## {title}", ""])
    for item in items:
        lines.append(f"- {item}")
    lines.append("")


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
