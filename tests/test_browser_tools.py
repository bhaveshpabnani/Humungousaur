import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs
from unittest.mock import patch

from humungousaur.config import AgentConfig
from humungousaur.executor import Executor
from humungousaur.orchestrator import AgentOrchestrator
from humungousaur.runtime import approve_pending_action
from humungousaur.safety.policy import PolicyEngine
from humungousaur.schemas import PlannedStep
from humungousaur.schemas import ActionStatus
from humungousaur.tools import default_tools
from humungousaur.tools.browser import common as browser_common
from humungousaur.tools.browser_tools import (
    BrowserBackTool,
    BrowserClickElementTool,
    BrowserClickLinkTool,
    BrowserExtractTool,
    BrowserFindTextTool,
    BrowserFillFormTool,
    BrowserForgetSessionTool,
    BrowserLiveBackTool,
    BrowserLiveCloseTabTool,
    BrowserLiveClickCoordinatesTool,
    BrowserLiveDragTool,
    BrowserLiveDragCoordinatesTool,
    BrowserLiveDownloadTool,
    BrowserLiveDropdownOptionsTool,
    BrowserLiveEvaluateJsTool,
    BrowserLiveExtractTool,
    BrowserLiveFillFormTool,
    BrowserLiveFindElementsTool,
    BrowserLiveForwardTool,
    BrowserLiveHtmlTool,
    BrowserLiveHoverTool,
    BrowserLiveNavigateTool,
    BrowserLiveNewTabTool,
    BrowserLiveOpenTool,
    BrowserLivePageSearchTool,
    BrowserLivePressKeyTool,
    BrowserLiveQuerySelectorTool,
    BrowserLiveReloadTool,
    BrowserLiveResizeTool,
    BrowserLiveSavePdfTool,
    BrowserLiveScrollToTextTool,
    BrowserLiveSelectOptionTool,
    BrowserLiveScreenshotTool,
    BrowserLiveSearchTool,
    BrowserLiveStatusTool,
    BrowserLiveUploadFileTool,
    BrowserLiveWaitTool,
    BrowserObserveTool,
    BrowserOpenTool,
    BrowserSessionStore,
    BrowserSessionsTool,
    BrowserTypeTool,
    FetchWebPageTool,
    ResearchWebPagesTool,
    WebSearchTool,
    extract_urls,
)


class BrowserToolTests(unittest.TestCase):
    def test_extract_urls_from_request(self) -> None:
        urls = extract_urls("Research https://example.com/a and http://127.0.0.1:8000/page.")

        self.assertEqual(urls, ["https://example.com/a", "http://127.0.0.1:8000/page"])

    def test_ssl_context_uses_certifi_bundle_when_available(self) -> None:
        with patch.object(browser_common, "certifi") as certifi, patch.object(
            browser_common.ssl,
            "create_default_context",
        ) as create_default_context:
            certifi.where.return_value = "/tmp/cacert.pem"

            browser_common._ssl_context()

        create_default_context.assert_called_once_with(cafile="/tmp/cacert.pem")

    def test_fetch_web_page_extracts_text_title_and_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts", planner_provider="explicit").normalized()
            with running_web_server({"/": SAMPLE_HTML}) as base_url:
                result = FetchWebPageTool().execute({"url": base_url}, config)

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertEqual(result.output["title"], "Umang Browser Test")
            self.assertIn("Browser research needle", result.output["text"])
            self.assertEqual(result.output["links"][0]["href"], "/next")
            self.assertEqual(result.output["images"][0]["alt"], "Browser diagram")
            self.assertIn("untrusted data", result.output["safety_note"])

    def test_research_web_pages_summarizes_local_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts", planner_provider="explicit").normalized()
            with running_web_server({"/a": SAMPLE_HTML, "/b": SECOND_HTML}) as base_url:
                result = ResearchWebPagesTool().execute({"urls": [f"{base_url}/a", f"{base_url}/b"], "query": "research"}, config)

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertEqual(len(result.output["summaries"]), 2)
            self.assertIn("Browser research needle", result.output["summaries"][0]["summary"])
            self.assertIn("Browser research needle", result.output["summaries"][0]["snippets"][0]["text"])
            self.assertIn("untrusted data", result.output["safety_note"])

    def test_fetch_web_page_follows_validated_redirects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts", planner_provider="explicit").normalized()
            with running_web_server({"/redirect": (302, {"location": "/target"}, ""), "/target": SECOND_HTML}) as base_url:
                result = FetchWebPageTool().execute({"url": f"{base_url}/redirect"}, config)

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertEqual(result.output["title"], "Second Source")
            self.assertTrue(result.output["url"].endswith("/target"))

    def test_web_search_returns_candidate_urls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with patch(
                "humungousaur.tools.browser.static_tools._search_web",
                return_value=([{"title": "Rail lookup", "url": "https://example.com/rail"}], "bing", []),
            ):
                result = WebSearchTool().execute({"query": "train availability Nagpur Kharagpur", "limit": 3}, config)

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertEqual(result.output["results"][0]["url"], "https://example.com/rail")
            self.assertEqual(result.output["engine"], "bing")
            self.assertEqual(result.output["source"], "web_search")

    def test_search_result_url_normalizes_absolute_duckduckgo_redirects(self) -> None:
        from humungousaur.tools.browser.static_tools import _normalize_search_result_url

        url = _normalize_search_result_url(
            "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.ixigo.com%2Fby-train-rail%2Fnagpur-to-kharagpur-by-train"
        )

        self.assertEqual(url, "https://www.ixigo.com/by-train-rail/nagpur-to-kharagpur-by-train")

    def test_research_web_pages_discovers_urls_from_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts", planner_provider="explicit").normalized()
            with running_web_server({"/a": SAMPLE_HTML}) as base_url:
                with patch(
                    "humungousaur.tools.browser.static_tools._search_web",
                    return_value=([{"title": "Local result", "url": f"{base_url}/a"}], "bing", []),
                ):
                    result = ResearchWebPagesTool().execute({"query": "browser research"}, config)

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertEqual(len(result.output["summaries"]), 1)
            self.assertIn("Browser research needle", result.output["summaries"][0]["summary"])

    def test_fetch_web_page_blocks_unsafe_urls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            file_result = FetchWebPageTool().execute({"url": "file:///C:/secret.txt"}, config)
            credential_result = FetchWebPageTool().execute({"url": "https://user:pass@example.com"}, config)
            private_result = FetchWebPageTool().execute({"url": "http://10.0.0.1/"}, config)

            self.assertEqual(file_result.status, ActionStatus.BLOCKED)
            self.assertEqual(credential_result.status, ActionStatus.BLOCKED)
            self.assertEqual(private_result.status, ActionStatus.BLOCKED)

    def test_browser_session_open_and_click_link_persists_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with running_web_server({"/": SAMPLE_HTML, "/next": SECOND_HTML}) as base_url:
                opened = BrowserOpenTool().execute({"url": base_url}, config)
                clicked = BrowserClickLinkTool().execute(
                    {"session_id": opened.output["session_id"], "link_index": 0},
                    config,
                )

            self.assertEqual(opened.status, ActionStatus.SUCCEEDED)
            self.assertEqual(clicked.status, ActionStatus.SUCCEEDED)
            self.assertEqual(clicked.output["title"], "Second Source")
            stored = BrowserSessionStore(config.browser_sessions_db_path).get(opened.output["session_id"])
            self.assertEqual(stored["current_url"], clicked.output["current_url"])
            self.assertIn("Second source confirms", stored["text"])
            self.assertEqual(stored["history"], [base_url, f"{base_url}/next"])
            self.assertTrue(clicked.output["can_go_back"])

    def test_browser_click_element_uses_observed_link_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with running_web_server({"/": SAMPLE_HTML, "/next": SECOND_HTML}) as base_url:
                opened = BrowserOpenTool().execute({"url": base_url}, config)
                clicked = BrowserClickElementTool().execute(
                    {"session_id": opened.output["session_id"], "element_id": "link:0"},
                    config,
                )

            self.assertEqual(clicked.status, ActionStatus.SUCCEEDED)
            self.assertEqual(clicked.output["title"], "Second Source")
            self.assertEqual(clicked.output["clicked_element"]["element_id"], "link:0")
            self.assertTrue(clicked.output["can_go_back"])

    def test_browser_back_uses_local_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with running_web_server({"/": SAMPLE_HTML, "/next": SECOND_HTML}) as base_url:
                opened = BrowserOpenTool().execute({"url": base_url}, config)
                clicked = BrowserClickLinkTool().execute(
                    {"session_id": opened.output["session_id"], "link_index": 0},
                    config,
                )
                backed = BrowserBackTool().execute(
                    {"session_id": opened.output["session_id"]},
                    config,
                )

            self.assertEqual(clicked.status, ActionStatus.SUCCEEDED)
            self.assertEqual(backed.status, ActionStatus.SUCCEEDED)
            self.assertEqual(backed.output["title"], "Umang Browser Test")
            self.assertFalse(backed.output["can_go_back"])
            stored = BrowserSessionStore(config.browser_sessions_db_path).get(opened.output["session_id"])
            self.assertEqual(stored["history"], [base_url])

    def test_browser_back_requires_previous_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with running_web_server({"/": SAMPLE_HTML}) as base_url:
                opened = BrowserOpenTool().execute({"url": base_url}, config)
                backed = BrowserBackTool().execute(
                    {"session_id": opened.output["session_id"]},
                    config,
                )

            self.assertEqual(backed.status, ActionStatus.FAILED)
            self.assertIn("no previous page", backed.summary)

    def test_browser_open_extracts_forms_and_fill_saves_local_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with running_web_server({"/": FORM_HTML}) as base_url:
                opened = BrowserOpenTool().execute({"url": base_url}, config)
                filled = BrowserFillFormTool().execute(
                    {
                        "session_id": opened.output["session_id"],
                        "form_index": 0,
                        "values": {"name": "Dev", "message": "Hello"},
                    },
                    config,
                )

            self.assertEqual(opened.output["forms"][0]["fields"], ["name", "message"])
            self.assertEqual(filled.status, ActionStatus.SUCCEEDED)
            self.assertEqual(filled.output["forms"][0]["draft"], {"message": "Hello", "name": "Dev"})
            stored = BrowserSessionStore(config.browser_sessions_db_path).get(opened.output["session_id"])
            self.assertEqual(stored["form_drafts"]["0"], {"message": "Hello", "name": "Dev"})

    def test_browser_observe_returns_indexed_elements_without_text_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with running_web_server({"/": SAMPLE_HTML}) as base_url:
                opened = BrowserOpenTool().execute({"url": base_url}, config)
                observed = BrowserObserveTool().execute({"session_id": opened.output["session_id"]}, config)

            self.assertEqual(observed.status, ActionStatus.SUCCEEDED)
            self.assertFalse(observed.output["text_included"])
            self.assertNotIn("text", observed.output)
            self.assertEqual(observed.output["interactive_elements"][0]["element_id"], "link:0")
            self.assertEqual(observed.output["images"][0]["alt"], "Browser diagram")

    def test_browser_observe_returns_form_field_elements_for_typing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with running_web_server({"/": FORM_HTML}) as base_url:
                opened = BrowserOpenTool().execute({"url": base_url}, config)
                observed = BrowserObserveTool().execute({"session_id": opened.output["session_id"]}, config)

            element_ids = {element["element_id"] for element in observed.output["interactive_elements"]}
            self.assertIn("form:0", element_ids)
            self.assertIn("form:0:field:name", element_ids)
            self.assertIn("form:0:field:message", element_ids)

    def test_browser_observe_can_include_bounded_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with running_web_server({"/": SAMPLE_HTML}) as base_url:
                opened = BrowserOpenTool().execute({"url": base_url}, config)
                observed = BrowserObserveTool().execute(
                    {"session_id": opened.output["session_id"], "include_text": True, "max_chars": 20},
                    config,
                )

            self.assertEqual(observed.status, ActionStatus.SUCCEEDED)
            self.assertTrue(observed.output["text_included"])
            self.assertLessEqual(len(observed.output["text"]), 20)
            self.assertTrue(observed.output["text_truncated"])

    def test_browser_extract_returns_relevant_snippets_links_and_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with running_web_server({"/": SAMPLE_HTML}) as base_url:
                opened = BrowserOpenTool().execute({"url": base_url}, config)
                extracted = BrowserExtractTool().execute(
                    {
                        "session_id": opened.output["session_id"],
                        "query": "browser diagram next",
                        "include_links": True,
                        "include_images": True,
                        "max_snippets": 5,
                    },
                    config,
                )

            self.assertEqual(extracted.status, ActionStatus.SUCCEEDED)
            self.assertIn("Browser research needle", extracted.output["snippets"][0]["text"])
            self.assertEqual(extracted.output["links"][0]["href"], "/next")
            self.assertEqual(extracted.output["images"][0]["alt"], "Browser diagram")
            self.assertIn("untrusted data", extracted.output["safety_note"])

    def test_browser_type_updates_one_observed_form_field_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with running_web_server({"/": FORM_HTML}) as base_url:
                opened = BrowserOpenTool().execute({"url": base_url}, config)
                typed_name = BrowserTypeTool().execute(
                    {
                        "session_id": opened.output["session_id"],
                        "element_id": "form:0:field:name",
                        "text": "Dev",
                    },
                    config,
                )
                typed_message = BrowserTypeTool().execute(
                    {
                        "session_id": opened.output["session_id"],
                        "element_id": "form:0:field:message",
                        "text": " says hello",
                        "clear": False,
                    },
                    config,
                )

            self.assertEqual(typed_name.status, ActionStatus.SUCCEEDED)
            self.assertEqual(typed_message.status, ActionStatus.SUCCEEDED)
            self.assertEqual(typed_message.output["forms"][0]["draft"], {"message": " says hello", "name": "Dev"})
            self.assertEqual(typed_message.output["typed_element"]["field"], "message")

    def test_browser_type_rejects_non_field_element_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            result = BrowserTypeTool().execute(
                {"session_id": "missing", "element_id": "link:0", "text": "Dev"},
                config,
            )

            self.assertEqual(result.status, ActionStatus.FAILED)
            self.assertIn("form field", result.summary)

    def test_live_browser_status_reports_backend_without_launching(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = BrowserLiveStatusTool().execute({}, config)

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertIn("available", result.output)
            self.assertEqual(result.output["backend"], "playwright")
            self.assertEqual(result.output["source"], "live_browser_backend_status")

    def test_live_browser_open_dry_run_does_not_launch_browser(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()
            with running_web_server({"/": SAMPLE_HTML}) as base_url:
                result = BrowserLiveOpenTool().execute({"url": base_url, "headless": True}, config)

            self.assertEqual(result.status, ActionStatus.SKIPPED)
            self.assertTrue(result.output["live_browser_not_launched"])

    def test_live_browser_open_reports_missing_playwright(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with running_web_server({"/": SAMPLE_HTML}) as base_url:
                result = BrowserLiveOpenTool().execute({"url": base_url}, config)

            if result.output.get("live_session_id"):
                self.skipTest("Playwright is installed in this runtime.")
            self.assertEqual(result.status, ActionStatus.FAILED)
            self.assertIn("Playwright", result.error or "")

    def test_live_browser_open_reuses_existing_session_on_async_loop_launch_error(self) -> None:
        class FakeLiveBrowserManager:
            def __init__(self) -> None:
                self.sessions = {"live-123": {}}

            def available(self) -> bool:
                return True

            def open(self, *args, **kwargs):
                del args, kwargs
                raise RuntimeError("It looks like you are using Playwright Sync API inside the asyncio loop.")

            def new_tab(self, session_id: str, url: str):
                return {
                    "live_session_id": session_id,
                    "tabs": [{"active": True, "url": url, "title": "Source"}],
                    "active_index": 0,
                    "source": "live_browser_tabs",
                }

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with (
                running_web_server({"/": SAMPLE_HTML}) as base_url,
                patch("humungousaur.tools.browser.live_tools.LIVE_BROWSER_MANAGER", FakeLiveBrowserManager()),
            ):
                result = BrowserLiveOpenTool().execute({"url": base_url}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertTrue(result.output["reused_existing_session"])
        self.assertEqual(result.output["live_session_id"], "live-123")

    def test_live_browser_screenshot_dry_run_does_not_capture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            result = BrowserLiveScreenshotTool().execute(
                {"live_session_id": "live-test", "reason": "verify dry run"},
                config,
            )

            self.assertEqual(result.status, ActionStatus.SKIPPED)
            self.assertTrue(result.output["screenshot_not_captured"])
            self.assertFalse(result.output["image_bytes_served"])

    def test_live_browser_wait_dry_run_does_not_wait(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            result = BrowserLiveWaitTool().execute(
                {"live_session_id": "live-test", "mode": "selector", "selector": "#ready", "timeout_ms": 500},
                config,
            )

            self.assertEqual(result.status, ActionStatus.SKIPPED)
            self.assertTrue(result.output["wait_not_performed"])

    def test_live_browser_new_tab_dry_run_validates_url_without_opening(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()
            with running_web_server({"/": SAMPLE_HTML}) as base_url:
                result = BrowserLiveNewTabTool().execute({"live_session_id": "live-test", "url": base_url}, config)

            self.assertEqual(result.status, ActionStatus.SKIPPED)
            self.assertTrue(result.output["new_tab_not_opened"])

    def test_live_browser_new_tab_blocks_unsafe_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            result = BrowserLiveNewTabTool().execute({"live_session_id": "live-test", "url": "file:///C:/secret.txt"}, config)

            self.assertEqual(result.status, ActionStatus.BLOCKED)

    def test_live_browser_navigation_history_and_reload_dry_runs_do_not_mutate_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()
            with running_web_server({"/": SAMPLE_HTML}) as base_url:
                navigate = BrowserLiveNavigateTool().execute(
                    {"live_session_id": "live-test", "url": f"{base_url}/next", "new_tab": False},
                    config,
                )
            back = BrowserLiveBackTool().execute({"live_session_id": "live-test"}, config)
            forward = BrowserLiveForwardTool().execute({"live_session_id": "live-test"}, config)
            reload = BrowserLiveReloadTool().execute({"live_session_id": "live-test"}, config)

            self.assertEqual(navigate.status, ActionStatus.SKIPPED)
            self.assertEqual(back.status, ActionStatus.SKIPPED)
            self.assertEqual(forward.status, ActionStatus.SKIPPED)
            self.assertEqual(reload.status, ActionStatus.SKIPPED)
            self.assertTrue(navigate.output["navigation_not_performed"])
            self.assertTrue(back.output["history_not_changed"])
            self.assertEqual(back.output["direction"], "back")
            self.assertTrue(forward.output["history_not_changed"])
            self.assertEqual(forward.output["direction"], "forward")
            self.assertTrue(reload.output["reload_not_performed"])

    def test_live_browser_navigate_blocks_unsafe_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            result = BrowserLiveNavigateTool().execute(
                {"live_session_id": "live-test", "url": "file:///C:/secret.txt"},
                config,
            )

            self.assertEqual(result.status, ActionStatus.BLOCKED)

    def test_live_browser_selector_query_dry_run_does_not_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            result = BrowserLiveQuerySelectorTool().execute(
                {"live_session_id": "live-test", "selector": "button.primary", "max_elements": 5},
                config,
            )

            self.assertEqual(result.status, ActionStatus.SKIPPED)
            self.assertTrue(result.output["selector_not_queried"])

    def test_live_browser_html_page_search_and_find_elements_dry_runs_do_not_inspect_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            html = BrowserLiveHtmlTool().execute(
                {"live_session_id": "live-test", "selector": "main", "max_chars": 500},
                config,
            )
            page_search = BrowserLivePageSearchTool().execute(
                {"live_session_id": "live-test", "pattern": "Checkout", "css_scope": "main", "max_results": 5},
                config,
            )
            elements = BrowserLiveFindElementsTool().execute(
                {"live_session_id": "live-test", "selector": "a.product", "attributes": ["href", "data-id"], "max_results": 5},
                config,
            )
            extract = BrowserLiveExtractTool().execute(
                {"live_session_id": "live-test", "query": "Checkout", "include_links": True, "output_schema": {"type": "object"}},
                config,
            )

            self.assertEqual(html.status, ActionStatus.SKIPPED)
            self.assertEqual(page_search.status, ActionStatus.SKIPPED)
            self.assertEqual(elements.status, ActionStatus.SKIPPED)
            self.assertEqual(extract.status, ActionStatus.SKIPPED)
            self.assertTrue(html.output["html_not_read"])
            self.assertTrue(page_search.output["page_not_searched"])
            self.assertTrue(elements.output["elements_not_found"])
            self.assertTrue(extract.output["extraction_not_performed"])

    def test_live_browser_html_page_search_and_find_elements_delegate_to_manager(self) -> None:
        class FakeLiveBrowserManager:
            def html(self, session_id: str, selector: str, max_chars: int):
                return {
                    "live_session_id": session_id,
                    "selector": selector,
                    "html": "<main>Browser research needle</main>"[:max_chars],
                    "source": "live_browser_html",
                }

            def search_page(self, session_id: str, pattern: str, regex: bool, case_sensitive: bool, context_chars: int, css_scope: str, max_results: int):
                return {
                    "live_session_id": session_id,
                    "pattern": pattern,
                    "regex": regex,
                    "case_sensitive": case_sensitive,
                    "css_scope": css_scope,
                    "matches": [
                        {
                            "match_text": "needle",
                            "context": "Browser research needle",
                            "element_path": "main",
                            "char_position": 17,
                        }
                    ],
                    "total": 1,
                    "has_more": False,
                    "error": None,
                    "source": "live_browser_page_search",
                }

            def find_elements(self, session_id: str, selector: str, attributes: list[str], max_results: int, include_text: bool):
                return {
                    "live_session_id": session_id,
                    "selector": selector,
                    "attributes": attributes,
                    "elements": [{"index": 0, "tag": "a", "text": "Next", "attrs": {"href": "https://example.com"}}],
                    "total": 1,
                    "showing": 1,
                    "error": None,
                    "source": "live_browser_find_elements",
                }

            def extract(
                self,
                session_id: str,
                query: str,
                include_links: bool,
                include_images: bool,
                start_from_char: int,
                max_snippets: int,
                output_schema: dict | None,
                already_collected: list[str],
            ):
                return {
                    "live_session_id": session_id,
                    "query": query,
                    "snippets": [{"index": 0, "text": "Browser research needle", "truncated": False}],
                    "links": [{"index": 0, "text": "Next", "href": "/next", "resolved_url": "https://example.com/next"}] if include_links else [],
                    "images": [],
                    "structured_data": {"summary": "Browser research needle"} if output_schema else {},
                    "source": "live_browser_extraction",
                }

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with patch("humungousaur.tools.browser.live_tools.LIVE_BROWSER_MANAGER", FakeLiveBrowserManager()):
                html = BrowserLiveHtmlTool().execute({"live_session_id": "live-test", "selector": "main", "max_chars": 500}, config)
                page_search = BrowserLivePageSearchTool().execute({"live_session_id": "live-test", "pattern": "needle"}, config)
                elements = BrowserLiveFindElementsTool().execute(
                    {"live_session_id": "live-test", "selector": "a", "attributes": ["href"]},
                    config,
                )
                extract = BrowserLiveExtractTool().execute(
                    {
                        "live_session_id": "live-test",
                        "query": "needle",
                        "include_links": True,
                        "output_schema": {"type": "object", "properties": {"summary": {"type": "string"}}},
                        "already_collected": ["old item"],
                    },
                    config,
                )

        self.assertEqual(html.status, ActionStatus.SUCCEEDED)
        self.assertEqual(page_search.status, ActionStatus.SUCCEEDED)
        self.assertEqual(elements.status, ActionStatus.SUCCEEDED)
        self.assertEqual(extract.status, ActionStatus.SUCCEEDED)
        self.assertEqual(html.output["source"], "live_browser_html")
        self.assertEqual(page_search.output["total"], 1)
        self.assertEqual(elements.output["elements"][0]["attrs"]["href"], "https://example.com")
        self.assertEqual(extract.output["source"], "live_browser_extraction")
        self.assertEqual(extract.output["structured_data"]["summary"], "Browser research needle")

    def test_browser_use_style_live_inspection_tools_are_registered(self) -> None:
        tools = default_tools()

        self.assertIn("browser_live_html", tools)
        self.assertIn("browser_live_page_search", tools)
        self.assertIn("browser_live_find_elements", tools)
        self.assertIn("browser_live_extract", tools)
        self.assertEqual(tools["browser_live_html"].capability_group, "browser")
        self.assertEqual(tools["browser_live_page_search"].capability_group, "browser")
        self.assertEqual(tools["browser_live_find_elements"].capability_group, "browser")
        self.assertEqual(tools["browser_live_extract"].capability_group, "browser")

    def test_live_browser_search_scroll_and_dropdown_dry_runs_do_not_mutate_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            search = BrowserLiveSearchTool().execute(
                {"live_session_id": "live-test", "query": "browser use tools", "engine": "duckduckgo"},
                config,
            )
            scroll_to_text = BrowserLiveScrollToTextTool().execute(
                {"live_session_id": "live-test", "text": "Checkout", "exact": False},
                config,
            )
            dropdown = BrowserLiveDropdownOptionsTool().execute(
                {"live_session_id": "live-test", "element_id": "live:2", "max_options": 5},
                config,
            )

            self.assertEqual(search.status, ActionStatus.SKIPPED)
            self.assertEqual(scroll_to_text.status, ActionStatus.SKIPPED)
            self.assertEqual(dropdown.status, ActionStatus.SKIPPED)
            self.assertTrue(search.output["search_not_performed"])
            self.assertTrue(scroll_to_text.output["scroll_not_performed"])
            self.assertTrue(dropdown.output["dropdown_not_queried"])

    def test_live_browser_approved_actions_dry_run_do_not_mutate_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            close_tab = BrowserLiveCloseTabTool().execute(
                {"live_session_id": "live-test", "reason": "cleanup"},
                config,
            )
            select = BrowserLiveSelectOptionTool().execute(
                {"live_session_id": "live-test", "element_id": "live:2", "values": ["weekly"], "reason": "set filter"},
                config,
            )
            press = BrowserLivePressKeyTool().execute(
                {"live_session_id": "live-test", "shortcut": "Enter", "reason": "submit field"},
                config,
            )
            coordinate_click = BrowserLiveClickCoordinatesTool().execute(
                {"live_session_id": "live-test", "x": 25, "y": 40, "reason": "click canvas control"},
                config,
            )

            self.assertEqual(close_tab.status, ActionStatus.SKIPPED)
            self.assertEqual(select.status, ActionStatus.SKIPPED)
            self.assertEqual(press.status, ActionStatus.SKIPPED)
            self.assertEqual(coordinate_click.status, ActionStatus.SKIPPED)
            self.assertTrue(close_tab.output["tab_not_closed"])
            self.assertTrue(select.output["options_not_selected"])
            self.assertTrue(press.output["key_not_pressed"])
            self.assertTrue(coordinate_click.output["coordinates_not_clicked"])

    def test_live_browser_hover_and_drag_dry_runs_do_not_mutate_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            hover = BrowserLiveHoverTool().execute(
                {"live_session_id": "live-test", "element_id": "live:1"},
                config,
            )
            drag = BrowserLiveDragCoordinatesTool().execute(
                {"live_session_id": "live-test", "start_x": 10, "start_y": 20, "end_x": 80, "end_y": 120, "reason": "move slider"},
                config,
            )
            element_drag = BrowserLiveDragTool().execute(
                {"live_session_id": "live-test", "start_element_id": "live:1", "end_element_id": "live:2", "reason": "reorder cards"},
                config,
            )
            fill = BrowserLiveFillFormTool().execute(
                {
                    "live_session_id": "live-test",
                    "fields": [{"element_id": "live:3", "text": "hello"}],
                    "reason": "fill observed fields",
                },
                config,
            )
            resize = BrowserLiveResizeTool().execute(
                {"live_session_id": "live-test", "width": 1440, "height": 900},
                config,
            )

            self.assertEqual(hover.status, ActionStatus.SKIPPED)
            self.assertEqual(drag.status, ActionStatus.SKIPPED)
            self.assertEqual(element_drag.status, ActionStatus.SKIPPED)
            self.assertEqual(fill.status, ActionStatus.SKIPPED)
            self.assertEqual(resize.status, ActionStatus.SKIPPED)
            self.assertTrue(hover.output["hover_not_performed"])
            self.assertTrue(drag.output["drag_not_performed"])
            self.assertTrue(element_drag.output["drag_not_performed"])
            self.assertTrue(fill.output["fields_not_filled"])
            self.assertTrue(resize.output["resize_not_performed"])
            self.assertEqual(drag.output["start"], {"x": 10, "y": 20})
            self.assertEqual(drag.output["end"], {"x": 80, "y": 120})
            self.assertEqual(fill.output["field_count"], 1)
            self.assertEqual(resize.output["viewport"], {"width": 1440, "height": 900})

    def test_live_browser_coordinate_click_requires_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            executor = Executor(default_tools(), PolicyEngine())

            result = executor.execute(
                PlannedStep(
                    "browser_live_click_coordinates",
                    {"live_session_id": "live-test", "x": 20, "y": 40, "reason": "click canvas"},
                    "test",
                ),
                config,
            )

            self.assertEqual(result.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(result.output["approval"]["tool_name"], "browser_live_click_coordinates")

    def test_live_browser_coordinate_drag_requires_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            executor = Executor(default_tools(), PolicyEngine())

            result = executor.execute(
                PlannedStep(
                    "browser_live_drag_coordinates",
                    {"live_session_id": "live-test", "start_x": 10, "start_y": 20, "end_x": 80, "end_y": 120, "reason": "move slider"},
                    "test",
                ),
                config,
            )

            self.assertEqual(result.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(result.output["approval"]["tool_name"], "browser_live_drag_coordinates")

    def test_live_browser_upload_dry_run_validates_allowed_file_without_uploading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            upload = workspace / "report.txt"
            upload.write_text("safe upload fixture", encoding="utf-8")
            config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                dry_run=True,
            ).normalized()

            result = BrowserLiveUploadFileTool().execute(
                {"live_session_id": "live-test", "element_id": "live:4", "path": "report.txt", "reason": "attach report"},
                config,
            )

            self.assertEqual(result.status, ActionStatus.SKIPPED)
            self.assertTrue(result.output["file_not_uploaded"])
            self.assertEqual(result.output["filename"], "report.txt")
            self.assertFalse(result.output["path_returned"])

    def test_live_browser_upload_blocks_file_outside_allowed_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            outside = root / "secret.txt"
            outside.write_text("secret", encoding="utf-8")
            config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                dry_run=True,
            ).normalized()

            result = BrowserLiveUploadFileTool().execute(
                {"live_session_id": "live-test", "element_id": "live:4", "path": str(outside), "reason": "attach"},
                config,
            )

            self.assertEqual(result.status, ActionStatus.BLOCKED)
            self.assertIn("outside allowed read roots", result.error or "")

    def test_live_browser_download_pdf_and_js_dry_runs_do_not_execute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            download = BrowserLiveDownloadTool().execute(
                {"live_session_id": "live-test", "element_id": "live:5", "reason": "save export"},
                config,
            )
            pdf = BrowserLiveSavePdfTool().execute(
                {"live_session_id": "live-test", "filename": "Export Report.pdf", "reason": "archive page"},
                config,
            )
            js = BrowserLiveEvaluateJsTool().execute(
                {"live_session_id": "live-test", "code": "() => document.title", "reason": "extract title"},
                config,
            )

            self.assertEqual(download.status, ActionStatus.SKIPPED)
            self.assertEqual(pdf.status, ActionStatus.SKIPPED)
            self.assertEqual(js.status, ActionStatus.SKIPPED)
            self.assertTrue(download.output["download_not_started"])
            self.assertTrue(pdf.output["pdf_not_saved"])
            self.assertTrue(js.output["js_not_evaluated"])
            self.assertEqual(pdf.output["filename"], "Export-Report.pdf")

    def test_live_browser_js_blocks_oversized_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                dry_run=True,
            ).normalized()

            result = BrowserLiveEvaluateJsTool().execute(
                {"live_session_id": "live-test", "code": "x" * 5000, "reason": "too large"},
                config,
            )

            self.assertEqual(result.status, ActionStatus.BLOCKED)
            self.assertIn("JavaScript exceeds", result.summary)

    def test_browser_find_text_returns_stored_page_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with running_web_server({"/": SAMPLE_HTML}) as base_url:
                opened = BrowserOpenTool().execute({"url": base_url}, config)
                found = BrowserFindTextTool().execute(
                    {"session_id": opened.output["session_id"], "text": "research needle", "max_matches": 3},
                    config,
                )

            self.assertEqual(found.status, ActionStatus.SUCCEEDED)
            self.assertIn("Browser research needle", found.output["matches"][0]["text"])
            self.assertEqual(found.output["source"], "browser_text_find")

    def test_browser_sessions_lists_metadata_without_page_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            store = BrowserSessionStore(config.browser_sessions_db_path)
            session = store.create_or_update(
                {
                    "url": "http://127.0.0.1/example",
                    "title": "Metadata Session",
                    "text": "Sensitive local page text should not be returned.",
                    "links": [{"href": "/next", "text": "Next"}],
                    "images": [{"src": "/image.png", "alt": "Preview", "title": ""}],
                    "forms": [
                        {
                            "action": "/submit",
                            "method": "post",
                            "inputs": [{"name": "message", "type": "textarea", "value": ""}],
                        }
                    ],
                }
            )
            store.update_form_draft(session["session_id"], 0, {"message": "draft"})

            result = BrowserSessionsTool().execute({"limit": 5}, config)

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertFalse(result.output["page_text_returned"])
            self.assertEqual(result.output["sessions"][0]["session_id"], session["session_id"])
            self.assertEqual(result.output["sessions"][0]["link_count"], 1)
            self.assertEqual(result.output["sessions"][0]["image_count"], 1)
            self.assertFalse(result.output["sessions"][0]["can_go_back"])
            self.assertTrue(result.output["sessions"][0]["has_form_drafts"])
            self.assertNotIn("Sensitive local page text", str(result.output))

    def test_browser_forget_session_removes_local_state_without_returning_page_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            store = BrowserSessionStore(config.browser_sessions_db_path)
            session = store.create_or_update(
                {
                    "url": "http://127.0.0.1/example",
                    "title": "Forgettable",
                    "text": "Sensitive page text should stay out of deletion output.",
                    "links": [{"href": "/next", "text": "Next"}],
                    "forms": [
                        {
                            "action": "/submit",
                            "method": "post",
                            "inputs": [{"name": "message", "type": "textarea", "value": ""}],
                        }
                    ],
                }
            )
            store.update_form_draft(session["session_id"], 0, {"message": "draft"})

            result = BrowserForgetSessionTool().execute(
                {"session_id": session["session_id"], "reason": "cleanup"},
                config,
            )

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertEqual(result.output["session_id"], session["session_id"])
            self.assertTrue(result.output["had_form_drafts"])
            self.assertNotIn("Sensitive page text", str(result.output))
            with self.assertRaises(KeyError):
                store.get(session["session_id"])

    def test_browser_forget_session_is_approval_gated_by_executor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            session = BrowserSessionStore(config.browser_sessions_db_path).create_or_update(
                {
                    "url": "http://127.0.0.1/example",
                    "title": "Needs Approval",
                    "text": "Local browser state.",
                    "links": [],
                    "forms": [],
                }
            )
            executor = Executor(default_tools(), PolicyEngine())
            step = PlannedStep(
                "browser_forget_session",
                {"session_id": session["session_id"], "reason": "cleanup"},
                "Forget stale local browser state.",
            )

            paused = executor.execute(step, config)
            approved = executor.execute(step, config, approved=True)

            self.assertEqual(paused.status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(paused.output["approval"]["tool_name"], "browser_forget_session")
            self.assertEqual(approved.status, ActionStatus.SUCCEEDED)
            with self.assertRaises(KeyError):
                BrowserSessionStore(config.browser_sessions_db_path).get(session["session_id"])

    def test_browser_fill_rejects_unknown_form_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with running_web_server({"/": FORM_HTML}) as base_url:
                opened = BrowserOpenTool().execute({"url": base_url}, config)
                filled = BrowserFillFormTool().execute(
                    {
                        "session_id": opened.output["session_id"],
                        "form_index": 0,
                        "values": {"unknown": "value"},
                    },
                    config,
                )

            self.assertEqual(filled.status, ActionStatus.FAILED)
            self.assertIn("Unknown form fields", filled.error or "")

    def test_browser_form_submit_requires_approval_and_replays(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts", planner_provider="explicit").normalized()
            with running_web_server({"/": FORM_HTML}) as base_url:
                opened = BrowserOpenTool().execute({"url": base_url}, config)
                fill_result = AgentOrchestrator(config).run(
                    f'browser_fill_form {{"session_id":"{opened.output["session_id"]}","form_index":0,"values":{{"name":"Dev","message":"Hello"}}}}'
                )
                submit_result = AgentOrchestrator(config).run(
                    f'browser_submit_form {{"session_id":"{opened.output["session_id"]}","form_index":0}}'
                )

                approved = approve_pending_action(
                    config,
                    submit_result.approvals[0].approval_token,
                    "submit form test",
                )

            self.assertIn("Prepared form 0", fill_result.results[0].summary)
            self.assertEqual(submit_result.results[0].status, ActionStatus.NEEDS_APPROVAL)
            self.assertEqual(submit_result.approvals[0].tool_name, "browser_submit_form")
            self.assertIn("Submitted form 0", approved["summary"])
            stored = BrowserSessionStore(config.browser_sessions_db_path).get(opened.output["session_id"])
            self.assertEqual(stored["title"], "Submitted")
            self.assertIn("Dev", stored["text"])

    def test_browser_click_link_blocks_unsafe_resolved_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with running_web_server({"/": UNSAFE_LINK_HTML}) as base_url:
                opened = BrowserOpenTool().execute({"url": base_url}, config)
                clicked = BrowserClickLinkTool().execute(
                    {"session_id": opened.output["session_id"], "link_index": 0},
                    config,
                )

            self.assertEqual(clicked.status, ActionStatus.BLOCKED)
            self.assertIn("Private, local", clicked.summary)

    def test_orchestrator_opens_browser_session_for_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit")
            with running_web_server({"/": SAMPLE_HTML}) as base_url:
                result = AgentOrchestrator(config).run(f'browser_open {{"url":"{base_url}"}}')

            self.assertIn("browser_open: succeeded", result.final_response)
            self.assertIn("Umang Browser Test", result.final_response)
            self.assertEqual(result.results[0].tool_name, "browser_open")

    def test_orchestrator_clicks_existing_browser_session_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit").normalized()
            with running_web_server({"/": SAMPLE_HTML, "/next": SECOND_HTML}) as base_url:
                opened = BrowserOpenTool().execute({"url": base_url}, config)
                result = AgentOrchestrator(config).run(
                    f'browser_click_link {{"session_id":"{opened.output["session_id"]}","link_index":0}}'
                )

            self.assertIn("Second Source", result.final_response)
            self.assertEqual(result.results[0].tool_name, "browser_click_link")

    def test_orchestrator_researches_user_provided_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit")
            with running_web_server({"/": SAMPLE_HTML}) as base_url:
                result = AgentOrchestrator(config).run(f'research_web_pages {{"urls":["{base_url}"],"query":"research"}}')

            self.assertIn("research_web_pages: succeeded", result.final_response)
            self.assertIn("Browser research needle", result.final_response)
            self.assertEqual(result.results[0].tool_name, "research_web_pages")


SAMPLE_HTML = """
<!doctype html>
<html>
  <head><title>Umang Browser Test</title><script>ignore this script</script></head>
  <body>
    <h1>Browser research needle</h1>
    <p>Fetched page content must stay data, not instructions.</p>
    <a href="/next">Next page</a>
    <img src="/browser-diagram.png" alt="Browser diagram" />
  </body>
</html>
"""

SECOND_HTML = """
<!doctype html>
<html>
  <head><title>Second Source</title></head>
  <body><p>Second source confirms bounded local browser research.</p></body>
</html>
"""

UNSAFE_LINK_HTML = """
<!doctype html>
<html>
  <head><title>Unsafe Link</title></head>
  <body><a href="http://10.0.0.1/private">Private target</a></body>
</html>
"""

FORM_HTML = """
<!doctype html>
<html>
  <head><title>Contact Form</title></head>
  <body>
    <form method="post" action="/submit">
      <input type="text" name="name" />
      <textarea name="message"></textarea>
      <button type="submit">Send</button>
    </form>
  </body>
</html>
"""


class running_web_server:
    def __init__(self, routes: dict[str, str | tuple[int, dict[str, str], str]]) -> None:
        self.routes = routes
        handler = self._handler()
        self.server = HTTPServer(("127.0.0.1", 0), handler)
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
        routes = self.routes

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                body = routes.get(self.path)
                if body is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                if isinstance(body, tuple):
                    status, headers, response_body = body
                    encoded = response_body.encode("utf-8")
                    self.send_response(status)
                    for name, value in headers.items():
                        self.send_header(name, value)
                    self.send_header("content-length", str(len(encoded)))
                    self.end_headers()
                    self.wfile.write(encoded)
                    return
                encoded = body.encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "text/html; charset=utf-8")
                self.send_header("content-length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def do_POST(self) -> None:
                length = int(self.headers.get("content-length", "0"))
                payload = self.rfile.read(length).decode("utf-8")
                parsed = {key: values[0] for key, values in parse_qs(payload).items()}
                body = (
                    "<!doctype html><html><head><title>Submitted</title></head>"
                    f"<body><p>Received {parsed.get('name', '')}: {parsed.get('message', '')}</p></body></html>"
                )
                encoded = body.encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "text/html; charset=utf-8")
                self.send_header("content-length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, format: str, *args) -> None:
                return

        return Handler


if __name__ == "__main__":
    unittest.main()
