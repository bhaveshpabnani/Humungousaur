from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib.util
import json
from pathlib import Path
import re
import sys
import threading
from typing import Any
import uuid

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, ToolResult
from humungousaur.tools import default_tools
from humungousaur.tools.skill_tools import AgentSkillCatalogTool, AgentSkillReadTool, AgentSkillScriptCatalogTool, AgentSkillScriptReadTool, AgentSkillScriptRunTool


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke every Humungousaur workspace skill and representative task capability.")
    parser.add_argument("--workspace", type=Path, default=REPO_ROOT)
    parser.add_argument("--data-dir", type=Path, default=Path("artifacts/skill-smoke"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    config = AgentConfig(workspace=args.workspace, data_dir=args.data_dir, planner_provider="explicit").normalized()
    tools = default_tools(config)
    tool_names = set(tools)
    sections: list[dict[str, Any]] = []

    def record(section: str, name: str, ok: bool, payload: Any) -> None:
        sections.append({"section": section, "name": name, "ok": ok, "payload": _jsonable(payload)})

    catalog = AgentSkillCatalogTool().execute({"source": "workspace", "limit": 300}, config)
    skills = catalog.output.get("workspace_skills", []) if catalog.status == ActionStatus.SUCCEEDED else []
    skill_names = {str(skill.get("name", "")) for skill in skills}
    record("skills", "catalog", catalog.status == ActionStatus.SUCCEEDED and len(skills) >= 100, _tool_payload(catalog))
    for skill in skills:
        skill_id = skill["skill_id"]
        read = AgentSkillReadTool().execute({"skill_id": skill_id}, config)
        content = read.output.get("content", "") if read.status == ActionStatus.SUCCEEDED else ""
        tool_map = _tool_map_entries(content)
        missing = [entry for entry in tool_map if entry not in tool_names and entry not in skill_names]
        record(
            "skills",
            f"read:{skill['name']}",
            read.status == ActionStatus.SUCCEEDED and "# " in content,
            {"skill_id": skill_id, "status": read.status.value, "summary": read.summary, "content_length": len(content)},
        )
        record(
            "skills",
            f"tool_map:{skill['name']}",
            bool(tool_map) and not missing,
            {
                "skill_id": skill_id,
                "tool_map": tool_map,
                "native_tools": [entry for entry in tool_map if entry in tool_names],
                "skill_refs": [entry for entry in tool_map if entry in skill_names],
                "missing": missing,
                "has_tool_map": bool(tool_map),
            },
        )

    script_catalog = AgentSkillScriptCatalogTool().execute({"limit": 300}, config)
    scripts = script_catalog.output.get("scripts", []) if script_catalog.status == ActionStatus.SUCCEEDED else []
    record("skills", "script_catalog", script_catalog.status == ActionStatus.SUCCEEDED, _tool_payload(script_catalog))
    _prepare_script_fixtures(config)
    for script in scripts:
        script_read = AgentSkillScriptReadTool().execute({"script_id": script["script_id"]}, config)
        record(
            "skills",
            f"script_read:{script['name']}",
            script_read.status == ActionStatus.SUCCEEDED and bool(script.get("input_schema")),
            {"script_id": script["script_id"], "status": script_read.status.value, "summary": script_read.summary},
        )
        script_input = _script_smoke_input(script["name"], config)
        script_run = AgentSkillScriptRunTool().execute(
            {"script_id": script["script_id"], "input": script_input, "reason": f"Skill smoke for {script['name']}."},
            config,
        )
        record(
            "skills",
            f"script_run:{script['name']}",
            script_run.status == ActionStatus.SUCCEEDED,
            {
                "script_id": script["script_id"],
                "status": script_run.status.value,
                "summary": script_run.summary,
                "returncode": script_run.output.get("returncode"),
                "json": script_run.output.get("json"),
                "stderr": script_run.output.get("stderr", "")[-500:],
            },
        )

    _smoke_productivity(record, tools, config)
    _smoke_pdf(record, tools, config)
    _smoke_office(record, tools, config)
    _smoke_analysis(record, tools, config)
    _smoke_writing(record, tools, config)
    _smoke_creative(record, tools, config)
    _smoke_content(record, tools, config)
    _smoke_research(record, tools, config)
    _smoke_media(record, tools, config)
    _smoke_travel(record, tools, config)
    _smoke_commerce(record, tools, config)
    _smoke_personal(record, tools, config)
    _smoke_design(record, tools, config)
    _smoke_visuals(record, tools, config)
    _smoke_channels(record, tools, config)
    _smoke_rss(record, tools, config)
    _smoke_network(record, tools, config)
    _smoke_core_surfaces(record, tools, config)
    _smoke_skill_task_surfaces(record, tools, config)

    failed = [item for item in sections if not item["ok"]]
    config.data_dir.mkdir(parents=True, exist_ok=True)
    result_path = config.data_dir / "skill-smoke-results.json"
    result_path.write_text(json.dumps({"sections": sections, "failed": failed}, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = {"ok": not failed, "result_path": str(result_path), "section_count": len(sections), "failed_count": len(failed), "failed": failed[:20]}
    print(json.dumps(summary, indent=2 if args.json else None, ensure_ascii=False))
    return 0 if not failed else 1


def _smoke_productivity(record, tools: dict[str, Any], config: AgentConfig) -> None:
    gmail = tools["gmail_draft_prepare"].execute(
        {
            "to": ["person@example.com"],
            "subject": "Humungousaur skill smoke",
            "body": "Hi,\n\nThis is a local Gmail draft smoke. It was not sent.\n\nBest,\nHumungousaur",
            "reason": "Verify Gmail draft preparation skill capability.",
        },
        config,
    )
    record("productivity", "gmail_draft_prepare", _ok(gmail) and gmail.output["draft"]["send_status"] == "not_sent", _tool_payload(gmail))

    xlsx = tools["xlsx_workbook_create"].execute(
        {
            "filename": "skill-smoke.xlsx",
            "reason": "Verify Excel workbook skill capability.",
            "sheets": [{"name": "Summary", "rows": [["Metric", "Value"], ["Revenue", 100], ["Cost", 40], ["Profit", None]], "formulas": [{"cell": "B4", "formula": "=B2-B3"}]}],
        },
        config,
    )
    inspect = tools["xlsx_workbook_inspect"].execute({"path": xlsx.output.get("path", ""), "sample_rows": 5}, config) if _ok(xlsx) else xlsx
    formula_ok = _ok(inspect) and any(item.get("formula") == "=B2-B3" for item in inspect.output["sheets"][0]["formulas"])
    record("productivity", "xlsx_workbook_create", _ok(xlsx), _tool_payload(xlsx))
    record("productivity", "xlsx_workbook_inspect", formula_ok, _tool_payload(inspect))
    notion = tools["notion_operation_prepare"].execute(
        {
            "operation": "create_page",
            "database_id": "db-skill-smoke",
            "title": "Humungousaur Skill Smoke",
            "properties": {"Status": {"select": {"name": "Draft"}}},
            "blocks": [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": "Prepared locally by skill smoke."}}]}}],
            "reason": "Verify native Notion operation preparation.",
        },
        config,
    )
    notion_inspect = tools["api_operation_inspect"].execute({"path": notion.output.get("path", "")}, config) if _ok(notion) else notion
    airtable = tools["airtable_operation_prepare"].execute(
        {
            "operation": "upsert_records",
            "base_id": "appSkillSmoke",
            "table_name": "Tasks",
            "upsert_key_fields": ["Task ID"],
            "records": [{"fields": {"Task ID": "skill-smoke", "Status": "Ready"}}],
            "reason": "Verify native Airtable operation preparation.",
        },
        config,
    )
    airtable_inspect = tools["api_operation_inspect"].execute({"path": airtable.output.get("path", "")}, config) if _ok(airtable) else airtable
    record("productivity", "notion_operation_prepare", _ok(notion) and notion.output.get("live_execution_status") == "not_executed", _tool_payload(notion))
    record("productivity", "notion_operation_inspect", _ok(notion_inspect) and notion_inspect.output.get("provider") == "notion", _tool_payload(notion_inspect))
    record("productivity", "airtable_operation_prepare", _ok(airtable) and airtable.output.get("live_execution_status") == "not_executed", _tool_payload(airtable))
    record("productivity", "airtable_operation_inspect", _ok(airtable_inspect) and airtable_inspect.output.get("provider") == "airtable", _tool_payload(airtable_inspect))
    google_calendar = tools["google_workspace_operation_prepare"].execute(
        {
            "app": "calendar",
            "operation": "create_event",
            "calendar_id": "primary",
            "title": "Humungousaur Skill Smoke",
            "description": "Prepared locally; not scheduled.",
            "start": "2026-06-08T09:00:00+05:30",
            "end": "2026-06-08T09:30:00+05:30",
            "timezone": "Asia/Kolkata",
            "attendees": ["person@example.com"],
            "reason": "Verify native Google Calendar operation packet.",
        },
        config,
    )
    google_drive = tools["google_workspace_operation_prepare"].execute(
        {
            "app": "drive",
            "operation": "share_file",
            "file_id": "file-skill-smoke",
            "recipients": ["person@example.com"],
            "role": "reader",
            "reason": "Verify native Google Drive operation packet.",
        },
        config,
    )
    google_docs = tools["google_workspace_operation_prepare"].execute(
        {
            "app": "docs",
            "operation": "append_doc_text",
            "document_id": "doc-skill-smoke",
            "body": "Prepared local batch update text for skill smoke.",
            "reason": "Verify native Google Docs operation packet.",
        },
        config,
    )
    google_sheets = tools["google_workspace_operation_prepare"].execute(
        {
            "app": "sheets",
            "operation": "update_values",
            "spreadsheet_id": "sheet-skill-smoke",
            "range": "Summary!A1:B2",
            "values": [["Metric", "Value"], ["Smoke", "Pass"]],
            "reason": "Verify native Google Sheets operation packet.",
        },
        config,
    )
    google_calendar_inspect = tools["api_operation_inspect"].execute({"path": google_calendar.output.get("path", "")}, config) if _ok(google_calendar) else google_calendar
    google_sheets_inspect = tools["api_operation_inspect"].execute({"path": google_sheets.output.get("path", "")}, config) if _ok(google_sheets) else google_sheets
    record("productivity", "google_calendar_operation_prepare", _ok(google_calendar) and google_calendar.output.get("live_execution_status") == "not_executed", _tool_payload(google_calendar))
    record("productivity", "google_drive_operation_prepare", _ok(google_drive) and google_drive.output.get("approval_required") is True, _tool_payload(google_drive))
    record("productivity", "google_docs_operation_prepare", _ok(google_docs) and google_docs.output.get("provider") == "google_workspace", _tool_payload(google_docs))
    record("productivity", "google_sheets_operation_prepare", _ok(google_sheets) and google_sheets.output.get("method") == "PUT", _tool_payload(google_sheets))
    record("productivity", "google_calendar_operation_inspect", _ok(google_calendar_inspect) and google_calendar_inspect.output.get("operation") == "calendar.create_event", _tool_payload(google_calendar_inspect))
    record("productivity", "google_sheets_operation_inspect", _ok(google_sheets_inspect) and google_sheets_inspect.output.get("operation") == "sheets.update_values", _tool_payload(google_sheets_inspect))


def _smoke_pdf(record, tools: dict[str, Any], config: AgentConfig) -> None:
    ocr = tools["ocr_provider_status"].execute({}, config)
    record("pdf", "ocr_provider_status", _ok(ocr) and ocr.output.get("cloud_ocr_used") is False, _tool_payload(ocr))
    if not _pdf_dependencies_available():
        record("pdf", "pdf_dependencies_available", True, {"status": "skipped_optional_dependency_missing", "missing": ["pypdf", "reportlab"], "reason": "Native PDF merge/extract smoke needs the pdf optional dependency group."})
        return
    fixtures = config.data_dir / "script-fixtures"
    first = fixtures / "pdf-first.pdf"
    second = fixtures / "pdf-second.pdf"
    _write_pdf_fixture(first, "First PDF skill smoke page.")
    _write_pdf_fixture(second, "Second PDF skill smoke page.")
    merged = tools["pdf_merge"].execute(
        {
            "paths": [str(first), str(second)],
            "filename": "skill-smoke-merged.pdf",
            "reason": "Verify native PDF merge capability.",
        },
        config,
    )
    extracted = tools["pdf_extract_pages"].execute(
        {
            "path": merged.output.get("path", ""),
            "start_page": 2,
            "end_page": 2,
            "filename": "skill-smoke-extracted.pdf",
            "reason": "Verify native PDF page extraction capability.",
        },
        config,
    ) if _ok(merged) else merged
    read = tools["read_pdf"].execute({"path": extracted.output.get("path", ""), "max_pages": 1}, config) if _ok(extracted) else extracted
    record("pdf", "pdf_merge", _ok(merged) and merged.output.get("input_count") == 2, _tool_payload(merged))
    record("pdf", "pdf_extract_pages", _ok(extracted) and extracted.output.get("page_count") == 1, _tool_payload(extracted))
    record("pdf", "read_extracted_pdf", _ok(read) and "Second PDF skill smoke page" in read.output.get("text", ""), _tool_payload(read))


def _smoke_office(record, tools: dict[str, Any], config: AgentConfig) -> None:
    presentation_plan = tools["presentation_plan_create"].execute(
        {
            "filename": "skill-smoke-presentation-plan.md",
            "title": "Humungousaur Skill Smoke Review",
            "audience": "Product owner",
            "goal": "Show that native presentation planning is wired to the agent.",
            "desired_action": "Approve the next skill capability slice.",
            "status": "ready_for_review",
            "narrative_arc": ["What changed", "Why it matters", "Verification"],
            "slide_plan": [
                {
                    "title": "Native Planning",
                    "purpose": "Show the planning capability.",
                    "key_points": ["Presentation design produces an inspectable plan before PPTX generation."],
                    "visual": "simple capability flow",
                    "speaker_notes": "Keep the focus on evidence and task progress.",
                    "evidence_refs": ["scripts/smoke_skills.py"],
                },
                {
                    "title": "Verification",
                    "purpose": "Show coverage.",
                    "key_points": ["Focused tests and full skill smoke cover the plan."],
                    "visual": "status checklist",
                    "speaker_notes": "Mention that the deck is not automatically published.",
                    "evidence_refs": ["tests/test_office_tools.py"],
                },
            ],
            "design_notes": ["Use one key message per slide.", "Keep executive slides scan-friendly."],
            "evidence_refs": ["scripts/smoke_skills.py synthetic fixture"],
            "risks": ["Synthetic content must be replaced before a real deck."],
            "reason": "Verify native presentation design planning capability.",
        },
        config,
    )
    presentation_plan_inspect = tools["presentation_plan_inspect"].execute({"path": presentation_plan.output.get("path", "")}, config) if _ok(presentation_plan) else presentation_plan
    record("office", "presentation_plan_create", _ok(presentation_plan) and presentation_plan.output.get("slide_count") == 2, _tool_payload(presentation_plan))
    record("office", "presentation_plan_inspect", _ok(presentation_plan_inspect) and presentation_plan_inspect.output.get("risk_count") == 1, _tool_payload(presentation_plan_inspect))

    docx = tools["docx_document_create"].execute(
        {
            "filename": "skill-smoke.docx",
            "title": "Humungousaur DOCX Skill Smoke",
            "reason": "Verify DOCX creation skill capability.",
            "sections": [
                {
                    "heading": "Summary",
                    "paragraphs": ["This DOCX was created by a native Humungousaur office tool."],
                    "bullets": ["Native artifact", "Inspectable text"],
                    "tables": [{"rows": [["Capability", "Status"], ["DOCX", "Created"]]}],
                }
            ],
        },
        config,
    )
    docx_inspect = tools["docx_document_inspect"].execute({"path": docx.output.get("path", ""), "sample_paragraphs": 10}, config) if _ok(docx) else docx
    record("office", "docx_document_create", _ok(docx), _tool_payload(docx))
    record(
        "office",
        "docx_document_inspect",
        _ok(docx_inspect) and "Humungousaur DOCX Skill Smoke" in docx_inspect.output.get("text_preview", ""),
        _tool_payload(docx_inspect),
    )

    pptx = tools["pptx_deck_create"].execute(
        {
            "filename": "skill-smoke.pptx",
            "title": "Humungousaur PPTX Skill Smoke",
            "reason": "Verify PPTX creation skill capability.",
            "slides": [
                {"title": "Capability", "bullets": ["Native PPTX artifact", "Inspectable slide text"]},
                {"title": "Verification", "bullets": ["File exists", "Slide count matches"]},
            ],
        },
        config,
    )
    pptx_inspect = tools["pptx_deck_inspect"].execute({"path": pptx.output.get("path", ""), "sample_slides": 5}, config) if _ok(pptx) else pptx
    record("office", "pptx_deck_create", _ok(pptx), _tool_payload(pptx))
    record(
        "office",
        "pptx_deck_inspect",
        _ok(pptx_inspect) and pptx_inspect.output.get("slide_count", 0) >= 3,
        _tool_payload(pptx_inspect),
    )


def _smoke_analysis(record, tools: dict[str, Any], config: AgentConfig) -> None:
    fixture = config.data_dir / "script-fixtures" / "sales.csv"
    profile = tools["csv_dataset_profile"].execute({"path": str(fixture), "sample_rows": 5}, config)
    chart = tools["chart_artifact_create"].execute(
        {
            "filename": "skill-smoke-sales.svg",
            "title": "Skill Smoke Revenue",
            "chart_type": "bar",
            "x_label": "Month",
            "y_label": "Revenue",
            "data": [{"label": "Jan", "value": 100}, {"label": "Feb", "value": 125}, {"label": "Mar", "value": 150}],
            "source_note": "Source: sales.csv fixture",
            "reason": "Verify native chart artifact creation.",
        },
        config,
    )
    chart_inspect = tools["chart_artifact_inspect"].execute({"path": chart.output.get("path", "")}, config) if _ok(chart) else chart
    report = tools["business_report_create"].execute(
        {
            "filename": "skill-smoke-sales-report.md",
            "title": "Skill Smoke Sales Report",
            "audience": "Smoke test",
            "period": "Q1",
            "summary": "Revenue rises across the three-row smoke fixture.",
            "metrics": [{"name": "Rows", "value": profile.output.get("row_count", 0), "note": "Profiled CSV rows"}],
            "findings": ["March has the highest revenue."],
            "recommendations": ["Review missing cost values before final reporting."],
            "artifact_paths": [chart.output.get("path", "")],
            "assumptions": ["Fixture data is synthetic."],
            "reason": "Verify native business report creation.",
        },
        config,
    )
    record("analysis", "csv_dataset_profile", _ok(profile) and profile.output.get("row_count") == 3, _tool_payload(profile))
    record("analysis", "chart_artifact_create", _ok(chart), _tool_payload(chart))
    record("analysis", "chart_artifact_inspect", _ok(chart_inspect) and chart_inspect.output.get("point_count") == 3, _tool_payload(chart_inspect))
    record("analysis", "business_report_create", _ok(report), _tool_payload(report))


def _smoke_writing(record, tools: dict[str, Any], config: AgentConfig) -> None:
    draft = tools["writing_draft_create"].execute(
        {
            "filename": "skill-smoke-status.md",
            "draft_type": "status_update",
            "title": "Skill Smoke Status Update",
            "audience": "Product team",
            "tone": "clear and concise",
            "body": "Done: native writing draft artifacts are covered by smoke tests.\nNext: continue one-by-one skill capability hardening.",
            "variants": [{"label": "short", "body": "Writing draft artifacts are now smoke-tested."}],
            "must_keep_facts": ["The draft is not sent."],
            "source_refs": ["scripts/smoke_skills.py"],
            "approval_required": True,
            "reason": "Verify writing draft creation.",
        },
        config,
    )
    inspected = tools["writing_draft_inspect"].execute({"path": draft.output.get("path", "")}, config) if _ok(draft) else draft
    followup = tools["meeting_followup_packet_create"].execute(
        {
            "filename": "skill-smoke-followup.md",
            "meeting_title": "Skill Smoke Planning",
            "summary": "The assistant should keep hardening skills with native tools and smoke tests.",
            "action_items": [{"task": "Run expanded skill smoke", "owner": "Humungousaur", "due": "current run", "evidence": "goal continuation"}],
            "draft_messages": [{"channel_id": "slack", "conversation_id": "D-SMOKE", "text": "Skill smoke is ready for review after approval."}],
            "reminders": [{"title": "Review next skill cluster", "scheduled_for": "2026-06-08T09:00:00Z", "reason": "Continue hardening"}],
            "open_questions": ["Which skill family should be made native next?"],
            "source_refs": ["active thread goal"],
            "reason": "Verify meeting follow-up packet creation.",
        },
        config,
    )
    record("writing", "writing_draft_create", _ok(draft) and draft.output.get("send_status") == "not_sent", _tool_payload(draft))
    record("writing", "writing_draft_inspect", _ok(inspected) and inspected.output.get("variant_count") == 1, _tool_payload(inspected))
    record("writing", "meeting_followup_packet_create", _ok(followup) and followup.output.get("send_status") == "not_sent", _tool_payload(followup))


def _smoke_creative(record, tools: dict[str, Any], config: AgentConfig) -> None:
    brief = tools["creative_brief_create"].execute(
        {
            "filename": "skill-smoke-creative-brief.md",
            "title": "Skill Smoke Rain Station Scene",
            "creative_type": "scene",
            "genre": "quiet speculative fiction",
            "theme": "repair over escape",
            "audience": "adult readers",
            "mood": "tender and tense",
            "constraints": ["Original scene, no living-author imitation."],
            "forbidden_elements": ["copyrighted characters", "quoted lyrics"],
            "beats": [{"label": "Arrival", "purpose": "Set place and conflict", "notes": "Rain reveals the broken station sign."}],
            "motifs": ["warm light", "delayed train"],
            "voice_notes": ["specific sensory details", "plainspoken emotional turn"],
            "source_refs": ["scripts/smoke_skills.py synthetic fixture"],
            "reason": "Verify native creative brief artifact support.",
        },
        config,
    )
    brief_inspect = tools["creative_brief_inspect"].execute({"path": brief.output.get("path", "")}, config) if _ok(brief) else brief
    song = tools["song_structure_create"].execute(
        {
            "filename": "skill-smoke-song-structure.md",
            "title": "Window Light",
            "genre": "indie pop",
            "mood": "hopeful",
            "tempo_bpm": 104,
            "hook_concept": "A small light becoming a signal.",
            "sections": [
                {"name": "Verse 1", "role": "setup", "length": "8 bars", "notes": "Original concrete image."},
                {"name": "Chorus", "role": "hook", "length": "8 bars", "notes": "Lift in contour, no borrowed melody."},
            ],
            "rhyme_notes": ["Favor loose internal rhyme, no quoted lyric references."],
            "production_notes": ["Clean drums, soft synth bass."],
            "originality_constraints": ["No copyrighted lyric reproduction.", "No living-artist voice imitation."],
            "reason": "Verify native songwriting structure artifact support.",
        },
        config,
    )
    song_inspect = tools["song_structure_inspect"].execute({"path": song.output.get("path", "")}, config) if _ok(song) else song
    revision = tools["creative_revision_packet_create"].execute(
        {
            "filename": "skill-smoke-creative-revision.md",
            "title": "Skill Smoke Scene Revision",
            "source_draft": "The train arrived late, and Mira watched the station lights blink awake.",
            "revision_goals": ["Make the image more specific.", "Preserve the quiet tone."],
            "protected_elements": ["Mira", "late train"],
            "change_notes": ["Keep it compact."],
            "variants": [{"label": "sensory", "body": "The late train sighed in, and Mira counted each amber station light as it woke."}],
            "reason": "Verify native creative revision packet support.",
        },
        config,
    )
    revision_inspect = tools["creative_revision_packet_inspect"].execute({"path": revision.output.get("path", "")}, config) if _ok(revision) else revision
    record("creative", "creative_brief_create", _ok(brief) and brief.output.get("beat_count") == 1, _tool_payload(brief))
    record("creative", "creative_brief_inspect", _ok(brief_inspect) and brief_inspect.output.get("forbidden_element_count") == 2, _tool_payload(brief_inspect))
    record("creative", "song_structure_create", _ok(song) and song.output.get("section_count") == 2, _tool_payload(song))
    record("creative", "song_structure_inspect", _ok(song_inspect) and song_inspect.output.get("originality_constraint_count") == 2, _tool_payload(song_inspect))
    record("creative", "creative_revision_packet_create", _ok(revision) and revision.output.get("variant_count") == 1, _tool_payload(revision))
    record("creative", "creative_revision_packet_inspect", _ok(revision_inspect) and revision_inspect.output.get("protected_element_count") == 2, _tool_payload(revision_inspect))


def _smoke_content(record, tools: dict[str, Any], config: AgentConfig) -> None:
    transcript_path = config.data_dir / "script-fixtures" / "skill-smoke-transcript.txt"
    transcript_path.write_text(
        "\n".join(
            [
                "00:00 Host: Today we test native transcript summary artifacts.",
                "00:31 Lead: Decision is to wire YouTube, audio, and meeting skills to content tools.",
                "01:04 Lead: Action item is to run focused and full smoke tests.",
            ]
        ),
        encoding="utf-8",
    )
    summary = tools["transcript_summary_create"].execute(
        {
            "filename": "skill-smoke-transcript-summary.md",
            "title": "Skill Smoke Transcript Summary",
            "source_type": "meeting",
            "transcript_path": str(transcript_path),
            "transcript_provider": "provided-fixture",
            "language": "en",
            "summary": "The fixture records a decision to wire spoken-media skills to native content tools and a follow-up to run verification.",
            "key_points": ["Transcript summaries preserve source metadata and timestamp evidence."],
            "decisions": ["Wire YouTube, audio, and meeting skills to content tools."],
            "action_items": [{"task": "Run focused and full smoke tests", "owner": "Humungousaur", "evidence": "01:04"}],
            "open_questions": ["Which spoken-media provider should be expanded next?"],
            "limitations": ["Synthetic transcript fixture."],
            "output_format": "meeting notes",
            "reason": "Verify native transcript/audio/video summary skill capability.",
        },
        config,
    )
    inspected = tools["transcript_summary_inspect"].execute({"path": summary.output.get("path", "")}, config) if _ok(summary) else summary
    record("content", "transcript_summary_create", _ok(summary) and summary.output.get("segment_count") == 3, _tool_payload(summary))
    record(
        "content",
        "transcript_summary_inspect",
        _ok(inspected) and inspected.output.get("action_item_count") == 1 and inspected.output.get("source_type") == "meeting",
        _tool_payload(inspected),
    )


def _smoke_research(record, tools: dict[str, Any], config: AgentConfig) -> None:
    bibliography = tools["citation_bibliography_create"].execute(
        {
            "filename": "skill-smoke-bibliography.md",
            "title": "Skill Smoke Bibliography",
            "target_style": "mixed",
            "entries": [
                {
                    "type": "article",
                    "title": "Attention Is All You Need",
                    "authors": ["Vaswani, Ashish", "Shazeer, Noam"],
                    "year": "2017",
                    "venue": "NeurIPS",
                    "url": "https://example.com/attention",
                    "source_refs": ["synthetic smoke metadata"],
                    "verified_fields": ["title", "authors", "year", "venue"],
                    "uncertain_fields": ["url"],
                }
            ],
            "global_source_refs": ["scripts/smoke_skills.py"],
            "reason": "Verify native citation cleanup and bibliography artifact creation.",
        },
        config,
    )
    bibliography_inspect = tools["citation_bibliography_inspect"].execute({"path": bibliography.output.get("path", "")}, config) if _ok(bibliography) else bibliography
    literature = tools["literature_set_create"].execute(
        {
            "filename": "skill-smoke-literature-set.md",
            "title": "Skill Smoke Literature Set",
            "research_question": "How should Humungousaur preserve research evidence?",
            "inclusion_criteria": ["Metadata has source references."],
            "papers": [
                {
                    "paper_id": "p1",
                    "title": "Tool Use Smoke Paper",
                    "authors": ["Example, Ada"],
                    "year": "2026",
                    "venue": "Local Smoke",
                    "relevance": "Exercises literature-set artifacts without live web search.",
                    "evidence_level": "metadata",
                    "themes": ["tool use"],
                    "source_refs": ["synthetic smoke metadata"],
                }
            ],
            "themes": [{"name": "Tool use", "summary": "Structured evidence is kept inspectable.", "paper_ids": ["p1"]}],
            "gaps": ["Run live scholarly adapters when added."],
            "limitations": ["Synthetic smoke metadata."],
            "source_refs": ["scripts/smoke_skills.py"],
            "reason": "Verify native research paper search/writing artifact support.",
        },
        config,
    )
    literature_inspect = tools["literature_set_inspect"].execute({"path": literature.output.get("path", "")}, config) if _ok(literature) else literature
    record("research", "citation_bibliography_create", _ok(bibliography) and bibliography.output.get("entry_count") == 1, _tool_payload(bibliography))
    record("research", "citation_bibliography_inspect", _ok(bibliography_inspect) and bibliography_inspect.output.get("uncertain_entry_count") == 1, _tool_payload(bibliography_inspect))
    record("research", "literature_set_create", _ok(literature) and literature.output.get("paper_count") == 1, _tool_payload(literature))
    record("research", "literature_set_inspect", _ok(literature_inspect) and literature_inspect.output.get("theme_count") == 1, _tool_payload(literature_inspect))


def _smoke_media(record, tools: dict[str, Any], config: AgentConfig) -> None:
    sound = tools["sound_spec_create"].execute(
        {
            "filename": "skill-smoke-sound.md",
            "title": "Skill Smoke Sound Spec",
            "sound_type": "sound_effect",
            "intended_use": "Agent UI completion chime",
            "duration_seconds": 1.5,
            "mood": "calm and satisfying",
            "instrumentation": ["soft bell", "low warm pad"],
            "sections": [{"name": "Chime", "start": "00:00", "duration": "1.5s", "notes": "Single gentle resolve."}],
            "sound_design_notes": ["No harsh transient.", "Keep suitable for repeated daily use."],
            "licensing_constraints": ["No living-artist or copyrighted motif imitation."],
            "prompt": "A short calm completion chime with a soft bell and warm pad, suitable for productivity software.",
            "reason": "Verify native music/sound specification artifact support.",
        },
        config,
    )
    sound_inspect = tools["sound_spec_inspect"].execute({"path": sound.output.get("path", "")}, config) if _ok(sound) else sound
    storyboard = tools["media_storyboard_create"].execute(
        {
            "filename": "skill-smoke-storyboard.md",
            "title": "Skill Smoke Slack GIF Storyboard",
            "media_type": "gif",
            "audience": "Product team",
            "intended_use": "Approval-safe Slack celebration draft",
            "duration_seconds": 2.4,
            "width": 480,
            "height": 270,
            "style": "clean geometric confetti",
            "palette": ["#1d3557", "#f1faee", "#e63946"],
            "scenes": [
                {"label": "Ready", "description": "A simple checkmark enters over a clean background.", "duration_seconds": 0.8, "motion": "fade and scale"},
                {"label": "Celebrate", "description": "Confetti blocks arc outward around the checkmark.", "duration_seconds": 1.6, "motion": "radial burst", "text": "Shipped"},
            ],
            "accessibility_notes": ["No flashing or rapid high-contrast flicker."],
            "licensing_constraints": ["No copyrighted characters or memes."],
            "reason": "Verify native GIF/video/image storyboard artifact support.",
        },
        config,
    )
    storyboard_inspect = tools["media_storyboard_inspect"].execute({"path": storyboard.output.get("path", "")}, config) if _ok(storyboard) else storyboard
    record("media", "sound_spec_create", _ok(sound) and sound.output.get("artifact_status") == "prepared_not_generated", _tool_payload(sound))
    record("media", "sound_spec_inspect", _ok(sound_inspect) and sound_inspect.output.get("section_count") == 1, _tool_payload(sound_inspect))
    record("media", "media_storyboard_create", _ok(storyboard) and storyboard.output.get("scene_count") == 2, _tool_payload(storyboard))
    record("media", "media_storyboard_inspect", _ok(storyboard_inspect) and storyboard_inspect.output.get("media_type") == "gif", _tool_payload(storyboard_inspect))


def _smoke_travel(record, tools: dict[str, Any], config: AgentConfig) -> None:
    plan = tools["travel_plan_create"].execute(
        {
            "filename": "skill-smoke-travel-plan.md",
            "title": "Skill Smoke Museum Commute",
            "origin": "Hotel district",
            "destination": "Museum district",
            "date_range": "2026-06-13",
            "travelers": "1 adult",
            "budget": "Prefer low-cost transit.",
            "preferences": ["low walking", "clear fallback option"],
            "constraints": ["Live schedules and opening hours must be verified before travel."],
            "places": [{"name": "City Museum", "kind": "museum", "location": "Museum district", "hours": "10:00-17:00", "cost": "ticketed", "notes": "Synthetic smoke venue.", "source_ref": "fixture"}],
            "route_options": [{"label": "Metro route", "mode": "transit", "estimated_duration": "35 min", "estimated_cost": "$3", "reliability": "medium", "accessibility": "elevator status needs live check", "tradeoffs": "Lowest cost, schedule-sensitive.", "source_ref": "fixture"}],
            "itinerary_days": [{"label": "Saturday", "summary": "Transit-first museum visit.", "items": [{"time": "09:30", "activity": "Depart hotel", "location": "Hotel district", "notes": "Verify route before leaving."}]}],
            "source_refs": ["scripts/smoke_skills.py synthetic fixture"],
            "uncertainties": ["No live transit or venue API was queried in smoke."],
            "reason": "Verify native travel-and-maps artifact support without booking.",
        },
        config,
    )
    inspected = tools["travel_plan_inspect"].execute({"path": plan.output.get("path", "")}, config) if _ok(plan) else plan
    record("travel", "travel_plan_create", _ok(plan) and plan.output.get("approval_status") == "planning_only_not_booked", _tool_payload(plan))
    record("travel", "travel_plan_inspect", _ok(inspected) and inspected.output.get("route_option_count") == 1, _tool_payload(inspected))


def _smoke_commerce(record, tools: dict[str, Any], config: AgentConfig) -> None:
    comparison = tools["shopping_comparison_create"].execute(
        {
            "filename": "skill-smoke-shopping-comparison.md",
            "title": "Skill Smoke Headphones Comparison",
            "budget": "$150",
            "region": "US",
            "decision_criteria": ["comfortable", "clear returns", "USB-C"],
            "products": [
                {
                    "name": "Headphones A",
                    "seller": "Example Store",
                    "price": "$129",
                    "availability": "fixture only",
                    "shipping": "standard",
                    "return_terms": "30 days",
                    "pros": ["comfortable", "USB-C"],
                    "cons": ["live stock not checked"],
                    "source_ref": "synthetic smoke fixture",
                }
            ],
            "recommendation": "Headphones A fits the fixture criteria but live price and stock still need verification.",
            "risks": ["Synthetic smoke data only.", "No live seller verification."],
            "source_refs": ["scripts/smoke_skills.py synthetic fixture"],
            "reason": "Verify native shopping comparison artifact support.",
        },
        config,
    )
    comparison_inspect = tools["shopping_comparison_inspect"].execute({"path": comparison.output.get("path", "")}, config) if _ok(comparison) else comparison
    purchase = tools["purchase_intent_prepare"].execute(
        {
            "filename": "skill-smoke-cart-review.md",
            "intent_type": "cart_review",
            "seller": "Example Store",
            "items": [{"name": "Headphones A", "quantity": "1", "price": "$129", "seller": "Example Store", "source_ref": "synthetic smoke fixture"}],
            "total": "$129 before taxes/shipping",
            "return_terms": "30 days",
            "checks": [{"name": "Final total verified", "status": "not_verified", "evidence": "smoke fixture only"}],
            "reason": "Verify native purchase/payment review artifact support without checkout.",
        },
        config,
    )
    purchase_inspect = tools["purchase_intent_inspect"].execute({"path": purchase.output.get("path", "")}, config) if _ok(purchase) else purchase
    record("commerce", "shopping_comparison_create", _ok(comparison) and comparison.output.get("purchase_status") == "research_only_not_purchased", _tool_payload(comparison))
    record("commerce", "shopping_comparison_inspect", _ok(comparison_inspect) and comparison_inspect.output.get("product_count") == 1, _tool_payload(comparison_inspect))
    record("commerce", "purchase_intent_prepare", _ok(purchase) and purchase.output.get("purchase_status") == "prepared_not_purchased", _tool_payload(purchase))
    record("commerce", "purchase_intent_inspect", _ok(purchase_inspect) and purchase_inspect.output.get("approval_required") is True, _tool_payload(purchase_inspect))


def _smoke_personal(record, tools: dict[str, Any], config: AgentConfig) -> None:
    contact = tools["contact_note_create"].execute(
        {
            "filename": "skill-smoke-contact.md",
            "person_name": "Ada Example",
            "role": "Product collaborator",
            "organization": "Example Labs",
            "preferred_channel": "email",
            "facts": [{"fact": "Prefers concise technical summaries.", "evidence": "synthetic smoke fixture", "confidence": "high"}],
            "preferences": [{"preference": "Likes agendas before calls.", "evidence": "synthetic smoke fixture"}],
            "followups": [{"title": "Send agenda draft", "due": "tomorrow", "reason": "Prepare for call", "evidence": "synthetic smoke fixture"}],
            "sensitivity": "medium",
            "source_refs": ["scripts/smoke_skills.py synthetic fixture"],
            "reason": "Verify native contact and relationship note artifact support.",
        },
        config,
    )
    contact_inspect = tools["contact_note_inspect"].execute({"path": contact.output.get("path", "")}, config) if _ok(contact) else contact
    plan = tools["daily_plan_create"].execute(
        {
            "filename": "skill-smoke-daily-plan.md",
            "title": "Skill Smoke Daily Plan",
            "date": "2026-06-07",
            "time_window": "afternoon",
            "energy": "medium",
            "evidence_refs": ["active goal continuation", "skill smoke fixture"],
            "must_do": [{"title": "Run skill smoke", "priority": "high", "evidence": "active goal", "reason": "Verify skill capability coverage"}],
            "time_blocks": [{"time": "14:00", "focus": "Implement next skill slice", "notes": "Keep edits scoped and tested."}],
            "waiting": ["User selection for future slice is optional."],
            "deferred": ["Live external action testing remains approval-gated."],
            "reminder_drafts": [{"title": "Review next skill family", "when": "next continuation", "reason": "Continue one-by-one hardening"}],
            "risks": ["Do not claim completion of the full broad goal from one slice."],
            "summary": "One focused implementation block plus explicit reminder draft, without creating wakeups automatically.",
            "reason": "Verify native daily planning artifact support.",
        },
        config,
    )
    plan_inspect = tools["daily_plan_inspect"].execute({"path": plan.output.get("path", "")}, config) if _ok(plan) else plan
    record("personal", "contact_note_create", _ok(contact) and contact.output.get("memory_status") == "prepared_not_memorized", _tool_payload(contact))
    record("personal", "contact_note_inspect", _ok(contact_inspect) and contact_inspect.output.get("followup_count") == 1, _tool_payload(contact_inspect))
    record("personal", "daily_plan_create", _ok(plan) and plan.output.get("plan_status") == "prepared_not_scheduled", _tool_payload(plan))
    record("personal", "daily_plan_inspect", _ok(plan_inspect) and plan_inspect.output.get("reminder_draft_count") == 1, _tool_payload(plan_inspect))


def _smoke_design(record, tools: dict[str, Any], config: AgentConfig) -> None:
    brand = tools["brand_guidelines_create"].execute(
        {
            "filename": "skill-smoke-brand.md",
            "brand_name": "Humungousaur",
            "status": "proposed",
            "colors": [
                {"name": "ink", "value": "#111827", "usage": "primary text", "accessibility": "Use on light surfaces."},
                {"name": "surface", "value": "#f8fafc", "usage": "background", "accessibility": "Pair with ink."},
            ],
            "typography": [{"role": "body", "family": "Segoe UI", "size": "14px", "weight": "400", "notes": "Readable default."}],
            "tone": ["calm", "direct", "evidence-led"],
            "layout_rules": ["Use compact panels for operational interfaces."],
            "accessibility_notes": ["Check contrast before applying to UI."],
            "source_refs": ["scripts/smoke_skills.py synthetic fixture"],
            "reason": "Verify native brand-guideline artifact support.",
        },
        config,
    )
    brand_inspect = tools["brand_guidelines_inspect"].execute({"path": brand.output.get("path", "")}, config) if _ok(brand) else brand
    theme = tools["theme_pack_create"].execute(
        {
            "filename": "skill-smoke-theme.md",
            "theme_name": "Skill Smoke Clear Work",
            "mode": "light",
            "palette": [{"name": "surface", "value": "#f8fafc", "usage": "page background"}, {"name": "ink", "value": "#111827", "usage": "text"}],
            "tokens": {"radius-card": "8px", "space-panel": "16px"},
            "typography": {"body": "Segoe UI 14px"},
            "spacing": {"panel": "16px"},
            "radii": {"card": "8px"},
            "component_states": [{"component": "button", "state": "hover", "token": "color-ink", "notes": "Preserve contrast."}],
            "contrast_checks": [{"foreground": "#111827", "background": "#f8fafc", "ratio": "15:1", "status": "pass"}],
            "source_refs": ["scripts/smoke_skills.py synthetic fixture"],
            "reason": "Verify native theme-pack artifact support.",
        },
        config,
    )
    theme_inspect = tools["theme_pack_inspect"].execute({"path": theme.output.get("path", "")}, config) if _ok(theme) else theme
    record("design", "brand_guidelines_create", _ok(brand) and brand.output.get("status") == "proposed", _tool_payload(brand))
    record("design", "brand_guidelines_inspect", _ok(brand_inspect) and brand_inspect.output.get("color_count") == 2, _tool_payload(brand_inspect))
    record("design", "theme_pack_create", _ok(theme) and theme.output.get("token_count", 0) >= 2, _tool_payload(theme))
    record("design", "theme_pack_inspect", _ok(theme_inspect) and theme_inspect.output.get("contrast_check_count") == 1, _tool_payload(theme_inspect))


def _smoke_visuals(record, tools: dict[str, Any], config: AgentConfig) -> None:
    diagram = tools["diagram_artifact_create"].execute(
        {
            "filename": "skill-smoke-agent-flow.md",
            "title": "Skill Smoke Agent Flow",
            "diagram_type": "component",
            "status": "current",
            "nodes": [
                {"id": "stimulus", "label": "Stimulus", "kind": "input", "notes": "User or channel event."},
                {"id": "agent", "label": "Agent", "kind": "reasoning", "notes": "Plans and selects tools."},
                {"id": "tool", "label": "Tool", "kind": "capability", "notes": "Executes native action."},
            ],
            "edges": [
                {"from": "stimulus", "to": "agent", "label": "activates", "evidence": "skill smoke fixture"},
                {"from": "agent", "to": "tool", "label": "calls", "evidence": "tool registry"},
            ],
            "evidence_refs": ["scripts/smoke_skills.py synthetic fixture"],
            "unknowns": ["No live UI render in this smoke."],
            "reason": "Verify native architecture diagram artifact support.",
        },
        config,
    )
    diagram_inspect = tools["diagram_artifact_inspect"].execute({"path": diagram.output.get("path", "")}, config) if _ok(diagram) else diagram
    excalidraw = tools["excalidraw_diagram_create"].execute(
        {
            "filename": "skill-smoke-agent-flow.excalidraw",
            "title": "Skill Smoke Agent Flow Sketch",
            "status": "draft",
            "nodes": [
                {"id": "stimulus", "label": "Stimulus", "x": 60, "y": 80},
                {"id": "agent", "label": "Agent", "x": 340, "y": 80},
                {"id": "tool", "label": "Tool", "x": 620, "y": 80},
            ],
            "edges": [{"from": "stimulus", "to": "agent", "label": "activates"}, {"from": "agent", "to": "tool", "label": "calls"}],
            "evidence_refs": ["scripts/smoke_skills.py synthetic fixture"],
            "reason": "Verify native Excalidraw-compatible JSON generation.",
        },
        config,
    )
    infographic = tools["infographic_plan_create"].execute(
        {
            "filename": "skill-smoke-infographic.md",
            "title": "Skill Smoke Capability Snapshot",
            "audience": "Product owner",
            "key_message": "Native tools can produce source-backed visual planning artifacts.",
            "status": "ready_for_review",
            "metrics": [{"label": "Visual tools", "value": "5", "unit": "tools", "source": "default_tools registry", "notes": "Synthetic smoke count."}],
            "sections": [{"title": "Flow", "body": "Show stimulus, agent reasoning, and native tool execution."}],
            "visual_marks": ["large count", "simple flow", "source note"],
            "accessibility_notes": ["Do not rely on color alone for state."],
            "source_refs": ["scripts/smoke_skills.py synthetic fixture"],
            "reason": "Verify native infographic planning support.",
        },
        config,
    )
    infographic_inspect = tools["infographic_plan_inspect"].execute({"path": infographic.output.get("path", "")}, config) if _ok(infographic) else infographic
    record("visuals", "diagram_artifact_create", _ok(diagram) and diagram.output.get("node_count") == 3, _tool_payload(diagram))
    record("visuals", "diagram_artifact_inspect", _ok(diagram_inspect) and diagram_inspect.output.get("edge_count") == 2, _tool_payload(diagram_inspect))
    record("visuals", "excalidraw_diagram_create", _ok(excalidraw) and excalidraw.output.get("element_count", 0) >= 7, _tool_payload(excalidraw))
    record("visuals", "infographic_plan_create", _ok(infographic) and infographic.output.get("metric_count") == 1, _tool_payload(infographic))
    record("visuals", "infographic_plan_inspect", _ok(infographic_inspect) and infographic_inspect.output.get("accessibility_note_count") == 1, _tool_payload(infographic_inspect))


class _SkillSmokeHttpHandler(BaseHTTPRequestHandler):
    def do_HEAD(self) -> None:
        self.send_response(204)
        self.send_header("X-Humungousaur-Smoke", "network")
        self.end_headers()

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Humungousaur skill smoke network endpoint")

    def log_message(self, format: str, *args: Any) -> None:
        return


def _smoke_network(record, tools: dict[str, Any], config: AgentConfig) -> None:
    dns = tools["dns_lookup"].execute({"hostname": "localhost", "record_types": ["A", "AAAA"], "reason": "Verify native DNS diagnostic skill capability."}, config)
    record("network", "dns_lookup", _ok(dns) and dns.output.get("resolved") is True, _tool_payload(dns))

    server = HTTPServer(("127.0.0.1", 0), _SkillSmokeHttpHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = int(server.server_address[1])
        http = tools["http_endpoint_check"].execute(
            {"url": f"http://127.0.0.1:{port}/health", "method": "GET", "timeout_seconds": 2, "reason": "Verify native HTTP endpoint diagnostic skill capability."},
            config,
        )
        tcp = tools["tcp_connectivity_probe"].execute({"host": "127.0.0.1", "port": port, "timeout_seconds": 2, "reason": "Verify native TCP diagnostic skill capability."}, config)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    closed_tcp = tools["tcp_connectivity_probe"].execute({"host": "127.0.0.1", "port": port, "timeout_seconds": 0.2, "reason": "Verify closed TCP diagnostic skill capability."}, config)
    record("network", "http_endpoint_check", _ok(http) and http.output.get("status_code") == 200, _tool_payload(http))
    record("network", "tcp_connectivity_probe_open", _ok(tcp) and tcp.output.get("reachable") is True, _tool_payload(tcp))
    record("network", "tcp_connectivity_probe_closed", _ok(closed_tcp) and closed_tcp.output.get("reachable") is False, _tool_payload(closed_tcp))


def _prepare_script_fixtures(config: AgentConfig) -> None:
    fixtures = config.data_dir / "script-fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    (fixtures / "sample.csv").write_text("name,score\nAda,10\nGrace,12\nAlan,\n", encoding="utf-8")
    (fixtures / "sales.csv").write_text("month,revenue,cost\nJan,100,40\nFeb,125,50\nMar,150,\n", encoding="utf-8")
    (fixtures / "note-a.md").write_text("# Note A\n\nLinks to [[Note B]] and [web](https://example.com).\n", encoding="utf-8")
    (fixtures / "note-b.md").write_text("# Note B\n\nBacklink target.\n", encoding="utf-8")


def _pdf_dependencies_available() -> bool:
    return bool(importlib.util.find_spec("pypdf") and importlib.util.find_spec("reportlab"))


def _write_pdf_fixture(path: Path, text: str) -> None:
    from reportlab.pdfgen import canvas

    document = canvas.Canvas(str(path))
    y = 760
    for line in text.splitlines() or [text]:
        document.drawString(72, y, line)
        y -= 18
    document.save()


def _script_smoke_input(name: str, config: AgentConfig) -> dict[str, Any]:
    fixtures = config.data_dir / "script-fixtures"
    if name == "inspect-repo":
        return {"path": ".", "max_files": 500}
    if name == "profile-csv":
        return {"path": str(fixtures / "sample.csv"), "max_rows": 100}
    if name == "build-markdown-index":
        return {"root": str(fixtures), "max_files": 20}
    if name == "redact-text":
        return {"text": "OPENAI_API_KEY=sk-test-secret and token ghp_testsecret", "replacement": "[REDACTED]"}
    if name == "inspect-skill-pack":
        return {"skill_dir": "skills/system-health-check"}
    if name == "check-readiness":
        return {"env_names": ["OPENAI_API_KEY", "GROQ_API_KEY"]}
    return {}


def _smoke_channels(record, tools: dict[str, Any], config: AgentConfig) -> None:
    for channel_id in ("slack", "whatsapp", "telegram", "discord"):
        manifest = tools["channel_manifest"].execute({"channel_id": channel_id}, config)
        doctor = tools["channel_doctor"].execute({"channel_id": channel_id}, config)
        requirements = tools["channel_setup_requirements"].execute({"channel_id": channel_id}, config)
        setup = tools["channel_setup_save"].execute(
            {
                "channel_id": channel_id,
                "enabled": True,
                "conversation_defaults": _channel_defaults(channel_id),
                "secret_refs": _channel_secret_refs(channel_id),
                "allowlist": ["user-smoke"],
                "group_allowlist": ["room-smoke"],
                "notes": f"Skill smoke setup for {channel_id}.",
            },
            config,
        )
        status = tools["channel_setup_status"].execute({"channel_id": channel_id}, config)
        listener = tools["channel_listener_status"].execute({"channel_id": channel_id}, config)
        prepared = tools["channel_message_prepare"].execute(
            {
                "channel_id": channel_id,
                "conversation_id": _channel_defaults(channel_id)["conversation_id"],
                "text": _channel_smoke_text(channel_id),
                "metadata": _channel_prepare_metadata(channel_id),
                "reason": f"Prepare a non-sending {channel_id} channel smoke envelope.",
            },
            config,
        )
        action = tools["channel_action_prepare"].execute(_channel_action_input(channel_id), config)
        webhook = tools["channel_webhook_ingest"].execute(
            {
                "channel_id": channel_id,
                "payload": _channel_webhook_payload(channel_id),
                "prepare_reply": True,
                "reason": f"Normalize and process a representative {channel_id} inbound event.",
            },
            config,
        )
        outbox = tools["channel_outbox"].execute({"limit": 20}, config)
        record("channels", f"{channel_id}_manifest", _ok(manifest), _tool_payload(manifest))
        record("channels", f"{channel_id}_doctor", _ok(doctor), _tool_payload(doctor))
        record("channels", f"{channel_id}_requirements", _ok(requirements), _tool_payload(requirements))
        record("channels", f"{channel_id}_setup_save", _ok(setup), _tool_payload(setup))
        record("channels", f"{channel_id}_setup_status", _ok(status), _tool_payload(status))
        record("channels", f"{channel_id}_listener_status", _ok(listener), _tool_payload(listener))
        record(
            "channels",
            f"{channel_id}_message_prepare",
            _ok(prepared) and prepared.output["message"]["status"] == "prepared_not_sent",
            _tool_payload(prepared),
        )
        record(
            "channels",
            f"{channel_id}_action_prepare",
            _ok(action) and action.output["action"]["status"] == "prepared_not_sent",
            _tool_payload(action),
        )
        record(
            "channels",
            f"{channel_id}_webhook_ingest",
            _ok(webhook) and webhook.output.get("message_count", 0) == 1,
            _tool_payload(webhook),
        )
        record(
            "channels",
            f"{channel_id}_outbox",
            _ok(outbox)
            and any(item.get("channel_id") == channel_id and item.get("item_type") == "message" for item in outbox.output.get("messages", []))
            and any(item.get("channel_id") == channel_id and item.get("item_type") == "action" for item in outbox.output.get("messages", [])),
            _tool_payload(outbox),
        )


def _smoke_rss(record, tools: dict[str, Any], config: AgentConfig) -> None:
    feed_path = config.data_dir / "script-fixtures" / "skill-smoke-feed.xml"
    feed_path.write_text(_rss_smoke_feed(), encoding="utf-8")
    read = tools["rss_feed_read"].execute({"source": str(feed_path), "max_items": 5, "query": "native"}, config)
    watch = tools["rss_watch_prepare"].execute(
        {
            "source": str(feed_path),
            "cadence": "daily",
            "summary_format": "briefing",
            "filters": ["native", "skills"],
            "notification_preference": "prepared note",
            "reason": "Verify RSS/blog monitoring skill watch preparation.",
        },
        config,
    )
    listed = tools["rss_watch_list"].execute({"limit": 5}, config)
    record("rss", "rss_feed_read", _ok(read) and read.output.get("item_count") == 1, _tool_payload(read))
    record("rss", "rss_watch_prepare", _ok(watch) and watch.output["watch"]["status"] == "prepared_not_scheduled", _tool_payload(watch))
    record("rss", "rss_watch_list", _ok(listed) and bool(listed.output.get("watches")), _tool_payload(listed))


def _channel_defaults(channel_id: str) -> dict[str, str]:
    return {
        "slack": {"conversation_id": "D-SMOKE", "conversation_type": "im"},
        "whatsapp": {"conversation_id": "+15555550100", "conversation_type": "private"},
        "telegram": {"conversation_id": "420001", "conversation_type": "private"},
        "discord": {"conversation_id": "990001", "conversation_type": "dm"},
    }.get(channel_id, {"conversation_id": "smoke-room", "conversation_type": "dm"})


def _channel_secret_refs(channel_id: str) -> dict[str, str]:
    return {
        "slack": {"bot_token": "SLACK_BOT_TOKEN", "signing_secret": "SLACK_SIGNING_SECRET"},
        "whatsapp": {"access_token": "WHATSAPP_ACCESS_TOKEN", "phone_number_id": "WHATSAPP_PHONE_NUMBER_ID"},
        "telegram": {"bot_token": "TELEGRAM_BOT_TOKEN"},
        "discord": {"bot_token": "DISCORD_BOT_TOKEN"},
    }.get(channel_id, {})


def _channel_smoke_text(channel_id: str) -> str:
    if channel_id == "telegram":
        return "Skill smoke with image: ![chart](https://example.com/chart.png)"
    return f"Humungousaur {channel_id} channel skill smoke. This was not sent."


def _channel_prepare_metadata(channel_id: str) -> dict[str, Any]:
    if channel_id == "slack":
        return {"thread_ts": "1712023032.1234"}
    if channel_id == "discord":
        return {"thread_id": "990001"}
    return {}


def _channel_action_input(channel_id: str) -> dict[str, Any]:
    defaults = _channel_defaults(channel_id)
    base = {
        "channel_id": channel_id,
        "conversation_id": defaults["conversation_id"],
        "target_message_id": f"{channel_id}-message-smoke",
        "reason": f"Prepare a richer non-sending {channel_id} channel action.",
    }
    if channel_id == "slack":
        return {**base, "action_type": "reaction_add", "metadata": {"emoji": "white_check_mark", "thread_ts": "1712023032.1234"}}
    if channel_id == "telegram":
        return {**base, "action_type": "thread_reply", "text": "Telegram topic/thread reply prepared by smoke.", "metadata": {"topic_id": "42"}}
    if channel_id == "discord":
        return {**base, "action_type": "thread_reply", "text": "Discord thread reply prepared by smoke.", "metadata": {"thread_id": "990001"}}
    if channel_id == "whatsapp":
        return {**base, "action_type": "reaction_add", "metadata": {"emoji": "thumbs_up", "bridge_mode": "prepared"}}
    return {**base, "action_type": "typing_indicator"}


def _channel_webhook_payload(channel_id: str) -> dict[str, Any]:
    suffix = uuid.uuid4().hex[:8]
    if channel_id == "slack":
        return {
            "event_id": f"EvSkillSmoke-{suffix}",
            "event": {
                "type": "message",
                "channel": "D-SMOKE",
                "channel_type": "im",
                "user": "U-SMOKE",
                "text": "Hello from Slack skill smoke.",
                "client_msg_id": f"slack-smoke-{suffix}",
            },
        }
    if channel_id == "telegram":
        return {
            "update_id": int(suffix[:6], 16),
            "message": {
                "message_id": int(suffix[-6:], 16),
                "chat": {"id": "420001", "type": "private"},
                "from": {"id": "7001", "is_bot": False},
                "text": "Hello from Telegram skill smoke.",
            },
        }
    if channel_id == "discord":
        return {
            "id": f"discord-smoke-{suffix}",
            "channel_id": "990001",
            "conversation_type": "dm",
            "author": {"id": "discord-user", "bot": False},
            "content": "Hello from Discord skill smoke.",
            "requires_response": True,
        }
    if channel_id == "whatsapp":
        return {"from": "+15555550100", "id": f"whatsapp-smoke-{suffix}", "text": "Hello from WhatsApp skill smoke."}
    return {"conversation_id": "smoke-room", "sender_id": "user-smoke", "text": f"Hello from {channel_id}."}


def _rss_smoke_feed() -> str:
    return """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Humungousaur Skill Feed</title>
    <link>https://example.com/skills</link>
    <description>Skill smoke updates</description>
    <item>
      <title>Native RSS skill support</title>
      <link>https://example.com/skills/rss</link>
      <description>Native feed parsing and prepared watches are available.</description>
      <pubDate>Sun, 07 Jun 2026 09:00:00 GMT</pubDate>
      <guid>native-rss</guid>
    </item>
    <item>
      <title>Other update</title>
      <link>https://example.com/skills/other</link>
      <description>General smoke item.</description>
      <pubDate>Sat, 06 Jun 2026 09:00:00 GMT</pubDate>
      <guid>other</guid>
    </item>
  </channel>
</rss>
"""


def _smoke_core_surfaces(record, tools: dict[str, Any], config: AgentConfig) -> None:
    scenarios = [
        ("files", "write_note", {"title": "skill smoke note", "content": "Skill smoke note."}),
        ("memory", "memory_write", {"text": "Skill smoke memory.", "kind": "observation", "source": "skill_smoke"}),
        ("system", "system_status", {}),
        ("voice", "voice_provider_status", {}),
        ("browser", "web_search", {"query": "Humungousaur local assistant", "limit": 1}),
        ("workflow", "diff_render", {"left_text": "old\n", "right_text": "new\n"}),
        ("workflow", "tokenjuice_compact", {"text": "\n".join(f"line {i}" for i in range(100)), "max_chars": 500}),
        ("capabilities", "capability_surface", {"include_tools": True, "include_plugins": True, "include_channels": True, "include_skills": True}),
    ]
    for section, tool_name, payload in scenarios:
        result = tools[tool_name].execute(payload, config)
        record(section, tool_name, result.status in {ActionStatus.SUCCEEDED, ActionStatus.SKIPPED}, _tool_payload(result))


def _smoke_skill_task_surfaces(record, tools: dict[str, Any], config: AgentConfig) -> None:
    dry_config = AgentConfig(
        workspace=config.workspace,
        data_dir=config.data_dir,
        max_file_bytes=config.max_file_bytes,
        max_search_results=config.max_search_results,
        dry_run=True,
        planner_provider=config.planner_provider,
        model_provider=config.model_provider,
        model_name=config.model_name,
        model_base_url=config.model_base_url,
        model_api_key_env=config.model_api_key_env,
        model_timeout_seconds=config.model_timeout_seconds,
        runtime_secrets=config.runtime_secrets,
        allowed_read_roots=config.allowed_read_roots,
        allowed_write_roots=config.allowed_write_roots,
    ).normalized()
    scenarios = [
        ("capability_surfaces", "tool_describe", {"record_id": "tool:channel_message_prepare"}),
        ("capability_surfaces", "tool_search", {"query": "voice response", "limit": 5}),
        ("computer_use", "browser_live_status", {}),
        ("computer_use", "os_active_window", {}),
        ("speech", "voice_response_prepare", {"text": "Humungousaur voice skill smoke.", "reason": "Prepare a voice artifact without playback.", "tts_provider": "artifact"}),
        ("speech", "voice_responses", {"limit": 5}),
        ("codex_delegation", "codex_capability_status", {"include_tools": True, "limit": 20}),
        (
            "codex_delegation",
            "codex_cli_plan",
            {
                "objective": "Inspect the repository and summarize the test command without editing files.",
                "context": "Skill smoke dry-run only.",
                "working_directory": ".",
                "preferred_sandbox": "read-only",
                "max_timeout_seconds": 60,
            },
        ),
        (
            "taskflow",
            "autonomous_task_graph_create",
            {
                "goal_title": "Skill smoke task graph",
                "success_criteria": ["Task graph exists"],
                "tasks": [
                    {"task_id": "inspect", "title": "Inspect capability", "owner": "planner"},
                    {"task_id": "verify", "title": "Verify result", "owner": "reviewer", "depends_on": ["inspect"]},
                ],
            },
        ),
        (
            "taskflow",
            "multi_agent_coordinate",
            {
                "goal_title": "Skill smoke coordination",
                "success_criteria": ["Specialist graph exists"],
                "specialists": [
                    {"name": "planner", "purpose": "Plan the smoke", "contract": "Return exact verification steps.", "tools": ["tool_describe"]},
                    {"name": "reviewer", "purpose": "Review the smoke", "contract": "Check evidence before completion.", "tools": ["capability_surface"]},
                ],
                "tasks": [
                    {"task_id": "plan", "title": "Plan smoke", "owner": "planner"},
                    {"task_id": "review", "title": "Review smoke", "owner": "reviewer", "depends_on": ["plan"]},
                ],
            },
        ),
        ("taskflow", "multi_agent_board", {"limit": 10}),
        ("taskflow", "autonomous_queue_status", {"limit": 10}),
        ("external_cli_companions", "external_integrations_status", {"probe_screenpipe": False}),
    ]
    for section, tool_name, payload in scenarios:
        execution_config = dry_config if tool_name in {"codex_cli_plan"} else config
        result = tools[tool_name].execute(payload, execution_config)
        record(section, tool_name, result.status in {ActionStatus.SUCCEEDED, ActionStatus.SKIPPED}, _tool_payload(result))


def _ok(result: ToolResult) -> bool:
    return result.status == ActionStatus.SUCCEEDED


def _tool_payload(result: ToolResult) -> dict[str, Any]:
    return {"status": result.status.value, "summary": result.summary, "error": result.error, "output": result.output}


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        return str(value)


def _tool_map_entries(content: str) -> list[str]:
    entries: list[str] = []
    in_tool_map = False
    for line in content.splitlines():
        if line.strip().lower().startswith("## tool map"):
            in_tool_map = True
            continue
        if in_tool_map and line.startswith("## "):
            break
        if not in_tool_map:
            continue
        match = re.match(r"\s*-\s+`([^`]+)`", line)
        if match:
            entries.append(match.group(1))
    return entries


if __name__ == "__main__":
    sys.exit(main())
