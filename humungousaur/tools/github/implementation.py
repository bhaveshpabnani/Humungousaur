from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


MAX_GITHUB_ITEMS = 300
MAX_TEXT_CHARS = 120_000


class GitHubIssueDraftCreateTool(Tool):
    def __init__(self, name: str = "github_issue_draft_create") -> None:
        super().__init__(
            name=name,
            description="Create a local GitHub issue draft artifact with repo, title, labels, severity, reproduction, impact, evidence, and privacy notes. Does not create a live issue.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/github/issues."},
                    "repo": {"type": "string"},
                    "issue_number": {"type": "string"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "problem": {"type": "string"},
                    "labels": {"type": "array", "items": {"type": "string"}},
                    "severity": {"type": "string"},
                    "status": {"type": "string"},
                    "reproduction_steps": {"type": "array", "items": {"type": "string"}},
                    "expected_behavior": {"type": "string"},
                    "actual_behavior": {"type": "string"},
                    "impact": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}},
                    "related_links": {"type": "array", "items": {"type": "string"}},
                    "privacy_notes": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                required=["repo", "title", "reason"],
            ),
            capability_group="github",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        repo = _compact_text(tool_input.get("repo"))
        title = _compact_text(tool_input.get("title"))
        body = _issue_body_from_input(tool_input)
        reason = str(tool_input.get("reason") or "").strip()
        if not repo or not title or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Repo, title, and reason are required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"issue-draft-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "github" / "issues" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "GitHub issue draft path is outside allowed write roots.")
        artifact = _issue_artifact(tool_input, repo=repo, title=title, body=body, reason=reason, markdown_path=markdown_path)
        return _write_artifact(
            self.name,
            self.risk_level,
            config,
            markdown_path,
            artifact,
            _render_issue_draft(artifact),
            self.name,
            {
                "github_issue_draft_id": artifact["github_issue_draft_id"],
                "github_issue_packet_id": artifact["github_issue_packet_id"],
                "status": artifact["status"],
                "label_count": len(artifact["labels"]),
                "evidence_count": len(artifact["evidence"]),
                "live_status": artifact["live_status"],
                "live_execution_status": artifact["live_execution_status"],
            },
        )


class GitHubPrSummaryCreateTool(Tool):
    def __init__(self, name: str = "github_pr_summary_create") -> None:
        super().__init__(
            name=name,
            description="Create a local GitHub PR summary artifact with branch, commits, changed files, tests, checklist, risks, and publication status. Does not push or open a PR.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/github/prs."},
                    "repo": {"type": "string"},
                    "pr_number": {"type": "string"},
                    "branch": {"type": "string"},
                    "base_branch": {"type": "string"},
                    "head_branch": {"type": "string"},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "changes": {"type": "array", "items": {"type": "string"}},
                    "commits": {"type": "array", "items": {"type": "string"}},
                    "changed_files": {"type": "array", "items": {"type": "string"}},
                    "tests": {"type": "array", "items": {"type": "object"}},
                    "ci_checks": {"type": "array", "items": {"type": "object"}},
                    "verification": {"type": "array", "items": {"type": "string"}},
                    "review_notes": {"type": "array", "items": {"type": "string"}},
                    "status": {"type": "string"},
                    "checklist": {"type": "array", "items": {"type": "string"}},
                    "risks": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                required=["repo", "branch", "title", "reason"],
            ),
            capability_group="github",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        repo = _compact_text(tool_input.get("repo"))
        branch = _compact_text(tool_input.get("branch"))
        title = _compact_text(tool_input.get("title"))
        summary = str(tool_input.get("summary") or tool_input.get("title") or "").strip()
        reason = str(tool_input.get("reason") or "").strip()
        if not repo or not branch or not title or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Repo, branch, title, and reason are required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"pr-summary-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "github" / "prs" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "GitHub PR summary path is outside allowed write roots.")
        artifact = _pr_artifact(tool_input, repo=repo, branch=branch, title=title, summary=summary, reason=reason, markdown_path=markdown_path)
        return _write_artifact(
            self.name,
            self.risk_level,
            config,
            markdown_path,
            artifact,
            _render_pr_summary(artifact),
            self.name,
            {
                "github_pr_summary_id": artifact["github_pr_summary_id"],
                "github_pr_packet_id": artifact["github_pr_packet_id"],
                "status": artifact["status"],
                "changed_file_count": len(artifact["changed_files"]),
                "change_count": len(artifact["changes"]),
                "test_count": len(artifact["tests"]),
                "ci_check_count": len(artifact["ci_checks"]),
                "verification_count": len(artifact["verification"]),
                "live_status": artifact["live_status"],
                "live_execution_status": artifact["live_execution_status"],
            },
        )


class CiFailureReportCreateTool(Tool):
    def __init__(self, name: str = "ci_failure_report_create") -> None:
        super().__init__(
            name=name,
            description="Create a local CI failure report artifact with check name, commit, failure class, log excerpts, suspected causes, reproduction commands, and verification plan.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/github/ci."},
                    "repo": {"type": "string"},
                    "commit": {"type": "string"},
                    "workflow": {"type": "string"},
                    "run_url": {"type": "string"},
                    "check_name": {"type": "string"},
                    "status": {"type": "string"},
                    "failure_class": {"type": "string"},
                    "log_excerpt": {"type": "string"},
                    "suspected_causes": {"type": "array", "items": {"type": "string"}},
                    "reproduction_commands": {"type": "array", "items": {"type": "string"}},
                    "fix_plan": {"type": "array", "items": {"type": "string"}},
                    "verification": {"type": "array", "items": {"type": "string"}},
                    "verification_commands": {"type": "array", "items": {"type": "string"}},
                    "residual_risks": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                required=["repo", "check_name", "reason"],
            ),
            capability_group="github",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        repo = _compact_text(tool_input.get("repo"))
        check_name = _compact_text(tool_input.get("check_name"))
        status = _compact_text(tool_input.get("status") or "failure")
        reason = str(tool_input.get("reason") or "").strip()
        if not repo or not check_name or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Repo, check_name, and reason are required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"ci-failure-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "github" / "ci" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "CI failure report path is outside allowed write roots.")
        artifact = _ci_artifact(tool_input, repo=repo, check_name=check_name, status=status, reason=reason, markdown_path=markdown_path)
        return _write_artifact(
            self.name,
            self.risk_level,
            config,
            markdown_path,
            artifact,
            _render_ci_report(artifact),
            self.name,
            {
                "ci_failure_report_id": artifact["ci_failure_report_id"],
                "suspected_cause_count": len(artifact["suspected_causes"]),
                "reproduction_command_count": len(artifact["reproduction_commands"]),
                "verification_count": len(artifact["verification"]),
                "verification_command_count": len(artifact["verification_commands"]),
                "live_execution_status": artifact["live_execution_status"],
            },
        )


class GitHubRepoStateReportCreateTool(Tool):
    def __init__(self, name: str = "github_repo_state_report_create") -> None:
        super().__init__(
            name=name,
            description="Create a local repo state report from supplied git status, branch, remotes, changed files, and verification evidence. Does not run git.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/github/repo_state."},
                    "repo": {"type": "string"},
                    "branch": {"type": "string"},
                    "base_branch": {"type": "string"},
                    "remote": {"type": "string"},
                    "status": {"type": "string"},
                    "status_summary": {"type": "string"},
                    "remotes": {"type": "array", "items": {"type": "string"}},
                    "changed_files": {"type": "array", "items": {"type": "string"}},
                    "recent_commits": {"type": "array", "items": {"type": "string"}},
                    "untracked_files": {"type": "array", "items": {"type": "string"}},
                    "verification": {"type": "array", "items": {"type": "object"}},
                    "risks": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                required=["repo", "reason"],
            ),
            capability_group="github",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        repo = _compact_text(tool_input.get("repo"))
        branch = _compact_text(tool_input.get("branch") or "unknown")
        status = _compact_text(tool_input.get("status") or tool_input.get("status_summary") or "not inspected")
        reason = str(tool_input.get("reason") or "").strip()
        if not repo or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Repo and reason are required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"repo-state-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "github" / "repo_state" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Repo state report path is outside allowed write roots.")
        artifact = _repo_state_artifact(tool_input, repo=repo, branch=branch, status=status, reason=reason, markdown_path=markdown_path)
        return _write_artifact(
            self.name,
            self.risk_level,
            config,
            markdown_path,
            artifact,
            _render_repo_state(artifact),
            self.name,
            {
                "github_repo_state_report_id": artifact["github_repo_state_report_id"],
                "changed_file_count": len(artifact["changed_files"]),
                "recent_commit_count": len(artifact["recent_commits"]),
                "untracked_file_count": len(artifact["untracked_files"]),
                "verification_count": len(artifact["verification"]),
                "live_execution_status": artifact["live_execution_status"],
            },
        )


class GitHubWorkflowArtifactInspectTool(Tool):
    def __init__(self, name: str = "github_workflow_artifact_inspect") -> None:
        super().__init__(
            name=name,
            description="Inspect a local GitHub issue, PR, CI, or repo-state artifact for type, status, counts, and preview text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string"}}, required=["path"]),
            capability_group="github",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_github_path(normalized, str(tool_input.get("path") or ""))
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "GitHub artifact path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".md":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "GitHub artifact file does not exist.")
        metadata = _load_sidecar(path.with_suffix(".json"))
        text = path.read_text(encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected GitHub workflow artifact {path}.",
            {
                "path": str(path),
                "metadata_path": str(path.with_suffix(".json")) if path.with_suffix(".json").exists() else "",
                "artifact_type": _artifact_type(metadata),
                "repo": metadata.get("repo", ""),
                "title": metadata.get("title", ""),
                "status": metadata.get("status", ""),
                "live_status": metadata.get("live_status", ""),
                "live_execution_status": metadata.get("live_execution_status", ""),
                "changed_file_count": _count(metadata.get("changed_files")),
                "evidence_count": _count(metadata.get("evidence")),
                "label_count": _count(metadata.get("labels")),
                "ci_check_count": _count(metadata.get("ci_checks")),
                "verification_count": _count(metadata.get("verification")),
                "test_count": _count(metadata.get("tests")),
                "finding_count": _count(metadata.get("suspected_causes")),
                "preview": text[:4000],
                "source": self.name,
            },
        )


def default_github_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        GitHubIssueDraftCreateTool(),
        GitHubIssueDraftCreateTool("github_issue_packet_create"),
        GitHubPrSummaryCreateTool(),
        GitHubPrSummaryCreateTool("github_pr_packet_create"),
        CiFailureReportCreateTool(),
        GitHubRepoStateReportCreateTool(),
        GitHubWorkflowArtifactInspectTool(),
        GitHubWorkflowArtifactInspectTool("github_artifact_inspect"),
    ]
    return {tool.name: tool for tool in tools}


def _issue_artifact(tool_input: dict[str, Any], *, repo: str, title: str, body: str, reason: str, markdown_path: Path) -> dict[str, Any]:
    artifact_id = f"github-issue-draft-{uuid4().hex[:12]}"
    evidence = _string_list(tool_input.get("evidence")) or _string_list(tool_input.get("evidence_refs"))
    return {
        "artifact_type": "github_issue_packet",
        "github_issue_draft_id": artifact_id,
        "github_issue_packet_id": artifact_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo": repo,
        "issue_number": _compact_text(tool_input.get("issue_number")),
        "title": title,
        "body": body[:MAX_TEXT_CHARS],
        "problem": _compact_text(tool_input.get("problem")),
        "labels": _string_list(tool_input.get("labels")),
        "severity": _compact_text(tool_input.get("severity")),
        "status": _compact_text(tool_input.get("status") or "draft"),
        "reproduction_steps": _string_list(tool_input.get("reproduction_steps")),
        "expected_behavior": _compact_text(tool_input.get("expected_behavior")),
        "actual_behavior": _compact_text(tool_input.get("actual_behavior")),
        "impact": _compact_text(tool_input.get("impact")),
        "evidence": evidence,
        "evidence_refs": evidence,
        "related_links": _string_list(tool_input.get("related_links")),
        "privacy_notes": _string_list(tool_input.get("privacy_notes")),
        "reason": reason,
        "path": str(markdown_path),
        "live_status": "draft_not_created",
        "live_execution_status": "not_executed",
        "safety_note": "Local draft only. No GitHub issue was created or updated.",
    }


def _pr_artifact(tool_input: dict[str, Any], *, repo: str, branch: str, title: str, summary: str, reason: str, markdown_path: Path) -> dict[str, Any]:
    artifact_id = f"github-pr-summary-{uuid4().hex[:12]}"
    changes = _string_list(tool_input.get("changes")) or _string_list(tool_input.get("changed_files"))
    return {
        "artifact_type": "github_pr_packet",
        "github_pr_summary_id": artifact_id,
        "github_pr_packet_id": artifact_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo": repo,
        "pr_number": _compact_text(tool_input.get("pr_number")),
        "branch": branch,
        "base_branch": _compact_text(tool_input.get("base_branch") or "main"),
        "head_branch": _compact_text(tool_input.get("head_branch") or branch),
        "title": title,
        "summary": summary[:MAX_TEXT_CHARS],
        "changes": changes,
        "commits": _string_list(tool_input.get("commits")),
        "changed_files": _string_list(tool_input.get("changed_files")),
        "tests": _object_list(tool_input.get("tests")),
        "ci_checks": _object_list(tool_input.get("ci_checks")),
        "verification": _string_list(tool_input.get("verification")),
        "review_notes": _string_list(tool_input.get("review_notes")),
        "status": _compact_text(tool_input.get("status") or "draft"),
        "checklist": _string_list(tool_input.get("checklist")),
        "risks": _string_list(tool_input.get("risks")),
        "reason": reason,
        "path": str(markdown_path),
        "live_status": "local_summary_not_pushed_or_opened",
        "live_execution_status": "not_executed",
        "safety_note": "Local PR summary only. No branch was pushed and no PR was opened.",
    }


def _ci_artifact(tool_input: dict[str, Any], *, repo: str, check_name: str, status: str, reason: str, markdown_path: Path) -> dict[str, Any]:
    verification = _string_list(tool_input.get("verification")) or _string_list(tool_input.get("verification_commands"))
    return {
        "artifact_type": "ci_failure_report",
        "ci_failure_report_id": f"ci-failure-report-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo": repo,
        "commit": _compact_text(tool_input.get("commit")),
        "workflow": _compact_text(tool_input.get("workflow")),
        "run_url": _compact_text(tool_input.get("run_url")),
        "check_name": check_name,
        "status": status,
        "failure_class": _compact_text(tool_input.get("failure_class")),
        "log_excerpt": str(tool_input.get("log_excerpt") or "")[:MAX_TEXT_CHARS],
        "suspected_causes": _string_list(tool_input.get("suspected_causes")),
        "reproduction_commands": _string_list(tool_input.get("reproduction_commands")),
        "fix_plan": _string_list(tool_input.get("fix_plan")),
        "verification": verification,
        "verification_commands": _string_list(tool_input.get("verification_commands")),
        "residual_risks": _string_list(tool_input.get("residual_risks")),
        "reason": reason,
        "path": str(markdown_path),
        "live_status": "local_report_only",
        "live_execution_status": "not_executed",
        "safety_note": "Local CI report only. CI status was not queried or changed by this artifact.",
    }


def _repo_state_artifact(tool_input: dict[str, Any], *, repo: str, branch: str, status: str, reason: str, markdown_path: Path) -> dict[str, Any]:
    return {
        "artifact_type": "github_repo_state_report",
        "github_repo_state_report_id": f"github-repo-state-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo": repo,
        "branch": branch,
        "base_branch": _compact_text(tool_input.get("base_branch") or "main"),
        "remote": _compact_text(tool_input.get("remote")),
        "status": status,
        "status_summary": status,
        "remotes": _string_list(tool_input.get("remotes")),
        "changed_files": _string_list(tool_input.get("changed_files")),
        "recent_commits": _string_list(tool_input.get("recent_commits")),
        "untracked_files": _string_list(tool_input.get("untracked_files")),
        "verification": _object_list(tool_input.get("verification")),
        "risks": _string_list(tool_input.get("risks")),
        "reason": reason,
        "path": str(markdown_path),
        "live_status": "local_report_only",
        "live_execution_status": "not_executed",
        "safety_note": "Local repo-state report only. No Git command was executed by this artifact.",
    }


def _render_issue_draft(artifact: dict[str, Any]) -> str:
    lines = [
        f"# {artifact['title']}",
        "",
        f"Repo: {artifact['repo']}",
        f"Issue number: {artifact['issue_number']}",
        f"Status: {artifact['status']}",
        f"Live status: {artifact['live_status']}",
        f"Live execution: {artifact['live_execution_status']}",
        f"Severity: {artifact['severity']}",
        "",
        "## Body",
        "",
        artifact["body"],
        "",
    ]
    _append_list(lines, "Labels", artifact["labels"])
    _append_list(lines, "Reproduction Steps", artifact["reproduction_steps"])
    _append_text(lines, "Expected Behavior", artifact["expected_behavior"])
    _append_text(lines, "Actual Behavior", artifact["actual_behavior"])
    _append_text(lines, "Impact", artifact["impact"])
    _append_list(lines, "Evidence", artifact["evidence"])
    _append_list(lines, "Related Links", artifact["related_links"])
    _append_list(lines, "Privacy Notes", artifact["privacy_notes"])
    return _finish(lines, artifact)


def _render_pr_summary(artifact: dict[str, Any]) -> str:
    lines = [
        f"# {artifact['title']}",
        "",
        f"Repo: {artifact['repo']}",
        f"PR number: {artifact['pr_number']}",
        f"Branch: {artifact['branch']}",
        f"Base branch: {artifact['base_branch']}",
        f"Head branch: {artifact['head_branch']}",
        f"Status: {artifact['status']}",
        f"Live status: {artifact['live_status']}",
        f"Live execution: {artifact['live_execution_status']}",
        "",
        "## Summary",
        "",
        artifact["summary"],
        "",
    ]
    _append_list(lines, "Changes", artifact["changes"])
    _append_list(lines, "Commits", artifact["commits"])
    _append_list(lines, "Changed Files", artifact["changed_files"])
    _append_object_table(lines, "Tests", artifact["tests"])
    _append_object_table(lines, "CI Checks", artifact["ci_checks"])
    _append_list(lines, "Verification", artifact["verification"])
    _append_list(lines, "Review Notes", artifact["review_notes"])
    _append_list(lines, "Checklist", artifact["checklist"])
    _append_list(lines, "Risks", artifact["risks"])
    return _finish(lines, artifact)


def _render_ci_report(artifact: dict[str, Any]) -> str:
    lines = [
        f"# {artifact['check_name']}",
        "",
        f"Repo: {artifact['repo']}",
        f"Workflow: {artifact['workflow']}",
        f"Run URL: {artifact['run_url']}",
        f"Commit: {artifact['commit']}",
        f"Status: {artifact['status']}",
        f"Failure class: {artifact['failure_class']}",
        f"Live status: {artifact['live_status']}",
        f"Live execution: {artifact['live_execution_status']}",
        "",
        "## Log Excerpt",
        "",
        artifact["log_excerpt"],
        "",
    ]
    _append_list(lines, "Suspected Causes", artifact["suspected_causes"])
    _append_list(lines, "Reproduction Commands", artifact["reproduction_commands"])
    _append_list(lines, "Fix Plan", artifact["fix_plan"])
    _append_list(lines, "Verification", artifact["verification"])
    _append_list(lines, "Verification Commands", artifact["verification_commands"])
    _append_list(lines, "Residual Risks", artifact["residual_risks"])
    return _finish(lines, artifact)


def _render_repo_state(artifact: dict[str, Any]) -> str:
    lines = [
        f"# Repo State: {artifact['repo']}",
        "",
        f"Branch: {artifact['branch']}",
        f"Base branch: {artifact['base_branch']}",
        f"Remote: {artifact['remote']}",
        f"Status: {artifact['status']}",
        f"Live status: {artifact['live_status']}",
        f"Live execution: {artifact['live_execution_status']}",
        "",
    ]
    _append_list(lines, "Remotes", artifact["remotes"])
    _append_list(lines, "Changed Files", artifact["changed_files"])
    _append_list(lines, "Recent Commits", artifact["recent_commits"])
    _append_list(lines, "Untracked Files", artifact["untracked_files"])
    _append_object_table(lines, "Verification", artifact["verification"])
    _append_list(lines, "Risks", artifact["risks"])
    return _finish(lines, artifact)


def _write_artifact(tool_name: str, risk_level: RiskLevel, config: AgentConfig, markdown_path: Path, metadata: dict[str, Any], markdown: str, source: str, extra: dict[str, Any]) -> ToolResult:
    if config.dry_run:
        return ToolResult(tool_name, ActionStatus.SKIPPED, risk_level, f"Dry run: would create GitHub workflow artifact {markdown_path}.", {"path": str(markdown_path), "metadata": metadata})
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(markdown, encoding="utf-8")
    metadata_path = markdown_path.with_suffix(".json")
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return ToolResult(tool_name, ActionStatus.SUCCEEDED, risk_level, f"Created GitHub workflow artifact {markdown_path}.", {"path": str(markdown_path), "metadata_path": str(metadata_path), "source": source, **extra})


def _finish(lines: list[str], artifact: dict[str, Any]) -> str:
    lines.extend(["## Safety Note", "", artifact["safety_note"], "", f"Created: {artifact['created_at']}"])
    return "\n".join(lines) + "\n"


def _append_text(lines: list[str], title: str, text: str) -> None:
    if text:
        lines.extend([f"## {title}", "", text, ""])


def _append_list(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines.extend([f"## {title}", ""])
    for item in items:
        lines.append(f"- {item}")
    lines.append("")


def _append_object_table(lines: list[str], title: str, items: list[dict[str, Any]]) -> None:
    if not items:
        return
    lines.extend([f"## {title}", ""])
    for item in items:
        for key, value in item.items():
            lines.append(f"- `{key}`: `{_compact_text(value)}`")
        lines.append("")


def _resolve_github_path(config: AgentConfig, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = config.workspace / path
        if not path.exists():
            data_path = config.data_dir / raw_path
            if data_path.exists():
                path = data_path
            else:
                path = config.data_dir / "github" / Path(raw_path).name
    if not path.suffix:
        path = path.with_suffix(".md")
    return path.resolve()


def _artifact_type(metadata: dict[str, Any]) -> str:
    artifact_type = metadata.get("artifact_type")
    if isinstance(artifact_type, str) and artifact_type:
        return artifact_type
    for key in ("github_issue_draft_id", "github_pr_summary_id", "ci_failure_report_id", "github_repo_state_report_id"):
        if key in metadata:
            return key.removesuffix("_id")
    return "github_workflow_artifact"


def _issue_body_from_input(tool_input: dict[str, Any]) -> str:
    body = str(tool_input.get("body") or "").strip()
    if body:
        return body
    sections: list[str] = []
    problem = _compact_text(tool_input.get("problem"))
    if problem:
        sections.append(problem)
    expected = _compact_text(tool_input.get("expected_behavior"))
    actual = _compact_text(tool_input.get("actual_behavior"))
    if expected:
        sections.append(f"Expected behavior: {expected}")
    if actual:
        sections.append(f"Actual behavior: {actual}")
    impact = _compact_text(tool_input.get("impact"))
    if impact:
        sections.append(f"Impact: {impact}")
    return "\n\n".join(sections) or "Issue details are pending."


def _object_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value[:MAX_GITHUB_ITEMS] if isinstance(item, dict)]


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip()[:MAX_TEXT_CHARS] for item in value[:MAX_GITHUB_ITEMS] if str(item).strip()]


def _compact_text(value: Any) -> str:
    return " ".join(str(value or "").split())[:MAX_TEXT_CHARS]


def _load_sidecar(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _safe_filename(value: str, suffix: str) -> str:
    name = Path(value).name.strip() or f"artifact{suffix}"
    if not name.lower().endswith(suffix):
        name += suffix
    stem = "".join(char if char.isalnum() or char in ("-", "_", ".") else "-" for char in Path(name).stem).strip(".-")
    return f"{stem or 'artifact'}{suffix}"


def _is_within(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)
