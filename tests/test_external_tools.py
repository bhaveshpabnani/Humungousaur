import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.external_tools import (
    ExternalIntegrationsStatusTool,
    RSSFeedReadTool,
    RSSWatchListTool,
    RSSWatchPrepareTool,
    ScreenpipeSearchTool,
)


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

    def test_rss_feed_read_parses_local_rss_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            feed = workspace / "feed.xml"
            feed.write_text(_rss_fixture(), encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = RSSFeedReadTool().execute({"source": "feed.xml", "max_items": 5}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertEqual(result.output["parser"], "rss")
        self.assertEqual(result.output["feed"]["title"], "Humungousaur Updates")
        self.assertEqual(result.output["item_count"], 2)
        self.assertEqual(result.output["items"][0]["title"], "Native RSS Reader")

    def test_rss_feed_read_parses_atom_and_filters_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            feed = workspace / "atom.xml"
            feed.write_text(_atom_fixture(), encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = RSSFeedReadTool().execute({"source": "atom.xml", "query": "planner", "max_items": 10}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertEqual(result.output["parser"], "atom")
        self.assertEqual(result.output["item_count"], 1)
        self.assertEqual(result.output["items"][0]["title"], "Planner Notes")

    def test_rss_watch_prepare_writes_explicit_non_scheduled_watch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            feed = workspace / "feed.xml"
            feed.write_text(_rss_fixture(), encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            prepared = RSSWatchPrepareTool().execute(
                {
                    "source": "feed.xml",
                    "cadence": "daily",
                    "summary_format": "bullet briefing",
                    "filters": ["native", "release"],
                    "notification_preference": "prepared note",
                    "reason": "Track release notes without hidden polling.",
                },
                config,
            )
            listed = RSSWatchListTool().execute({"limit": 5}, config)
            watch_path_exists = Path(prepared.output["path"]).exists()

        self.assertEqual(prepared.status, ActionStatus.SUCCEEDED)
        self.assertEqual(prepared.output["watch"]["status"], "prepared_not_scheduled")
        self.assertEqual(prepared.output["watch"]["scheduler_status"], "not_created")
        self.assertTrue(watch_path_exists)
        self.assertEqual(listed.output["watches"][0]["watch_id"], prepared.output["watch"]["watch_id"])

    def test_rss_feed_read_blocks_files_outside_allowed_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            outside = workspace.parent / "outside-feed.xml"
            outside.write_text(_rss_fixture(), encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = RSSFeedReadTool().execute({"source": str(outside)}, config)

        self.assertEqual(result.status, ActionStatus.FAILED)
        self.assertIn("outside allowed read roots", result.summary)
        outside.unlink(missing_ok=True)


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


def _rss_fixture() -> str:
    return """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Humungousaur Updates</title>
    <link>https://example.com/blog</link>
    <description>Release notes</description>
    <item>
      <title>Native RSS Reader</title>
      <link>https://example.com/blog/rss-reader</link>
      <description>Native feed parsing is now available.</description>
      <pubDate>Sun, 07 Jun 2026 09:00:00 GMT</pubDate>
      <guid>rss-reader</guid>
    </item>
    <item>
      <title>Channel Actions</title>
      <link>https://example.com/blog/channel-actions</link>
      <description>Prepared channel actions are safer.</description>
      <pubDate>Sat, 06 Jun 2026 09:00:00 GMT</pubDate>
      <guid>channel-actions</guid>
    </item>
  </channel>
</rss>
"""


def _atom_fixture() -> str:
    return """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Humungousaur Atom</title>
  <link href="https://example.com/atom" />
  <subtitle>Atom feed</subtitle>
  <entry>
    <title>Planner Notes</title>
    <link href="https://example.com/planner" />
    <summary>Planner release notes for RSS smoke.</summary>
    <updated>2026-06-07T09:00:00Z</updated>
    <id>planner</id>
  </entry>
  <entry>
    <title>Voice Notes</title>
    <link href="https://example.com/voice" />
    <summary>Voice loop update.</summary>
    <updated>2026-06-06T09:00:00Z</updated>
    <id>voice</id>
  </entry>
</feed>
"""


if __name__ == "__main__":
    unittest.main()
