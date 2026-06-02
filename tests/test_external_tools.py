import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.external_tools import ExternalIntegrationsStatusTool, ScreenpipeSearchTool


class ExternalToolTests(unittest.TestCase):
    def test_external_integrations_status_reports_reference_projects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = ExternalIntegrationsStatusTool().execute({"probe_screenpipe": False}, config)

            keys = {item["key"] for item in result.output["integrations"]}
            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertEqual(keys, {"browser_use", "screenpipe", "windows_use", "open_interpreter"})
            open_interpreter = next(item for item in result.output["integrations"] if item["key"] == "open_interpreter")
            self.assertEqual(open_interpreter["license"], "AGPL-3.0")
            self.assertIn("plugin integration", open_interpreter["install_hint"])

    def test_screenpipe_search_queries_loopback_api_and_trims_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with running_screenpipe_api() as base_url:
                result = ScreenpipeSearchTool().execute(
                    {
                        "query": "project",
                        "content_type": "all",
                        "limit": 5,
                        "base_url": base_url,
                    },
                    config,
                )

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertEqual(result.output["results"][0]["app_name"], "Code")
            self.assertIn("project deadline", result.output["results"][0]["text"])
            self.assertNotIn("x" * 1500, json.dumps(result.output))
            self.assertEqual(result.output["raw_shape"]["keys"], ["data"])

    def test_screenpipe_search_blocks_non_loopback_urls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = ScreenpipeSearchTool().execute(
                {"query": "secret", "base_url": "http://192.168.1.10:3030"},
                config,
            )

            self.assertEqual(result.status, ActionStatus.BLOCKED)
            self.assertIn("loopback", result.summary)


class running_screenpipe_api:
    def __init__(self) -> None:
        self.server = HTTPServer(("127.0.0.1", 0), self._handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> str:
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, exc_type, exc, tb) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def _handler(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path == "/health":
                    self._send({"status": "ok"})
                    return
                if parsed.path != "/search":
                    self.send_response(404)
                    self.end_headers()
                    return
                query = parse_qs(parsed.query)
                body = {
                    "data": [
                        {
                            "content_type": query.get("content_type", ["all"])[0],
                            "timestamp": "2026-06-01T12:00:00Z",
                            "app_name": "Code",
                            "window_name": "Umang",
                            "content": "project deadline " + ("x" * 2000),
                            "score": 0.9,
                        }
                    ]
                }
                self._send(body)

            def _send(self, payload: dict) -> None:
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, format: str, *args) -> None:
                return

        return Handler


if __name__ == "__main__":
    unittest.main()
