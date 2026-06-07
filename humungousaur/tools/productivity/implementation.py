from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


EMAIL_ADDRESS_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EMAIL_DRAFT_MAX_RECIPIENTS = 50
EMAIL_DRAFT_MAX_BODY_CHARS = 50_000
XLSX_MAX_ROWS = 5_000
XLSX_MAX_COLUMNS = 100


class EmailDraftPrepareTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="email_draft_prepare",
            description=(
                "Prepare a local email draft artifact from explicit recipients, subject, and body. "
                "This does not send email; use it for approval-ready Gmail, Outlook, IMAP, or SMTP drafts."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=_email_draft_schema(),
            capability_group="productivity",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        return _prepare_email_draft(tool_input, config, provider="email")


class GmailDraftPrepareTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="gmail_draft_prepare",
            description=(
                "Prepare a Gmail-ready local draft artifact from explicit recipients, subject, and body. "
                "This validates the draft and records the next gog/native Gmail command shape, but never sends."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=_email_draft_schema(),
            capability_group="productivity",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        return _prepare_email_draft(tool_input, config, provider="gmail")


class XlsxWorkbookCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="xlsx_workbook_create",
            description=(
                "Create a native XLSX workbook artifact with sheets, rows, formulas, and optional number formats. "
                "Use for Excel-style workbook tasks before sharing or editing source files."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output filename under data_dir/spreadsheets."},
                    "sheets": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Sheet specs: name, rows, formulas, freeze_panes, widths.",
                    },
                    "reason": {"type": "string", "description": "Why this workbook should be created."},
                },
                required=["sheets", "reason"],
            ),
            capability_group="productivity",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "openpyxl is required for XLSX creation.", error=str(exc))

        sheets = tool_input.get("sheets")
        if not isinstance(sheets, list) or not sheets:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "At least one sheet spec is required.")
        filename = _safe_filename(str(tool_input.get("filename") or "humungousaur-workbook.xlsx"), ".xlsx")
        path = (config.normalized().data_dir / "spreadsheets" / filename).resolve()
        if not _is_within(path, config.normalized().allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Workbook path is outside allowed write roots.")
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would create workbook {path}.", {"path": str(path), "sheets": sheets})

        workbook = Workbook()
        default_sheet = workbook.active
        workbook.remove(default_sheet)
        summaries: list[dict[str, Any]] = []
        for index, spec in enumerate(sheets[:20], start=1):
            if not isinstance(spec, dict):
                continue
            sheet_name = _safe_sheet_name(str(spec.get("name") or f"Sheet{index}"), workbook.sheetnames)
            worksheet = workbook.create_sheet(sheet_name)
            rows = spec.get("rows") or []
            if not isinstance(rows, list):
                rows = []
            if len(rows) > XLSX_MAX_ROWS:
                return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, f"Sheet {sheet_name} exceeds row limit.")
            for row in rows:
                if not isinstance(row, list):
                    row = [row]
                if len(row) > XLSX_MAX_COLUMNS:
                    return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, f"Sheet {sheet_name} exceeds column limit.")
                worksheet.append([_xlsx_cell_value(value) for value in row])
            formulas = spec.get("formulas") or []
            if isinstance(formulas, list):
                for formula in formulas[:500]:
                    if not isinstance(formula, dict):
                        continue
                    cell = str(formula.get("cell") or "").strip()
                    value = str(formula.get("formula") or "").strip()
                    if cell and value:
                        worksheet[cell] = value if value.startswith("=") else f"={value}"
            if worksheet.max_row >= 1:
                for cell in worksheet[1]:
                    cell.font = Font(bold=True)
            freeze_panes = str(spec.get("freeze_panes") or "").strip()
            if freeze_panes:
                worksheet.freeze_panes = freeze_panes
            widths = spec.get("widths") or {}
            if isinstance(widths, dict):
                for column, width in widths.items():
                    try:
                        worksheet.column_dimensions[str(column).upper()].width = max(1, min(float(width), 80))
                    except (TypeError, ValueError):
                        continue
            summaries.append({"name": sheet_name, "rows": worksheet.max_row, "columns": worksheet.max_column})
        if not workbook.sheetnames:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "No valid sheets were provided.")
        path.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(path)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created XLSX workbook {path}.",
            {"path": str(path), "sheets": summaries, "source": "xlsx_workbook_create"},
        )


class XlsxWorkbookInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="xlsx_workbook_inspect",
            description="Inspect a local XLSX workbook artifact for sheets, dimensions, headers, formulas, and sample rows.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "path": {"type": "string", "description": "Workspace-relative or allowed absolute XLSX path."},
                    "sample_rows": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                required=["path"],
            ),
            capability_group="productivity",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        try:
            from openpyxl import load_workbook
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "openpyxl is required for XLSX inspection.", error=str(exc))
        path = _resolve_allowed_path(config.normalized(), str(tool_input.get("path") or ""))
        if not _is_within(path, config.normalized().allowed_read_roots + config.normalized().allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Workbook path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".xlsx":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Workbook does not exist or is not an XLSX file.")
        sample_rows = max(1, min(int(tool_input.get("sample_rows") or 5), 20))
        try:
            workbook = load_workbook(path, data_only=False, read_only=True)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Workbook could not be opened.", error=str(exc))
        sheets: list[dict[str, Any]] = []
        for worksheet in workbook.worksheets:
            rows = []
            formulas = []
            for row_index, row in enumerate(worksheet.iter_rows(values_only=False), start=1):
                if row_index <= sample_rows:
                    rows.append([cell.value for cell in row])
                for cell in row:
                    if isinstance(cell.value, str) and cell.value.startswith("="):
                        formulas.append({"cell": cell.coordinate, "formula": cell.value})
                if row_index >= sample_rows and len(formulas) >= 50:
                    break
            sheets.append(
                {
                    "name": worksheet.title,
                    "max_row": worksheet.max_row,
                    "max_column": worksheet.max_column,
                    "sample_rows": rows,
                    "formulas": formulas[:50],
                }
            )
        workbook.close()
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected XLSX workbook {path}.",
            {"path": str(path), "sheets": sheets, "source": "xlsx_workbook_inspect"},
        )


def default_productivity_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        EmailDraftPrepareTool(),
        GmailDraftPrepareTool(),
        XlsxWorkbookCreateTool(),
        XlsxWorkbookInspectTool(),
    ]
    return {tool.name: tool for tool in tools}


def _email_draft_schema() -> dict[str, Any]:
    return object_input_schema(
        {
            "to": {"type": "array", "items": {"type": "string"}, "description": "Explicit recipient email addresses."},
            "cc": {"type": "array", "items": {"type": "string"}, "description": "Optional CC email addresses."},
            "bcc": {"type": "array", "items": {"type": "string"}, "description": "Optional BCC email addresses."},
            "subject": {"type": "string", "description": "Email subject."},
            "body": {"type": "string", "description": "Email body text."},
            "tone": {"type": "string", "description": "Optional requested tone label."},
            "attachments": {"type": "array", "items": {"type": "string"}, "description": "Optional attachment paths to review before sending."},
            "reason": {"type": "string", "description": "Why this draft should be prepared."},
        },
        required=["to", "subject", "body", "reason"],
    )


def _prepare_email_draft(tool_input: dict[str, Any], config: AgentConfig, *, provider: str) -> ToolResult:
    normalized = config.normalized()
    to = _email_list(tool_input.get("to"))
    cc = _email_list(tool_input.get("cc"))
    bcc = _email_list(tool_input.get("bcc"))
    invalid = [address for address in [*to, *cc, *bcc] if not EMAIL_ADDRESS_RE.match(address)]
    if not to:
        return ToolResult(f"{provider}_draft_prepare", ActionStatus.FAILED, RiskLevel.MEDIUM, "At least one explicit recipient is required.")
    if invalid:
        return ToolResult(f"{provider}_draft_prepare", ActionStatus.FAILED, RiskLevel.MEDIUM, "Draft contains invalid email addresses.", {"invalid_addresses": invalid})
    if len([*to, *cc, *bcc]) > EMAIL_DRAFT_MAX_RECIPIENTS:
        return ToolResult(f"{provider}_draft_prepare", ActionStatus.BLOCKED, RiskLevel.MEDIUM, "Draft exceeds recipient limit.")
    subject = " ".join(str(tool_input.get("subject") or "").split())
    body = str(tool_input.get("body") or "").strip()
    if not subject or not body:
        return ToolResult(f"{provider}_draft_prepare", ActionStatus.FAILED, RiskLevel.MEDIUM, "Subject and body are required.")
    if len(body) > EMAIL_DRAFT_MAX_BODY_CHARS:
        return ToolResult(f"{provider}_draft_prepare", ActionStatus.BLOCKED, RiskLevel.MEDIUM, "Draft body exceeds safety limit.")
    draft_id = f"{provider}-draft-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
    root = normalized.data_dir / "email_drafts"
    json_path = (root / f"{draft_id}.json").resolve()
    body_path = (root / f"{draft_id}.txt").resolve()
    if not _is_within(json_path, normalized.allowed_write_roots):
        return ToolResult(f"{provider}_draft_prepare", ActionStatus.BLOCKED, RiskLevel.MEDIUM, "Draft path is outside allowed write roots.")
    attachments = [str(item).strip() for item in (tool_input.get("attachments") or []) if str(item).strip()]
    draft = {
        "draft_id": draft_id,
        "provider": provider,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "to": to,
        "cc": cc,
        "bcc": bcc,
        "subject": subject,
        "body": body,
        "tone": str(tool_input.get("tone") or "").strip(),
        "attachments": attachments,
        "reason": str(tool_input.get("reason") or "").strip(),
        "send_status": "not_sent",
        "approval_required_for_send": True,
    }
    draft["gmail_command_preview"] = [
        "gog",
        "gmail",
        "drafts",
        "create",
        "--to",
        ",".join(to),
        "--subject",
        subject,
        "--body-file",
        str(body_path),
    ] if provider == "gmail" else []
    if config.dry_run:
        return ToolResult(
            f"{provider}_draft_prepare",
            ActionStatus.SKIPPED,
            RiskLevel.MEDIUM,
            f"Dry run: would prepare {provider} draft.",
            {"draft": draft, "path": str(json_path), "body_path": str(body_path)},
        )
    root.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(draft, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    body_path.write_text(body + "\n", encoding="utf-8")
    return ToolResult(
        f"{provider}_draft_prepare",
        ActionStatus.SUCCEEDED,
        RiskLevel.MEDIUM,
        f"Prepared {provider} draft artifact.",
        {"draft": {**draft, "body": body[:500], "body_truncated": len(body) > 500}, "path": str(json_path), "body_path": str(body_path)},
    )


def _email_list(value: Any) -> list[str]:
    if isinstance(value, str):
        raw = [value]
    elif isinstance(value, list):
        raw = value
    else:
        raw = []
    cleaned = []
    seen = set()
    for item in raw:
        address = str(item).strip().lower()
        if address and address not in seen:
            seen.add(address)
            cleaned.append(address)
    return cleaned


def _safe_filename(value: str, suffix: str) -> str:
    name = Path(value).name.strip() or f"artifact{suffix}"
    if not name.lower().endswith(suffix):
        name += suffix
    stem = "".join(char if char.isalnum() or char in ("-", "_", ".") else "-" for char in Path(name).stem).strip(".-")
    return f"{stem or 'artifact'}{suffix}"


def _safe_sheet_name(value: str, existing: list[str]) -> str:
    cleaned = "".join(char for char in value if char not in r"[]:*?/\\").strip()[:31] or "Sheet"
    candidate = cleaned
    index = 2
    while candidate in existing:
        suffix = f" {index}"
        candidate = f"{cleaned[:31 - len(suffix)]}{suffix}"
        index += 1
    return candidate


def _resolve_allowed_path(config: AgentConfig, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = config.workspace / path
        if not path.exists():
            data_path = config.data_dir / raw_path
            if data_path.exists():
                path = data_path
            else:
                spreadsheet_path = config.data_dir / "spreadsheets" / Path(raw_path).name
                if spreadsheet_path.exists():
                    path = spreadsheet_path
    return path.resolve()


def _xlsx_cell_value(value: Any) -> Any:
    if isinstance(value, dict):
        if "formula" in value:
            formula = str(value.get("formula") or "").strip()
            if formula:
                return formula if formula.startswith("=") else f"={formula}"
            return None
        if "value" in value:
            return value.get("value")
    return value


def _is_within(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)
