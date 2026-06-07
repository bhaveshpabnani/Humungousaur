from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


MAX_PERSONAL_ITEMS = 200
MAX_TEXT_CHARS = 20_000


class ContactNoteCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="contact_note_create",
            description=(
                "Create a local contact or relationship note artifact from explicit evidence with privacy labels, "
                "preferences, follow-ups, and memory boundary. This does not write durable memory unless another approved tool is used."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/personal/contact_notes."},
                    "person_name": {"type": "string"},
                    "role": {"type": "string"},
                    "organization": {"type": "string"},
                    "preferred_channel": {"type": "string"},
                    "timezone": {"type": "string"},
                    "facts": {"type": "array", "items": {"type": "object"}},
                    "preferences": {"type": "array", "items": {"type": "object"}},
                    "followups": {"type": "array", "items": {"type": "object"}},
                    "sensitivity": {"type": "string", "enum": ["low", "medium", "high"]},
                    "source_refs": {"type": "array", "items": {"type": "string"}},
                    "memory_boundary": {"type": "string"},
                    "reason": {"type": "string"},
                },
                required=["person_name", "reason"],
            ),
            capability_group="personal",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        person_name = " ".join(str(tool_input.get("person_name") or "").split())
        reason = str(tool_input.get("reason") or "").strip()
        if not person_name or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Person name and reason are required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"contact-note-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "personal" / "contact_notes" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Contact note path is outside allowed write roots.")
        artifact = _contact_artifact(tool_input, person_name=person_name, reason=reason, markdown_path=markdown_path)
        markdown = _render_contact_note(artifact)
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would create contact note {markdown_path}.", {"path": str(markdown_path), "artifact": artifact})
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        metadata_path = markdown_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created contact note artifact {markdown_path}.",
            {
                "path": str(markdown_path),
                "metadata_path": str(metadata_path),
                "contact_note_id": artifact["contact_note_id"],
                "person_name": artifact["person_name"],
                "fact_count": len(artifact["facts"]),
                "preference_count": len(artifact["preferences"]),
                "followup_count": len(artifact["followups"]),
                "memory_status": artifact["memory_status"],
                "source": "contact_note_create",
            },
        )


class ContactNoteInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="contact_note_inspect",
            description="Inspect a local contact/relationship note artifact for evidence, sensitivity, follow-ups, memory status, and preview text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string", "description": "Workspace-relative or allowed absolute contact note markdown path."}}, required=["path"]),
            capability_group="personal",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_allowed_path(normalized, str(tool_input.get("path") or ""), subdir="personal/contact_notes", suffix=".md")
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Contact note path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".md":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Contact note file does not exist.")
        metadata = _load_sidecar(path.with_suffix(".json"))
        text = path.read_text(encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected contact note artifact {path}.",
            {
                "path": str(path),
                "metadata_path": str(path.with_suffix(".json")) if path.with_suffix(".json").exists() else "",
                "contact_note_id": metadata.get("contact_note_id", ""),
                "person_name": metadata.get("person_name", ""),
                "sensitivity": metadata.get("sensitivity", ""),
                "fact_count": len(metadata.get("facts", [])) if isinstance(metadata.get("facts"), list) else 0,
                "followup_count": len(metadata.get("followups", [])) if isinstance(metadata.get("followups"), list) else 0,
                "memory_status": metadata.get("memory_status", ""),
                "preview": text[:4000],
                "source": "contact_note_inspect",
            },
        )


class DailyPlanCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="daily_plan_create",
            description=(
                "Create a local daily/work-session planning artifact from explicit evidence, priorities, time blocks, commitments, "
                "waiting items, recovery time, and optional reminder drafts. This does not create wakeups or commitments by itself."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/personal/daily_plans."},
                    "title": {"type": "string"},
                    "date": {"type": "string"},
                    "time_window": {"type": "string"},
                    "energy": {"type": "string"},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}},
                    "must_do": {"type": "array", "items": {"type": "object"}},
                    "time_blocks": {"type": "array", "items": {"type": "object"}},
                    "waiting": {"type": "array", "items": {"type": "string"}},
                    "deferred": {"type": "array", "items": {"type": "string"}},
                    "reminder_drafts": {"type": "array", "items": {"type": "object"}},
                    "risks": {"type": "array", "items": {"type": "string"}},
                    "summary": {"type": "string"},
                    "reason": {"type": "string"},
                },
                required=["title", "reason"],
            ),
            capability_group="personal",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        title = " ".join(str(tool_input.get("title") or "").split())
        reason = str(tool_input.get("reason") or "").strip()
        if not title or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Daily plan title and reason are required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"daily-plan-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "personal" / "daily_plans" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Daily plan path is outside allowed write roots.")
        artifact = _daily_plan_artifact(tool_input, title=title, reason=reason, markdown_path=markdown_path)
        markdown = _render_daily_plan(artifact)
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would create daily plan {markdown_path}.", {"path": str(markdown_path), "artifact": artifact})
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        metadata_path = markdown_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created daily plan artifact {markdown_path}.",
            {
                "path": str(markdown_path),
                "metadata_path": str(metadata_path),
                "daily_plan_id": artifact["daily_plan_id"],
                "must_do_count": len(artifact["must_do"]),
                "time_block_count": len(artifact["time_blocks"]),
                "reminder_draft_count": len(artifact["reminder_drafts"]),
                "plan_status": artifact["plan_status"],
                "source": "daily_plan_create",
            },
        )


class DailyPlanInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="daily_plan_inspect",
            description="Inspect a local daily/work-session planning artifact for priorities, blocks, reminders, evidence, and preview text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string", "description": "Workspace-relative or allowed absolute daily plan markdown path."}}, required=["path"]),
            capability_group="personal",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_allowed_path(normalized, str(tool_input.get("path") or ""), subdir="personal/daily_plans", suffix=".md")
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Daily plan path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".md":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Daily plan file does not exist.")
        metadata = _load_sidecar(path.with_suffix(".json"))
        text = path.read_text(encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected daily plan artifact {path}.",
            {
                "path": str(path),
                "metadata_path": str(path.with_suffix(".json")) if path.with_suffix(".json").exists() else "",
                "daily_plan_id": metadata.get("daily_plan_id", ""),
                "title": metadata.get("title", ""),
                "must_do_count": len(metadata.get("must_do", [])) if isinstance(metadata.get("must_do"), list) else 0,
                "time_block_count": len(metadata.get("time_blocks", [])) if isinstance(metadata.get("time_blocks"), list) else 0,
                "reminder_draft_count": len(metadata.get("reminder_drafts", [])) if isinstance(metadata.get("reminder_drafts"), list) else 0,
                "plan_status": metadata.get("plan_status", ""),
                "preview": text[:4000],
                "source": "daily_plan_inspect",
            },
        )


def default_personal_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        ContactNoteCreateTool(),
        ContactNoteInspectTool(),
        DailyPlanCreateTool(),
        DailyPlanInspectTool(),
    ]
    return {tool.name: tool for tool in tools}


def _contact_artifact(tool_input: dict[str, Any], *, person_name: str, reason: str, markdown_path: Path) -> dict[str, Any]:
    return {
        "contact_note_id": f"contact-note-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "person_name": person_name,
        "role": _bounded_text(tool_input.get("role")),
        "organization": _bounded_text(tool_input.get("organization")),
        "preferred_channel": _bounded_text(tool_input.get("preferred_channel")),
        "timezone": _bounded_text(tool_input.get("timezone")),
        "facts": _evidence_items(tool_input.get("facts"), label_key="fact"),
        "preferences": _evidence_items(tool_input.get("preferences"), label_key="preference"),
        "followups": _followups(tool_input.get("followups")),
        "sensitivity": _sensitivity(tool_input.get("sensitivity")),
        "source_refs": _string_list(tool_input.get("source_refs"), limit=MAX_PERSONAL_ITEMS),
        "memory_boundary": _bounded_text(tool_input.get("memory_boundary")) or "Prepared local artifact only; durable memory requires an explicit memory tool action.",
        "memory_status": "prepared_not_memorized",
        "reason": reason,
        "path": str(markdown_path),
        "safety_note": "Do not infer protected traits, emotions, relationship quality, health, politics, or private facts without direct evidence.",
    }


def _daily_plan_artifact(tool_input: dict[str, Any], *, title: str, reason: str, markdown_path: Path) -> dict[str, Any]:
    return {
        "daily_plan_id": f"daily-plan-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "date": _bounded_text(tool_input.get("date")),
        "time_window": _bounded_text(tool_input.get("time_window")),
        "energy": _bounded_text(tool_input.get("energy")),
        "evidence_refs": _string_list(tool_input.get("evidence_refs"), limit=MAX_PERSONAL_ITEMS),
        "must_do": _tasks(tool_input.get("must_do")),
        "time_blocks": _time_blocks(tool_input.get("time_blocks")),
        "waiting": _string_list(tool_input.get("waiting"), limit=MAX_PERSONAL_ITEMS),
        "deferred": _string_list(tool_input.get("deferred"), limit=MAX_PERSONAL_ITEMS),
        "reminder_drafts": _reminders(tool_input.get("reminder_drafts")),
        "risks": _string_list(tool_input.get("risks"), limit=MAX_PERSONAL_ITEMS),
        "summary": _bounded_text(tool_input.get("summary")),
        "reason": reason,
        "path": str(markdown_path),
        "plan_status": "prepared_not_scheduled",
        "safety_note": "Reminder drafts and commitments are not created unless a separate approved cognition/wakeup tool records them.",
    }


def _render_contact_note(note: dict[str, Any]) -> str:
    lines = [f"# {note['person_name']}", "", f"Memory status: {note['memory_status']}", f"Sensitivity: {note['sensitivity']}", ""]
    for key in ("role", "organization", "preferred_channel", "timezone"):
        if note[key]:
            lines.append(f"{key.replace('_', ' ').title()}: {note[key]}")
    lines.append("")
    _append_evidence_table(lines, "Facts", note["facts"], "fact")
    _append_evidence_table(lines, "Preferences", note["preferences"], "preference")
    if note["followups"]:
        lines.extend(["## Follow-Ups", "", "| Title | Due | Reason | Evidence |", "| --- | --- | --- | --- |"])
        for item in note["followups"]:
            lines.append(f"| {item['title']} | {item['due']} | {item['reason']} | {item['evidence']} |")
        lines.append("")
    _append_list(lines, "Source References", note["source_refs"])
    lines.extend(["## Memory Boundary", "", note["memory_boundary"], "", "## Safety Note", "", note["safety_note"], "", f"Created: {note['created_at']}"])
    return "\n".join(lines) + "\n"


def _render_daily_plan(plan: dict[str, Any]) -> str:
    lines = [f"# {plan['title']}", "", f"Plan status: {plan['plan_status']}", ""]
    for key in ("date", "time_window", "energy"):
        if plan[key]:
            lines.append(f"{key.replace('_', ' ').title()}: {plan[key]}")
    lines.append("")
    if plan["summary"]:
        lines.extend(["## Summary", "", plan["summary"], ""])
    if plan["must_do"]:
        lines.extend(["## Must Do", "", "| Task | Priority | Evidence | Reason |", "| --- | --- | --- | --- |"])
        for item in plan["must_do"]:
            lines.append(f"| {item['title']} | {item['priority']} | {item['evidence']} | {item['reason']} |")
        lines.append("")
    if plan["time_blocks"]:
        lines.extend(["## Time Blocks", "", "| Time | Focus | Notes |", "| --- | --- | --- |"])
        for item in plan["time_blocks"]:
            lines.append(f"| {item['time']} | {item['focus']} | {item['notes']} |")
        lines.append("")
    _append_list(lines, "Waiting", plan["waiting"])
    _append_list(lines, "Deferred", plan["deferred"])
    if plan["reminder_drafts"]:
        lines.extend(["## Reminder Drafts", "", "| Title | When | Reason |", "| --- | --- | --- |"])
        for item in plan["reminder_drafts"]:
            lines.append(f"| {item['title']} | {item['when']} | {item['reason']} |")
        lines.append("")
    _append_list(lines, "Risks", plan["risks"])
    _append_list(lines, "Evidence References", plan["evidence_refs"])
    lines.extend(["## Safety Note", "", plan["safety_note"], "", f"Created: {plan['created_at']}"])
    return "\n".join(lines) + "\n"


def _append_evidence_table(lines: list[str], title: str, items: list[dict[str, str]], label_key: str) -> None:
    if not items:
        return
    lines.extend([f"## {title}", "", f"| {label_key.title()} | Evidence | Confidence |", "| --- | --- | --- |"])
    for item in items:
        lines.append(f"| {item[label_key]} | {item['evidence']} | {item['confidence']} |")
    lines.append("")


def _append_list(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines.extend([f"## {title}", ""])
    for item in items:
        lines.append(f"- {item}")
    lines.append("")


def _evidence_items(value: Any, *, label_key: str) -> list[dict[str, str]]:
    items = []
    for raw in _bounded_list(value, MAX_PERSONAL_ITEMS):
        if isinstance(raw, str):
            text = _bounded_text(raw)
            if text:
                items.append({label_key: text, "evidence": "", "confidence": "unspecified"})
            continue
        if not isinstance(raw, dict):
            continue
        text = _bounded_text(raw.get(label_key) or raw.get("text") or raw.get("value"))
        if not text:
            continue
        items.append({label_key: text, "evidence": _bounded_text(raw.get("evidence")), "confidence": _bounded_text(raw.get("confidence") or "unspecified")})
    return items


def _followups(value: Any) -> list[dict[str, str]]:
    followups = []
    for raw in _bounded_list(value, MAX_PERSONAL_ITEMS):
        if not isinstance(raw, dict):
            continue
        title = _bounded_text(raw.get("title") or raw.get("task"))
        if title:
            followups.append({"title": title, "due": _bounded_text(raw.get("due")), "reason": _bounded_text(raw.get("reason")), "evidence": _bounded_text(raw.get("evidence"))})
    return followups


def _tasks(value: Any) -> list[dict[str, str]]:
    tasks = []
    for raw in _bounded_list(value, MAX_PERSONAL_ITEMS):
        if not isinstance(raw, dict):
            continue
        title = _bounded_text(raw.get("title") or raw.get("task"))
        if title:
            tasks.append({"title": title, "priority": _bounded_text(raw.get("priority") or "normal"), "evidence": _bounded_text(raw.get("evidence")), "reason": _bounded_text(raw.get("reason"))})
    return tasks


def _time_blocks(value: Any) -> list[dict[str, str]]:
    blocks = []
    for raw in _bounded_list(value, MAX_PERSONAL_ITEMS):
        if not isinstance(raw, dict):
            continue
        focus = _bounded_text(raw.get("focus") or raw.get("title"))
        if focus:
            blocks.append({"time": _bounded_text(raw.get("time")), "focus": focus, "notes": _bounded_text(raw.get("notes"))})
    return blocks


def _reminders(value: Any) -> list[dict[str, str]]:
    reminders = []
    for raw in _bounded_list(value, MAX_PERSONAL_ITEMS):
        if not isinstance(raw, dict):
            continue
        title = _bounded_text(raw.get("title"))
        if title:
            reminders.append({"title": title, "when": _bounded_text(raw.get("when") or raw.get("scheduled_for")), "reason": _bounded_text(raw.get("reason"))})
    return reminders


def _sensitivity(value: Any) -> str:
    text = str(value or "medium").strip().lower()
    return text if text in {"low", "medium", "high"} else "medium"


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
