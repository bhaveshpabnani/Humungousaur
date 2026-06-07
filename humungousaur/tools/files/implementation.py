from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


IGNORED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "artifacts",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
}

TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".csv",
    ".html",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

PDF_SUFFIX = ".pdf"
PDF_MAX_PAGES = 10
PDF_TEXT_LIMIT_CHARS = 12_000
PDF_MAX_MERGE_FILES = 20
PDF_MAX_EXTRACT_PAGES = 50
ALLOWED_SHELL_COMMANDS = ("python", "python.exe")
BLOCKED_INLINE_SHELL_TOKENS = ("-c", "/c")
SHELL_COMMAND_PROFILES = ("read_only", "workspace_write", "trusted_dev", "blocked")
READ_ONLY_SHELL_ARGV = {
    ("python", "--version"),
    ("python", "-V"),
    ("python", "-VV"),
    ("python.exe", "--version"),
    ("python.exe", "-V"),
    ("python.exe", "-VV"),
}
SHELL_TIMEOUT_SECONDS = 15
SEARCH_STOPWORDS = {
    "and",
    "behavior",
    "behaviour",
    "find",
    "for",
    "in",
    "of",
    "project",
    "references",
    "the",
    "this",
    "to",
}


def _resolve_workspace_path(config: AgentConfig, raw_path: str | None) -> Path:
    if not raw_path:
        return config.workspace
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = config.workspace / path
    return path.resolve()


def _resolve_read_path(config: AgentConfig, raw_path: str | None) -> Path:
    if not raw_path:
        return config.workspace
    text = str(raw_path).strip()
    if not text:
        return config.workspace
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        lowered = text.lower()
        for root in config.allowed_read_roots:
            if root.name.lower() == lowered:
                return root
    return _resolve_workspace_path(config, text)


def _is_default_scan_path(raw_path: Any) -> bool:
    return raw_path is None or str(raw_path).strip() in {"", "."}


def _is_within(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def _relative(path: Path, config: AgentConfig) -> str:
    try:
        return str(path.relative_to(config.workspace))
    except ValueError:
        return str(path)


def _iter_text_files(root: Path, config: AgentConfig) -> list[Path]:
    files: list[Path] = []
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in IGNORED_DIRS]
        for filename in filenames:
            path = Path(current_root) / filename
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if path.stat().st_size > config.max_file_bytes:
                continue
            files.append(path.resolve())
    return sorted(files)


def _iter_allowed_text_files(config: AgentConfig) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for root in config.allowed_read_roots:
        if not root.exists() or not root.is_dir():
            continue
        for path in _iter_text_files(root, config):
            if path in seen:
                continue
            seen.add(path)
            files.append(path)
    return sorted(files)


def _iter_pdf_files(root: Path, config: AgentConfig) -> list[Path]:
    if root.is_file():
        if root.suffix.lower() == PDF_SUFFIX and root.stat().st_size <= config.max_file_bytes:
            return [root.resolve()]
        return []
    files: list[Path] = []
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in IGNORED_DIRS]
        for filename in filenames:
            path = Path(current_root) / filename
            if path.suffix.lower() != PDF_SUFFIX:
                continue
            if path.stat().st_size > config.max_file_bytes:
                continue
            files.append(path.resolve())
    return sorted(files)


def _extract_pdf_text(path: Path, max_pages: int = PDF_MAX_PAGES, max_chars: int = PDF_TEXT_LIMIT_CHARS) -> dict[str, Any]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ValueError("Encrypted PDF could not be opened without a password.") from exc

    chunks: list[str] = []
    pages_read = 0
    total_pages = len(reader.pages)
    for page in reader.pages:
        if pages_read >= max_pages:
            break
        text = page.extract_text() or ""
        if text.strip():
            chunks.append(text.strip())
        pages_read += 1
        if sum(len(chunk) for chunk in chunks) >= max_chars:
            break
    text = "\n\n".join(chunks)
    if len(text) > max_chars:
        text = text[:max_chars].rstrip()
    return {"text": text, "pages_read": pages_read, "total_pages": total_pages}


def _resolve_write_pdf_path(config: AgentConfig, raw_filename: str | None, default_name: str) -> Path:
    filename = Path(str(raw_filename or default_name)).name.strip() or default_name
    if not filename.lower().endswith(PDF_SUFFIX):
        filename += PDF_SUFFIX
    safe_stem = "".join(char if char.isalnum() or char in ("-", "_", ".") else "-" for char in Path(filename).stem).strip(".-")
    filename = f"{safe_stem or Path(default_name).stem}{PDF_SUFFIX}"
    return (config.data_dir / "pdfs" / filename).resolve()


def _resolve_pdf_read_file(config: AgentConfig, raw_path: str | None) -> Path:
    path = _resolve_read_path(config, raw_path)
    if not _is_within(path, config.allowed_read_roots):
        raise ValueError("PDF path is outside allowed roots.")
    if not path.exists() or not path.is_file():
        raise ValueError(f"PDF file does not exist: {path}")
    if path.suffix.lower() != PDF_SUFFIX:
        raise ValueError("Path is not a PDF file.")
    if path.stat().st_size > config.max_file_bytes:
        raise ValueError("PDF exceeds configured read limit.")
    return path


def _page_indices(start_page: int, end_page: int, total_pages: int) -> list[int]:
    start = max(1, start_page)
    end = min(max(start, end_page), total_pages)
    return list(range(start - 1, end))


def summarize_text(text: str, max_sentences: int = 6) -> str:
    meaningful_lines: list[str] = []
    in_code_block = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block or not line:
            continue
        line = line.lstrip("#-*0123456789. ").strip()
        if line:
            meaningful_lines.append(line)
        if len(meaningful_lines) >= max_sentences:
            break
    cleaned = " ".join(meaningful_lines)
    if not cleaned:
        return ""
    separators = [". ", "? ", "! "]
    sentences = [cleaned]
    for separator in separators:
        if separator in cleaned:
            parts = cleaned.split(separator)
            sentences = [part.strip() + (separator.strip() if index < len(parts) - 1 else "") for index, part in enumerate(parts)]
            break
    summary = " ".join(sentence for sentence in sentences[:max_sentences] if sentence).strip()
    if len(summary) <= 700:
        return summary
    return summary[:697].rstrip() + "..."


class ListFilesTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="list_files",
            description="List relevant text/code files inside the workspace.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {"path": {"type": "string", "description": "Workspace-relative or allowed absolute folder path."}}
            ),
            capability_group="files",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        raw_path = tool_input.get("path")
        if _is_default_scan_path(raw_path):
            files = _iter_allowed_text_files(config)[: config.max_search_results]
        else:
            root = _resolve_workspace_path(config, raw_path)
            if not _is_within(root, config.allowed_read_roots):
                return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Read path is outside allowed roots.")
            files = _iter_text_files(root, config)[: config.max_search_results]
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(files)} relevant text/code files.",
            {"files": [_relative(path, config) for path in files]},
        )


class ReadFileTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="read_file",
            description="Read a small text file from an allowed workspace path.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {"path": {"type": "string", "description": "Workspace-relative or allowed absolute text file path."}},
                required=["path"],
            ),
            capability_group="files",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        path = _resolve_workspace_path(config, tool_input.get("path"))
        if not _is_within(path, config.allowed_read_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Read path is outside allowed roots.")
        if not path.exists() or not path.is_file():
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"File does not exist: {path}")
        if path.stat().st_size > config.max_file_bytes:
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "File exceeds configured read limit.")
        text = path.read_text(encoding="utf-8", errors="replace")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Read {_relative(path, config)}.",
            {"path": _relative(path, config), "text": text},
        )


class SearchWorkspaceTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="search_workspace",
            description="Search allowed workspace text files for a query.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {"query": {"type": "string", "description": "Case-insensitive text to search for."}},
                required=["query"],
            ),
            capability_group="files",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        query = str(tool_input.get("query", "")).strip().lower()
        if not query:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Search query is empty.")
        from humungousaur.indexing import FileIndex

        file_index = FileIndex(config.file_index_db_path)
        if file_index.is_usable_for(config):
            indexed_matches = file_index.search(query, config, limit=config.max_search_results)
            if indexed_matches:
                return ToolResult(
                    self.name,
                    ActionStatus.SUCCEEDED,
                    self.risk_level,
                    f"Found {len(indexed_matches)} indexed matches.",
                    {"matches": indexed_matches, "source": "index"},
                )
            token_matches = _ranked_token_search(query, config)
            return ToolResult(
                self.name,
                ActionStatus.SUCCEEDED,
                self.risk_level,
                f"Found {len(token_matches)} ranked token matches.",
                {"matches": token_matches, "source": "token_scan"},
            )
        matches = _exact_text_search(query, config)
        if not matches:
            matches = _ranked_token_search(query, config)
            return ToolResult(
                self.name,
                ActionStatus.SUCCEEDED,
                self.risk_level,
                f"Found {len(matches)} ranked token matches.",
                {"matches": matches, "source": "token_scan"},
            )
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(matches)} matches.",
            {"matches": matches, "source": "scan"},
        )


def _exact_text_search(query: str, config: AgentConfig) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    lowered = query.lower()
    for path in _iter_allowed_text_files(config):
        if not _is_within(path, config.allowed_read_roots):
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if lowered in line.lower():
                matches.append({"path": _relative(path, config), "line": line_number, "text": line.strip(), "source": "scan"})
                if len(matches) >= config.max_search_results:
                    return matches
    return matches


def _ranked_token_search(query: str, config: AgentConfig) -> list[dict[str, Any]]:
    terms = _search_terms(query)
    if len(terms) < 2:
        return []
    candidates: list[tuple[int, int, str, dict[str, Any]]] = []
    for path in _iter_allowed_text_files(config):
        if not _is_within(path, config.allowed_read_roots):
            continue
        rel = _relative(path, config)
        path_text = rel.lower()
        path_score = sum(1 for term in terms if term in path_text)
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            lowered = line.lower()
            matched_terms = [term for term in terms if term in lowered]
            if not matched_terms and path_score == 0:
                continue
            score = len(set(matched_terms)) * 3 + path_score
            if score <= 0:
                continue
            payload = {
                "path": rel,
                "line": line_number,
                "text": line.strip(),
                "source": "token_scan",
                "matched_terms": sorted(set(matched_terms) | {term for term in terms if term in path_text}),
            }
            candidates.append((-score, line_number, rel, payload))
    candidates.sort()
    return [payload for _score, _line, _path, payload in candidates[: config.max_search_results]]


def _search_terms(query: str) -> list[str]:
    terms = []
    seen = set()
    for term in re.findall(r"[a-z0-9_]{3,}", query.lower()):
        if term in SEARCH_STOPWORDS or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms


class ListPDFsTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="list_pdfs",
            description="List PDF files inside allowed read roots.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {"path": {"type": "string", "description": "Allowed folder or PDF path. Defaults to workspace."}}
            ),
            capability_group="files",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        root = _resolve_read_path(config, tool_input.get("path"))
        if not _is_within(root, config.allowed_read_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "PDF path is outside allowed roots.")
        if not root.exists():
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"PDF path does not exist: {root}")
        files = _iter_pdf_files(root, config)[: config.max_search_results]
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(files)} PDF files.",
            {"files": [{"path": _relative(path, config), "size": path.stat().st_size} for path in files]},
        )


class ReadPDFTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="read_pdf",
            description="Extract text from a small PDF inside allowed read roots.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "path": {"type": "string", "description": "Allowed PDF file path."},
                    "max_pages": {"type": "integer", "minimum": 1, "maximum": PDF_MAX_PAGES},
                    "max_chars": {"type": "integer", "minimum": 1, "maximum": PDF_TEXT_LIMIT_CHARS},
                },
                required=["path"],
            ),
            capability_group="files",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        path = _resolve_read_path(config, tool_input.get("path"))
        if not _is_within(path, config.allowed_read_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "PDF path is outside allowed roots.")
        if not path.exists() or not path.is_file():
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"PDF file does not exist: {path}")
        if path.suffix.lower() != PDF_SUFFIX:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Path is not a PDF file.")
        if path.stat().st_size > config.max_file_bytes:
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "PDF exceeds configured read limit.")
        extracted = _extract_pdf_text(
            path,
            max_pages=int(tool_input.get("max_pages") or PDF_MAX_PAGES),
            max_chars=int(tool_input.get("max_chars") or PDF_TEXT_LIMIT_CHARS),
        )
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Read PDF {_relative(path, config)}.",
            {"path": _relative(path, config), **extracted},
        )


class SummarizePDFsTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="summarize_pdfs",
            description="Extract and summarize PDF files inside an allowed read root.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "path": {"type": "string", "description": "Allowed folder or PDF path. Defaults to workspace."},
                    "max_pages": {"type": "integer", "minimum": 1, "maximum": PDF_MAX_PAGES},
                    "max_chars": {"type": "integer", "minimum": 1, "maximum": PDF_TEXT_LIMIT_CHARS},
                }
            ),
            capability_group="files",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        root = _resolve_read_path(config, tool_input.get("path"))
        if not _is_within(root, config.allowed_read_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "PDF path is outside allowed roots.")
        if not root.exists():
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"PDF path does not exist: {root}")
        files = _iter_pdf_files(root, config)[: config.max_search_results]
        summaries: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for path in files:
            try:
                extracted = _extract_pdf_text(
                    path,
                    max_pages=int(tool_input.get("max_pages") or PDF_MAX_PAGES),
                    max_chars=int(tool_input.get("max_chars") or PDF_TEXT_LIMIT_CHARS),
                )
                text = extracted["text"]
                summaries.append(
                    {
                        "path": _relative(path, config),
                        "pages_read": extracted["pages_read"],
                        "total_pages": extracted["total_pages"],
                        "summary": summarize_text(text, max_sentences=4) or "No extractable text found.",
                    }
                )
            except Exception as exc:
                errors.append({"path": _relative(path, config), "error": str(exc)})
        status = ActionStatus.SUCCEEDED if summaries or not errors else ActionStatus.FAILED
        return ToolResult(
            self.name,
            status,
            self.risk_level,
            f"Summarized {len(summaries)} PDF files.",
            {"summaries": summaries, "errors": errors, "source": "pdf"},
            None if status == ActionStatus.SUCCEEDED else "No PDF files could be summarized.",
        )


class MergePDFsTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="pdf_merge",
            description=(
                "Merge multiple allowed local PDF files into one new PDF artifact under data_dir/pdfs. "
                "Uses Humungousaur-owned local PDF handling and does not send files to cloud OCR or upstream scripts."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "paths": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": PDF_MAX_MERGE_FILES},
                    "filename": {"type": "string", "description": "Output PDF filename under data_dir/pdfs."},
                    "reason": {"type": "string", "description": "Why these PDFs should be merged."},
                },
                required=["paths", "reason"],
            ),
            capability_group="files",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        try:
            from pypdf import PdfReader, PdfWriter
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "pypdf is required for native PDF merge.", error=str(exc))
        normalized = config.normalized()
        raw_paths = tool_input.get("paths", [])
        if not isinstance(raw_paths, list) or len(raw_paths) < 2:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "At least two PDF paths are required.")
        if len(raw_paths) > PDF_MAX_MERGE_FILES:
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "PDF merge file count exceeds safety limit.")
        try:
            paths = [_resolve_pdf_read_file(normalized, str(raw_path)) for raw_path in raw_paths]
        except ValueError as exc:
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, str(exc))
        output_path = _resolve_write_pdf_path(normalized, tool_input.get("filename"), "merged.pdf")
        if not _is_within(output_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Merged PDF path is outside allowed write roots.")
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                f"Dry run: would merge {len(paths)} PDFs.",
                {"path": str(output_path), "input_paths": [_relative(path, normalized) for path in paths]},
            )
        writer = PdfWriter()
        page_counts = []
        try:
            for path in paths:
                reader = PdfReader(str(path))
                page_counts.append({"path": _relative(path, normalized), "pages": len(reader.pages)})
                for page in reader.pages:
                    writer.add_page(page)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("wb") as handle:
                writer.write(handle)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "PDF merge failed.", error=str(exc))
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Merged {len(paths)} PDFs into {output_path}.",
            {"path": str(output_path), "input_count": len(paths), "inputs": page_counts, "source": "pdf_merge"},
        )


class ExtractPDFPagesTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="pdf_extract_pages",
            description="Extract a bounded page range from one allowed local PDF into a new PDF artifact under data_dir/pdfs.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "path": {"type": "string", "description": "Allowed source PDF file path."},
                    "start_page": {"type": "integer", "minimum": 1},
                    "end_page": {"type": "integer", "minimum": 1},
                    "filename": {"type": "string", "description": "Output PDF filename under data_dir/pdfs."},
                    "reason": {"type": "string", "description": "Why this page range should be extracted."},
                },
                required=["path", "start_page", "end_page", "reason"],
            ),
            capability_group="files",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        try:
            from pypdf import PdfReader, PdfWriter
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "pypdf is required for native PDF page extraction.", error=str(exc))
        normalized = config.normalized()
        try:
            source = _resolve_pdf_read_file(normalized, str(tool_input.get("path") or ""))
            start_page = int(tool_input.get("start_page") or 1)
            end_page = int(tool_input.get("end_page") or start_page)
        except (TypeError, ValueError) as exc:
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, str(exc))
        output_path = _resolve_write_pdf_path(normalized, tool_input.get("filename"), "extracted-pages.pdf")
        if not _is_within(output_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Extracted PDF path is outside allowed write roots.")
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would extract PDF pages.",
                {"path": str(output_path), "source_path": _relative(source, normalized), "start_page": start_page, "end_page": end_page},
            )
        try:
            reader = PdfReader(str(source))
            indices = _page_indices(start_page, end_page, len(reader.pages))
            if len(indices) > PDF_MAX_EXTRACT_PAGES:
                return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "PDF extract page count exceeds safety limit.")
            writer = PdfWriter()
            for index in indices:
                writer.add_page(reader.pages[index])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("wb") as handle:
                writer.write(handle)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "PDF page extraction failed.", error=str(exc))
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Extracted {len(indices)} PDF page(s) to {output_path}.",
            {
                "path": str(output_path),
                "source_path": _relative(source, normalized),
                "start_page": start_page,
                "end_page": end_page,
                "page_count": len(indices),
                "source": "pdf_extract_pages",
            },
        )


class OCRProviderStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="ocr_provider_status",
            description=(
                "Report local OCR provider availability without sending images or documents anywhere. "
                "Use before claiming OCR can run."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({}),
            capability_group="files",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        del tool_input, config
        providers = [
            {
                "provider": "tesseract",
                "binary_available": bool(shutil.which("tesseract")),
                "python_package_available": bool(importlib.util.find_spec("pytesseract")),
                "mode": "local_binary",
            },
            {
                "provider": "easyocr",
                "binary_available": False,
                "python_package_available": bool(importlib.util.find_spec("easyocr")),
                "mode": "local_python",
            },
            {
                "provider": "pillow_image_support",
                "binary_available": False,
                "python_package_available": bool(importlib.util.find_spec("PIL")),
                "mode": "local_image_preprocessing",
            },
        ]
        ready = any(item["provider"] == "tesseract" and item["binary_available"] and item["python_package_available"] for item in providers)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            "Checked local OCR provider availability.",
            {
                "ready_for_local_ocr": ready,
                "providers": providers,
                "cloud_ocr_used": False,
                "source": "ocr_provider_status",
            },
        )


class WriteNoteTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="write_note",
            description="Write an agent-generated note under the configured notes directory.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "title": {"type": "string", "description": "Safe note title used to create a markdown filename."},
                    "content": {"type": "string", "description": "Markdown note content."},
                },
                required=["title", "content"],
            ),
            capability_group="files",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        title = str(tool_input.get("title", "agent-note")).strip() or "agent-note"
        content = str(tool_input.get("content", "")).strip()
        safe_title = "".join(char if char.isalnum() or char in ("-", "_") else "-" for char in title.lower()).strip("-")
        path = (config.notes_dir / f"{safe_title}.md").resolve()
        if not _is_within(path, config.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Write path is outside allowed roots.")
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                f"Dry run: would write note {path}.",
                {"path": str(path), "content": content},
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Wrote note {path}.",
            {"path": str(path)},
        )


class ShellCommandTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="run_shell_command",
            description="Run a constrained local command in the workspace after explicit approval.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "argv": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "description": "Command argv list. Only allowlisted executables are accepted.",
                    },
                    "command_profile": {
                        "type": "string",
                        "enum": list(SHELL_COMMAND_PROFILES),
                        "description": (
                            "Shell execution profile: read_only allows safe probes, workspace_write uses the normal "
                            "allowlist, trusted_dev permits approved inline Python, and blocked refuses execution."
                        ),
                    },
                },
                required=["argv"],
            ),
            capability_group="shell",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        argv = tool_input.get("argv", [])
        if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv) or not argv:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Shell command argv must be a non-empty string list.")
        command_profile = str(tool_input.get("command_profile") or "workspace_write")
        if command_profile not in SHELL_COMMAND_PROFILES:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unsupported command profile: {command_profile}.")
        if command_profile == "blocked":
            return ToolResult(
                self.name,
                ActionStatus.BLOCKED,
                self.risk_level,
                "Command profile blocks shell execution.",
                {"command_profile": command_profile},
            )
        if argv[0].lower() not in ALLOWED_SHELL_COMMANDS:
            return ToolResult(
                self.name,
                ActionStatus.BLOCKED,
                self.risk_level,
                "Only explicitly allowlisted commands can run.",
                {"allowed_commands": list(ALLOWED_SHELL_COMMANDS)},
            )
        if command_profile == "read_only" and not _read_only_shell_argv(argv):
            return ToolResult(
                self.name,
                ActionStatus.BLOCKED,
                self.risk_level,
                "Read-only command profile only allows safe command probes.",
                {"command_profile": command_profile, "allowed_examples": [list(item) for item in sorted(READ_ONLY_SHELL_ARGV)]},
            )
        if command_profile != "trusted_dev" and any(token in BLOCKED_INLINE_SHELL_TOKENS for token in argv[1:]):
            return ToolResult(
                self.name,
                ActionStatus.BLOCKED,
                self.risk_level,
                "Inline shell/code execution is blocked by policy.",
            )
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would execute approved shell command.",
                {"argv": argv, "cwd": str(config.workspace), "command_profile": command_profile},
            )
        env = dict(os.environ)
        if command_profile == "read_only":
            env["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            argv,
            cwd=config.workspace,
            capture_output=True,
            text=True,
            timeout=SHELL_TIMEOUT_SECONDS,
            shell=False,
            check=False,
            env=env,
        )
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED if completed.returncode == 0 else ActionStatus.FAILED,
            self.risk_level,
            f"Command exited with code {completed.returncode}.",
            {
                "argv": argv,
                "command_profile": command_profile,
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            },
            None if completed.returncode == 0 else completed.stderr[-1000:],
        )


def _read_only_shell_argv(argv: list[str]) -> bool:
    normalized = [argv[0].lower(), *argv[1:]]
    return tuple(normalized) in READ_ONLY_SHELL_ARGV


def default_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        ListFilesTool(),
        ReadFileTool(),
        SearchWorkspaceTool(),
        ListPDFsTool(),
        ReadPDFTool(),
        SummarizePDFsTool(),
        MergePDFsTool(),
        ExtractPDFPagesTool(),
        OCRProviderStatusTool(),
        WriteNoteTool(),
        ShellCommandTool(),
    ]
    return {tool.name: tool for tool in tools}
