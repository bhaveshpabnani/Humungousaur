from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


MAX_CREATIVE_ITEMS = 200
MAX_TEXT_CHARS = 80_000


class CreativeBriefCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="creative_brief_create",
            description="Create a local creative-writing brief artifact with genre, theme, audience, constraints, beats, motifs, originality guardrails, and draft status.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/creative/briefs."},
                    "title": {"type": "string"},
                    "creative_type": {"type": "string", "enum": ["story", "scene", "poem", "song", "slogan", "prompt", "other"]},
                    "genre": {"type": "string"},
                    "theme": {"type": "string"},
                    "audience": {"type": "string"},
                    "mood": {"type": "string"},
                    "language": {"type": "string"},
                    "length": {"type": "string"},
                    "status": {"type": "string", "enum": ["draft", "ready_for_review", "final"]},
                    "constraints": {"type": "array", "items": {"type": "string"}},
                    "forbidden_elements": {"type": "array", "items": {"type": "string"}},
                    "beats": {"type": "array", "items": {"type": "object"}},
                    "motifs": {"type": "array", "items": {"type": "string"}},
                    "voice_notes": {"type": "array", "items": {"type": "string"}},
                    "source_refs": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                required=["title", "creative_type", "reason"],
            ),
            capability_group="creative",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        title = " ".join(str(tool_input.get("title") or "").split())
        creative_type = str(tool_input.get("creative_type") or "").strip()
        reason = str(tool_input.get("reason") or "").strip()
        if not title or not creative_type or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Title, creative_type, and reason are required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"creative-brief-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "creative" / "briefs" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Creative brief path is outside allowed write roots.")
        artifact = _creative_brief_artifact(tool_input, title=title, creative_type=creative_type, reason=reason, markdown_path=markdown_path)
        return _write_artifact(self.name, self.risk_level, config, markdown_path, artifact, _render_creative_brief(artifact), "creative_brief_create", {"brief_id": artifact["brief_id"], "beat_count": len(artifact["beats"]), "status": artifact["status"]})


class CreativeBriefInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="creative_brief_inspect",
            description="Inspect a local creative brief for type, status, beat count, originality guardrails, source refs, and preview text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string"}}, required=["path"]),
            capability_group="creative",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        return _inspect_markdown_artifact(self.name, self.risk_level, config, str(tool_input.get("path") or ""), subdir="creative/briefs", suffix=".md", count_fields={"beat_count": "beats", "forbidden_element_count": "forbidden_elements", "source_ref_count": "source_refs"})


class SongStructureCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="song_structure_create",
            description="Create a local song-structure artifact with sections, hook concept, rhyme/production notes, and copyright-safe originality boundaries. Does not generate audio.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/creative/songs."},
                    "title": {"type": "string"},
                    "genre": {"type": "string"},
                    "mood": {"type": "string"},
                    "tempo_bpm": {"type": "number"},
                    "key": {"type": "string"},
                    "hook_concept": {"type": "string"},
                    "sections": {"type": "array", "items": {"type": "object"}},
                    "rhyme_notes": {"type": "array", "items": {"type": "string"}},
                    "production_notes": {"type": "array", "items": {"type": "string"}},
                    "originality_constraints": {"type": "array", "items": {"type": "string"}},
                    "status": {"type": "string", "enum": ["draft", "ready_for_review", "final"]},
                    "reason": {"type": "string"},
                },
                required=["title", "sections", "reason"],
            ),
            capability_group="creative",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        title = " ".join(str(tool_input.get("title") or "").split())
        reason = str(tool_input.get("reason") or "").strip()
        sections = _song_sections(tool_input.get("sections"))
        if not title or not reason or not sections:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Title, sections, and reason are required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"song-structure-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "creative" / "songs" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Song structure path is outside allowed write roots.")
        artifact = _song_artifact(tool_input, title=title, sections=sections, reason=reason, markdown_path=markdown_path)
        return _write_artifact(self.name, self.risk_level, config, markdown_path, artifact, _render_song_structure(artifact), "song_structure_create", {"song_structure_id": artifact["song_structure_id"], "section_count": len(artifact["sections"]), "status": artifact["status"]})


class SongStructureInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="song_structure_inspect",
            description="Inspect a local song structure for sections, hook, originality constraints, production notes, and preview text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string"}}, required=["path"]),
            capability_group="creative",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        return _inspect_markdown_artifact(self.name, self.risk_level, config, str(tool_input.get("path") or ""), subdir="creative/songs", suffix=".md", count_fields={"section_count": "sections", "originality_constraint_count": "originality_constraints", "production_note_count": "production_notes"})


class CreativeRevisionPacketCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="creative_revision_packet_create",
            description="Create a local creative revision packet with source draft, goals, protected elements, change notes, and variant revisions.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/creative/revisions."},
                    "title": {"type": "string"},
                    "source_draft": {"type": "string"},
                    "revision_goals": {"type": "array", "items": {"type": "string"}},
                    "protected_elements": {"type": "array", "items": {"type": "string"}},
                    "change_notes": {"type": "array", "items": {"type": "string"}},
                    "variants": {"type": "array", "items": {"type": "object"}},
                    "status": {"type": "string", "enum": ["draft", "ready_for_review", "final"]},
                    "reason": {"type": "string"},
                },
                required=["title", "source_draft", "reason"],
            ),
            capability_group="creative",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        title = " ".join(str(tool_input.get("title") or "").split())
        source_draft = str(tool_input.get("source_draft") or "").strip()
        reason = str(tool_input.get("reason") or "").strip()
        if not title or not source_draft or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Title, source_draft, and reason are required.")
        if len(source_draft) > MAX_TEXT_CHARS:
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Source draft exceeds safety limit.")
        filename = _safe_filename(str(tool_input.get("filename") or f"creative-revision-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "creative" / "revisions" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Creative revision path is outside allowed write roots.")
        artifact = _revision_artifact(tool_input, title=title, source_draft=source_draft, reason=reason, markdown_path=markdown_path)
        return _write_artifact(self.name, self.risk_level, config, markdown_path, artifact, _render_revision_packet(artifact), "creative_revision_packet_create", {"revision_packet_id": artifact["revision_packet_id"], "variant_count": len(artifact["variants"]), "status": artifact["status"]})


class CreativeRevisionPacketInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="creative_revision_packet_inspect",
            description="Inspect a local creative revision packet for variants, revision goals, protected elements, and preview text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string"}}, required=["path"]),
            capability_group="creative",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        return _inspect_markdown_artifact(self.name, self.risk_level, config, str(tool_input.get("path") or ""), subdir="creative/revisions", suffix=".md", count_fields={"variant_count": "variants", "revision_goal_count": "revision_goals", "protected_element_count": "protected_elements"})


def default_creative_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        CreativeBriefCreateTool(),
        CreativeBriefInspectTool(),
        SongStructureCreateTool(),
        SongStructureInspectTool(),
        CreativeRevisionPacketCreateTool(),
        CreativeRevisionPacketInspectTool(),
    ]
    return {tool.name: tool for tool in tools}


def _creative_brief_artifact(tool_input: dict[str, Any], *, title: str, creative_type: str, reason: str, markdown_path: Path) -> dict[str, Any]:
    return {
        "brief_id": f"creative-brief-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "creative_type": creative_type,
        "genre": _bounded_text(tool_input.get("genre")),
        "theme": _bounded_text(tool_input.get("theme")),
        "audience": _bounded_text(tool_input.get("audience")),
        "mood": _bounded_text(tool_input.get("mood")),
        "language": _bounded_text(tool_input.get("language")) or "unspecified",
        "length": _bounded_text(tool_input.get("length")),
        "status": _status(tool_input.get("status")),
        "constraints": _string_list(tool_input.get("constraints")),
        "forbidden_elements": _string_list(tool_input.get("forbidden_elements")),
        "beats": _beats(tool_input.get("beats")),
        "motifs": _string_list(tool_input.get("motifs")),
        "voice_notes": _string_list(tool_input.get("voice_notes")),
        "source_refs": _string_list(tool_input.get("source_refs")),
        "reason": reason,
        "path": str(markdown_path),
        "safety_note": "Create original material. Do not copy protected works or imitate living artists too closely.",
    }


def _song_artifact(tool_input: dict[str, Any], *, title: str, sections: list[dict[str, str]], reason: str, markdown_path: Path) -> dict[str, Any]:
    return {
        "song_structure_id": f"song-structure-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "genre": _bounded_text(tool_input.get("genre")),
        "mood": _bounded_text(tool_input.get("mood")),
        "tempo_bpm": _bounded_text(tool_input.get("tempo_bpm")),
        "key": _bounded_text(tool_input.get("key")),
        "hook_concept": _bounded_text(tool_input.get("hook_concept")),
        "sections": sections,
        "rhyme_notes": _string_list(tool_input.get("rhyme_notes")),
        "production_notes": _string_list(tool_input.get("production_notes")),
        "originality_constraints": _string_list(tool_input.get("originality_constraints")) or ["Do not reuse copyrighted lyrics, melodies, or living-artist signatures."],
        "status": _status(tool_input.get("status")),
        "reason": reason,
        "path": str(markdown_path),
        "audio_generation_status": "not_generated",
        "safety_note": "This is a structure/specification artifact only. No audio was generated and no copyrighted lyrics were reproduced.",
    }


def _revision_artifact(tool_input: dict[str, Any], *, title: str, source_draft: str, reason: str, markdown_path: Path) -> dict[str, Any]:
    return {
        "revision_packet_id": f"creative-revision-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "source_draft": source_draft,
        "revision_goals": _string_list(tool_input.get("revision_goals")),
        "protected_elements": _string_list(tool_input.get("protected_elements")),
        "change_notes": _string_list(tool_input.get("change_notes")),
        "variants": _variants(tool_input.get("variants")),
        "status": _status(tool_input.get("status")),
        "reason": reason,
        "path": str(markdown_path),
        "safety_note": "Revisions should preserve user-owned source material and avoid copying protected third-party expression.",
    }


def _render_creative_brief(artifact: dict[str, Any]) -> str:
    lines = [f"# {artifact['title']}", "", f"Type: {artifact['creative_type']}", f"Status: {artifact['status']}", f"Genre: {artifact['genre']}", f"Theme: {artifact['theme']}", f"Audience: {artifact['audience']}", f"Mood: {artifact['mood']}", f"Language: {artifact['language']}", f"Length: {artifact['length']}", ""]
    _append_list(lines, "Constraints", artifact["constraints"])
    _append_list(lines, "Forbidden Elements", artifact["forbidden_elements"])
    if artifact["beats"]:
        lines.extend(["## Beats", "", "| Label | Purpose | Notes |", "| --- | --- | --- |"])
        for beat in artifact["beats"]:
            lines.append(f"| {beat['label']} | {beat['purpose']} | {beat['notes']} |")
        lines.append("")
    _append_list(lines, "Motifs", artifact["motifs"])
    _append_list(lines, "Voice Notes", artifact["voice_notes"])
    _append_list(lines, "Source References", artifact["source_refs"])
    lines.extend(["## Safety Note", "", artifact["safety_note"], "", f"Created: {artifact['created_at']}"])
    return "\n".join(lines) + "\n"


def _render_song_structure(artifact: dict[str, Any]) -> str:
    lines = [f"# {artifact['title']}", "", f"Status: {artifact['status']}", f"Genre: {artifact['genre']}", f"Mood: {artifact['mood']}", f"Tempo BPM: {artifact['tempo_bpm']}", f"Key: {artifact['key']}", f"Hook concept: {artifact['hook_concept']}", f"Audio generation status: {artifact['audio_generation_status']}", ""]
    lines.extend(["## Sections", "", "| Name | Role | Length | Notes |", "| --- | --- | --- | --- |"])
    for section in artifact["sections"]:
        lines.append(f"| {section['name']} | {section['role']} | {section['length']} | {section['notes']} |")
    lines.append("")
    _append_list(lines, "Rhyme Notes", artifact["rhyme_notes"])
    _append_list(lines, "Production Notes", artifact["production_notes"])
    _append_list(lines, "Originality Constraints", artifact["originality_constraints"])
    lines.extend(["## Safety Note", "", artifact["safety_note"], "", f"Created: {artifact['created_at']}"])
    return "\n".join(lines) + "\n"


def _render_revision_packet(artifact: dict[str, Any]) -> str:
    lines = [f"# {artifact['title']}", "", f"Status: {artifact['status']}", "", "## Source Draft", "", artifact["source_draft"], ""]
    _append_list(lines, "Revision Goals", artifact["revision_goals"])
    _append_list(lines, "Protected Elements", artifact["protected_elements"])
    _append_list(lines, "Change Notes", artifact["change_notes"])
    if artifact["variants"]:
        lines.extend(["## Variants", ""])
        for variant in artifact["variants"]:
            lines.extend([f"### {variant['label']}", "", variant["body"], ""])
    lines.extend(["## Safety Note", "", artifact["safety_note"], "", f"Created: {artifact['created_at']}"])
    return "\n".join(lines) + "\n"


def _write_artifact(tool_name: str, risk_level: RiskLevel, config: AgentConfig, markdown_path: Path, metadata: dict[str, Any], markdown: str, source: str, extra: dict[str, Any]) -> ToolResult:
    if config.dry_run:
        return ToolResult(tool_name, ActionStatus.SKIPPED, risk_level, f"Dry run: would create creative artifact {markdown_path}.", {"path": str(markdown_path), "metadata": metadata})
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(markdown, encoding="utf-8")
    metadata_path = markdown_path.with_suffix(".json")
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return ToolResult(
        tool_name,
        ActionStatus.SUCCEEDED,
        risk_level,
        f"Created creative artifact {markdown_path}.",
        {"path": str(markdown_path), "metadata_path": str(metadata_path), "source": source, **extra},
    )


def _inspect_markdown_artifact(tool_name: str, risk_level: RiskLevel, config: AgentConfig, raw_path: str, *, subdir: str, suffix: str, count_fields: dict[str, str]) -> ToolResult:
    normalized = config.normalized()
    path = _resolve_allowed_path(normalized, raw_path, subdir=subdir, suffix=suffix)
    if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
        return ToolResult(tool_name, ActionStatus.BLOCKED, risk_level, "Creative artifact path is outside allowed roots.")
    if not path.exists() or path.suffix.lower() != ".md":
        return ToolResult(tool_name, ActionStatus.FAILED, risk_level, "Creative artifact file does not exist.")
    metadata = _load_sidecar(path.with_suffix(".json"))
    text = path.read_text(encoding="utf-8")
    output: dict[str, Any] = {
        "path": str(path),
        "metadata_path": str(path.with_suffix(".json")) if path.with_suffix(".json").exists() else "",
        "title": metadata.get("title", ""),
        "status": metadata.get("status", ""),
        "preview": text[:4000],
        "source": tool_name,
    }
    for output_key, metadata_key in count_fields.items():
        value = metadata.get(metadata_key, [])
        output[output_key] = len(value) if isinstance(value, list) else 0
    return ToolResult(tool_name, ActionStatus.SUCCEEDED, risk_level, f"Inspected creative artifact {path}.", output)


def _beats(value: Any) -> list[dict[str, str]]:
    beats = []
    for raw in _bounded_list(value):
        if not isinstance(raw, dict):
            continue
        label = _bounded_text(raw.get("label") or raw.get("name"))
        if label:
            beats.append({"label": label, "purpose": _bounded_text(raw.get("purpose")), "notes": _bounded_text(raw.get("notes"))})
    return beats


def _song_sections(value: Any) -> list[dict[str, str]]:
    sections = []
    for raw in _bounded_list(value):
        if not isinstance(raw, dict):
            continue
        name = _bounded_text(raw.get("name") or raw.get("label"))
        if name:
            sections.append({"name": name, "role": _bounded_text(raw.get("role")), "length": _bounded_text(raw.get("length")), "notes": _bounded_text(raw.get("notes"))})
    return sections


def _variants(value: Any) -> list[dict[str, str]]:
    variants = []
    for raw in _bounded_list(value):
        if not isinstance(raw, dict):
            continue
        body = str(raw.get("body") or "").strip()
        if body:
            variants.append({"label": _bounded_text(raw.get("label") or f"variant-{len(variants) + 1}"), "body": body[:MAX_TEXT_CHARS]})
    return variants


def _append_list(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines.extend([f"## {title}", ""])
    for item in items:
        lines.append(f"- {item}")
    lines.append("")


def _status(value: Any) -> str:
    status = str(value or "draft").strip().lower()
    return status if status in {"draft", "ready_for_review", "final"} else "draft"


def _bounded_text(value: Any) -> str:
    return " ".join(str(value or "").split())[:MAX_TEXT_CHARS]


def _bounded_list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    return value[:MAX_CREATIVE_ITEMS]


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip()[:MAX_TEXT_CHARS] for item in value[:MAX_CREATIVE_ITEMS] if str(item).strip()]


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
