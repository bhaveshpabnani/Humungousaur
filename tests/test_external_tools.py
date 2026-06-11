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
    CitationRedirectCanonicalizeTool,
    DevicePairingPrepareTool,
    ExternalSkillCatalogTool,
    ExternalSkillShortlistPrepareTool,
    ExternalIntegrationsStatusTool,
    GoogleMeetContextPrepareTool,
    LTMRecordPrepareTool,
    LTMSearchTool,
    LTMStatusTool,
    MemoryWikiEntryPrepareTool,
    MemoryWikiSearchTool,
    OCPathResolveTool,
    NativeCapabilityDeltaAuditTool,
    ExternalExtensionCatalogTool,
    ExternalExtensionManifestTool,
    NativeProviderConfigPrepareTool,
    NativeProviderRegistryTool,
    NativeProviderRequestPrepareTool,
    WebProviderRegistryTool,
    WebProviderRequestPrepareTool,
    PolicyExplainTool,
    RSSFeedReadTool,
    RSSWatchListTool,
    RSSWatchPrepareTool,
    ScreenpipeSearchTool,
    WebReadabilityExtractTool,
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

    def test_external_extension_catalog_reads_metadata_without_executing_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            _write_native_extension_fixture(workspace)
            _write_native_docs_fixture(workspace)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = ExternalExtensionCatalogTool().execute({"kind": "all", "limit": 10}, config)
            manifest = ExternalExtensionManifestTool().execute({"extension_id": "line", "include_package": True}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertEqual(result.output["summary"]["total"], 2)
        line = next(item for item in result.output["extensions"] if item["extension_id"] == "line")
        self.assertEqual(line["channels"], ["line"])
        self.assertEqual(line["command_aliases"], ["line-login"])
        self.assertEqual(line["env_vars"], ["LINE_CHANNEL_SECRET"])
        self.assertFalse(line["provenance"]["runtime_code_executed"])
        self.assertIn(line["humungousaur_mapping"]["status"], {"native_present", "native_gap_pending", "external_tracked"})
        self.assertEqual(manifest.status, ActionStatus.SUCCEEDED)
        self.assertEqual(manifest.output["extension"]["package"]["script_names"], ["postinstall"])

    def test_external_skill_catalog_reports_category_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            _write_external_skill_fixture(workspace)
            _write_native_docs_fixture(workspace)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = ExternalSkillCatalogTool().execute({"category": "browser-and-automation", "limit": 5}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertEqual(result.output["summary"]["total"], 2)
        first = result.output["skills"][0]
        self.assertEqual(first["category"], "browser-and-automation")
        self.assertFalse(first["provenance"]["runtime_code_executed"])
        self.assertIn("coverage_status", first)

    def test_external_skill_shortlist_prepare_writes_native_proposals_without_importing_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            _write_external_skill_fixture(workspace)
            _write_native_docs_fixture(workspace)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = ExternalSkillShortlistPrepareTool().execute(
                {
                    "category": "browser-and-automation",
                    "query": "browser",
                    "max_items": 2,
                    "reason": "Prioritize owned browser skills.",
                },
                config,
            )
            path_exists = Path(result.output["path"]).exists()

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertTrue(path_exists)
        self.assertEqual(result.output["shortlist"]["status"], "prepared_for_native_implementation_review")
        self.assertGreaterEqual(result.output["shortlist"]["proposal_count"], 1)
        proposal = result.output["shortlist"]["proposals"][0]
        self.assertEqual(proposal["implementation_mode"], "humungousaur_owned_from_scratch")
        self.assertFalse(proposal["source_evidence"]["trusted_as_implementation"])

    def test_native_provider_registry_and_config_prepare_are_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                runtime_secrets={"CEREBRAS_API_KEY": "secret-value"},
            ).normalized()

            registry = NativeProviderRegistryTool().execute({"provider_id": "cerebras"}, config)
            prepared = NativeProviderConfigPrepareTool().execute(
                {"provider_id": "cerebras", "model": "llama3.1-8b", "reason": "Provider adapter smoke."},
                config,
            )
            provider_config_path_exists = Path(prepared.output["path"]).exists()

        self.assertEqual(registry.status, ActionStatus.SUCCEEDED)
        self.assertEqual(registry.output["providers"][0]["provider_id"], "cerebras")
        self.assertTrue(registry.output["providers"][0]["configured"])
        self.assertEqual(registry.output["providers"][0]["missing_env"], [])
        self.assertEqual(prepared.status, ActionStatus.SUCCEEDED)
        self.assertTrue(provider_config_path_exists)
        self.assertEqual(prepared.output["provider_config"]["api_key_value"], "redacted")
        self.assertNotIn("secret-value", json.dumps(prepared.output))

    def test_native_provider_request_prepare_supports_synthetic_and_prepared_packets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            synthetic = NativeProviderRequestPrepareTool().execute(
                {"provider_id": "synthetic", "prompt": "hello", "reason": "Exercise local provider."},
                config,
            )
            prepared = NativeProviderRequestPrepareTool().execute(
                {"provider_id": "mistral", "prompt": "hello", "reason": "Prepare provider packet."},
                config,
            )
            request_path_exists = Path(prepared.output["path"]).exists()

        self.assertEqual(synthetic.status, ActionStatus.SUCCEEDED)
        self.assertEqual(synthetic.output["status"], "completed_locally")
        self.assertFalse(synthetic.output["live_request_sent"])
        self.assertEqual(prepared.status, ActionStatus.SUCCEEDED)
        self.assertEqual(prepared.output["request"]["status"], "prepared_not_sent")
        self.assertFalse(prepared.output["request"]["live_request_sent"])
        self.assertIn("MISTRAL_API_KEY", prepared.output["request"]["missing_env"])
        self.assertTrue(request_path_exists)

    def test_web_provider_registry_and_request_prepare_are_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                runtime_secrets={"BRAVE_SEARCH_API_KEY": "brave-secret"},
            ).normalized()

            registry = WebProviderRegistryTool().execute({"provider_id": "brave"}, config)
            prepared = WebProviderRequestPrepareTool().execute(
                {"provider_id": "firecrawl", "mode": "scrape", "url": "https://example.com", "reason": "Prepare scrape."},
                config,
            )
            request_path_exists = Path(prepared.output["path"]).exists()

        self.assertEqual(registry.status, ActionStatus.SUCCEEDED)
        self.assertTrue(registry.output["providers"][0]["configured"])
        self.assertEqual(registry.output["providers"][0]["missing_env"], [])
        self.assertEqual(prepared.status, ActionStatus.SUCCEEDED)
        self.assertEqual(prepared.output["request"]["status"], "prepared_not_sent")
        self.assertIn("FIRECRAWL_API_KEY", prepared.output["request"]["missing_env"])
        self.assertNotIn("brave-secret", json.dumps(registry.output))
        self.assertTrue(request_path_exists)

    def test_web_readability_extract_and_citation_canonicalize_are_source_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            page = workspace / "page.html"
            page.write_text(
                """<!doctype html>
<html>
  <head>
    <title>Example Page</title>
    <link rel="canonical" href="https://example.com/articles/main?utm_source=nope" />
    <style>.hidden{display:none}</style>
  </head>
  <body>
    <article>
      <h1>Readable Heading</h1>
      <p>This is readable source text for citation extraction.</p>
      <a href="/next?utm_campaign=nope&keep=1">Next page</a>
    </article>
    <script>window.secret = true;</script>
  </body>
</html>
""",
                encoding="utf-8",
            )
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            extracted = WebReadabilityExtractTool().execute({"source": "page.html", "include_links": True}, config)
            canonicalized = CitationRedirectCanonicalizeTool().execute(
                {
                    "results": [
                        {
                            "title": "Wrapped",
                            "url": "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.example.com%2Farticle%2F%3Futm_source%3Dx%26keep%3D1",
                        }
                    ],
                    "source_provider": "duckduckgo",
                },
                config,
            )

        self.assertEqual(extracted.status, ActionStatus.SUCCEEDED)
        self.assertEqual(extracted.output["title"], "Example Page")
        self.assertIn("Readable Heading", extracted.output["text"])
        self.assertNotIn("window.secret", extracted.output["text"])
        self.assertEqual(extracted.output["canonical_url"], "https://example.com/articles/main?utm_source=nope")
        self.assertEqual(canonicalized.status, ActionStatus.SUCCEEDED)
        self.assertEqual(canonicalized.output["results"][0]["canonical_url"], "https://example.com/article?keep=1")

    def test_native_delta_audit_fails_on_duplicate_native_parity_task_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            _write_native_extension_fixture(workspace)
            _write_external_skill_fixture(workspace)
            docs = workspace / "docs"
            docs.mkdir(parents=True)
            duplicate = "- `[ ]` Shared duplicate task.\n"
            (docs / "NATIVE_CAPABILITY_IMPLEMENTATION_TASKS.md").write_text("# native capability\n\n" + duplicate, encoding="utf-8")
            (docs / "NATIVE_PARITY_IMPLEMENTATION_TASKS.md").write_text("# native parity\n\n" + duplicate, encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            result = NativeCapabilityDeltaAuditTool().execute({"include_examples": False}, config)

        self.assertEqual(result.status, ActionStatus.FAILED)
        self.assertEqual(result.output["summary"]["duplicate_task_count"], 1)

    def test_native_command_surfaces_prepare_local_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            pairing = DevicePairingPrepareTool().execute(
                {
                    "device_type": "phone",
                    "pairing_method": "QR",
                    "setup_steps": ["Open the mobile app", "Scan QR after approval"],
                    "required_env_refs": ["PHONE_BRIDGE_TOKEN"],
                    "approval_note": "Prepare phone pairing plan.",
                },
                config,
            )
            meet = GoogleMeetContextPrepareTool().execute(
                {
                    "meeting_url": "https://meet.google.com/abc-defg-hij",
                    "capture_goal": "Capture agenda context after consent.",
                    "approval_note": "Meeting capture needs consent.",
                },
                config,
            )
            ltm = LTMRecordPrepareTool().execute(
                {"title": "native capability note", "content": "Remember adapter gap.", "tags": ["adapter"], "reason": "Track parity work."},
                config,
            )
            ltm_search = LTMSearchTool().execute({"query": "adapter"}, config)
            pairing_path_exists = Path(pairing.output["path"]).exists()

        self.assertEqual(pairing.status, ActionStatus.SUCCEEDED)
        self.assertTrue(pairing_path_exists)
        self.assertEqual(pairing.output["pairing"]["status"], "prepared_not_paired")
        self.assertEqual(meet.status, ActionStatus.SUCCEEDED)
        self.assertEqual(meet.output["plan"]["status"], "prepared_not_joined")
        self.assertEqual(ltm.status, ActionStatus.SUCCEEDED)
        self.assertTrue(ltm.output["record"]["durable_cognitive_memory_written"])
        self.assertEqual(ltm_search.status, ActionStatus.SUCCEEDED)
        self.assertEqual(len(ltm_search.output["matches"]), 1)

    def test_oc_path_policy_and_memory_wiki_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("hello", encoding="utf-8")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            resolved = OCPathResolveTool().execute({"path": "README.md", "must_exist": True}, config)
            policy = PolicyExplainTool().execute({"include_channels": False}, config)
            prepared = MemoryWikiEntryPrepareTool().execute(
                {
                    "title": "Adapter Note",
                    "body": "native capability adapter implementation note.",
                    "tags": ["native"],
                    "evidence_refs": ["test"],
                    "reason": "Exercise Memory Wiki surface.",
                },
                config,
            )
            searched = MemoryWikiSearchTool().execute({"query": "adapter"}, config)
            ltm_status = LTMStatusTool().execute({}, config)

        self.assertEqual(resolved.status, ActionStatus.SUCCEEDED)
        self.assertTrue(resolved.output["allowed_read"])
        self.assertEqual(policy.status, ActionStatus.SUCCEEDED)
        self.assertIsNone(policy.output["selected_tool"])
        self.assertEqual(prepared.status, ActionStatus.SUCCEEDED)
        self.assertEqual(searched.status, ActionStatus.SUCCEEDED)
        self.assertEqual(len(searched.output["matches"]), 1)
        self.assertIn(ltm_status.output["vector_backend"], {"sqlite_fts5", "sqlite_like"})

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
                            "window_name": "Humungousaur",
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


def _write_native_extension_fixture(workspace: Path) -> None:
    extensions = workspace / "external_repos" / "native" / "extensions"
    line = extensions / "line"
    line.mkdir(parents=True)
    (line / "native.plugin.json").write_text(
        json.dumps(
            {
                "id": "line",
                "name": "LINE",
                "channels": ["line"],
                "commandAliases": [{"name": "line-login"}],
                "envVars": ["LINE_CHANNEL_SECRET"],
                "setup": {"requiresRuntime": True},
            }
        ),
        encoding="utf-8",
    )
    (line / "package.json").write_text(
        json.dumps({"name": "@native/line", "version": "1.0.0", "scripts": {"postinstall": "node setup.js"}}),
        encoding="utf-8",
    )
    provider = extensions / "cerebras"
    provider.mkdir(parents=True)
    (provider / "native.plugin.json").write_text(
        json.dumps({"id": "cerebras", "name": "Cerebras", "providers": ["cerebras"]}),
        encoding="utf-8",
    )


def _write_external_skill_fixture(workspace: Path) -> None:
    categories = workspace / "external_repos" / "external-skill-catalog" / "categories"
    categories.mkdir(parents=True)
    (categories / "browser-and-automation.md").write_text(
        """# Browser And Automation

**2 skills**

- [agent-browser](https://clawskills.sh/skills/acme-agent-browser) - Headless browser automation for agents.
- [form-filler](https://clawskills.sh/skills/acme-form-filler) - Fill and review forms with approval gates.
""",
        encoding="utf-8",
    )


def _write_native_docs_fixture(workspace: Path) -> None:
    docs = workspace / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "NATIVE_PARITY_IMPLEMENTATION_TASKS.md").write_text(
        "# native parity\n\n- `[ ]` Add unrelated Feishu support.\n",
        encoding="utf-8",
    )
    (docs / "NATIVE_CAPABILITY_IMPLEMENTATION_TASKS.md").write_text(
        "# native capability\n\n- `[ ]` Add LINE channel adapter.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
