from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


WRITING_MAX_BODY_CHARS = 80_000
WRITING_MAX_VARIANTS = 12
FOLLOWUP_MAX_ITEMS = 100


class WritingDraftCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="writing_draft_create",
            description=(
                "Create a local approval-safe writing draft artifact for internal comms, status updates, social posts, "
                "humanized rewrites, docs, or messages. This never posts or sends."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/writing_drafts."},
                    "draft_type": {
                        "type": "string",
                        "enum": ["general", "internal_update", "status_update", "social_post", "humanized_rewrite", "message", "document"],
                    },
                    "title": {"type": "string"},
                    "audience": {"type": "string"},
                    "tone": {"type": "string"},
                    "body": {"type": "string"},
                    "variants": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Optional variant drafts with label and body.",
                    },
                    "must_keep_facts": {"type": "array", "items": {"type": "string"}},
                    "source_refs": {"type": "array", "items": {"type": "string"}},
                    "approval_required": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                required=["draft_type", "title", "body", "reason"],
            ),
            capability_group="writing",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        draft_type = str(tool_input.get("draft_type") or "general").strip()
        title = " ".join(str(tool_input.get("title") or "").split())
        body = str(tool_input.get("body") or "").strip()
        if not title or not body:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Draft title and body are required.")
        if len(body) > WRITING_MAX_BODY_CHARS:
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Draft body exceeds safety limit.")
        filename = _safe_filename(str(tool_input.get("filename") or f"{draft_type}-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "writing_drafts" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Draft path is outside allowed write roots.")
        metadata = _draft_metadata(tool_input, title=title, body=body, markdown_path=markdown_path)
        markdown = _render_writing_draft(metadata)
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would create writing draft {markdown_path}.", {"path": str(markdown_path), "metadata": metadata})
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        metadata_path = markdown_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created writing draft {markdown_path}.",
            {
                "path": str(markdown_path),
                "metadata_path": str(metadata_path),
                "draft_type": draft_type,
                "send_status": "not_sent",
                "approval_required": metadata["approval_required"],
                "variant_count": len(metadata["variants"]),
                "source": "writing_draft_create",
            },
        )


class WritingDraftInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="writing_draft_inspect",
            description="Inspect a local writing draft artifact for type, audience, send status, variants, and preview text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string", "description": "Workspace-relative or allowed absolute draft markdown path."}}, required=["path"]),
            capability_group="writing",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_allowed_path(normalized, str(tool_input.get("path") or ""), subdir="writing_drafts", suffix=".md")
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Draft path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".md":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Draft file does not exist.")
        text = path.read_text(encoding="utf-8")
        metadata_path = path.with_suffix(".json")
        metadata: dict[str, Any] = {}
        if metadata_path.exists():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                metadata = {}
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected writing draft {path}.",
            {
                "path": str(path),
                "metadata_path": str(metadata_path) if metadata_path.exists() else "",
                "draft_type": metadata.get("draft_type", ""),
                "title": metadata.get("title", ""),
                "audience": metadata.get("audience", ""),
                "send_status": metadata.get("send_status", "not_sent"),
                "approval_required": bool(metadata.get("approval_required", True)),
                "variant_count": len(metadata.get("variants", [])) if isinstance(metadata.get("variants", []), list) else 0,
                "preview": text[:2000],
                "source": "writing_draft_inspect",
            },
        )


class MeetingFollowupPacketCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="meeting_followup_packet_create",
            description=(
                "Create a local meeting follow-up packet with summary, action items, draft messages, reminders, and approval state. "
                "This does not assign, send, or schedule externally."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/meeting_followups."},
                    "meeting_title": {"type": "string"},
                    "summary": {"type": "string"},
                    "action_items": {"type": "array", "items": {"type": "object"}},
                    "draft_messages": {"type": "array", "items": {"type": "object"}},
                    "reminders": {"type": "array", "items": {"type": "object"}},
                    "open_questions": {"type": "array", "items": {"type": "string"}},
                    "source_refs": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                required=["meeting_title", "summary", "reason"],
            ),
            capability_group="writing",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        title = " ".join(str(tool_input.get("meeting_title") or "").split())
        summary = str(tool_input.get("summary") or "").strip()
        if not title or not summary:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Meeting title and summary are required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"meeting-followup-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "meeting_followups" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Follow-up path is outside allowed write roots.")
        packet = _followup_packet(tool_input, title=title, summary=summary)
        markdown = _render_followup_packet(packet)
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would create meeting follow-up packet {markdown_path}.", {"path": str(markdown_path), "packet": packet})
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        metadata_path = markdown_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created meeting follow-up packet {markdown_path}.",
            {
                "path": str(markdown_path),
                "metadata_path": str(metadata_path),
                "action_item_count": len(packet["action_items"]),
                "draft_message_count": len(packet["draft_messages"]),
                "reminder_count": len(packet["reminders"]),
                "send_status": "not_sent",
                "source": "meeting_followup_packet_create",
            },
        )


def default_writing_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        WritingDraftCreateTool(),
        WritingDraftInspectTool(),
        MeetingFollowupPacketCreateTool(),
    ]
    return {tool.name: tool for tool in tools}


def _draft_metadata(tool_input: dict[str, Any], *, title: str, body: str, markdown_path: Path) -> dict[str, Any]:
    variants = []
    for raw in _bounded_list(tool_input.get("variants"), WRITING_MAX_VARIANTS):
        if not isinstance(raw, dict):
            continue
        label = str(raw.get("label") or f"variant-{len(variants) + 1}").strip()
        variant_body = str(raw.get("body") or "").strip()
        if variant_body:
            variants.append({"label": label, "body": variant_body[:WRITING_MAX_BODY_CHARS]})
    return {
        "draft_id": f"writing-draft-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "draft_type": str(tool_input.get("draft_type") or "general").strip(),
        "title": title,
        "audience": str(tool_input.get("audience") or "").strip(),
        "tone": str(tool_input.get("tone") or "").strip(),
        "body": body,
        "variants": variants,
        "must_keep_facts": _string_list(tool_input.get("must_keep_facts")),
        "source_refs": _string_list(tool_input.get("source_refs")),
        "approval_required": bool(tool_input.get("approval_required", True)),
        "send_status": "not_sent",
        "reason": str(tool_input.get("reason") or "").strip(),
        "path": str(markdown_path),
    }


def _followup_packet(tool_input: dict[str, Any], *, title: str, summary: str) -> dict[str, Any]:
    action_items = []
    for raw in _bounded_list(tool_input.get("action_items"), FOLLOWUP_MAX_ITEMS):
        if isinstance(raw, dict) and str(raw.get("task") or "").strip():
            action_items.append(
                {
                    "task": str(raw.get("task") or "").strip(),
                    "owner": str(raw.get("owner") or "").strip(),
                    "due": str(raw.get("due") or "").strip(),
                    "evidence": str(raw.get("evidence") or "").strip(),
                    "status": str(raw.get("status") or "draft").strip(),
                }
            )
    draft_messages = []
    for raw in _bounded_list(tool_input.get("draft_messages"), FOLLOWUP_MAX_ITEMS):
        if isinstance(raw, dict) and str(raw.get("text") or "").strip():
            draft_messages.append(
                {
                    "channel_id": str(raw.get("channel_id") or "").strip(),
                    "conversation_id": str(raw.get("conversation_id") or "").strip(),
                    "recipient": str(raw.get("recipient") or "").strip(),
                    "text": str(raw.get("text") or "").strip(),
                    "send_status": "not_sent",
                    "approval_required": True,
                }
            )
    reminders = [
        {key: str(raw.get(key) or "").strip() for key in ("title", "scheduled_for", "reason")}
        for raw in _bounded_list(tool_input.get("reminders"), FOLLOWUP_MAX_ITEMS)
        if isinstance(raw, dict) and str(raw.get("title") or "").strip()
    ]
    return {
        "packet_id": f"meeting-followup-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "meeting_title": title,
        "summary": summary,
        "action_items": action_items,
        "draft_messages": draft_messages,
        "reminders": reminders,
        "open_questions": _string_list(tool_input.get("open_questions")),
        "source_refs": _string_list(tool_input.get("source_refs")),
        "send_status": "not_sent",
        "reason": str(tool_input.get("reason") or "").strip(),
    }


def _render_writing_draft(metadata: dict[str, Any]) -> str:
    lines = [f"# {metadata['title']}", ""]
    lines.extend(
        [
            f"Type: {metadata['draft_type']}",
            f"Audience: {metadata['audience'] or 'unspecified'}",
            f"Tone: {metadata['tone'] or 'unspecified'}",
            f"Send status: {metadata['send_status']}",
            f"Approval required: {metadata['approval_required']}",
            "",
            "## Draft",
            "",
            metadata["body"],
            "",
        ]
    )
    _append_list(lines, "Must Keep Facts", metadata["must_keep_facts"])
    _append_list(lines, "Source References", metadata["source_refs"], code=True)
    if metadata["variants"]:
        lines.extend(["## Variants", ""])
        for variant in metadata["variants"]:
            lines.extend([f"### {variant['label']}", "", variant["body"], ""])
    lines.append(f"Created: {metadata['created_at']}")
    return "\n".join(lines) + "\n"


def _render_followup_packet(packet: dict[str, Any]) -> str:
    lines = [f"# {packet['meeting_title']}", "", "## Summary", "", packet["summary"], ""]
    if packet["action_items"]:
        lines.extend(["## Action Items", "", "| Task | Owner | Due | Status | Evidence |", "| --- | --- | --- | --- | --- |"])
        for item in packet["action_items"]:
            lines.append(f"| {item['task']} | {item['owner']} | {item['due']} | {item['status']} | {item['evidence']} |")
        lines.append("")
    if packet["draft_messages"]:
        lines.extend(["## Draft Messages", ""])
        for message in packet["draft_messages"]:
            target = message["recipient"] or message["conversation_id"] or message["channel_id"] or "unspecified"
            lines.extend([f"### To {target}", "", message["text"], "", "Status: not_sent; approval required.", ""])
    if packet["reminders"]:
        lines.extend(["## Reminder Drafts", ""])
        for reminder in packet["reminders"]:
            lines.append(f"- {reminder['title']} at {reminder['scheduled_for']} - {reminder['reason']}")
        lines.append("")
    _append_list(lines, "Open Questions", packet["open_questions"])
    _append_list(lines, "Source References", packet["source_refs"], code=True)
    lines.append(f"Created: {packet['created_at']}")
    return "\n".join(lines) + "\n"


def _append_list(lines: list[str], title: str, items: list[str], *, code: bool = False) -> None:
    if not items:
        return
    lines.extend([f"## {title}", ""])
    for item in items:
        lines.append(f"- `{item}`" if code else f"- {item}")
    lines.append("")


def _safe_filename(value: str, suffix: str) -> str:
    name = Path(value).name.strip() or f"artifact{suffix}"
    if not name.lower().endswith(suffix):
        name += suffix
    stem = "".join(char if char.isalnum() or char in ("-", "_", ".") else "-" for char in Path(name).stem).strip(".-")
    return f"{stem or 'artifact'}{suffix}"


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


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _bounded_list(value: Any, limit: int) -> list[Any]:
    if not isinstance(value, list):
        return []
    return value[: max(0, limit)]


def _is_within(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)
