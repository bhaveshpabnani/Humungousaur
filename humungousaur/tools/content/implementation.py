from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


TRANSCRIPT_MAX_CHARS = 160_000
TRANSCRIPT_PREVIEW_CHARS = 4_000
TRANSCRIPT_MAX_ITEMS = 120


class TranscriptSummaryCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="transcript_summary_create",
            description=(
                "Create a local transcript/video/audio summary artifact from provided transcript text or an allowed transcript file. "
                "The tool preserves provenance, timestamps, extracted follow-ups, and limitations without downloading media."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/transcript_summaries."},
                    "title": {"type": "string"},
                    "source_url": {"type": "string"},
                    "source_type": {
                        "type": "string",
                        "enum": ["audio", "video", "youtube", "meeting", "voice_note", "podcast", "lecture", "transcript", "other"],
                    },
                    "transcript": {"type": "string", "description": "Transcript text. Use transcript_path instead for larger local files."},
                    "transcript_path": {"type": "string", "description": "Allowed local transcript file path."},
                    "transcript_provider": {"type": "string", "description": "Provider/source such as local-whisper, deepgram, provided, youtube-captions."},
                    "language": {"type": "string"},
                    "summary": {"type": "string", "description": "Model/user-produced summary grounded in the transcript."},
                    "key_points": {"type": "array", "items": {"type": "string"}},
                    "decisions": {"type": "array", "items": {"type": "string"}},
                    "action_items": {"type": "array", "items": {"type": "object"}},
                    "open_questions": {"type": "array", "items": {"type": "string"}},
                    "risks": {"type": "array", "items": {"type": "string"}},
                    "chapters": {"type": "array", "items": {"type": "object"}},
                    "quotes": {"type": "array", "items": {"type": "object"}},
                    "limitations": {"type": "array", "items": {"type": "string"}},
                    "output_format": {"type": "string", "description": "Requested format such as notes, tasks, blog, thread, study guide, meeting notes."},
                    "reason": {"type": "string"},
                },
                required=["title", "summary", "reason"],
            ),
            capability_group="content",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        title = " ".join(str(tool_input.get("title") or "").split())
        summary = str(tool_input.get("summary") or "").strip()
        reason = str(tool_input.get("reason") or "").strip()
        if not title or not summary or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Title, summary, and reason are required.")
        try:
            transcript, transcript_source = _transcript_text(normalized, tool_input)
        except ValueError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc), error=str(exc))
        filename = _safe_filename(str(tool_input.get("filename") or f"transcript-summary-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "transcript_summaries" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Transcript summary path is outside allowed write roots.")
        artifact = _artifact_payload(tool_input, title=title, summary=summary, reason=reason, transcript=transcript, transcript_source=transcript_source, markdown_path=markdown_path)
        markdown = _render_artifact(artifact)
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                f"Dry run: would create transcript summary {markdown_path}.",
                {"path": str(markdown_path), "artifact": artifact},
            )
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        metadata_path = markdown_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created transcript summary {markdown_path}.",
            {
                "path": str(markdown_path),
                "metadata_path": str(metadata_path),
                "summary_id": artifact["summary_id"],
                "source_type": artifact["source_type"],
                "transcript_source": transcript_source,
                "transcript_chars": artifact["transcript_chars"],
                "segment_count": len(artifact["timestamp_segments"]),
                "action_item_count": len(artifact["action_items"]),
                "source": "transcript_summary_create",
            },
        )


class TranscriptSummaryInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="transcript_summary_inspect",
            description="Inspect a local transcript summary artifact for provenance, counts, preview text, and extracted structured fields.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string", "description": "Workspace-relative or allowed absolute transcript summary markdown path."}}, required=["path"]),
            capability_group="content",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_allowed_path(normalized, str(tool_input.get("path") or ""), subdir="transcript_summaries", suffix=".md")
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Transcript summary path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".md":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Transcript summary file does not exist.")
        text = path.read_text(encoding="utf-8")
        metadata_path = path.with_suffix(".json")
        metadata: dict[str, Any] = {}
        if metadata_path.exists():
            try:
                loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    metadata = loaded
            except json.JSONDecodeError:
                metadata = {}
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected transcript summary {path}.",
            {
                "path": str(path),
                "metadata_path": str(metadata_path) if metadata_path.exists() else "",
                "summary_id": metadata.get("summary_id", ""),
                "title": metadata.get("title", ""),
                "source_type": metadata.get("source_type", ""),
                "transcript_source": metadata.get("transcript_source", ""),
                "transcript_chars": metadata.get("transcript_chars", 0),
                "segment_count": len(metadata.get("timestamp_segments", [])) if isinstance(metadata.get("timestamp_segments", []), list) else 0,
                "action_item_count": len(metadata.get("action_items", [])) if isinstance(metadata.get("action_items", []), list) else 0,
                "open_question_count": len(metadata.get("open_questions", [])) if isinstance(metadata.get("open_questions", []), list) else 0,
                "preview": text[:TRANSCRIPT_PREVIEW_CHARS],
                "source": "transcript_summary_inspect",
            },
        )


def default_content_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        TranscriptSummaryCreateTool(),
        TranscriptSummaryInspectTool(),
    ]
    return {tool.name: tool for tool in tools}


def _artifact_payload(
    tool_input: dict[str, Any],
    *,
    title: str,
    summary: str,
    reason: str,
    transcript: str,
    transcript_source: str,
    markdown_path: Path,
) -> dict[str, Any]:
    timestamp_segments = _timestamp_segments(transcript)
    chapters = _chapters(tool_input.get("chapters"), timestamp_segments)
    limitations = _string_list(tool_input.get("limitations"), limit=TRANSCRIPT_MAX_ITEMS)
    if not transcript:
        limitations.append("No transcript text was provided; artifact is based only on supplied summary fields.")
    return {
        "summary_id": f"transcript-summary-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "source_url": str(tool_input.get("source_url") or "").strip(),
        "source_type": str(tool_input.get("source_type") or "transcript").strip() or "transcript",
        "transcript_provider": str(tool_input.get("transcript_provider") or ("provided" if transcript else "")).strip(),
        "transcript_source": transcript_source,
        "language": str(tool_input.get("language") or "").strip(),
        "output_format": str(tool_input.get("output_format") or "notes").strip() or "notes",
        "summary": summary,
        "key_points": _string_list(tool_input.get("key_points"), limit=TRANSCRIPT_MAX_ITEMS),
        "decisions": _string_list(tool_input.get("decisions"), limit=TRANSCRIPT_MAX_ITEMS),
        "action_items": _action_items(tool_input.get("action_items")),
        "open_questions": _string_list(tool_input.get("open_questions"), limit=TRANSCRIPT_MAX_ITEMS),
        "risks": _string_list(tool_input.get("risks"), limit=TRANSCRIPT_MAX_ITEMS),
        "quotes": _quotes(tool_input.get("quotes")),
        "chapters": chapters,
        "timestamp_segments": timestamp_segments,
        "limitations": limitations,
        "transcript_chars": len(transcript),
        "transcript_preview": transcript[:TRANSCRIPT_PREVIEW_CHARS],
        "reason": reason,
        "path": str(markdown_path),
        "status": "prepared_not_published",
    }


def _transcript_text(config: AgentConfig, tool_input: dict[str, Any]) -> tuple[str, str]:
    inline = str(tool_input.get("transcript") or "")
    transcript_path = str(tool_input.get("transcript_path") or "").strip()
    if inline and transcript_path:
        raise ValueError("Provide either transcript or transcript_path, not both.")
    if inline:
        if len(inline) > TRANSCRIPT_MAX_CHARS:
            raise ValueError("Transcript text exceeds safety limit.")
        return inline.strip(), "inline"
    if transcript_path:
        path = Path(transcript_path).expanduser()
        if not path.is_absolute():
            path = config.workspace / path
        path = path.resolve()
        if not _is_within(path, config.allowed_read_roots + config.allowed_write_roots):
            raise ValueError("Transcript file path is outside allowed roots.")
        if not path.exists() or not path.is_file():
            raise ValueError(f"Transcript file does not exist: {path}")
        if path.stat().st_size > TRANSCRIPT_MAX_CHARS:
            raise ValueError("Transcript file exceeds safety limit.")
        return path.read_text(encoding="utf-8", errors="replace").strip(), str(path)
    return "", "summary_fields_only"


def _timestamp_segments(transcript: str) -> list[dict[str, str]]:
    segments: list[dict[str, str]] = []
    for raw in transcript.splitlines():
        line = raw.strip()
        if not line:
            continue
        timestamp, text = _split_timestamp_line(line)
        if timestamp:
            segments.append({"timestamp": timestamp, "text": text[:1000]})
        if len(segments) >= TRANSCRIPT_MAX_ITEMS:
            break
    return segments


def _split_timestamp_line(line: str) -> tuple[str, str]:
    candidates = []
    for separator in ("]", " ", " - ", " | "):
        if separator in line:
            left, right = line.split(separator, 1)
            candidates.append((left.strip("[]() "), right.strip(":-| ")))
    for left, right in candidates:
        normalized = _normalized_timestamp(left)
        if normalized:
            return normalized, right or line
    return "", line


def _normalized_timestamp(value: str) -> str:
    parts = value.split(":")
    if len(parts) not in {2, 3}:
        return ""
    cleaned: list[int] = []
    for part in parts:
        if not part.isdigit():
            return ""
        cleaned.append(int(part))
    if len(cleaned) == 2:
        minutes, seconds = cleaned
        if seconds > 59:
            return ""
        return f"{minutes:02d}:{seconds:02d}"
    hours, minutes, seconds = cleaned
    if minutes > 59 or seconds > 59:
        return ""
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _chapters(value: Any, segments: list[dict[str, str]]) -> list[dict[str, str]]:
    chapters = []
    for raw in _bounded_list(value, TRANSCRIPT_MAX_ITEMS):
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or raw.get("heading") or "").strip()
        if not title:
            continue
        chapters.append(
            {
                "title": title,
                "timestamp": str(raw.get("timestamp") or "").strip(),
                "summary": str(raw.get("summary") or "").strip(),
            }
        )
    if chapters or not segments:
        return chapters
    return [{"title": segment["text"][:80], "timestamp": segment["timestamp"], "summary": segment["text"]} for segment in segments[:10]]


def _action_items(value: Any) -> list[dict[str, str]]:
    items = []
    for raw in _bounded_list(value, TRANSCRIPT_MAX_ITEMS):
        if isinstance(raw, str):
            task = raw.strip()
            if task:
                items.append({"task": task, "owner": "", "due": "", "evidence": ""})
            continue
        if not isinstance(raw, dict):
            continue
        task = str(raw.get("task") or raw.get("title") or "").strip()
        if not task:
            continue
        items.append(
            {
                "task": task,
                "owner": str(raw.get("owner") or "").strip(),
                "due": str(raw.get("due") or raw.get("due_date") or "").strip(),
                "evidence": str(raw.get("evidence") or raw.get("timestamp") or "").strip(),
            }
        )
    return items


def _quotes(value: Any) -> list[dict[str, str]]:
    quotes = []
    for raw in _bounded_list(value, TRANSCRIPT_MAX_ITEMS):
        if isinstance(raw, str):
            text = raw.strip()
            if text:
                quotes.append({"text": text, "speaker": "", "timestamp": ""})
            continue
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or raw.get("quote") or "").strip()
        if not text:
            continue
        quotes.append(
            {
                "text": text[:500],
                "speaker": str(raw.get("speaker") or "").strip(),
                "timestamp": str(raw.get("timestamp") or "").strip(),
            }
        )
    return quotes


def _render_artifact(artifact: dict[str, Any]) -> str:
    lines = [f"# {artifact['title']}", ""]
    lines.extend(
        [
            f"Source type: {artifact['source_type']}",
            f"Source URL: {artifact['source_url'] or 'unspecified'}",
            f"Transcript source: {artifact['transcript_source']}",
            f"Transcript provider: {artifact['transcript_provider'] or 'unspecified'}",
            f"Language: {artifact['language'] or 'unspecified'}",
            f"Output format: {artifact['output_format']}",
            f"Status: {artifact['status']}",
            "",
            "## Summary",
            "",
            artifact["summary"],
            "",
        ]
    )
    _append_list(lines, "Key Points", artifact["key_points"])
    _append_list(lines, "Decisions", artifact["decisions"])
    _append_table(lines, "Action Items", artifact["action_items"], ("task", "owner", "due", "evidence"))
    _append_list(lines, "Open Questions", artifact["open_questions"])
    _append_list(lines, "Risks", artifact["risks"])
    _append_table(lines, "Chapters", artifact["chapters"], ("timestamp", "title", "summary"))
    _append_table(lines, "Notable Quotes", artifact["quotes"], ("timestamp", "speaker", "text"))
    _append_list(lines, "Limitations", artifact["limitations"])
    if artifact["transcript_preview"]:
        lines.extend(["## Transcript Preview", "", "```text", artifact["transcript_preview"], "```", ""])
    lines.append(f"Created: {artifact['created_at']}")
    return "\n".join(lines) + "\n"


def _append_list(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines.extend([f"## {title}", ""])
    for item in items:
        lines.append(f"- {item}")
    lines.append("")


def _append_table(lines: list[str], title: str, rows: list[dict[str, str]], columns: tuple[str, ...]) -> None:
    if not rows:
        return
    lines.extend([f"## {title}", "", "| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"])
    for row in rows:
        values = [_table_cell(row.get(column, "")) for column in columns]
        lines.append("| " + " | ".join(values) + " |")
    lines.append("")


def _table_cell(value: str) -> str:
    return " ".join(str(value or "").replace("|", "/").split())


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


def _string_list(value: Any, *, limit: int) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value[:limit] if str(item).strip()]


def _bounded_list(value: Any, limit: int) -> list[Any]:
    if not isinstance(value, list):
        return []
    return value[: max(0, limit)]


def _is_within(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)
