import json
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

from humungousaur.api import create_api_server
from humungousaur.config import AgentConfig
from humungousaur.cognition import TriggerStore, WakeupStore, WakeupStatus
from humungousaur.orchestrator import AgentOrchestrator
from humungousaur.safety.audit import AuditLog
from humungousaur.tools.browser_tools import BrowserSessionStore


class APITests(unittest.TestCase):
    def test_api_serves_dashboard_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            with running_api(AgentConfig(workspace=workspace, data_dir=workspace / "artifacts")) as base_url:
                html = api_get_text(base_url, "/")
                css = api_get_text(base_url, "/dashboard/styles.css")
                js = api_get_text(base_url, "/dashboard/app.js")

                self.assertIn("Humungousaur", html)
                self.assertIn("commandForm", html)
                self.assertIn("cancelRunBtn", html)
                self.assertIn("modelProviderSelect", html)
                self.assertIn("modelNameInput", html)
                self.assertIn("modelApiKeyEnvInput", html)
                self.assertIn("dryRunToggle", html)
                self.assertIn("permissions", html)
                self.assertIn("readRootForm", html)
                self.assertIn("browserSessions", html)
                self.assertIn("screenCaptures", html)
                self.assertIn("memorySummaryBtn", html)
                self.assertIn("memoryProfile", html)
                self.assertIn(".topbar", css)
                self.assertIn(".modelRow", css)
                self.assertIn(".inlineToggle", css)
                self.assertIn(".notice", css)
                self.assertIn(".memoryRecap", css)
                self.assertIn("refreshAll", js)
                self.assertIn("startTimelinePolling", js)
                self.assertIn("cancelCurrentRun", js)
                self.assertIn("renderPermissions", js)
                self.assertIn("renderCapabilityGroup", js)
                self.assertIn("renderBrowserSession", js)
                self.assertIn("renderScreenCapture", js)
                self.assertIn("renderMemorySummary", js)
                self.assertIn("renderMemoryProfile", js)
                self.assertIn("renderApprovalPreview", js)
                self.assertIn("Forget browser session", js)
                self.assertIn("editApproval", js)
                self.assertIn("renderSystemStatus", js)
                self.assertIn("addReadRoot", js)
                self.assertIn("rebuildIndex", js)
                self.assertIn("model_provider", js)
                self.assertIn("model_api_key_env", js)

    def test_api_run_plan_and_memory_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# API Demo\n\nLocal runtime.", encoding="utf-8")
            with running_api(AgentConfig(workspace=workspace, data_dir=workspace / "artifacts")) as base_url:
                health = api_get(base_url, "/health")
                self.assertEqual(health["status"], "ok")
                self.assertIn("system", health)
                self.assertIn("overall_status", health["system"])
                system_status = api_get(base_url, "/system/status")
                self.assertEqual(system_status["workspace"], str(workspace.resolve()))
                screen_captures = api_get(base_url, "/screen/captures")
                self.assertFalse(screen_captures["image_bytes_served"])
                self.assertEqual(screen_captures["captures"], [])
                self.assertEqual(api_get(base_url, "/plugins"), [])

                permissions = api_get(base_url, "/permissions")
                self.assertEqual(permissions["workspace"], str(workspace.resolve()))
                self.assertIn("index", permissions)
                self.assertIn("plugins", permissions)
                self.assertIn(str(workspace.resolve()), permissions["allowed_read_roots"])
                self.assertIn(str((workspace / "artifacts").resolve()), permissions["allowed_write_roots"])
                self.assertIn("python", permissions["shell"]["allowed_commands"])
                self.assertIn("trusted_dev", permissions["shell"]["command_profiles"])
                self.assertEqual(permissions["plugins"]["manifest_count"], 0)
                group_names = {group["name"] for group in permissions["capability_groups"]}
                self.assertIn("activity", group_names)
                self.assertIn("files", group_names)
                self.assertIn("browser", group_names)
                self.assertIn("memory", group_names)
                self.assertIn("os", group_names)
                self.assertIn("plugins", group_names)
                self.assertIn("screen", group_names)
                self.assertIn("shell", group_names)
                self.assertIn("integrations", group_names)
                self.assertIn("voice", group_names)
                shell_tool = next(tool for tool in permissions["tools"] if tool["name"] == "run_shell_command")
                plugin_tool = next(tool for tool in permissions["tools"] if tool["name"] == "plugin_manifests")
                sessions_tool = next(tool for tool in permissions["tools"] if tool["name"] == "browser_sessions")
                back_tool = next(tool for tool in permissions["tools"] if tool["name"] == "browser_back")
                forget_tool = next(tool for tool in permissions["tools"] if tool["name"] == "browser_forget_session")
                self.assertEqual(shell_tool["capability_group"], "shell")
                self.assertEqual(shell_tool["risk_level"], "high")
                self.assertTrue(shell_tool["requires_approval"])
                self.assertFalse(shell_tool["allowed_without_approval"])
                self.assertEqual(shell_tool["input_schema"]["required"], ["argv"])
                self.assertEqual(plugin_tool["capability_group"], "plugins")
                self.assertFalse(plugin_tool["requires_approval"])
                self.assertEqual(sessions_tool["capability_group"], "browser")
                self.assertEqual(sessions_tool["risk_level"], "low")
                self.assertFalse(sessions_tool["requires_approval"])
                self.assertTrue(sessions_tool["allowed_without_approval"])
                self.assertEqual(back_tool["capability_group"], "browser")
                self.assertEqual(back_tool["risk_level"], "low")
                self.assertFalse(back_tool["requires_approval"])
                self.assertTrue(back_tool["allowed_without_approval"])
                self.assertEqual(forget_tool["capability_group"], "browser")
                self.assertEqual(forget_tool["risk_level"], "medium")
                self.assertTrue(forget_tool["requires_approval"])
                self.assertFalse(forget_tool["allowed_without_approval"])

                benchmarks = api_get(base_url, "/benchmarks?iterations=1&q=runtime")
                self.assertEqual(benchmarks["iterations"], 1)
                self.assertIn("permissions_snapshot", {item["name"] for item in benchmarks["benchmarks"]})

                index_status = api_get(base_url, "/index/status")
                self.assertFalse(index_status["usable"])
                rebuilt = api_post(base_url, "/index/rebuild", {})
                self.assertTrue(rebuilt["usable"])
                self.assertGreaterEqual(rebuilt["indexed_files"], 1)

                run = api_post(base_url, "/runs", {"request": 'read_file {"path":"README.md"}', "planner": "explicit"})
                self.assertIn("README.md", run["final_response"])
                stimulus = api_post(
                    base_url,
                    "/stimuli",
                    {"source": "voice_transcript", "text": 'read_file {"path":"README.md"}', "response_mode": "voice_prepare", "planner": "explicit"},
                )
                self.assertEqual(stimulus["decision"]["decision"], "respond")
                self.assertEqual(stimulus["run"]["results"][0]["tool_name"], "read_file")
                self.assertIn("README.md", stimulus["run"]["final_response"])
                self.assertIn("response_id", stimulus["voice_result"])

                plans = api_get(base_url, "/plans?limit=1")
                self.assertEqual(plans[0]["run_id"], stimulus["run"]["run_id"])
                self.assertEqual(plans[0]["used_provider"], "explicit")

                memory = api_get(base_url, "/memory?limit=5")
                self.assertIn(stimulus["run"]["run_id"], [event["payload"].get("run_id") for event in memory])
                memory_summary = api_get(base_url, "/memory/summary?period=recent")
                self.assertGreaterEqual(memory_summary["total_events"], 1)
                self.assertIn("read_file", memory_summary["summary"])
                api_post(
                    base_url,
                    "/runs",
                    {"request": 'memory_write {"kind":"preference","text":"I prefer compact API summaries"}', "planner": "explicit"},
                )
                profile = api_get(base_url, "/memory/profile")
                self.assertIn("compact API summaries", profile["preferences"][0]["text"])

    def test_api_reports_local_plugin_manifests_and_declared_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            plugin_dir = workspace / ".umang" / "plugins" / "demo"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "plugin.json").write_text(
                json.dumps(
                    {
                        "name": "demo-plugin",
                        "version": "0.1.0",
                        "capability_group": "plugins.demo",
                        "tools": [
                            {
                                "name": "plugin_demo_echo",
                                "description": "Echo plugin input.",
                                "risk_level": "low",
                                "input_schema": {"type": "object", "properties": {}},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with running_api(AgentConfig(workspace=workspace, data_dir=workspace / "artifacts")) as base_url:
                plugins = api_get(base_url, "/plugins?detail=true")
                permissions = api_get(base_url, "/permissions")
                declared_tool = next(tool for tool in permissions["tools"] if tool["name"] == "plugin_demo_echo")

            self.assertEqual(plugins[0]["name"], "demo-plugin")
            self.assertEqual(plugins[0]["tools"][0]["execution_status"], "blocked_until_trusted_runtime")
            self.assertEqual(permissions["plugins"]["manifest_count"], 1)
            self.assertEqual(permissions["plugins"]["declared_tool_count"], 1)
            self.assertEqual(declared_tool["risk_level"], "blocked")
            self.assertEqual(declared_tool["capability_group"], "plugins.demo")
            self.assertFalse(declared_tool["allowed_with_approval"])

    def test_api_async_run_accepts_dashboard_model_runtime_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Runtime Options\n\nModel UI smoke.", encoding="utf-8")
            with running_api(AgentConfig(workspace=workspace, data_dir=workspace / "artifacts")) as base_url:
                queued = api_post(
                    base_url,
                    "/runs/async",
                    {
                        "request": "summarize this project",
                        "planner": "model",
                        "model_provider": "local-openai",
                        "model": "gpt-oss:20b",
                        "model_base_url": "http://127.0.0.1:9/v1",
                        "model_api_key_env": "LOCAL_LLM_API_KEY",
                        "model_timeout_seconds": 0.2,
                        "dry_run": True,
                    },
                )
                run = wait_for_finished_run(base_url, queued["run_id"])
                trace = api_get(base_url, f"/plans?run_id={queued['run_id']}")

                self.assertIn(run["status"], {"succeeded", "failed"})
                self.assertEqual(trace["requested_provider"], "model")
                self.assertTrue(trace["fallback_used"])
                self.assertIn("local-openai", trace["error"])
                self.assertNotIn("LOCAL_LLM_API_KEY=", json.dumps(trace))

    def test_api_runs_bounded_autonomous_cycles_for_due_wakeup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Autonomous API\n\nCycle endpoint works.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()
            WakeupStore(config.cognition_db_path).schedule(
                scheduled_for=_utc_seconds_from_now(-1),
                event_type="STIMULUS",
                payload={
                    "text": 'read_file {"path":"README.md"}',
                    "source": "wakeup",
                    "metadata": {"should_run_agent": True, "intent": "task"},
                    "response_mode": "silent",
                },
                reason="API due wakeup.",
            )

            with running_api(config) as base_url:
                before = api_get(base_url, "/autonomous/status?limit=5")
                loop = api_post(
                    base_url,
                    "/autonomous/cycles",
                    {"max_cycles": 3, "stop_after_idle_cycles": 1, "planner": "explicit"},
                )
                after = api_get(base_url, "/autonomous/status?limit=5")

            self.assertEqual(len(before["scheduled_wakeups"]), 1)
            self.assertEqual(loop["stopped_reason"], "idle")
            self.assertEqual(loop["cycles"][0]["status"], "run_finished")
            self.assertEqual(loop["cycles"][1]["status"], "no_op")
            self.assertEqual(after["scheduled_wakeups"], [])
            self.assertEqual(after["recent_wakeups"][0]["status"], WakeupStatus.FIRED)

    def test_api_evaluates_structured_triggers_into_autonomous_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            trigger = TriggerStore(config.cognition_db_path).create(
                name="File changed trigger",
                match_source="file_event",
                match_stimulus_type="changed",
                conditions={"metadata_equals": {"workspace": "api-test"}},
                payload={
                    "text": "review the changed file",
                    "metadata": {"should_run_agent": True, "intent": "task"},
                    "response_mode": "silent",
                },
                reason="API trigger evaluation test.",
            )

            with running_api(config) as base_url:
                result = api_post(
                    base_url,
                    "/triggers/evaluate",
                    {
                        "source": "file_event",
                        "stimulus_type": "changed",
                        "metadata": {"workspace": "api-test"},
                        "payload": {"path": "README.md"},
                        "stimulus_id": "stim-api",
                    },
                )
                status = api_get(base_url, "/autonomous/status?limit=5")

            self.assertEqual(result["fired"][0]["trigger"]["trigger_id"], trigger.trigger_id)
            self.assertEqual(result["fired"][0]["event"]["payload"]["metadata"]["triggered_by"]["stimulus_id"], "stim-api")
            self.assertEqual(status["queued_events"][0]["payload"]["text"], "review the changed file")
            self.assertEqual(status["recent_triggers"][0]["fire_count"], 1)

    def test_api_approval_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            with running_api(AgentConfig(workspace=workspace, data_dir=workspace / "artifacts")) as base_url:
                run = api_post(base_url, "/runs", {"request": 'run_shell_command {"argv":["python","--version"]}', "planner": "explicit"})
                token = run["approvals"][0]["approval_token"]

                pending = api_get(base_url, "/approvals?limit=1")
                self.assertEqual(pending[0]["approval_token"], token)
                paused = api_get(base_url, f"/runs/{run['run_id']}")
                self.assertEqual(paused["status"], "needs_approval")
                self.assertIsNone(paused["finished_at"])

                approved = api_post(base_url, f"/approvals/{token}/approve", {"note": "api test"})
                self.assertEqual(approved["run_id"], run["run_id"])
                self.assertIn("Python", approved["stdout"])

                all_approvals = api_get(base_url, "/approvals?status=all&limit=1")
                self.assertEqual(all_approvals[0]["status"], "executed")
                source_run = api_get(base_url, f"/runs/{run['run_id']}")
                self.assertEqual(source_run["status"], "succeeded")
                timeline = api_get(base_url, f"/runs/{run['run_id']}/timeline?limit=100")
                event_types = [event["event_type"] for event in timeline]
                self.assertIn("approval_approved", event_types)
                self.assertIn("run_waiting_for_approval", event_types)
                self.assertIn("run_finished", event_types)

    def test_api_approval_input_can_be_edited_before_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            with running_api(AgentConfig(workspace=workspace, data_dir=workspace / "artifacts")) as base_url:
                run = api_post(base_url, "/runs", {"request": 'run_shell_command {"argv":["python","--version"]}', "planner": "explicit"})
                token = run["approvals"][0]["approval_token"]

                edited = api_post(
                    base_url,
                    f"/approvals/{token}/edit",
                    {"tool_input": {"argv": ["python", "-V"]}, "note": "api edit"},
                )
                pending = api_get(base_url, "/approvals?limit=1")
                approved = api_post(base_url, f"/approvals/{token}/approve", {"note": "api approved edit"})

                self.assertEqual(edited["approval"]["tool_input"], {"argv": ["python", "-V"]})
                self.assertEqual(pending[0]["tool_input"], {"argv": ["python", "-V"]})
                self.assertIn("Python", approved["stdout"])
                timeline = api_get(base_url, f"/runs/{run['run_id']}/timeline?limit=100")
                self.assertIn("approval_updated", [event["event_type"] for event in timeline])

    def test_api_rejects_approval_on_source_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            with running_api(AgentConfig(workspace=workspace, data_dir=workspace / "artifacts")) as base_url:
                run = api_post(base_url, "/runs", {"request": 'run_shell_command {"argv":["python","--version"]}', "planner": "explicit"})
                token = run["approvals"][0]["approval_token"]

                rejected = api_post(base_url, f"/approvals/{token}/reject", {"note": "api test reject"})

                self.assertEqual(rejected["run_id"], run["run_id"])
                self.assertEqual(rejected["approval"]["status"], "rejected")
                source_run = api_get(base_url, f"/runs/{run['run_id']}")
                self.assertEqual(source_run["status"], "blocked")
                self.assertIn("Approval rejected", source_run["final_response"])
                timeline = api_get(base_url, f"/runs/{run['run_id']}/timeline?limit=100")
                event_types = [event["event_type"] for event in timeline]
                self.assertIn("approval_rejected", event_types)
                self.assertIn("run_finished", event_types)

    def test_api_async_run_timeline_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Async Demo\n\nTimeline runtime.", encoding="utf-8")
            with running_api(AgentConfig(workspace=workspace, data_dir=workspace / "artifacts")) as base_url:
                queued = api_post(base_url, "/runs/async", {"request": 'read_file {"path":"README.md"}', "planner": "explicit"})
                run_id = queued["run_id"]
                self.assertEqual(queued["status"], "planned")

                run = wait_for_finished_run(base_url, run_id)
                self.assertEqual(run["status"], "succeeded")
                self.assertIn("README.md", run["final_response"])

                timeline = api_get(base_url, f"/runs/{run_id}/timeline?limit=100")
                event_types = [event["event_type"] for event in timeline]
                self.assertEqual(event_types[0], "queued")
                for expected in [
                    "run_started",
                    "plan_created",
                    "action_started",
                    "action_finished",
                    "run_finished",
                ]:
                    self.assertIn(expected, event_types)
                self.assertEqual(timeline[-1]["payload"]["status"], "succeeded")

    def test_api_cancel_run_before_worker_starts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Cancel Demo\n\nInterruptible runtime.", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()
            audit = AuditLog(config.audit_db_path)
            run_id = audit.start_run('read_file {"path":"README.md"}')
            with running_api(config) as base_url:
                cancelling = api_post(base_url, f"/runs/{run_id}/cancel", {"reason": "api test"})
                self.assertEqual(cancelling["status"], "cancelling")
                self.assertIsNotNone(cancelling["cancel_requested_at"])

            result = AgentOrchestrator(config).run('read_file {"path":"README.md"}', run_id=run_id)
            self.assertEqual(result.final_response, "Run cancelled before completing remaining actions.")

            run = audit.get_run(run_id)
            self.assertEqual(run["status"], "cancelled")
            self.assertIsNotNone(run["finished_at"])
            timeline = audit.get_run_events(run_id)
            event_types = [event["event_type"] for event in timeline]
            self.assertIn("cancel_requested", event_types)
            self.assertIn("run_cancelled", event_types)

    def test_api_permission_read_roots_are_persistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            extra = root / "external-docs"
            extra.mkdir()
            config = AgentConfig(workspace=workspace, data_dir=root / "data")

            with running_api(config) as base_url:
                updated = api_post(base_url, "/permissions/read-roots/add", {"path": str(extra)})
                self.assertIn(str(extra.resolve()), updated["extra_read_roots"])
                self.assertIn(str(extra.resolve()), updated["allowed_read_roots"])
                self.assertTrue(updated["index"]["usable"])
                self.assertIn(str(extra.resolve()), updated["index"]["allowed_read_roots"])

            with running_api(config) as base_url:
                persisted = api_get(base_url, "/permissions")
                self.assertIn(str(extra.resolve()), persisted["extra_read_roots"])
                self.assertIn(str(extra.resolve()), persisted["allowed_read_roots"])
                self.assertTrue(persisted["index"]["usable"])
                removed = api_post(base_url, "/permissions/read-roots/remove", {"path": str(extra)})
                self.assertNotIn(str(extra.resolve()), removed["extra_read_roots"])
                self.assertTrue(removed["index"]["usable"])
                self.assertNotIn(str(extra.resolve()), removed["index"]["allowed_read_roots"])

    def test_api_added_read_root_expands_agent_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            extra = root / "external-docs"
            extra.mkdir()
            external_file = extra / "research.md"
            external_file.write_text("externalneedle from added permission", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=root / "data")

            with running_api(config) as base_url:
                updated = api_post(base_url, "/permissions/read-roots/add", {"path": str(extra)})
                self.assertTrue(updated["index"]["usable"])
                run = api_post(base_url, "/runs", {"request": 'search_workspace {"query":"externalneedle"}', "planner": "explicit"})

                self.assertIn(str(external_file.resolve()), run["final_response"])
                self.assertEqual(run["results"][0]["output"]["source"], "index")

    def test_api_stale_index_falls_back_to_live_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            readme = workspace / "README.md"
            readme.write_text("oldneedle", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts")

            with running_api(config) as base_url:
                rebuilt = api_post(base_url, "/index/rebuild", {})
                self.assertTrue(rebuilt["usable"])

                readme.write_text("freshneedle with a different size", encoding="utf-8")
                status = api_get(base_url, "/index/status")
                self.assertFalse(status["usable"])
                self.assertTrue(status["stale"])

                run = api_post(base_url, "/runs", {"request": 'search_workspace {"query":"freshneedle"}', "planner": "explicit"})

                self.assertIn("freshneedle", run["final_response"])
                self.assertEqual(run["results"][0]["output"]["source"], "scan")

    def test_api_lists_browser_sessions_for_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            session = BrowserSessionStore(config.browser_sessions_db_path).create_or_update(
                {
                    "url": "http://127.0.0.1/example",
                    "title": "Browser Session",
                    "text": "Visible browser page text.",
                    "links": [{"href": "/next", "text": "Next"}],
                    "images": [{"src": "/preview.png", "alt": "Preview image", "title": ""}],
                    "forms": [
                        {
                            "action": "/submit",
                            "method": "post",
                            "inputs": [{"name": "message", "type": "textarea", "value": ""}],
                        }
                    ],
                }
            )
            BrowserSessionStore(config.browser_sessions_db_path).update_form_draft(
                session["session_id"],
                0,
                {"message": "draft"},
            )

            with running_api(config) as base_url:
                sessions = api_get(base_url, "/browser/sessions")
                detail = api_get(base_url, f"/browser/sessions/{session['session_id']}")

            self.assertEqual(sessions[0]["session_id"], session["session_id"])
            self.assertEqual(sessions[0]["forms"][0]["draft"], {"message": "draft"})
            self.assertFalse(sessions[0]["can_go_back"])
            self.assertEqual(detail["links"][0]["text"], "Next")
            self.assertEqual(detail["images"][0]["alt"], "Preview image")


class running_api:
    def __init__(self, config: AgentConfig) -> None:
        self.server = create_api_server(config, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> str:
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, exc_type, exc, tb) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def api_get(base_url: str, path: str):
    with urllib.request.urlopen(base_url + path, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def api_get_text(base_url: str, path: str):
    with urllib.request.urlopen(base_url + path, timeout=10) as response:
        return response.read().decode("utf-8")


def api_post(base_url: str, path: str, payload: dict):
    request = urllib.request.Request(
        base_url + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_finished_run(base_url: str, run_id: str, timeout_seconds: float = 5.0):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        run = api_get(base_url, f"/runs/{run_id}")
        if run["finished_at"]:
            return run
        time.sleep(0.05)
    raise AssertionError(f"Run did not finish: {run_id}")


def _utc_seconds_from_now(seconds: int) -> str:
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


if __name__ == "__main__":
    unittest.main()
