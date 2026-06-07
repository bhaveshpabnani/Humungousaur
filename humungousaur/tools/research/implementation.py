from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


MAX_CITATION_ENTRIES = 300
MAX_LITERATURE_PAPERS = 300
MAX_TEXT_CHARS = 20_000


class CitationBibliographyCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="citation_bibliography_create",
            description=(
                "Create a local cleaned bibliography artifact from explicit citation metadata. "
                "Stores Markdown, BibTeX-like entries, verification status, uncertainty labels, and source references."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/research/bibliographies."},
                    "title": {"type": "string"},
                    "target_style": {"type": "string", "enum": ["apa", "ieee", "bibtex", "mixed"]},
                    "entries": {"type": "array", "items": {"type": "object"}},
                    "global_source_refs": {"type": "array", "items": {"type": "string"}},
                    "notes": {"type": "string"},
                    "reason": {"type": "string"},
                },
                required=["title", "entries", "reason"],
            ),
            capability_group="research",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        title = " ".join(str(tool_input.get("title") or "").split())
        reason = str(tool_input.get("reason") or "").strip()
        if not title or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Bibliography title and reason are required.")
        try:
            entries = _citation_entries(tool_input.get("entries"))
        except ValueError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc), error=str(exc))
        if not entries:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "At least one citation entry is required.")
        style = str(tool_input.get("target_style") or "mixed").strip().lower()
        filename = _safe_filename(str(tool_input.get("filename") or f"bibliography-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "research" / "bibliographies" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Bibliography path is outside allowed write roots.")
        artifact = {
            "bibliography_id": f"bibliography-{uuid4().hex[:12]}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "title": title,
            "target_style": style,
            "entries": entries,
            "global_source_refs": _string_list(tool_input.get("global_source_refs"), limit=MAX_CITATION_ENTRIES),
            "notes": _bounded_text(tool_input.get("notes")),
            "reason": reason,
            "path": str(markdown_path),
            "status": "prepared_not_published",
        }
        markdown = _render_bibliography(artifact)
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would create bibliography {markdown_path}.", {"path": str(markdown_path), "artifact": artifact})
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        metadata_path = markdown_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        bibtex_path = markdown_path.with_suffix(".bib")
        bibtex_path.write_text("\n\n".join(entry["bibtex"] for entry in entries) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created bibliography artifact {markdown_path}.",
            {
                "path": str(markdown_path),
                "metadata_path": str(metadata_path),
                "bibtex_path": str(bibtex_path),
                "bibliography_id": artifact["bibliography_id"],
                "entry_count": len(entries),
                "uncertain_entry_count": sum(1 for entry in entries if entry["uncertain_fields"]),
                "source": "citation_bibliography_create",
            },
        )


class CitationBibliographyInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="citation_bibliography_inspect",
            description="Inspect a local bibliography artifact for entry count, uncertain fields, source references, and preview text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string", "description": "Workspace-relative or allowed absolute bibliography markdown path."}}, required=["path"]),
            capability_group="research",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_allowed_path(normalized, str(tool_input.get("path") or ""), subdir="research/bibliographies", suffix=".md")
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Bibliography path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".md":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Bibliography file does not exist.")
        text = path.read_text(encoding="utf-8")
        metadata = _load_sidecar(path.with_suffix(".json"))
        entries = metadata.get("entries", []) if isinstance(metadata.get("entries"), list) else []
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected bibliography artifact {path}.",
            {
                "path": str(path),
                "metadata_path": str(path.with_suffix(".json")) if path.with_suffix(".json").exists() else "",
                "bibtex_path": str(path.with_suffix(".bib")) if path.with_suffix(".bib").exists() else "",
                "bibliography_id": metadata.get("bibliography_id", ""),
                "title": metadata.get("title", ""),
                "entry_count": len(entries),
                "uncertain_entry_count": sum(1 for entry in entries if isinstance(entry, dict) and entry.get("uncertain_fields")),
                "preview": text[:4000],
                "source": "citation_bibliography_inspect",
            },
        )


class LiteratureSetCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="literature_set_create",
            description=(
                "Create a local literature-set artifact from explicit paper metadata, relevance notes, themes, evidence limits, and gaps. "
                "Use after web/PDF evidence collection; this does not search the web by itself."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/research/literature_sets."},
                    "title": {"type": "string"},
                    "research_question": {"type": "string"},
                    "inclusion_criteria": {"type": "array", "items": {"type": "string"}},
                    "papers": {"type": "array", "items": {"type": "object"}},
                    "themes": {"type": "array", "items": {"type": "object"}},
                    "gaps": {"type": "array", "items": {"type": "string"}},
                    "limitations": {"type": "array", "items": {"type": "string"}},
                    "source_refs": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                required=["title", "papers", "reason"],
            ),
            capability_group="research",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        title = " ".join(str(tool_input.get("title") or "").split())
        reason = str(tool_input.get("reason") or "").strip()
        if not title or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Literature set title and reason are required.")
        try:
            papers = _literature_papers(tool_input.get("papers"))
        except ValueError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc), error=str(exc))
        if not papers:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "At least one paper is required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"literature-set-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "research" / "literature_sets" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Literature set path is outside allowed write roots.")
        artifact = {
            "literature_set_id": f"literature-set-{uuid4().hex[:12]}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "title": title,
            "research_question": _bounded_text(tool_input.get("research_question")),
            "inclusion_criteria": _string_list(tool_input.get("inclusion_criteria"), limit=100),
            "papers": papers,
            "themes": _themes(tool_input.get("themes")),
            "gaps": _string_list(tool_input.get("gaps"), limit=100),
            "limitations": _string_list(tool_input.get("limitations"), limit=100),
            "source_refs": _string_list(tool_input.get("source_refs"), limit=MAX_CITATION_ENTRIES),
            "reason": reason,
            "path": str(markdown_path),
            "status": "prepared_not_published",
        }
        markdown = _render_literature_set(artifact)
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would create literature set {markdown_path}.", {"path": str(markdown_path), "artifact": artifact})
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        metadata_path = markdown_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created literature set artifact {markdown_path}.",
            {
                "path": str(markdown_path),
                "metadata_path": str(metadata_path),
                "literature_set_id": artifact["literature_set_id"],
                "paper_count": len(papers),
                "theme_count": len(artifact["themes"]),
                "source": "literature_set_create",
            },
        )


class LiteratureSetInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="literature_set_inspect",
            description="Inspect a local literature-set artifact for paper count, themes, gaps, limitations, and preview text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string", "description": "Workspace-relative or allowed absolute literature-set markdown path."}}, required=["path"]),
            capability_group="research",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_allowed_path(normalized, str(tool_input.get("path") or ""), subdir="research/literature_sets", suffix=".md")
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Literature set path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".md":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Literature set file does not exist.")
        text = path.read_text(encoding="utf-8")
        metadata = _load_sidecar(path.with_suffix(".json"))
        papers = metadata.get("papers", []) if isinstance(metadata.get("papers"), list) else []
        themes = metadata.get("themes", []) if isinstance(metadata.get("themes"), list) else []
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected literature set artifact {path}.",
            {
                "path": str(path),
                "metadata_path": str(path.with_suffix(".json")) if path.with_suffix(".json").exists() else "",
                "literature_set_id": metadata.get("literature_set_id", ""),
                "title": metadata.get("title", ""),
                "paper_count": len(papers),
                "theme_count": len(themes),
                "gap_count": len(metadata.get("gaps", [])) if isinstance(metadata.get("gaps"), list) else 0,
                "preview": text[:4000],
                "source": "literature_set_inspect",
            },
        )


def default_research_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        CitationBibliographyCreateTool(),
        CitationBibliographyInspectTool(),
        LiteratureSetCreateTool(),
        LiteratureSetInspectTool(),
    ]
    return {tool.name: tool for tool in tools}


def _citation_entries(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("Citation entries must be a list.")
    entries = []
    for index, raw in enumerate(value[:MAX_CITATION_ENTRIES], start=1):
        if not isinstance(raw, dict):
            raise ValueError("Each citation entry must be an object.")
        title = _bounded_text(raw.get("title"))
        if not title:
            raise ValueError("Each citation entry requires a title.")
        authors = _authors(raw.get("authors"))
        entry = {
            "entry_id": str(raw.get("entry_id") or _citation_key(raw, title=title, authors=authors)).strip(),
            "type": str(raw.get("type") or "article").strip() or "article",
            "title": title,
            "authors": authors,
            "year": _year(raw.get("year")),
            "venue": _bounded_text(raw.get("venue")),
            "publisher": _bounded_text(raw.get("publisher")),
            "doi": _bounded_text(raw.get("doi")),
            "url": _bounded_text(raw.get("url")),
            "arxiv_id": _bounded_text(raw.get("arxiv_id")),
            "source_refs": _string_list(raw.get("source_refs"), limit=40),
            "verified_fields": _string_list(raw.get("verified_fields"), limit=40),
            "uncertain_fields": _string_list(raw.get("uncertain_fields"), limit=40),
            "notes": _bounded_text(raw.get("notes")),
            "order": index,
        }
        entry["apa"] = _format_apa(entry)
        entry["ieee"] = _format_ieee(entry, index=index)
        entry["bibtex"] = _format_bibtex(entry)
        entries.append(entry)
    return entries


def _literature_papers(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("Literature papers must be a list.")
    papers = []
    for index, raw in enumerate(value[:MAX_LITERATURE_PAPERS], start=1):
        if not isinstance(raw, dict):
            raise ValueError("Each literature paper must be an object.")
        title = _bounded_text(raw.get("title"))
        if not title:
            raise ValueError("Each literature paper requires a title.")
        papers.append(
            {
                "paper_id": str(raw.get("paper_id") or f"paper-{index}").strip(),
                "title": title,
                "authors": _authors(raw.get("authors")),
                "year": _year(raw.get("year")),
                "venue": _bounded_text(raw.get("venue")),
                "url": _bounded_text(raw.get("url")),
                "doi": _bounded_text(raw.get("doi")),
                "abstract": _bounded_text(raw.get("abstract")),
                "relevance": _bounded_text(raw.get("relevance")),
                "evidence_level": str(raw.get("evidence_level") or "metadata").strip(),
                "themes": _string_list(raw.get("themes"), limit=30),
                "source_refs": _string_list(raw.get("source_refs"), limit=40),
                "limitations": _string_list(raw.get("limitations"), limit=30),
            }
        )
    return papers


def _themes(value: Any) -> list[dict[str, Any]]:
    themes = []
    for raw in _bounded_list(value, 100):
        if isinstance(raw, str):
            name = raw.strip()
            if name:
                themes.append({"name": name, "summary": "", "paper_ids": []})
            continue
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or raw.get("theme") or "").strip()
        if not name:
            continue
        themes.append({"name": name, "summary": _bounded_text(raw.get("summary")), "paper_ids": _string_list(raw.get("paper_ids"), limit=100)})
    return themes


def _render_bibliography(artifact: dict[str, Any]) -> str:
    lines = [f"# {artifact['title']}", "", f"Target style: {artifact['target_style']}", f"Status: {artifact['status']}", ""]
    if artifact["notes"]:
        lines.extend(["## Notes", "", artifact["notes"], ""])
    lines.extend(["## Cleaned References", ""])
    for entry in artifact["entries"]:
        lines.append(f"{entry['order']}. {entry['apa']}")
        if entry["uncertain_fields"]:
            lines.append(f"   - Uncertain: {', '.join(entry['uncertain_fields'])}")
        if entry["source_refs"]:
            lines.append(f"   - Sources: {', '.join(entry['source_refs'])}")
    lines.extend(["", "## BibTeX", "", "```bibtex"])
    for entry in artifact["entries"]:
        lines.extend([entry["bibtex"], ""])
    lines.extend(["```", ""])
    _append_list(lines, "Global Source References", artifact["global_source_refs"])
    lines.append(f"Created: {artifact['created_at']}")
    return "\n".join(lines) + "\n"


def _render_literature_set(artifact: dict[str, Any]) -> str:
    lines = [f"# {artifact['title']}", "", f"Status: {artifact['status']}", ""]
    if artifact["research_question"]:
        lines.extend(["## Research Question", "", artifact["research_question"], ""])
    _append_list(lines, "Inclusion Criteria", artifact["inclusion_criteria"])
    lines.extend(["## Papers", ""])
    for paper in artifact["papers"]:
        authors = ", ".join(paper["authors"]) if paper["authors"] else "Unknown authors"
        year = f" ({paper['year']})" if paper["year"] else ""
        lines.extend([f"### {paper['title']}", "", f"{authors}{year}. {paper['venue']}".strip(), ""])
        if paper["relevance"]:
            lines.extend(["Relevance: " + paper["relevance"], ""])
        if paper["evidence_level"]:
            lines.extend([f"Evidence level: {paper['evidence_level']}", ""])
        if paper["source_refs"]:
            lines.extend(["Sources: " + ", ".join(paper["source_refs"]), ""])
    if artifact["themes"]:
        lines.extend(["## Themes", ""])
        for theme in artifact["themes"]:
            ids = ", ".join(theme["paper_ids"]) if theme["paper_ids"] else "no paper ids"
            lines.extend([f"- {theme['name']}: {theme['summary']} ({ids})"])
        lines.append("")
    _append_list(lines, "Gaps", artifact["gaps"])
    _append_list(lines, "Limitations", artifact["limitations"])
    _append_list(lines, "Source References", artifact["source_refs"])
    lines.append(f"Created: {artifact['created_at']}")
    return "\n".join(lines) + "\n"


def _format_apa(entry: dict[str, Any]) -> str:
    authors = _apa_authors(entry["authors"])
    year = f"({entry['year']})." if entry["year"] else "(n.d.)."
    title = entry["title"].rstrip(".") + "."
    venue = f" {entry['venue'].rstrip('.')}." if entry["venue"] else ""
    identifier = _identifier_suffix(entry)
    return " ".join(part for part in [authors, year, title, venue.strip(), identifier] if part).strip()


def _format_ieee(entry: dict[str, Any], *, index: int) -> str:
    authors = ", ".join(entry["authors"]) if entry["authors"] else "Unknown author"
    venue = f", {entry['venue']}" if entry["venue"] else ""
    year = f", {entry['year']}" if entry["year"] else ""
    identifier = f", {_identifier_suffix(entry)}" if _identifier_suffix(entry) else ""
    return f"[{index}] {authors}, \"{entry['title']}\"{venue}{year}{identifier}."


def _format_bibtex(entry: dict[str, Any]) -> str:
    fields = {
        "title": entry["title"],
        "author": " and ".join(entry["authors"]),
        "year": entry["year"],
        "journal": entry["venue"] if entry["type"] == "article" else "",
        "booktitle": entry["venue"] if entry["type"] in {"inproceedings", "conference"} else "",
        "publisher": entry["publisher"],
        "doi": entry["doi"],
        "url": entry["url"],
        "note": f"arXiv:{entry['arxiv_id']}" if entry["arxiv_id"] else entry["notes"],
    }
    lines = [f"@{entry['type']}{{{entry['entry_id']},"]
    for key, value in fields.items():
        if value:
            escaped = str(value).replace("{", "\\{").replace("}", "\\}")
            lines.append(f"  {key} = {{{escaped}}},")
    lines.append("}")
    return "\n".join(lines)


def _apa_authors(authors: list[str]) -> str:
    if not authors:
        return "Unknown author."
    return ", ".join(authors) + "."


def _identifier_suffix(entry: dict[str, Any]) -> str:
    if entry["doi"]:
        return f"https://doi.org/{entry['doi'].removeprefix('https://doi.org/')}"
    if entry["url"]:
        return entry["url"]
    if entry["arxiv_id"]:
        return f"arXiv:{entry['arxiv_id']}"
    return ""


def _citation_key(raw: dict[str, Any], *, title: str, authors: list[str]) -> str:
    author = authors[0] if authors else "unknown"
    last_name = author.replace(",", " ").split()[0] if author.replace(",", " ").split() else "unknown"
    year = _year(raw.get("year")) or "nd"
    title_word = next((part for part in _alnum_words(title) if len(part) > 2), "work")
    return "".join(char for char in f"{last_name}{year}{title_word}".lower() if char.isalnum())[:80] or f"entry{uuid4().hex[:8]}"


def _alnum_words(text: str) -> list[str]:
    words = []
    current = []
    for char in text:
        if char.isalnum():
            current.append(char)
        elif current:
            words.append("".join(current))
            current = []
    if current:
        words.append("".join(current))
    return words


def _authors(value: Any) -> list[str]:
    if isinstance(value, str):
        raw = [part.strip() for part in value.replace(" and ", ";").split(";")]
    elif isinstance(value, list):
        raw = [str(item).strip() for item in value]
    else:
        raw = []
    return [item for item in raw if item][:50]


def _year(value: Any) -> str:
    text = str(value or "").strip()
    digits = "".join(char for char in text if char.isdigit())
    return digits[:4] if len(digits) >= 4 else ""


def _bounded_text(value: Any) -> str:
    return " ".join(str(value or "").split())[:MAX_TEXT_CHARS]


def _append_list(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines.extend([f"## {title}", ""])
    for item in items:
        lines.append(f"- {item}")
    lines.append("")


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


def _safe_filename(value: str, suffix: str) -> str:
    name = Path(value).name.strip() or f"artifact{suffix}"
    if not name.lower().endswith(suffix):
        name += suffix
    stem = "".join(char if char.isalnum() or char in ("-", "_", ".") else "-" for char in Path(name).stem).strip(".-")
    return f"{stem or 'artifact'}{suffix}"


def _is_within(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)
