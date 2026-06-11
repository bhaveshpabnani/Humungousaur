from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REQUIRED_SECTIONS = (
    "Summary",
    "Signals",
    "Helpful Moments",
    "Stay Silent When",
    "Deep Dive Triggers",
    "Memory Guidance",
    "Privacy Notes",
)

SECTION_ALIASES = {
    "common signals": "Signals",
    "do not classify as": "Stay Silent When",
    "do not classify as authoring when": "Stay Silent When",
    "agent posture": "Helpful Moments",
    "useful memory": "Memory Guidance",
    "privacy concerns": "Privacy Notes",
    "deep-dive permissions": "Deep Dive Triggers",
}

GUIDE_LIMIT = 20
GUIDE_TEXT_LIMIT = 8_000


@dataclass(frozen=True, slots=True)
class ActivityGuide:
    guide_id: str
    title: str
    text: str
    sections: dict[str, str] = field(default_factory=dict)
    relevance_score: int = 0

    @property
    def prompt_payload(self) -> dict[str, Any]:
        return {
            "guide_id": self.guide_id,
            "title": self.title,
            "selection": "included_for_model_semantic_choice",
            "sections": self.sections,
        }


class ActivityGuideValidationError(ValueError):
    """Raised when an Activity Skill Pack is malformed."""


def load_activity_guides(
    root: Path | None = None,
    *,
    limit: int = 12,
    context: dict[str, Any] | None = None,
    strict: bool = False,
) -> list[ActivityGuide]:
    _ = context
    guides = _read_activity_guides(root=root, strict=strict)
    return guides[: _bounded_limit(limit)]


def select_activity_guides(
    *,
    route: Any,
    event: dict[str, Any],
    context_window: dict[str, Any] | None = None,
    task_contexts: list[dict[str, Any]] | None = None,
    root: Path | None = None,
    limit: int = 12,
) -> list[ActivityGuide]:
    """Return compact guide cards and let the Reflex LLM choose the activity frame.

    Activity guides are the reverse of tool skills: they orient model reasoning
    over human work patterns. The runtime intentionally avoids keyword scoring,
    regex matching, and task-family classifiers here.
    """

    _ = (route, event, context_window, task_contexts)
    return load_activity_guides(root=root, limit=limit)


def validate_activity_guides(root: Path | None = None) -> dict[str, Any]:
    base = root or Path(__file__).with_name("activity_guides")
    errors: dict[str, list[str]] = {}
    guides: list[ActivityGuide] = []
    for path in sorted(base.glob("*.md")) if base.exists() else []:
        try:
            guides.append(_parse_guide(path, strict=True))
        except ActivityGuideValidationError as exc:
            errors[path.name] = [str(exc)]
    return {
        "valid": not errors,
        "guide_count": len(guides),
        "errors": errors,
        "required_sections": list(REQUIRED_SECTIONS),
        "guides": [{"guide_id": guide.guide_id, "title": guide.title} for guide in guides],
    }


def _read_activity_guides(root: Path | None = None, *, strict: bool) -> list[ActivityGuide]:
    base = root or Path(__file__).with_name("activity_guides")
    if not base.exists():
        return []
    guides: list[ActivityGuide] = []
    for path in sorted(base.glob("*.md"))[:GUIDE_LIMIT]:
        try:
            guides.append(_parse_guide(path, strict=strict))
        except (OSError, ActivityGuideValidationError):
            if strict:
                raise
            continue
    return guides


def _parse_guide(path: Path, *, strict: bool) -> ActivityGuide:
    text = path.read_text(encoding="utf-8")[:GUIDE_TEXT_LIMIT]
    title = _extract_title(text) or path.stem.replace("_", " ").title()
    sections = _extract_sections(text)
    missing = [section for section in REQUIRED_SECTIONS if not sections.get(section)]
    if missing and strict:
        raise ActivityGuideValidationError(f"{path.name} missing required sections: {', '.join(missing)}")
    return ActivityGuide(
        guide_id=path.stem,
        title=title,
        text=text,
        sections=sections,
    )


def _extract_title(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].replace("Activity Guide:", "").strip() or stripped[2:].strip()
    return ""


def _extract_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = "Summary"
    sections[current] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            continue
        heading = _normalize_heading(stripped)
        if heading:
            current = heading
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line.rstrip())
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def _normalize_heading(line: str) -> str:
    if not line:
        return ""
    if line.startswith("## "):
        raw = line[3:].strip()
    elif line.endswith(":") and not line.startswith("-"):
        raw = line[:-1].strip()
    else:
        return ""
    canonical = raw[:1].upper() + raw[1:]
    lower = raw.lower()
    return SECTION_ALIASES.get(lower) or canonical


def _bounded_limit(limit: int) -> int:
    return max(1, min(int(limit or 8), GUIDE_LIMIT))
