import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.executor import Executor
from humungousaur.safety.policy import PolicyEngine
from humungousaur.schemas import ActionStatus, PlannedStep
from humungousaur.tools import default_tools


class ExecutorValidationTests(unittest.TestCase):
    def test_executor_rejects_unknown_tool_input_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            executor = Executor(default_tools(), PolicyEngine())

            result = executor.execute(
                PlannedStep("read_file", {"path": "README.md", "unexpected": True}, "test"),
                config,
            )

            self.assertEqual(result.status, ActionStatus.FAILED)
            self.assertIn("not allowed", result.error or "")

    def test_executor_rejects_malformed_high_risk_input_before_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            executor = Executor(default_tools(), PolicyEngine())

            result = executor.execute(
                PlannedStep("run_shell_command", {"argv": "python --version"}, "test"),
                config,
            )

            self.assertEqual(result.status, ActionStatus.FAILED)
            self.assertNotIn("approval", result.output)
            self.assertIn("must be an array", result.error or "")

    def test_executor_still_routes_valid_high_risk_input_to_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            executor = Executor(default_tools(), PolicyEngine())

            result = executor.execute(
                PlannedStep("run_shell_command", {"argv": ["python", "--version"]}, "test"),
                config,
            )

            self.assertEqual(result.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(result.output["approval"]["tool_input"], {"argv": ["python", "--version"]})

    def test_executor_rejects_invalid_shell_command_profile_before_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            executor = Executor(default_tools(), PolicyEngine())

            result = executor.execute(
                PlannedStep("run_shell_command", {"argv": ["python", "--version"], "command_profile": "everywhere"}, "test"),
                config,
            )

            self.assertEqual(result.status, ActionStatus.FAILED)
            self.assertNotIn("approval", result.output)
            self.assertIn("must be one of", result.error or "")

    def test_executor_routes_python_interpreter_to_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            executor = Executor(default_tools(), PolicyEngine())

            result = executor.execute(
                PlannedStep("python_interpreter", {"code": "print('hi')", "reason": "analyze"}, "test"),
                config,
            )

            self.assertEqual(result.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(result.output["approval"]["tool_name"], "python_interpreter")

    def test_executor_rejects_invalid_python_import_mode_before_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            executor = Executor(default_tools(), PolicyEngine())

            result = executor.execute(
                PlannedStep(
                    "python_interpreter",
                    {"code": "print('hi')", "import_mode": "anything", "reason": "analyze"},
                    "test",
                ),
                config,
            )

            self.assertEqual(result.status, ActionStatus.FAILED)
            self.assertNotIn("approval", result.output)
            self.assertIn("must be one of", result.error or "")

    def test_executor_rejects_invalid_python_sandbox_profile_before_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            executor = Executor(default_tools(), PolicyEngine())

            result = executor.execute(
                PlannedStep(
                    "python_interpreter",
                    {"code": "print('hi')", "sandbox_profile": "everywhere", "reason": "analyze"},
                    "test",
                ),
                config,
            )

            self.assertEqual(result.status, ActionStatus.FAILED)
            self.assertNotIn("approval", result.output)
            self.assertIn("must be one of", result.error or "")

    def test_executor_routes_screenshot_capture_to_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            executor = Executor(default_tools(), PolicyEngine())

            result = executor.execute(
                PlannedStep("screenshot_capture", {"reason": "understand visible screen"}, "test"),
                config,
            )

            self.assertEqual(result.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(result.output["approval"]["tool_name"], "screenshot_capture")

    def test_executor_routes_os_observe_ui_to_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            executor = Executor(default_tools(), PolicyEngine())

            result = executor.execute(
                PlannedStep("os_observe_ui", {"reason": "inspect foreground UI"}, "test"),
                config,
            )

            self.assertEqual(result.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(result.output["approval"]["tool_name"], "os_observe_ui")

    def test_executor_routes_os_ui_actions_to_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            executor = Executor(default_tools(), PolicyEngine())

            click = executor.execute(
                PlannedStep(
                    "os_click_element",
                    {"observation_id": "11111111-1111-1111-1111-111111111111", "element_id": "uia:1", "reason": "click"},
                    "test",
                ),
                config,
            )
            typed = executor.execute(
                PlannedStep(
                    "os_type_text",
                    {
                        "observation_id": "11111111-1111-1111-1111-111111111111",
                        "element_id": "uia:1",
                        "text": "Hello",
                        "reason": "type",
                    },
                    "test",
                ),
                config,
            )
            keys = executor.execute(
                PlannedStep("os_send_keys", {"shortcut": "Ctrl+S", "reason": "save"}, "test"),
                config,
            )
            scroll = executor.execute(
                PlannedStep(
                    "os_scroll_element",
                    {
                        "observation_id": "11111111-1111-1111-1111-111111111111",
                        "element_id": "uia:1",
                        "direction": "down",
                        "reason": "scroll",
                    },
                    "test",
                ),
                config,
            )
            switch = executor.execute(
                PlannedStep("os_switch_window", {"window_id": "window:1234", "reason": "focus"}, "test"),
                config,
            )
            resize = executor.execute(
                PlannedStep(
                    "os_resize_window",
                    {"window_id": "window:1234", "x": 0, "y": 0, "width": 800, "height": 600, "reason": "resize"},
                    "test",
                ),
                config,
            )
            coord_click = executor.execute(
                PlannedStep("os_click_coordinates", {"x": 10, "y": 20, "reason": "click point"}, "test"),
                config,
            )
            pattern = executor.execute(
                PlannedStep(
                    "os_uia_pattern_action",
                    {
                        "observation_id": "11111111-1111-1111-1111-111111111111",
                        "element_id": "uia:1",
                        "action": "invoke",
                        "reason": "invoke",
                    },
                    "test",
                ),
                config,
            )
            window_state = executor.execute(
                PlannedStep("os_window_state", {"window_id": "window:1234", "action": "maximize", "reason": "maximize"}, "test"),
                config,
            )
            move_desktop = executor.execute(
                PlannedStep(
                    "os_move_window_to_desktop",
                    {
                        "window_id": "window:1234",
                        "desktop_id": "11111111-1111-1111-1111-111111111111",
                        "reason": "move",
                    },
                    "test",
                ),
                config,
            )
            desktop_action = executor.execute(
                PlannedStep("os_virtual_desktop_action", {"action": "next", "reason": "switch"}, "test"),
                config,
            )
            launch = executor.execute(
                PlannedStep("os_launch_app", {"app": "Notepad", "reason": "open editor"}, "test"),
                config,
            )
            clipboard_read = executor.execute(
                PlannedStep("os_clipboard_read", {"reason": "inspect clipboard"}, "test"),
                config,
            )
            clipboard_write = executor.execute(
                PlannedStep("os_clipboard_write", {"text": "Hello", "reason": "prepare paste"}, "test"),
                config,
            )

            self.assertEqual(click.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(typed.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(keys.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(scroll.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(switch.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(resize.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(coord_click.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(pattern.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(window_state.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(move_desktop.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(desktop_action.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(launch.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(clipboard_read.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(clipboard_write.status, ActionStatus.NEEDS_APPROVAL)

    def test_executor_routes_screen_capture_delete_to_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            executor = Executor(default_tools(), PolicyEngine())

            result = executor.execute(
                PlannedStep(
                    "screen_capture_delete",
                    {"filename": "screenshot-test.png", "reason": "cleanup"},
                    "test",
                ),
                config,
            )

            self.assertEqual(result.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(result.output["approval"]["tool_name"], "screen_capture_delete")

    def test_executor_routes_activity_policy_mutations_to_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            executor = Executor(default_tools(), PolicyEngine())

            update = executor.execute(
                PlannedStep(
                    "activity_policy_update",
                    {"retention_days": 7, "excluded_apps": ["Mail"], "reason": "privacy"},
                    "test",
                ),
                config,
            )
            prune = executor.execute(
                PlannedStep("activity_prune", {"older_than_days": 30, "reason": "retention"}, "test"),
                config,
            )

            self.assertEqual(update.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(prune.status, ActionStatus.NEEDS_APPROVAL)

    def test_executor_routes_live_browser_actions_to_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            executor = Executor(default_tools(), PolicyEngine())

            click = executor.execute(
                PlannedStep("browser_live_click", {"live_session_id": "live-1", "element_id": "live:0", "reason": "click"}, "test"),
                config,
            )
            typed = executor.execute(
                PlannedStep(
                    "browser_live_type",
                    {"live_session_id": "live-1", "element_id": "live:1", "text": "Hello", "reason": "type"},
                    "test",
                ),
                config,
            )
            screenshot = executor.execute(
                PlannedStep("browser_live_screenshot", {"live_session_id": "live-1", "reason": "inspect page"}, "test"),
                config,
            )
            close_tab = executor.execute(
                PlannedStep("browser_live_close_tab", {"live_session_id": "live-1", "reason": "cleanup"}, "test"),
                config,
            )
            select = executor.execute(
                PlannedStep(
                    "browser_live_select_option",
                    {"live_session_id": "live-1", "element_id": "live:2", "values": ["daily"], "reason": "set filter"},
                    "test",
                ),
                config,
            )
            press = executor.execute(
                PlannedStep("browser_live_press_key", {"live_session_id": "live-1", "shortcut": "Enter", "reason": "submit"}, "test"),
                config,
            )
            upload = executor.execute(
                PlannedStep(
                    "browser_live_upload_file",
                    {"live_session_id": "live-1", "element_id": "live:3", "path": "report.txt", "reason": "attach"},
                    "test",
                ),
                config,
            )
            download = executor.execute(
                PlannedStep(
                    "browser_live_download",
                    {"live_session_id": "live-1", "element_id": "live:4", "reason": "download"},
                    "test",
                ),
                config,
            )
            pdf = executor.execute(
                PlannedStep("browser_live_save_pdf", {"live_session_id": "live-1", "reason": "archive"}, "test"),
                config,
            )
            js = executor.execute(
                PlannedStep("browser_live_evaluate_js", {"live_session_id": "live-1", "code": "() => document.title", "reason": "inspect"}, "test"),
                config,
            )
            close = executor.execute(
                PlannedStep("browser_live_close", {"live_session_id": "live-1", "reason": "cleanup"}, "test"),
                config,
            )

            self.assertEqual(click.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(typed.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(screenshot.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(close_tab.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(select.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(press.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(upload.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(download.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(pdf.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(js.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(close.status, ActionStatus.NEEDS_APPROVAL)

    def test_executor_rejects_schema_enum_violations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            executor = Executor(default_tools(), PolicyEngine())

            result = executor.execute(
                PlannedStep("memory_summary", {"period": "century"}, "test"),
                config,
            )

            self.assertEqual(result.status, ActionStatus.FAILED)
            self.assertIn("must be one of", result.error or "")


if __name__ == "__main__":
    unittest.main()
