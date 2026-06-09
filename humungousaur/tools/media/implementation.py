from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from html import escape
import json
import mimetypes
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any
from uuid import uuid4

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema
from humungousaur.tools.domain_capabilities import build_domain_capability_tools


MAX_MEDIA_ITEMS = 120
MAX_TEXT_CHARS = 40_000
MAX_MEDIA_STORE_BYTES = 100 * 1024 * 1024
MEDIA_SNIFF_BYTES = 4096


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


class MediaReferenceCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="media_reference_create",
            description=(
                "Create a local native-style media reference record for a local file, remote URL, generated artifact, "
                "channel inbound attachment, or outbound attachment without fetching remote media."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "source_type": {
                        "type": "string",
                        "enum": ["local_file", "remote_url", "generated_artifact", "channel_inbound", "outbound_attachment"],
                    },
                    "source": {"type": "string", "description": "Path, URL, artifact id, or attachment id."},
                    "mime_type": {"type": "string"},
                    "filename": {"type": "string"},
                    "channel_id": {"type": "string"},
                    "description": {"type": "string"},
                    "reason": {"type": "string"},
                },
                required=["source_type", "source", "reason"],
            ),
            capability_group="media",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        source_type = str(tool_input.get("source_type") or "").strip()
        source = str(tool_input.get("source") or "").strip()
        reason = str(tool_input.get("reason") or "").strip()
        if not source_type or not source or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Source type, source, and reason are required.")
        reference = _media_reference_payload(tool_input, normalized, source_type=source_type, source=source, reason=reason)
        path = _media_artifact_path(normalized, "references", reference["media_ref_id"], ".json")
        return _write_media_json_result(self.name, self.risk_level, config, path, reference, output_key="reference", summary=f"Created media reference {reference['media_ref_id']}.")


class MediaStoreImportTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="media_store_import",
            description=(
                "Copy an allowed local media file into Humungousaur's native-style media store with MIME sniffing, size limits, "
                "hashing, and a manifest sidecar."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "path": {"type": "string", "description": "Workspace-relative or allowed absolute local media path."},
                    "label": {"type": "string"},
                    "max_bytes": {"type": "integer", "minimum": 1, "maximum": MAX_MEDIA_STORE_BYTES},
                    "reason": {"type": "string"},
                },
                required=["path", "reason"],
            ),
            capability_group="media",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        raw_path = str(tool_input.get("path") or "").strip()
        reason = str(tool_input.get("reason") or "").strip()
        if not raw_path or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Path and reason are required.")
        source = _resolve_media_source_path(normalized, raw_path)
        if not _is_within(source, normalized.allowed_read_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Media source path is outside allowed read roots.")
        if not source.exists() or not source.is_file():
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Media source file does not exist.")
        max_bytes = max(1, min(int(tool_input.get("max_bytes") or MAX_MEDIA_STORE_BYTES), MAX_MEDIA_STORE_BYTES))
        size = source.stat().st_size
        if size > max_bytes:
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, f"Media source exceeds max_bytes ({size} > {max_bytes}).")
        digest = _sha256_file(source)
        media_id = f"media-{digest[:16]}"
        mime_type = _sniff_mime_type(source)
        destination = _media_artifact_path(normalized, "store", media_id, source.suffix.lower() or _extension_for_mime(mime_type))
        manifest_path = destination.with_suffix(destination.suffix + ".json")
        manifest = {
            "media_id": media_id,
            "status": "stored_local_copy",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_path": str(source),
            "stored_path": str(destination),
            "filename": source.name,
            "label": str(tool_input.get("label") or "").strip(),
            "mime_type": mime_type,
            "size_bytes": size,
            "sha256": digest,
            "reason": reason,
            "trusted_local_copy": True,
        }
        if not _is_within(destination, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Media store destination is outside allowed write roots.")
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would import media into store.", {"manifest": manifest, "path": str(destination), "manifest_path": str(manifest_path)})
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Imported media file into local store as {media_id}.",
            {"manifest": manifest, "path": str(destination), "manifest_path": str(manifest_path)},
        )


class MediaRootsPolicyTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="media_roots_policy",
            description="Inspect local media root policy for workspace, data artifacts, temp-like store paths, and channel inbound roots.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(),
            capability_group="media",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        del tool_input
        normalized = config.normalized()
        roots = {
            "allowed_read_roots": [str(path) for path in normalized.allowed_read_roots],
            "allowed_write_roots": [str(path) for path in normalized.allowed_write_roots],
            "media_store_root": str(normalized.data_dir / "media" / "native" / "store"),
            "media_reference_root": str(normalized.data_dir / "media" / "native" / "references"),
            "channel_inbound_root": str(normalized.data_dir / "media" / "native" / "channel_inbound"),
            "outbound_attachment_root": str(normalized.data_dir / "media" / "native" / "outbound_attachments"),
        }
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, "Inspected media root policy.", {"roots": roots, "remote_fetch_allowed": False, "source": "media_roots_policy"})


class AudioTagParseTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="audio_tag_parse",
            description="Parse native-style audio tags such as audio_as_voice from message text without modifying media.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"text": {"type": "string"}}, required=["text"]),
            capability_group="media",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        del config
        text = str(tool_input.get("text") or "")
        cleaned = text.replace("audio_as_voice", "").replace("[audio_as_voice]", "")
        audio_as_voice = cleaned != text
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            "Parsed audio tag metadata.",
            {"audio_as_voice": audio_as_voice, "cleaned_text": " ".join(cleaned.split()), "source": "audio_tag_parse"},
        )


class OutboundAttachmentPrepareTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="outbound_attachment_prepare",
            description=(
                "Prepare an outbound media attachment manifest for a channel send. "
                "This does not send the attachment or contact a channel provider."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "media_path": {"type": "string"},
                    "channel_id": {"type": "string"},
                    "caption": {"type": "string"},
                    "as_voice": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                required=["media_path", "channel_id", "reason"],
            ),
            capability_group="media",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        media_path = _resolve_media_source_path(normalized, str(tool_input.get("media_path") or ""))
        if not _is_within(media_path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Media path is outside allowed roots.")
        if not media_path.exists() or not media_path.is_file():
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Media file does not exist.")
        attachment_id = f"attachment-{uuid4().hex[:12]}"
        manifest = {
            "attachment_id": attachment_id,
            "status": "prepared_not_sent",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "media_path": str(media_path),
            "filename": media_path.name,
            "channel_id": str(tool_input.get("channel_id") or "").strip(),
            "caption": str(tool_input.get("caption") or "").strip()[:4000],
            "as_voice": bool(tool_input.get("as_voice", False)),
            "mime_type": _sniff_mime_type(media_path),
            "size_bytes": media_path.stat().st_size,
            "sha256": _sha256_file(media_path),
            "reason": str(tool_input.get("reason") or "").strip(),
        }
        path = _media_artifact_path(normalized, "outbound_attachments", attachment_id, ".json")
        return _write_media_json_result(self.name, self.risk_level, config, path, manifest, output_key="attachment", summary=f"Prepared outbound attachment {attachment_id}.")


class QRPairingArtifactCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="qr_pairing_artifact_create",
            description=(
                "Create a local QR pairing artifact. Uses an installed qrcode backend when available; otherwise writes a clear non-scannable SVG placeholder."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "data": {"type": "string"},
                    "label": {"type": "string"},
                    "reason": {"type": "string"},
                },
                required=["data", "reason"],
            ),
            capability_group="media",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        data = str(tool_input.get("data") or "").strip()
        reason = str(tool_input.get("reason") or "").strip()
        if not data or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "QR data and reason are required.")
        qr_id = f"qr-{uuid4().hex[:12]}"
        png_path = _media_artifact_path(normalized, "qr_pairing", qr_id, ".png")
        svg_path = _media_artifact_path(normalized, "qr_pairing", qr_id, ".svg")
        metadata = {
            "qr_id": qr_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "label": str(tool_input.get("label") or "").strip(),
            "data_sha256": hashlib.sha256(data.encode("utf-8")).hexdigest(),
            "reason": reason,
            "status": "prepared",
        }
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would create QR pairing artifact.", {"metadata": metadata})
        svg_path.parent.mkdir(parents=True, exist_ok=True)
        backend = _write_qr_artifact(data, png_path=png_path, svg_path=svg_path)
        metadata["backend"] = backend
        metadata_path = svg_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created QR pairing artifact {qr_id}.",
            {"metadata": metadata, "png_path": str(png_path) if png_path.exists() else "", "svg_path": str(svg_path), "metadata_path": str(metadata_path)},
        )


class FFProbeMediaProbeTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="ffprobe_media_probe",
            description="Probe local audio/video/image metadata with ffprobe when available, with bounded output and no remote fetch.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string"}}, required=["path"]),
            capability_group="media",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_media_source_path(normalized, str(tool_input.get("path") or ""))
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Media path is outside allowed roots.")
        if not path.exists() or not path.is_file():
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Media file does not exist.")
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "ffprobe is not installed.", {"available": False, "path": str(path), "mime_type": _sniff_mime_type(path)})
        completed = subprocess.run(
            [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if completed.returncode != 0:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "ffprobe failed.", {"stderr": completed.stderr[-2000:]})
        try:
            payload = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError:
            payload = {"raw_stdout": completed.stdout[:4000]}
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, "Probed media metadata with ffprobe.", {"available": True, "path": str(path), "probe": payload})


class MediaRemoteFetchPlanTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="media_remote_fetch_plan",
            description=(
                "Prepare a remote media fetch policy artifact with redirect, size, MIME, and domain constraints. "
                "This does not fetch the remote URL."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "url": {"type": "string"},
                    "allowed_domains": {"type": "array", "items": {"type": "string"}},
                    "max_redirects": {"type": "integer", "minimum": 0, "maximum": 10},
                    "max_bytes": {"type": "integer", "minimum": 1, "maximum": MAX_MEDIA_STORE_BYTES},
                    "allowed_mime_types": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                required=["url", "reason"],
            ),
            capability_group="media",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        url = str(tool_input.get("url") or "").strip()
        reason = str(tool_input.get("reason") or "").strip()
        if not url or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "URL and reason are required.")
        if not (url.startswith("https://") or url.startswith("http://")):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Only HTTP(S) media URLs can be planned.")
        plan_id = f"remote-fetch-{uuid4().hex[:12]}"
        plan = {
            "plan_id": plan_id,
            "status": "prepared_not_fetched",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "url": url,
            "allowed_domains": _string_list(tool_input.get("allowed_domains"), limit=50),
            "max_redirects": int(_bounded_number(tool_input.get("max_redirects"), default=3, minimum=0, maximum=10)),
            "max_bytes": int(_bounded_number(tool_input.get("max_bytes"), default=MAX_MEDIA_STORE_BYTES, minimum=1, maximum=MAX_MEDIA_STORE_BYTES)),
            "allowed_mime_types": _string_list(tool_input.get("allowed_mime_types"), limit=50),
            "redirect_policy": "follow_with_limit_and_domain_recheck",
            "credential_policy": "no_ambient_credentials",
            "reason": reason,
        }
        path = _media_artifact_path(normalized, "remote_fetch_plans", plan_id, ".json")
        return _write_media_json_result(self.name, self.risk_level, config, path, plan, output_key="plan", summary=f"Prepared remote media fetch plan {plan_id}.")


class MediaStoreCleanupTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="media_store_cleanup",
            description="Inspect or clean native media store files whose manifest is missing or whose manifest age exceeds a configured limit.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "media_id": {"type": "string", "description": "Optional exact media id to inspect or remove."},
                    "max_age_days": {"type": "integer", "minimum": 0},
                    "execute": {"type": "boolean", "description": "Actually delete matched files. Default is false."},
                    "reason": {"type": "string"},
                }
            ),
            capability_group="media",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        store_root = normalized.data_dir / "media" / "native" / "store"
        store_root.mkdir(parents=True, exist_ok=True)
        media_id = str(tool_input.get("media_id") or "").strip()
        max_age_days = int(_bounded_number(tool_input.get("max_age_days"), default=36500, minimum=0, maximum=36500))
        execute = bool(tool_input.get("execute", False))
        now = time_seconds()
        candidates = []
        for path in sorted(store_root.iterdir() if store_root.exists() else []):
            if not path.is_file() or path.suffix == ".json":
                continue
            if media_id and path.stem != media_id:
                continue
            manifest_path = path.with_suffix(path.suffix + ".json")
            age_days = max(0.0, (now - path.stat().st_mtime) / 86400)
            missing_manifest = not manifest_path.exists()
            expired = age_days >= max_age_days if max_age_days == 0 else age_days > max_age_days
            if missing_manifest or expired or media_id:
                candidates.append(
                    {
                        "path": str(path),
                        "manifest_path": str(manifest_path),
                        "media_id": path.stem,
                        "age_days": round(age_days, 3),
                        "missing_manifest": missing_manifest,
                        "expired": expired,
                    }
                )
        deleted: list[str] = []
        if execute:
            for candidate in candidates:
                path = Path(candidate["path"])
                manifest_path = Path(candidate["manifest_path"])
                if _is_within(path, normalized.allowed_write_roots) and path.exists():
                    path.unlink()
                    deleted.append(str(path))
                if _is_within(manifest_path, normalized.allowed_write_roots) and manifest_path.exists():
                    manifest_path.unlink()
                    deleted.append(str(manifest_path))
        action = "Deleted" if execute else "Inspected"
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"{action} {len(deleted) if execute else len(candidates)} media store cleanup candidate(s).",
            {"candidates": candidates, "deleted": deleted, "execute": execute, "store_root": str(store_root)},
        )


class HEICToJPEGConvertTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="heic_to_jpeg_convert",
            description="Convert a local HEIC/HEIF image to JPEG for provider compatibility using an available local converter.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "path": {"type": "string"},
                    "quality": {"type": "integer", "minimum": 1, "maximum": 100},
                    "reason": {"type": "string"},
                },
                required=["path", "reason"],
            ),
            capability_group="media",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        source = _resolve_media_source_path(normalized, str(tool_input.get("path") or ""))
        reason = str(tool_input.get("reason") or "").strip()
        if not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Reason is required.")
        if not _is_within(source, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Image source path is outside allowed roots.")
        if not source.exists() or not source.is_file():
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Image source file does not exist.")
        if source.suffix.lower() not in {".heic", ".heif"} and _sniff_mime_type(source) not in {"image/heic", "image/heif"}:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Source is not a HEIC/HEIF image.")
        output_id = f"heic-jpeg-{uuid4().hex[:12]}"
        destination = _media_artifact_path(normalized, "converted", output_id, ".jpg")
        if not _is_within(destination, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Converted image destination is outside allowed write roots.")
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would convert HEIC/HEIF to JPEG.", {"path": str(destination)})
        quality = int(_bounded_number(tool_input.get("quality"), default=90, minimum=1, maximum=100))
        destination.parent.mkdir(parents=True, exist_ok=True)
        converted = _convert_heic_to_jpeg(source, destination, quality=quality)
        if not converted["ok"]:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, converted["summary"], {"source_path": str(source), "path": str(destination), **converted})
        manifest = {
            "conversion_id": output_id,
            "status": "converted",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_path": str(source),
            "path": str(destination),
            "mime_type": "image/jpeg",
            "quality": quality,
            "sha256": _sha256_file(destination),
            "reason": reason,
            "backend": converted["backend"],
        }
        destination.with_suffix(".json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, "Converted HEIC/HEIF image to JPEG.", {"conversion": manifest, "path": str(destination)})


class VoiceMemoPackagePrepareTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="voice_memo_package_prepare",
            description="Prepare a channel-specific voice memo attachment manifest from a local audio file without sending it.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "audio_path": {"type": "string"},
                    "channel_id": {"type": "string"},
                    "transcoded_path": {"type": "string"},
                    "caption": {"type": "string"},
                    "reason": {"type": "string"},
                },
                required=["audio_path", "channel_id", "reason"],
            ),
            capability_group="media",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        audio_path = _resolve_media_source_path(normalized, str(tool_input.get("audio_path") or ""))
        if not _is_within(audio_path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Audio path is outside allowed roots.")
        if not audio_path.exists() or not audio_path.is_file():
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Audio file does not exist.")
        package_id = f"voice-memo-{uuid4().hex[:12]}"
        transcoded = str(tool_input.get("transcoded_path") or "").strip()
        manifest = {
            "package_id": package_id,
            "status": "prepared_not_sent",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "audio_path": str(audio_path),
            "transcoded_path": transcoded,
            "channel_id": str(tool_input.get("channel_id") or "").strip(),
            "caption": str(tool_input.get("caption") or "").strip()[:4000],
            "as_voice": True,
            "mime_type": _sniff_mime_type(audio_path),
            "size_bytes": audio_path.stat().st_size,
            "sha256": _sha256_file(audio_path),
            "reason": str(tool_input.get("reason") or "").strip(),
        }
        path = _media_artifact_path(normalized, "voice_memos", package_id, ".json")
        return _write_media_json_result(self.name, self.risk_level, config, path, manifest, output_key="voice_memo", summary=f"Prepared voice memo package {package_id}.")


class FFmpegMediaTranscodeTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="ffmpeg_media_transcode",
            description="Transcode a local audio/video file with bounded ffmpeg settings when ffmpeg is installed.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "path": {"type": "string"},
                    "target": {"type": "string", "enum": ["mp3", "opus", "m4a", "mp4", "wav"]},
                    "max_seconds": {"type": "number", "minimum": 1, "maximum": 600},
                    "reason": {"type": "string"},
                },
                required=["path", "target", "reason"],
            ),
            capability_group="media",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        source = _resolve_media_source_path(normalized, str(tool_input.get("path") or ""))
        target = str(tool_input.get("target") or "").strip().lower()
        reason = str(tool_input.get("reason") or "").strip()
        if not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Reason is required.")
        if target not in {"mp3", "opus", "m4a", "mp4", "wav"}:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Unsupported transcode target.")
        if not _is_within(source, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Media path is outside allowed roots.")
        if not source.exists() or not source.is_file():
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Media file does not exist.")
        ffmpeg = shutil.which("ffmpeg")
        transcode_id = f"transcode-{uuid4().hex[:12]}"
        destination = _media_artifact_path(normalized, "transcoded", transcode_id, f".{target}")
        plan = {
            "transcode_id": transcode_id,
            "source_path": str(source),
            "path": str(destination),
            "target": target,
            "max_seconds": _bounded_number(tool_input.get("max_seconds"), default=60, minimum=1, maximum=600),
            "reason": reason,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if not ffmpeg:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "ffmpeg is not installed.", {"available": False, "plan": plan})
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, "Dry run: would transcode media with ffmpeg.", {"available": True, "plan": plan})
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = _ffmpeg_command(ffmpeg, source, destination, target=target, max_seconds=float(plan["max_seconds"]))
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        if completed.returncode != 0:
            return ToolResult(
                self.name,
                ActionStatus.FAILED,
                self.risk_level,
                "ffmpeg transcode failed.",
                {"available": True, "plan": plan, "stderr": completed.stderr[-2000:]},
            )
        manifest = {
            **plan,
            "status": "transcoded",
            "mime_type": _sniff_mime_type(destination),
            "size_bytes": destination.stat().st_size,
            "sha256": _sha256_file(destination),
        }
        destination.with_suffix(destination.suffix + ".json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, "Transcoded media with ffmpeg.", {"available": True, "transcode": manifest, "path": str(destination)})


def default_media_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        SoundSpecCreateTool(),
        SoundSpecInspectTool(),
        MediaStoryboardCreateTool(),
        MediaStoryboardInspectTool(),
        MediaReferenceCreateTool(),
        MediaStoreImportTool(),
        MediaRootsPolicyTool(),
        AudioTagParseTool(),
        OutboundAttachmentPrepareTool(),
        QRPairingArtifactCreateTool(),
        FFProbeMediaProbeTool(),
        MediaRemoteFetchPlanTool(),
        MediaStoreCleanupTool(),
        HEICToJPEGConvertTool(),
        VoiceMemoPackagePrepareTool(),
        FFmpegMediaTranscodeTool(),
    ]
    registry = {tool.name: tool for tool in tools}
    registry.update(build_domain_capability_tools("media"))
    return registry


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


def _media_reference_payload(tool_input: dict[str, Any], config: AgentConfig, *, source_type: str, source: str, reason: str) -> dict[str, Any]:
    media_ref_id = f"media-ref-{uuid4().hex[:12]}"
    exists = False
    resolved_path = ""
    size_bytes = 0
    mime_type = str(tool_input.get("mime_type") or "").strip()
    if source_type in {"local_file", "generated_artifact", "outbound_attachment"}:
        path = _resolve_media_source_path(config, source)
        resolved_path = str(path)
        exists = path.exists()
        if exists and path.is_file():
            size_bytes = path.stat().st_size
            mime_type = mime_type or _sniff_mime_type(path)
    return {
        "media_ref_id": media_ref_id,
        "source_type": source_type,
        "source": source,
        "resolved_path": resolved_path,
        "exists": exists,
        "filename": str(tool_input.get("filename") or (Path(source).name if source_type != "remote_url" else "")).strip(),
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "channel_id": str(tool_input.get("channel_id") or "").strip(),
        "description": str(tool_input.get("description") or "").strip()[:4000],
        "reason": reason,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "remote_fetched": False,
        "trusted_local": source_type != "remote_url" and exists,
    }


def _media_artifact_path(config: AgentConfig, subdir: str, stem: str, suffix: str) -> Path:
    safe_subdir = _safe_path_segment(subdir)
    safe_stem = _safe_path_segment(stem)
    return (config.normalized().data_dir / "media" / "native" / safe_subdir / f"{safe_stem}{suffix}").resolve()


def _write_media_json_result(
    tool_name: str,
    risk_level: RiskLevel,
    config: AgentConfig,
    path: Path,
    payload: dict[str, Any],
    *,
    output_key: str,
    summary: str,
) -> ToolResult:
    normalized = config.normalized()
    if not _is_within(path, normalized.allowed_write_roots):
        return ToolResult(tool_name, ActionStatus.BLOCKED, risk_level, "Media artifact path is outside allowed write roots.")
    if config.dry_run:
        return ToolResult(tool_name, ActionStatus.SKIPPED, risk_level, f"Dry run: would write {path}.", {output_key: payload, "path": str(path)})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ToolResult(tool_name, ActionStatus.SUCCEEDED, risk_level, summary, {output_key: payload, "path": str(path)})


def _resolve_media_source_path(config: AgentConfig, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path.resolve()
    candidates = [
        config.workspace / path,
        config.data_dir / path,
        config.data_dir / "media" / path,
        config.data_dir / "media" / "native" / path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return (config.workspace / path).resolve()


def _sniff_mime_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    try:
        header = path.read_bytes()[:MEDIA_SNIFF_BYTES]
    except OSError:
        header = b""
    detected = _mime_from_header(header)
    return detected or guessed or "application/octet-stream"


def _mime_from_header(header: bytes) -> str:
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
        return "image/gif"
    if header.startswith(b"%PDF"):
        return "application/pdf"
    if header.startswith(b"RIFF") and b"WAVE" in header[:16]:
        return "audio/wav"
    if header.startswith(b"ID3"):
        return "audio/mpeg"
    if header.startswith(b"OggS"):
        return "application/ogg"
    if len(header) >= 12 and header[4:8] == b"ftyp" and header[8:12] in {b"heic", b"heix", b"hevc", b"hevx"}:
        return "image/heic"
    if len(header) >= 12 and header[4:8] == b"ftyp" and header[8:12] in {b"heif", b"heim"}:
        return "image/heif"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return "video/mp4"
    return ""


def _extension_for_mime(mime_type: str) -> str:
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/heic": ".heic",
        "image/heif": ".heif",
        "application/pdf": ".pdf",
        "audio/wav": ".wav",
        "audio/mpeg": ".mp3",
        "video/mp4": ".mp4",
    }.get(mime_type, ".bin")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_path_segment(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in ("-", "_", ".") else "-" for char in str(value or "")).strip(".-")
    return cleaned or "artifact"


def _write_qr_artifact(data: str, *, png_path: Path, svg_path: Path) -> str:
    try:
        import qrcode  # type: ignore

        image = qrcode.make(data)
        png_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(png_path)
        svg_path.write_text(_qr_placeholder_svg(data, scannable=True), encoding="utf-8")
        return "qrcode_png"
    except Exception:
        svg_path.write_text(_qr_placeholder_svg(data, scannable=False), encoding="utf-8")
        return "svg_placeholder_no_qr_backend"


def _convert_heic_to_jpeg(source: Path, destination: Path, *, quality: int) -> dict[str, Any]:
    try:
        from PIL import Image  # type: ignore

        with Image.open(source) as image:
            image.convert("RGB").save(destination, "JPEG", quality=quality)
        return {"ok": True, "backend": "pillow", "summary": "Converted with Pillow."}
    except Exception:
        pass
    sips = shutil.which("sips")
    if sips:
        completed = subprocess.run(
            [sips, "-s", "format", "jpeg", "-s", "formatOptions", str(quality), str(source), "--out", str(destination)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if completed.returncode == 0 and destination.exists():
            return {"ok": True, "backend": "sips", "summary": "Converted with sips."}
    magick = shutil.which("magick") or shutil.which("convert")
    if magick:
        command = [magick, str(source), "-quality", str(quality), str(destination)]
        if Path(magick).name == "magick":
            command = [magick, str(source), "-quality", str(quality), str(destination)]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        if completed.returncode == 0 and destination.exists():
            return {"ok": True, "backend": Path(magick).name, "summary": "Converted with ImageMagick."}
    return {
        "ok": False,
        "backend": "unavailable",
        "summary": "No local HEIC/HEIF converter is available or conversion failed.",
    }


def _ffmpeg_command(ffmpeg: str, source: Path, destination: Path, *, target: str, max_seconds: float) -> list[str]:
    base = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-t", str(max_seconds), "-i", str(source)]
    if target == "mp3":
        return base + ["-vn", "-codec:a", "libmp3lame", "-b:a", "128k", str(destination)]
    if target == "opus":
        return base + ["-vn", "-codec:a", "libopus", "-b:a", "64k", str(destination)]
    if target == "m4a":
        return base + ["-vn", "-codec:a", "aac", "-b:a", "128k", str(destination)]
    if target == "wav":
        return base + ["-vn", "-codec:a", "pcm_s16le", str(destination)]
    return base + ["-codec:v", "libx264", "-preset", "veryfast", "-crf", "28", "-codec:a", "aac", "-b:a", "128k", str(destination)]


def time_seconds() -> float:
    return time.time()


def _qr_placeholder_svg(data: str, *, scannable: bool) -> str:
    label = "QR image written as PNG" if scannable else "QR backend unavailable"
    digest = hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]
    return "\n".join(
        [
            '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320" viewBox="0 0 320 320" role="img">',
            '<rect width="320" height="320" fill="#f7f7f4"/>',
            '<rect x="36" y="36" width="248" height="248" fill="white" stroke="#1d2528" stroke-width="2"/>',
            f'<text x="54" y="140" font-family="Arial, sans-serif" font-size="18" fill="#1d2528">{escape(label)}</text>',
            f'<text x="54" y="170" font-family="Arial, sans-serif" font-size="13" fill="#465154">data sha256: {escape(digest)}</text>',
            "</svg>",
            "",
        ]
    )


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
