import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools import default_tools
from humungousaur.tools.github_tools import (
    CiFailureReportCreateTool,
    GitHubIssueDraftCreateTool,
    GitHubPrSummaryCreateTool,
    GitHubRepoStateReportCreateTool,
    GitHubWorkflowArtifactInspectTool,
)


class GitHubToolTests(unittest.TestCase):
    def test_issue_packet_create_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = GitHubIssueDraftCreateTool("github_issue_packet_create").execute(
                {
                    "filename": "issue.md",
                    "repo": "owner/repo",
                    "title": "Fix chat 400 response",
                    "problem": "The app sends an invalid stimulus payload.",
                    "labels": ["bug", "needs-triage"],
                    "severity": "high",
                    "reproduction_steps": ["Open the desktop app.", "Send Hi."],
                    "expected_behavior": "Agent replies normally.",
                    "actual_behavior": "HTTP 400 is shown.",
                    "impact": "Chat onboarding is blocked.",
                    "evidence": ["screenshot:chat-400.png"],
                    "reason": "Verify native issue packet artifact.",
                },
                config,
            )
            inspected = GitHubWorkflowArtifactInspectTool("github_artifact_inspect").execute({"path": created.output["path"]}, config)

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["live_execution_status"], "not_executed")
        self.assertEqual(created.output["label_count"], 2)
        self.assertEqual(created.output["evidence_count"], 1)
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["artifact_type"], "github_issue_packet")
        self.assertEqual(inspected.output["status"], "draft")
        self.assertIn("No GitHub issue was created", inspected.output["preview"])

    def test_pr_packet_create_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = GitHubPrSummaryCreateTool("github_pr_packet_create").execute(
                {
                    "filename": "pr.md",
                    "repo": "owner/repo",
                    "title": "Add GitHub workflow artifacts",
                    "branch": "main",
                    "base_branch": "main",
                    "changes": ["Added local issue packet.", "Added local CI report."],
                    "verification": ["pytest tests/test_github_tools.py -q"],
                    "ci_checks": [{"name": "pytest", "status": "pending"}],
                    "risks": ["Live GitHub posting is not executed by this packet."],
                    "reason": "Verify native PR packet artifact.",
                },
                config,
            )
            inspected = GitHubWorkflowArtifactInspectTool("github_artifact_inspect").execute({"path": created.output["path"]}, config)

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["change_count"], 2)
        self.assertEqual(created.output["verification_count"], 1)
        self.assertEqual(created.output["ci_check_count"], 1)
        self.assertEqual(created.output["live_execution_status"], "not_executed")
        self.assertEqual(inspected.output["artifact_type"], "github_pr_packet")
        self.assertEqual(inspected.output["ci_check_count"], 1)

    def test_ci_failure_report_create_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = CiFailureReportCreateTool().execute(
                {
                    "filename": "ci.md",
                    "repo": "owner/repo",
                    "check_name": "pytest",
                    "workflow": "CI",
                    "failure_class": "test",
                    "log_excerpt": "AssertionError: expected text field.",
                    "suspected_causes": ["Stimulus payload omitted text."],
                    "reproduction_commands": ["python -m pytest tests/test_api.py -q"],
                    "verification": ["Focused API regression."],
                    "reason": "Verify native CI report artifact.",
                },
                config,
            )
            inspected = GitHubWorkflowArtifactInspectTool().execute({"path": created.output["path"]}, config)

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["suspected_cause_count"], 1)
        self.assertEqual(created.output["reproduction_command_count"], 1)
        self.assertEqual(created.output["verification_count"], 1)
        self.assertEqual(inspected.output["artifact_type"], "ci_failure_report")
        self.assertIn("Local CI report only", inspected.output["preview"])

    def test_repo_state_report_create_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = GitHubRepoStateReportCreateTool().execute(
                {
                    "filename": "repo-state.md",
                    "repo": "owner/repo",
                    "branch": "main",
                    "status_summary": "One local doc and one tool file changed.",
                    "changed_files": ["docs/GOAL_STATUS_AND_REMAINING_WORK.md", "humungousaur/tools/github/implementation.py"],
                    "recent_commits": ["6d13f22 Add native security review artifacts"],
                    "verification": [{"command": "git status --short", "result": "reviewed"}],
                    "reason": "Verify native repo-state artifact.",
                },
                config,
            )
            inspected = GitHubWorkflowArtifactInspectTool().execute({"path": created.output["path"]}, config)

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["changed_file_count"], 2)
        self.assertEqual(created.output["recent_commit_count"], 1)
        self.assertEqual(created.output["verification_count"], 1)
        self.assertEqual(inspected.output["artifact_type"], "github_repo_state_report")

    def test_github_tools_are_in_global_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            tools = default_tools(config)

        self.assertIn("github_issue_packet_create", tools)
        self.assertIn("github_pr_packet_create", tools)
        self.assertIn("ci_failure_report_create", tools)
        self.assertIn("github_repo_state_report_create", tools)
        self.assertIn("github_artifact_inspect", tools)
        self.assertEqual(tools["github_issue_packet_create"].capability_group, "github")


if __name__ == "__main__":
    unittest.main()
