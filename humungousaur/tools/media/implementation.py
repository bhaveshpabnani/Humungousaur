from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


MAX_MEDIA_ITEMS = 120
MAX_TEXT_CHARS = 40_000


class SoundSpecCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="sound_spec_create",
            description=(
                "Create a local music, song, sound-effect, or audio-generation specification artifact with arrangement, "
                "lyrics, timing, licensing constraints, prompt text, and provider boundary. Does not generate or upload audio."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/media/sound_specs."},
                    "title": {"type": "string"},
                    "sound_type": {"type": "string", "enum": ["song", "sound_effect", "music_bed", "voice_tag", "ambient_loop", "other"]},
                    "intended_use": {"type": "string"},
                    "duration_seconds": {"type": "number"},
                    "genre": {"type": "string"},
                    "mood": {"type": "string"},
                    "tempo_bpm": {"type": "number"},
                    "instrumentation": {"type": "array", "items": {"type": "string"}},
                    "lyrics": {"type": "string"},
                    "sections": {"type": "array", "items": {"type": "object"}},
                    "sound_design_notes": {"type": "array", "items": {"type": "string"}},
                    "prompt": {"type": "string"},
                    "negative_prompt": {"type": "string"},
                    "licensing_constraints": {"type": "array", "items": {"type": "string"}},
                    "provider": {"type": "string"},
                    "reason": {"type": "string"},
                },
                required=["title", "sound_type", "reason"],
            ),
            capability_group="media",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        title = " ".join(str(tool_input.get("title") or "").split())
        sound_type = str(tool_input.get("sound_type") or "").strip()
        reason = str(tool_input.get("reason") or "").strip()
        if not title or not sound_type or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Sound title, sound_type, and reason are required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"sound-spec-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "media" / "sound_specs" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Sound spec path is outside allowed write roots.")
        artifact = _sound_artifact(tool_input, title=title, sound_type=sound_type, reason=reason, markdown_path=markdown_path)
        markdown = _render_sound_spec(artifact)
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would create sound spec {markdown_path}.", {"path": str(markdown_path), "artifact": artifact})
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        metadata_path = markdown_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created sound specification artifact {markdown_path}.",
            {
                "path": str(markdown_path),
                "metadata_path": str(metadata_path),
                "sound_spec_id": artifact["sound_spec_id"],
                "sound_type": artifact["sound_type"],
                "section_count": len(artifact["sections"]),
                "artifact_status": artifact["status"],
                "source": "sound_spec_create",
            },
        )


class SoundSpecInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="sound_spec_inspect",
            description="Inspect a local sound/music specification artifact for type, timing, sections, licensing constraints, and preview text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string", "description": "Workspace-relative or allowed absolute sound spec markdown path."}}, required=["path"]),
            capability_group="media",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_allowed_path(normalized, str(tool_input.get("path") or ""), subdir="media/sound_specs", suffix=".md")
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Sound spec path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".md":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Sound spec file does not exist.")
        metadata = _load_sidecar(path.with_suffix(".json"))
        text = path.read_text(encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected sound specification artifact {path}.",
            {
                "path": str(path),
                "metadata_path": str(path.with_suffix(".json")) if path.with_suffix(".json").exists() else "",
                "sound_spec_id": metadata.get("sound_spec_id", ""),
                "title": metadata.get("title", ""),
                "sound_type": metadata.get("sound_type", ""),
                "duration_seconds": metadata.get("duration_seconds", 0),
                "section_count": len(metadata.get("sections", [])) if isinstance(metadata.get("sections"), list) else 0,
                "licensing_constraint_count": len(metadata.get("licensing_constraints", [])) if isinstance(metadata.get("licensing_constraints"), list) else 0,
                "preview": text[:4000],
                "source": "sound_spec_inspect",
            },
        )


class MediaStoryboardCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="media_storyboard_create",
            description=(
                "Create a local storyboard/art-direction artifact for GIFs, videos, image sequences, or algorithmic art. "
                "Writes Markdown, JSON metadata, and an SVG contact sheet; does not post externally."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/media/storyboards."},
                    "title": {"type": "string"},
                    "media_type": {"type": "string", "enum": ["gif", "video", "image", "image_sequence", "algorithmic_art", "animation", "other"]},
                    "audience": {"type": "string"},
                    "intended_use": {"type": "string"},
                    "duration_seconds": {"type": "number"},
                    "width": {"type": "integer"},
                    "height": {"type": "integer"},
                    "style": {"type": "string"},
                    "palette": {"type": "array", "items": {"type": "string"}},
                    "scenes": {"type": "array", "items": {"type": "object"}},
                    "prompt": {"type": "string"},
                    "negative_prompt": {"type": "string"},
                    "delivery_channel": {"type": "string"},
                    "accessibility_notes": {"type": "array", "items": {"type": "string"}},
                    "licensing_constraints": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                required=["title", "media_type", "scenes", "reason"],
            ),
            capability_group="media",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        title = " ".join(str(tool_input.get("title") or "").split())
        media_type = str(tool_input.get("media_type") or "").strip()
        reason = str(tool_input.get("reason") or "").strip()
        if not title or not media_type or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Storyboard title, media_type, and reason are required.")
        try:
            scenes = _scenes(tool_input.get("scenes"))
        except ValueError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc), error=str(exc))
        if not scenes:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "At least one storyboard scene is required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"storyboard-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "media" / "storyboards" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Storyboard path is outside allowed write roots.")
        artifact = _storyboard_artifact(tool_input, title=title, media_type=media_type, scenes=scenes, reason=reason, markdown_path=markdown_path)
        markdown = _render_storyboard(artifact)
        svg = _render_storyboard_svg(artifact)
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would create storyboard {markdown_path}.", {"path": str(markdown_path), "artifact": artifact})
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        metadata_path = markdown_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        svg_path = markdown_path.with_suffix(".svg")
        svg_path.write_text(svg, encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created media storyboard artifact {markdown_path}.",
            {
                "path": str(markdown_path),
                "metadata_path": str(metadata_path),
                "svg_path": str(svg_path),
                "storyboard_id": artifact["storyboard_id"],
                "media_type": artifact["media_type"],
                "scene_count": len(artifact["scenes"]),
                "artifact_status": artifact["status"],
                "source": "media_storyboard_create",
            },
        )


class MediaStoryboardInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="media_storyboard_inspect",
            description="Inspect a local media storyboard artifact for media type, dimensions, scene count, SVG contact sheet, and preview text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string", "description": "Workspace-relative or allowed absolute storyboard markdown path."}}, required=["path"]),
            capability_group="media",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_allowed_path(normalized, str(tool_input.get("path") or ""), subdir="media/storyboards", suffix=".md")
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Storyboard path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".md":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Storyboard file does not exist.")
        metadata = _load_sidecar(path.with_suffix(".json"))
        text = path.read_text(encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected media storyboard artifact {path}.",
            {
                "path": str(path),
                "metadata_path": str(path.with_suffix(".json")) if path.with_suffix(".json").exists() else "",
                "svg_path": str(path.with_suffix(".svg")) if path.with_suffix(".svg").exists() else "",
                "storyboard_id": metadata.get("storyboard_id", ""),
                "title": metadata.get("title", ""),
                "media_type": metadata.get("media_type", ""),
                "scene_count": len(metadata.get("scenes", [])) if isinstance(metadata.get("scenes"), list) else 0,
                "width": metadata.get("width", 0),
                "height": metadata.get("height", 0),
                "preview": text[:4000],
                "source": "media_storyboard_inspect",
            },
        )


def default_media_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        SoundSpecCreateTool(),
        SoundSpecInspectTool(),
        MediaStoryboardCreateTool(),
        MediaStoryboardInspectTool(),
    ]
    return {tool.name: tool for tool in tools}


def _sound_artifact(tool_input: dict[str, Any], *, title: str, sound_type: str, reason: str, markdown_path: Path) -> dict[str, Any]:
    return {
        "sound_spec_id": f"sound-spec-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "sound_type": sound_type,
        "intended_use": _bounded_text(tool_input.get("intended_use")),
        "duration_seconds": _bounded_number(tool_input.get("duration_seconds"), default=0, minimum=0, maximum=3600),
        "genre": _bounded_text(tool_input.get("genre")),
        "mood": _bounded_text(tool_input.get("mood")),
        "tempo_bpm": _bounded_number(tool_input.get("tempo_bpm"), default=0, minimum=0, maximum=400),
        "instrumentation": _string_list(tool_input.get("instrumentation"), limit=MAX_MEDIA_ITEMS),
        "lyrics": _bounded_text(tool_input.get("lyrics")),
        "sections": _sections(tool_input.get("sections")),
        "sound_design_notes": _string_list(tool_input.get("sound_design_notes"), limit=MAX_MEDIA_ITEMS),
        "prompt": _bounded_text(tool_input.get("prompt")),
        "negative_prompt": _bounded_text(tool_input.get("negative_prompt")),
        "licensing_constraints": _string_list(tool_input.get("licensing_constraints"), limit=MAX_MEDIA_ITEMS),
        "provider": _bounded_text(tool_input.get("provider")),
        "reason": reason,
        "path": str(markdown_path),
        "status": "prepared_not_generated",
        "safety_note": "This is a local specification. No audio was generated, uploaded, or published.",
    }


def _storyboard_artifact(tool_input: dict[str, Any], *, title: str, media_type: str, scenes: list[dict[str, Any]], reason: str, markdown_path: Path) -> dict[str, Any]:
    return {
        "storyboard_id": f"storyboard-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "media_type": media_type,
        "audience": _bounded_text(tool_input.get("audience")),
        "intended_use": _bounded_text(tool_input.get("intended_use")),
        "duration_seconds": _bounded_number(tool_input.get("duration_seconds"), default=0, minimum=0, maximum=3600),
        "width": int(_bounded_number(tool_input.get("width"), default=640, minimum=64, maximum=4096)),
        "height": int(_bounded_number(tool_input.get("height"), default=360, minimum=64, maximum=4096)),
        "style": _bounded_text(tool_input.get("style")),
        "palette": _palette(tool_input.get("palette")),
        "scenes": scenes,
        "prompt": _bounded_text(tool_input.get("prompt")),
        "negative_prompt": _bounded_text(tool_input.get("negative_prompt")),
        "delivery_channel": _bounded_text(tool_input.get("delivery_channel")),
        "accessibility_notes": _string_list(tool_input.get("accessibility_notes"), limit=MAX_MEDIA_ITEMS),
        "licensing_constraints": _string_list(tool_input.get("licensing_constraints"), limit=MAX_MEDIA_ITEMS),
        "reason": reason,
        "path": str(markdown_path),
        "status": "prepared_not_published",
        "safety_note": "This is a local storyboard/contact-sheet artifact. It is not a posted GIF, video, or external generation result.",
    }


def _render_sound_spec(artifact: dict[str, Any]) -> str:
    lines = [f"# {artifact['title']}", "", f"Type: {artifact['sound_type']}", f"Status: {artifact['status']}", f"Provider: {artifact['provider'] or 'unspecified'}", ""]
    details = [
        ("Intended use", artifact["intended_use"]),
        ("Duration", f"{artifact['duration_seconds']} seconds" if artifact["duration_seconds"] else ""),
        ("Genre", artifact["genre"]),
        ("Mood", artifact["mood"]),
        ("Tempo", f"{artifact['tempo_bpm']} BPM" if artifact["tempo_bpm"] else ""),
    ]
    for label, value in details:
        if value:
            lines.append(f"{label}: {value}")
    if details:
        lines.append("")
    _append_list(lines, "Instrumentation", artifact["instrumentation"])
    if artifact["lyrics"]:
        lines.extend(["## Lyrics", "", artifact["lyrics"], ""])
    if artifact["sections"]:
        lines.extend(["## Arrangement", "", "| Section | Start | Duration | Notes |", "| --- | --- | --- | --- |"])
        for section in artifact["sections"]:
            lines.append(f"| {section['name']} | {section['start']} | {section['duration']} | {section['notes']} |")
        lines.append("")
    _append_list(lines, "Sound Design Notes", artifact["sound_design_notes"])
    if artifact["prompt"]:
        lines.extend(["## Prompt", "", artifact["prompt"], ""])
    if artifact["negative_prompt"]:
        lines.extend(["## Negative Prompt", "", artifact["negative_prompt"], ""])
    _append_list(lines, "Licensing Constraints", artifact["licensing_constraints"])
    lines.extend(["## Safety Note", "", artifact["safety_note"], "", f"Created: {artifact['created_at']}"])
    return "\n".join(lines) + "\n"


def _render_storyboard(artifact: dict[str, Any]) -> str:
    lines = [f"# {artifact['title']}", "", f"Media type: {artifact['media_type']}", f"Status: {artifact['status']}", f"Dimensions: {artifact['width']} x {artifact['height']}", ""]
    for label in ("audience", "intended_use", "style", "delivery_channel"):
        if artifact[label]:
            lines.append(f"{label.replace('_', ' ').title()}: {artifact[label]}")
    if artifact["duration_seconds"]:
        lines.append(f"Duration: {artifact['duration_seconds']} seconds")
    lines.append("")
    _append_list(lines, "Palette", artifact["palette"])
    lines.extend(["## Scenes", ""])
    for scene in artifact["scenes"]:
        lines.extend([f"### {scene['label']}", "", scene["description"], ""])
        if scene["duration_seconds"]:
            lines.append(f"Duration: {scene['duration_seconds']} seconds")
        if scene["motion"]:
            lines.append(f"Motion: {scene['motion']}")
        if scene["text"]:
            lines.append(f"Text: {scene['text']}")
        lines.append("")
    if artifact["prompt"]:
        lines.extend(["## Prompt", "", artifact["prompt"], ""])
    if artifact["negative_prompt"]:
        lines.extend(["## Negative Prompt", "", artifact["negative_prompt"], ""])
    _append_list(lines, "Accessibility Notes", artifact["accessibility_notes"])
    _append_list(lines, "Licensing Constraints", artifact["licensing_constraints"])
    lines.extend(["## Safety Note", "", artifact["safety_note"], "", f"Created: {artifact['created_at']}"])
    return "\n".join(lines) + "\n"


def _render_storyboard_svg(artifact: dict[str, Any]) -> str:
    palette = artifact["palette"] or ["#223843", "#eff1f3", "#dbd3d8", "#d77a61"]
    scene_count = len(artifact["scenes"])
    card_w = 260
    card_h = 170
    gap = 24
    cols = min(3, max(1, scene_count))
    rows = (scene_count + cols - 1) // cols
    width = cols * card_w + (cols + 1) * gap
    height = rows * card_h + (rows + 1) * gap + 70
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(artifact["title"])} storyboard">',
        '<rect width="100%" height="100%" fill="#f7f7f4"/>',
        f'<text x="{gap}" y="36" font-family="Segoe UI, Arial, sans-serif" font-size="22" font-weight="700" fill="#1d2528">{escape(artifact["title"])}</text>',
    ]
    for index, scene in enumerate(artifact["scenes"]):
        row = index // cols
        col = index % cols
        x = gap + col * (card_w + gap)
        y = gap + 50 + row * (card_h + gap)
        fill = palette[index % len(palette)]
        accent = palette[(index + 1) % len(palette)]
        lines.extend(
            [
                f'<rect x="{x}" y="{y}" width="{card_w}" height="{card_h}" rx="8" fill="white" stroke="#d2d6d6"/>',
                f'<rect x="{x + 12}" y="{y + 14}" width="{card_w - 24}" height="76" rx="6" fill="{escape(fill)}" opacity="0.88"/>',
                f'<circle cx="{x + card_w - 48}" cy="{y + 52}" r="24" fill="{escape(accent)}" opacity="0.82"/>',
                f'<text x="{x + 16}" y="{y + 116}" font-family="Segoe UI, Arial, sans-serif" font-size="15" font-weight="700" fill="#1d2528">{escape(scene["label"][:32])}</text>',
                f'<text x="{x + 16}" y="{y + 140}" font-family="Segoe UI, Arial, sans-serif" font-size="12" fill="#465154">{escape(scene["description"][:62])}</text>',
            ]
        )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _sections(value: Any) -> list[dict[str, str]]:
    sections = []
    for raw in _bounded_list(value, MAX_MEDIA_ITEMS):
        if not isinstance(raw, dict):
            continue
        name = _bounded_text(raw.get("name") or raw.get("section"))
        if not name:
            continue
        sections.append(
            {
                "name": name,
                "start": _bounded_text(raw.get("start") or raw.get("start_time")),
                "duration": _bounded_text(raw.get("duration") or raw.get("duration_seconds")),
                "notes": _bounded_text(raw.get("notes")),
            }
        )
    return sections


def _scenes(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("Storyboard scenes must be a list.")
    scenes = []
    for index, raw in enumerate(value[:MAX_MEDIA_ITEMS], start=1):
        if not isinstance(raw, dict):
            raise ValueError("Each storyboard scene must be an object.")
        description = _bounded_text(raw.get("description"))
        if not description:
            raise ValueError("Each storyboard scene requires a description.")
        scenes.append(
            {
                "label": _bounded_text(raw.get("label") or raw.get("title") or f"Scene {index}"),
                "description": description,
                "duration_seconds": _bounded_number(raw.get("duration_seconds"), default=0, minimum=0, maximum=3600),
                "motion": _bounded_text(raw.get("motion")),
                "text": _bounded_text(raw.get("text")),
                "visual_notes": _string_list(raw.get("visual_notes"), limit=20),
            }
        )
    return scenes


def _palette(value: Any) -> list[str]:
    colors = _string_list(value, limit=16)
    return [color if color.startswith("#") else f"#{color}" for color in colors]


def _append_list(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines.extend([f"## {title}", ""])
    for item in items:
        lines.append(f"- {item}")
    lines.append("")


def _bounded_number(value: Any, *, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


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
