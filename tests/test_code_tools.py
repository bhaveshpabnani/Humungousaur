import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.code_tools import (
    PythonInterpreterArtifactTool,
    PythonInterpreterRunTool,
    PythonInterpreterRunsTool,
    PythonInterpreterSessionTool,
    PythonInterpreterSessionsTool,
    PythonInterpreterTool,
)


class CodeToolTests(unittest.TestCase):
    def test_python_interpreter_dry_run_does_not_execute_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", dry_run=True).normalized()

            result = PythonInterpreterTool().execute(
                {"code": "print('hello')", "reason": "test"},
                config,
            )

            self.assertEqual(result.status, ActionStatus.SKIPPED)
            self.assertTrue(result.output["code_not_executed"])

    def test_python_interpreter_executes_bounded_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = PythonInterpreterTool().execute(
                {"code": "print('analysis ok')", "reason": "test"},
                config,
            )

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertIn("analysis ok", result.output["stdout"])
            self.assertEqual(result.output["returncode"], 0)
            self.assertTrue(Path(result.output["manifest_path"]).exists())

    def test_python_interpreter_allows_write_inside_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            output_path = config.data_dir / "analysis.txt"

            result = PythonInterpreterTool().execute(
                {
                    "code": f"from pathlib import Path\nPath({str(output_path)!r}).write_text('ok', encoding='utf-8')\nprint('wrote')",
                    "reason": "test",
                },
                config,
            )

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "ok")
            self.assertEqual(result.output["sandbox_profile"], "data_write")

    def test_python_interpreter_read_only_profile_allows_run_artifacts_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            output_path = config.data_dir / "analysis.txt"

            result = PythonInterpreterTool().execute(
                {
                    "code": (
                        "import os\n"
                        "from pathlib import Path\n"
                        "Path(os.environ['UMANG_RUN_DIR'], 'result.txt').write_text('ok', encoding='utf-8')\n"
                        f"Path({str(output_path)!r}).write_text('blocked', encoding='utf-8')\n"
                    ),
                    "sandbox_profile": "read_only",
                    "reason": "test read-only sandbox",
                },
                config,
            )

            self.assertEqual(result.status, ActionStatus.FAILED)
            self.assertEqual(result.output["sandbox_profile"], "read_only")
            self.assertIn("blocked write outside allowed roots", result.output["stderr"])
            self.assertFalse(output_path.exists())
            self.assertEqual(result.output["artifact_count"], 1)

    def test_python_interpreter_default_profile_blocks_workspace_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            output_path = workspace / "project-edit.txt"

            result = PythonInterpreterTool().execute(
                {
                    "code": f"from pathlib import Path\nPath({str(output_path)!r}).write_text('blocked', encoding='utf-8')",
                    "reason": "test default sandbox",
                },
                config,
            )

            self.assertEqual(result.status, ActionStatus.FAILED)
            self.assertEqual(result.output["sandbox_profile"], "data_write")
            self.assertIn("blocked write outside allowed roots", result.output["stderr"])
            self.assertFalse(output_path.exists())

    def test_python_interpreter_workspace_write_profile_allows_workspace_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            output_path = workspace / "project-edit.txt"

            result = PythonInterpreterTool().execute(
                {
                    "code": f"from pathlib import Path\nPath({str(output_path)!r}).write_text('ok', encoding='utf-8')",
                    "sandbox_profile": "workspace_write",
                    "reason": "test workspace write sandbox",
                },
                config,
            )

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertEqual(result.output["sandbox_profile"], "workspace_write")
            self.assertEqual(output_path.read_text(encoding="utf-8"), "ok")

    def test_python_interpreter_blocks_read_outside_allowed_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            outside = root / "secret.txt"
            outside.write_text("secret", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = PythonInterpreterTool().execute(
                {"code": f"print(open({str(outside)!r}, encoding='utf-8').read())", "reason": "test"},
                config,
            )

            self.assertEqual(result.status, ActionStatus.FAILED)
            self.assertIn("blocked read outside allowed roots", result.output["stderr"])

    def test_python_interpreter_blocks_network_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = PythonInterpreterTool().execute(
                {"code": "import socket\nsocket.socket()", "reason": "test"},
                config,
            )

            self.assertEqual(result.status, ActionStatus.FAILED)
            self.assertIn("blocked network", result.output["stderr"])

    def test_python_interpreter_blocks_non_stdlib_imports_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "local_package.py").write_text("VALUE = 42\n", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = PythonInterpreterTool().execute(
                {"code": "import local_package\nprint(local_package.VALUE)", "reason": "test import policy"},
                config,
            )

            self.assertEqual(result.status, ActionStatus.FAILED)
            self.assertIn("blocked import outside allowed packages: local_package", result.output["stderr"])
            self.assertEqual(result.output["import_mode"], "stdlib")

    def test_python_interpreter_allows_explicit_package_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "local_package.py").write_text("VALUE = 42\n", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = PythonInterpreterTool().execute(
                {
                    "code": "import local_package\nprint(local_package.VALUE)",
                    "import_mode": "allowlist",
                    "allowed_imports": ["local_package"],
                    "reason": "test import allowlist",
                },
                config,
            )

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertIn("42", result.output["stdout"])
            self.assertEqual(result.output["import_mode"], "allowlist")
            self.assertEqual(result.output["allowed_imports"], ["local_package"])

    def test_python_interpreter_allows_all_import_mode_when_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "local_package.py").write_text("VALUE = 7\n", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = PythonInterpreterTool().execute(
                {
                    "code": "import local_package\nprint(local_package.VALUE)",
                    "import_mode": "all",
                    "reason": "trusted local import test",
                },
                config,
            )

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertIn("7", result.output["stdout"])
            self.assertEqual(result.output["import_mode"], "all")

    def test_python_interpreter_times_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = PythonInterpreterTool().execute(
                {"code": "while True:\n    pass", "timeout_seconds": 1, "reason": "test"},
                config,
            )

            self.assertEqual(result.status, ActionStatus.FAILED)
            self.assertTrue(result.output["timed_out"])
            self.assertTrue(Path(result.output["manifest_path"]).exists())

    def test_python_interpreter_writes_manifest_and_lists_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            executed = PythonInterpreterTool().execute(
                {"code": "print('analysis ok')", "reason": "test manifest"},
                config,
            )
            listed = PythonInterpreterRunsTool().execute({"limit": 5}, config)

            self.assertEqual(executed.status, ActionStatus.SUCCEEDED)
            self.assertEqual(listed.status, ActionStatus.SUCCEEDED)
            self.assertEqual(listed.output["runs"][0]["run_id"], executed.output["run_id"])
            self.assertEqual(listed.output["runs"][0]["status"], "succeeded")
            self.assertIn("analysis ok", listed.output["runs"][0]["stdout_tail"])

    def test_python_interpreter_run_tool_reads_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            executed = PythonInterpreterTool().execute(
                {"code": "print('manifest details')", "reason": "test manifest read"},
                config,
            )
            loaded = PythonInterpreterRunTool().execute({"run_id": executed.output["run_id"]}, config)

            self.assertEqual(loaded.status, ActionStatus.SUCCEEDED)
            self.assertEqual(loaded.output["run"]["run_id"], executed.output["run_id"])
            self.assertIn("manifest details", loaded.output["run"]["stdout_tail"])
            self.assertEqual(loaded.output["run"]["artifact_bytes_served"], False)

    def test_python_interpreter_artifact_reads_only_manifested_text_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            executed = PythonInterpreterTool().execute(
                {
                    "code": (
                        "import os\n"
                        "from pathlib import Path\n"
                        "Path(os.environ['UMANG_RUN_DIR'], 'result.txt').write_text('artifact hello', encoding='utf-8')\n"
                    ),
                    "reason": "test artifact",
                },
                config,
            )
            artifact = PythonInterpreterArtifactTool().execute(
                {"run_id": executed.output["run_id"], "filename": "result.txt"},
                config,
            )

            self.assertEqual(executed.status, ActionStatus.SUCCEEDED)
            self.assertEqual(executed.output["artifact_count"], 1)
            self.assertEqual(artifact.status, ActionStatus.SUCCEEDED)
            self.assertEqual(artifact.output["content"], "artifact hello")
            self.assertFalse(artifact.output["truncated"])

    def test_python_interpreter_artifact_blocks_traversal_and_internal_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            executed = PythonInterpreterTool().execute(
                {"code": "print('internal files stay private')", "reason": "test artifact guards"},
                config,
            )
            traversal = PythonInterpreterArtifactTool().execute(
                {"run_id": executed.output["run_id"], "filename": "../policy.json"},
                config,
            )
            internal = PythonInterpreterArtifactTool().execute(
                {"run_id": executed.output["run_id"], "filename": "policy.json"},
                config,
            )

            self.assertEqual(traversal.status, ActionStatus.BLOCKED)
            self.assertEqual(internal.status, ActionStatus.BLOCKED)

    def test_python_interpreter_session_groups_runs_and_lists_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            executed = PythonInterpreterTool().execute(
                {"code": "x = 41", "session_label": "analysis thread", "reason": "start session"},
                config,
            )
            sessions = PythonInterpreterSessionsTool().execute({"limit": 5}, config)
            session = PythonInterpreterSessionTool().execute({"session_id": executed.output["session_id"]}, config)

            self.assertEqual(executed.status, ActionStatus.SUCCEEDED)
            self.assertTrue(executed.output["session_id"].startswith("py-session-"))
            self.assertEqual(sessions.status, ActionStatus.SUCCEEDED)
            self.assertEqual(sessions.output["sessions"][0]["session_id"], executed.output["session_id"])
            self.assertEqual(sessions.output["sessions"][0]["run_count"], 1)
            self.assertEqual(session.status, ActionStatus.SUCCEEDED)
            self.assertEqual(session.output["session"]["label"], "analysis thread")
            self.assertEqual(session.output["session"]["runs"][0]["run_id"], executed.output["run_id"])
            self.assertFalse(session.output["session"]["code_bodies_served"])

    def test_python_interpreter_session_replay_can_resume_variables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            first = PythonInterpreterTool().execute(
                {"code": "x = 41", "session_label": "resume variables", "reason": "define variable"},
                config,
            )
            second = PythonInterpreterTool().execute(
                {
                    "code": "print(x + 1)",
                    "session_id": first.output["session_id"],
                    "replay_session": True,
                    "reason": "resume variable",
                },
                config,
            )
            session = PythonInterpreterSessionTool().execute({"session_id": first.output["session_id"]}, config)

            self.assertEqual(second.status, ActionStatus.SUCCEEDED)
            self.assertIn("42", second.output["stdout"])
            self.assertEqual(second.output["replayed_run_ids"], [first.output["run_id"]])
            self.assertEqual(session.output["session"]["run_count"], 2)
            self.assertEqual(session.output["session"]["runs"][1]["replayed_run_ids"], [first.output["run_id"]])

    def test_python_interpreter_session_without_replay_does_not_share_variables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            first = PythonInterpreterTool().execute(
                {"code": "x = 41", "session_label": "isolated variables", "reason": "define variable"},
                config,
            )
            second = PythonInterpreterTool().execute(
                {
                    "code": "print(x + 1)",
                    "session_id": first.output["session_id"],
                    "reason": "no replay",
                },
                config,
            )

            self.assertEqual(second.status, ActionStatus.FAILED)
            self.assertIn("NameError", second.output["stderr"])
            self.assertEqual(second.output["replayed_run_ids"], [])


if __name__ == "__main__":
    unittest.main()
