from __future__ import annotations

from datetime import datetime
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema

from .common import LIVE_BROWSER_UNAVAILABLE, LIVE_JS_MAX_CHARS, LIVE_JS_RESULT_MAX_CHARS, WEB_TEXT_LIMIT_CHARS, _validate_url
from .live_manager import LIVE_BROWSER_MANAGER
from .live_utils import (
    _live_browser_downloads_dir,
    _live_browser_pdfs_dir,
    _live_browser_screenshots_dir,
    _resolve_live_upload_path,
    _safe_browser_artifact_filename,
    _unique_path,
)

class BrowserLiveStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_status",
            description="Report whether the optional native Playwright live-browser backend is available in this runtime.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        del tool_input, config
        available = LIVE_BROWSER_MANAGER.available()
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            "Live browser backend is available." if available else "Live browser backend is not installed.",
            {
                "available": available,
                "backend": "playwright",
                "active_sessions": len(LIVE_BROWSER_MANAGER.sessions),
                "source": "live_browser_backend_status",
            },
        )


class BrowserLiveOpenTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_open",
            description=(
                "Open an HTTP(S) URL in a native Playwright-backed live browser session. "
                "Use when static fetch/research is insufficient, or the task depends on visible page state, JavaScript, forms, date pickers, or interactive controls."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "url": {"type": "string", "description": "HTTP(S) URL without embedded credentials."},
                    "headless": {"type": "boolean", "description": "Launch the browser headlessly when true."},
                    "viewport_width": {"type": "integer", "minimum": 320, "maximum": 3840},
                    "viewport_height": {"type": "integer", "minimum": 240, "maximum": 2160},
                },
                required=["url"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        url = str(tool_input.get("url", "")).strip()
        validation_error = _validate_url(url)
        if validation_error:
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, validation_error, error=validation_error)
        headless = bool(tool_input.get("headless", True))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would open a live browser session.",
                {"url": url, "headless": headless, "live_browser_not_launched": True},
            )
        if not LIVE_BROWSER_MANAGER.available():
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser backend is not installed.", error=LIVE_BROWSER_UNAVAILABLE)
        try:
            viewport_width = max(320, min(int(tool_input.get("viewport_width") or 1280), 3840))
            viewport_height = max(240, min(int(tool_input.get("viewport_height") or 720), 2160))
            output = LIVE_BROWSER_MANAGER.open(
                url,
                headless=headless,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
            )
        except Exception as exc:
            if LIVE_BROWSER_MANAGER.sessions and "Playwright Sync API inside the asyncio loop" in str(exc):
                try:
                    live_session_id = next(iter(LIVE_BROWSER_MANAGER.sessions))
                    output = LIVE_BROWSER_MANAGER.new_tab(live_session_id, url)
                    output["reused_existing_session"] = True
                    output["reuse_reason"] = "Opening a separate Playwright session failed inside an active async loop, so the URL was opened in an existing live session."
                    return ToolResult(
                        self.name,
                        ActionStatus.SUCCEEDED,
                        self.risk_level,
                        f"Reused live browser session {live_session_id} and opened the URL in a new tab.",
                        output,
                    )
                except Exception:
                    pass
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser open failed.", error=str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Opened live browser session {output['live_session_id']}.", output)


class BrowserLiveObserveTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_observe",
            description=(
                "Observe a Playwright-backed live browser session: URL, title, live element ids, and optional visible text. "
                "Use after opening or changing an interactive page to inspect current browser-visible evidence."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string", "description": "Live browser session id returned by browser_live_open."},
                    "include_text": {"type": "boolean", "description": "Include bounded visible page text."},
                    "max_elements": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                required=["live_session_id"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        if not live_session_id:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser session id is required.")
        max_elements = max(1, min(int(tool_input.get("max_elements") or 50), 100))
        include_text = bool(tool_input.get("include_text", False))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would observe a live browser session.",
                {
                    "live_session_id": live_session_id,
                    "include_text": include_text,
                    "max_elements": max_elements,
                    "observation_not_performed": True,
                },
            )
        try:
            output = LIVE_BROWSER_MANAGER.observe(live_session_id, include_text=include_text, max_elements=max_elements)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser observation failed.", error=str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Observed live browser session {live_session_id}.", output)


class BrowserLiveClickTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_click",
            description="Click an observed live browser element id after explicit approval.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "element_id": {"type": "string", "description": "Observed live element id, for example live:0."},
                    "reason": {"type": "string", "description": "Why this live page element should be clicked."},
                },
                required=["live_session_id", "element_id", "reason"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        element_id = str(tool_input.get("element_id", "")).strip()
        reason = str(tool_input.get("reason", "")).strip()
        if not live_session_id or not element_id or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "live_session_id, element_id, and reason are required.")
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would click an observed live browser element.",
                {
                    "live_session_id": live_session_id,
                    "clicked_element": {"element_id": element_id, "reason": reason},
                    "click_not_performed": True,
                },
            )
        try:
            output = LIVE_BROWSER_MANAGER.click(live_session_id, element_id)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser click failed.", error=str(exc))
        output["clicked_element"] = {"element_id": element_id, "reason": reason}
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Clicked {element_id} in live browser session {live_session_id}.", output)


class BrowserLiveDragTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_drag",
            description="Drag one observed live browser element onto another after explicit approval.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "start_element_id": {"type": "string", "description": "Observed live element id to drag."},
                    "end_element_id": {"type": "string", "description": "Observed live element id to drop onto."},
                    "reason": {"type": "string", "description": "Why this drag action is needed."},
                },
                required=["live_session_id", "start_element_id", "end_element_id", "reason"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        start_element_id = str(tool_input.get("start_element_id", "")).strip()
        end_element_id = str(tool_input.get("end_element_id", "")).strip()
        reason = str(tool_input.get("reason", "")).strip()
        if not live_session_id or not start_element_id or not end_element_id or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "live_session_id, start_element_id, end_element_id, and reason are required.")
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would drag a live browser element after approval.",
                {
                    "live_session_id": live_session_id,
                    "start_element_id": start_element_id,
                    "end_element_id": end_element_id,
                    "reason": reason,
                    "drag_not_performed": True,
                },
            )
        try:
            output = LIVE_BROWSER_MANAGER.drag(live_session_id, start_element_id=start_element_id, end_element_id=end_element_id)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser drag failed.", error=str(exc))
        output["dragged_element"]["reason"] = reason
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Dragged {start_element_id} to {end_element_id} in live browser session {live_session_id}.", output)


class BrowserLiveTypeTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_type",
            description="Type text into an observed live browser element id after explicit approval.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "element_id": {"type": "string", "description": "Observed live element id, for example live:0."},
                    "text": {"type": "string", "description": "Text to type into the page element."},
                    "clear": {"type": "boolean", "description": "Fill/replace existing value when true."},
                    "press_enter": {"type": "boolean", "description": "Press Enter after typing when true."},
                    "reason": {"type": "string", "description": "Why this text should be typed into the live page."},
                },
                required=["live_session_id", "element_id", "text", "reason"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        element_id = str(tool_input.get("element_id", "")).strip()
        text = str(tool_input.get("text", ""))
        clear = bool(tool_input.get("clear", True))
        press_enter = bool(tool_input.get("press_enter", False))
        reason = str(tool_input.get("reason", "")).strip()
        if not live_session_id or not element_id or not text or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "live_session_id, element_id, text, and reason are required.")
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would type into an observed live browser element.",
                {
                    "live_session_id": live_session_id,
                    "typed_element": {
                        "element_id": element_id,
                        "text_length": len(text),
                        "clear": clear,
                        "pressed_enter": press_enter,
                        "reason": reason,
                    },
                    "typing_not_performed": True,
                },
            )
        try:
            output = LIVE_BROWSER_MANAGER.type_text(
                live_session_id,
                element_id,
                text=text,
                clear=clear,
                press_enter=press_enter,
            )
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser typing failed.", error=str(exc))
        output["typed_element"] = {
            "element_id": element_id,
            "text_length": len(text),
            "pressed_enter": press_enter,
            "reason": reason,
        }
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Typed into {element_id} in live browser session {live_session_id}.", output)


class BrowserLiveFillFormTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_fill_form",
            description="Fill multiple observed live browser fields in one approved action, then re-observe the page.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "fields": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 20,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "element_id": {"type": "string", "description": "Observed live field id."},
                                "text": {"type": "string", "description": "Text to enter."},
                                "clear": {"type": "boolean", "description": "Replace existing value when true."},
                            },
                            "required": ["element_id", "text"],
                        },
                    },
                    "reason": {"type": "string", "description": "Why these fields should be filled."},
                },
                required=["live_session_id", "fields", "reason"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        reason = str(tool_input.get("reason", "")).strip()
        raw_fields = tool_input.get("fields")
        if not isinstance(raw_fields, list) or not raw_fields:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "At least one field is required.")
        fields = [field for field in raw_fields[:20] if isinstance(field, dict)]
        if len(fields) != len(raw_fields[:20]) or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "fields must be objects and reason is required.")
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would fill live browser fields after approval.",
                {
                    "live_session_id": live_session_id,
                    "field_count": len(fields),
                    "text_lengths": [len(str(field.get("text", ""))) for field in fields],
                    "reason": reason,
                    "fields_not_filled": True,
                },
            )
        try:
            output = LIVE_BROWSER_MANAGER.fill_fields(live_session_id, fields=fields)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser form fill failed.", error=str(exc))
        output["filled_form"] = {"field_count": len(fields), "reason": reason}
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Filled {len(fields)} live browser field(s).", output)


class BrowserLiveResizeTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_resize",
            description="Resize the viewport for a Playwright-backed live browser session.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "width": {"type": "integer", "minimum": 320, "maximum": 3840},
                    "height": {"type": "integer", "minimum": 240, "maximum": 2160},
                },
                required=["live_session_id", "width", "height"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        width = max(320, min(int(tool_input.get("width", 1280)), 3840))
        height = max(240, min(int(tool_input.get("height", 720)), 2160))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would resize the live browser viewport.",
                {"live_session_id": live_session_id, "viewport": {"width": width, "height": height}, "resize_not_performed": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.resize(live_session_id, width=width, height=height)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser resize failed.", error=str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Resized live browser session {live_session_id}.", output)


class BrowserLiveScrollTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_scroll",
            description="Scroll a Playwright-backed live browser page.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "direction": {"type": "string", "enum": ["up", "down", "left", "right"]},
                    "amount": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                required=["live_session_id", "direction"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        direction = str(tool_input.get("direction", "down")).strip().lower()
        if not live_session_id:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser session id is required.")
        if direction not in {"up", "down", "left", "right"}:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Unsupported scroll direction.")
        amount = max(1, min(int(tool_input.get("amount") or 3), 10))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would scroll a live browser page.",
                {
                    "live_session_id": live_session_id,
                    "scroll": {"direction": direction, "amount": amount},
                    "scroll_not_performed": True,
                },
            )
        try:
            output = LIVE_BROWSER_MANAGER.scroll(live_session_id, direction=direction, amount=amount)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser scroll failed.", error=str(exc))
        output["scroll"] = {"direction": direction, "amount": amount}
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Scrolled live browser session {live_session_id}.", output)


class BrowserLiveWaitTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_wait",
            description="Wait in a Playwright-backed live browser session for load state, selector, text, or a bounded timeout.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "mode": {"type": "string", "enum": ["load", "selector", "text", "timeout"]},
                    "selector": {"type": "string", "description": "CSS selector for selector wait mode."},
                    "text": {"type": "string", "description": "Visible text for text wait mode."},
                    "state": {
                        "type": "string",
                        "enum": ["load", "domcontentloaded", "networkidle", "attached", "detached", "visible", "hidden"],
                    },
                    "timeout_ms": {"type": "integer", "minimum": 100, "maximum": 30000},
                },
                required=["live_session_id", "mode"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        mode = str(tool_input.get("mode", "load")).strip().lower()
        selector = str(tool_input.get("selector", "")).strip()
        text = str(tool_input.get("text", "")).strip()
        state = str(tool_input.get("state", "domcontentloaded" if mode == "load" else "visible")).strip().lower()
        timeout_ms = max(100, min(int(tool_input.get("timeout_ms") or 5000), 30000))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would wait in live browser session.",
                {"live_session_id": live_session_id, "mode": mode, "wait_not_performed": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.wait(
                live_session_id,
                mode=mode,
                selector=selector,
                text=text,
                state=state,
                timeout_ms=timeout_ms,
            )
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser wait failed.", error=str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Waited in live browser session {live_session_id}.", output)


class BrowserLiveTabsTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_tabs",
            description="List tabs for a Playwright-backed live browser session without returning page text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {"live_session_id": {"type": "string", "description": "Live browser session id."}},
                required=["live_session_id"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        if not live_session_id:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser session id is required.")
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would list live browser tabs.",
                {"live_session_id": live_session_id, "tabs_not_read": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.tabs(live_session_id)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser tab listing failed.", error=str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Listed live browser tabs for {live_session_id}.", output)


class BrowserLiveSearchTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_search",
            description=(
                "Search DuckDuckGo, Google, or Bing in an existing Playwright-backed live browser session. "
                "Use when search result pages or follow-up navigation need live browser-visible state."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "query": {"type": "string", "description": "Search query."},
                    "engine": {"type": "string", "enum": ["duckduckgo", "google", "bing"]},
                    "new_tab": {"type": "boolean", "description": "Open search results in a new tab when true."},
                },
                required=["live_session_id", "query"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        query = str(tool_input.get("query", "")).strip()
        engine = str(tool_input.get("engine", "duckduckgo")).strip().lower()
        new_tab = bool(tool_input.get("new_tab", False))
        if not query:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Search query is required.")
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would search in live browser session.",
                {"live_session_id": live_session_id, "query": query, "engine": engine, "new_tab": new_tab, "search_not_performed": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.search(live_session_id, query=query, engine=engine, new_tab=new_tab)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser search failed.", error=str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Searched {engine} in live browser session {live_session_id}.", output)


class BrowserLiveNavigateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_navigate",
            description="Navigate an existing Playwright-backed live browser session to an HTTP(S) URL, optionally in a new tab.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "url": {"type": "string", "description": "HTTP(S) URL without embedded credentials."},
                    "new_tab": {"type": "boolean", "description": "Open URL in a new tab when true."},
                },
                required=["live_session_id", "url"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        url = str(tool_input.get("url", "")).strip()
        validation_error = _validate_url(url)
        if validation_error:
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, validation_error, error=validation_error)
        new_tab = bool(tool_input.get("new_tab", False))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would navigate the live browser session.",
                {"live_session_id": live_session_id, "url": url, "new_tab": new_tab, "navigation_not_performed": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.navigate(live_session_id, url=url, new_tab=new_tab)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser navigation failed.", error=str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Navigated live browser session {live_session_id}.", output)


class BrowserLiveBackTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_back",
            description="Navigate the active tab in a live browser session back in history.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"live_session_id": {"type": "string"}}, required=["live_session_id"]),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would navigate live browser history back.",
                {"live_session_id": live_session_id, "history_not_changed": True, "direction": "back"},
            )
        try:
            output = LIVE_BROWSER_MANAGER.back(live_session_id)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser back navigation failed.", error=str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Navigated live browser session {live_session_id} back.", output)


class BrowserLiveForwardTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_forward",
            description="Navigate the active tab in a live browser session forward in history.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"live_session_id": {"type": "string"}}, required=["live_session_id"]),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would navigate live browser history forward.",
                {"live_session_id": live_session_id, "history_not_changed": True, "direction": "forward"},
            )
        try:
            output = LIVE_BROWSER_MANAGER.forward(live_session_id)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser forward navigation failed.", error=str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Navigated live browser session {live_session_id} forward.", output)


class BrowserLiveReloadTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_reload",
            description="Reload the active tab in a live browser session.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"live_session_id": {"type": "string"}}, required=["live_session_id"]),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would reload the live browser tab.",
                {"live_session_id": live_session_id, "reload_not_performed": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.reload(live_session_id)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser reload failed.", error=str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Reloaded live browser session {live_session_id}.", output)


class BrowserLiveNewTabTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_new_tab",
            description="Open a new tab in an existing Playwright-backed live browser session.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "url": {"type": "string", "description": "Optional HTTP(S) URL to open in the new tab."},
                },
                required=["live_session_id"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        url = str(tool_input.get("url", "")).strip()
        if url:
            validation_error = _validate_url(url)
            if validation_error:
                return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, validation_error, error=validation_error)
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would open a new live browser tab.",
                {"live_session_id": live_session_id, "url": url, "new_tab_not_opened": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.new_tab(live_session_id, url or None)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser new tab failed.", error=str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Opened a new tab in live browser session {live_session_id}.", output)


class BrowserLiveSwitchTabTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_switch_tab",
            description="Switch the active tab in a Playwright-backed live browser session.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "index": {"type": "integer", "minimum": 0, "description": "Tab index from browser_live_tabs."},
                },
                required=["live_session_id", "index"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        del config
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        index = int(tool_input.get("index", 0))
        try:
            output = LIVE_BROWSER_MANAGER.switch_tab(live_session_id, index)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser tab switch failed.", error=str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Switched live browser session {live_session_id} to tab {index}.", output)


class BrowserLiveCloseTabTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_close_tab",
            description="Close a tab in a Playwright-backed live browser session after explicit approval.",
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "index": {"type": "integer", "minimum": 0, "description": "Optional tab index; current tab is used when omitted."},
                    "reason": {"type": "string", "description": "Why this live browser tab should be closed."},
                },
                required=["live_session_id", "reason"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        index = int(tool_input["index"]) if "index" in tool_input else None
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would close a live browser tab after approval.",
                {"live_session_id": live_session_id, "index": index, "tab_not_closed": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.close_tab(live_session_id, index)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser tab close failed.", error=str(exc))
        output["closed_tab"] = {"index": index, "reason": str(tool_input.get("reason", "")).strip()}
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Closed a tab in live browser session {live_session_id}.", output)


class BrowserLiveQuerySelectorTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_query_selector",
            description="Query a live browser page with a CSS selector and return bounded element metadata.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "selector": {"type": "string", "description": "CSS selector to query."},
                    "max_elements": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                required=["live_session_id", "selector"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        selector = str(tool_input.get("selector", "")).strip()
        max_elements = max(1, min(int(tool_input.get("max_elements") or 25), 100))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would query live browser selector.",
                {"live_session_id": live_session_id, "selector": selector, "selector_not_queried": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.query_selector(live_session_id, selector=selector, max_elements=max_elements)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser selector query failed.", error=str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Found {output['match_count']} live browser selector match(es).", output)


class BrowserLiveHtmlTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_html",
            description=(
                "Read bounded raw HTML from the current live browser page or one CSS-selected element. "
                "Use when visible text is insufficient and the page structure/attributes matter."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "selector": {"type": "string", "description": "Optional CSS selector; when omitted, reads document HTML."},
                    "max_chars": {"type": "integer", "minimum": 1, "maximum": WEB_TEXT_LIMIT_CHARS},
                },
                required=["live_session_id"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        selector = str(tool_input.get("selector", "")).strip()
        max_chars = max(1, min(int(tool_input.get("max_chars") or 12000), WEB_TEXT_LIMIT_CHARS))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would read live browser HTML.",
                {"live_session_id": live_session_id, "selector": selector, "html_not_read": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.html(live_session_id, selector=selector, max_chars=max_chars)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser HTML read failed.", error=str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, "Read bounded live browser HTML.", output)


class BrowserLivePageSearchTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_page_search",
            description=(
                "Search current live browser page text for a literal string or regex and return bounded context snippets. "
                "Use for Browser Use-style page search before extracting or clicking."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "pattern": {"type": "string", "description": "Text or regex pattern to search for."},
                    "regex": {"type": "boolean", "description": "Treat pattern as regex when true."},
                    "case_sensitive": {"type": "boolean"},
                    "context_chars": {"type": "integer", "minimum": 0, "maximum": 1000},
                    "css_scope": {"type": "string", "description": "Optional CSS selector limiting the text search scope."},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                required=["live_session_id", "pattern"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        pattern = str(tool_input.get("pattern", ""))
        if not pattern:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Search pattern is required.")
        context_chars = max(0, min(int(tool_input.get("context_chars") or 150), 1000))
        max_results = max(1, min(int(tool_input.get("max_results") or 25), 100))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would search live browser page text.",
                {"live_session_id": live_session_id, "pattern": pattern, "page_not_searched": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.search_page(
                live_session_id,
                pattern=pattern,
                regex=bool(tool_input.get("regex", False)),
                case_sensitive=bool(tool_input.get("case_sensitive", False)),
                context_chars=context_chars,
                css_scope=str(tool_input.get("css_scope", "")).strip(),
                max_results=max_results,
            )
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser page search failed.", error=str(exc))
        if output.get("error"):
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(output["error"]), output, error=str(output["error"]))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Found {output['total']} page text match(es).", output)


class BrowserLiveFindElementsTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_find_elements",
            description=(
                "Find elements on the current live browser page by CSS selector and return tag, bounded text, selected attributes, and child counts. "
                "Use for Browser Use-style structured DOM extraction."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "selector": {"type": "string", "description": "CSS selector such as table tr, a, img, or div.product."},
                    "attributes": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
                    "include_text": {"type": "boolean"},
                },
                required=["live_session_id", "selector"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        selector = str(tool_input.get("selector", "")).strip()
        if not selector:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "CSS selector is required.")
        raw_attributes = tool_input.get("attributes") or []
        attributes = [str(item).strip() for item in raw_attributes[:20] if str(item).strip()] if isinstance(raw_attributes, list) else []
        max_results = max(1, min(int(tool_input.get("max_results") or 50), 100))
        include_text = bool(tool_input.get("include_text", True))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would find live browser elements.",
                {"live_session_id": live_session_id, "selector": selector, "elements_not_found": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.find_elements(
                live_session_id,
                selector=selector,
                attributes=attributes,
                max_results=max_results,
                include_text=include_text,
            )
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser element search failed.", error=str(exc))
        if output.get("error"):
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(output["error"]), output, error=str(output["error"]))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Found {output['total']} selector match(es).", output)


class BrowserLiveExtractTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_extract",
            description=(
                "Extract query-relevant snippets, links, images, and optional schema-shaped data from the current rendered live browser page. "
                "Use for Browser Use-style extraction when static browser_extract is insufficient."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "query": {"type": "string", "description": "What to extract from the rendered page."},
                    "include_links": {"type": "boolean", "description": "Include matching links."},
                    "include_images": {"type": "boolean", "description": "Include matching image URLs and alt/title metadata."},
                    "start_from_char": {"type": "integer", "minimum": 0, "description": "Character offset for long rendered page text."},
                    "max_snippets": {"type": "integer", "minimum": 1, "maximum": 20},
                    "output_schema": {"type": "object", "description": "Optional JSON schema used to shape extracted evidence fields."},
                    "already_collected": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 100,
                        "description": "Identifiers, names, URLs, or snippets already collected on earlier pages.",
                    },
                },
                required=["live_session_id", "query"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        query = str(tool_input.get("query", "")).strip()
        if not live_session_id:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser session id is required.")
        if not query:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser extraction query is required.")
        output_schema = tool_input.get("output_schema")
        if output_schema is not None and not isinstance(output_schema, dict):
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "output_schema must be an object when provided.")
        raw_collected = tool_input.get("already_collected") or []
        already_collected = [str(item).strip() for item in raw_collected[:100] if str(item).strip()] if isinstance(raw_collected, list) else []
        start_from_char = max(0, int(tool_input.get("start_from_char") or 0))
        max_snippets = max(1, min(int(tool_input.get("max_snippets") or 8), 20))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would extract rendered live browser page evidence.",
                {
                    "live_session_id": live_session_id,
                    "query": query,
                    "include_links": bool(tool_input.get("include_links", True)),
                    "include_images": bool(tool_input.get("include_images", False)),
                    "output_schema_used": bool(output_schema),
                    "extraction_not_performed": True,
                },
            )
        try:
            output = LIVE_BROWSER_MANAGER.extract(
                live_session_id,
                query=query,
                include_links=bool(tool_input.get("include_links", True)),
                include_images=bool(tool_input.get("include_images", False)),
                start_from_char=start_from_char,
                max_snippets=max_snippets,
                output_schema=output_schema,
                already_collected=already_collected,
            )
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser extraction failed.", error=str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Extracted {len(output['snippets'])} rendered browser snippet(s).", output)


class BrowserLiveSelectOptionTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_select_option",
            description="Select option values in an observed live browser select element after explicit approval.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "element_id": {"type": "string", "description": "Observed live select element id, for example live:3."},
                    "values": {"type": "array", "items": {"type": "string"}, "description": "Option values or labels to select."},
                    "reason": {"type": "string", "description": "Why these dropdown option values should be selected."},
                },
                required=["live_session_id", "element_id", "values", "reason"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        element_id = str(tool_input.get("element_id", "")).strip()
        values = [str(value) for value in tool_input.get("values", []) if str(value)]
        if not values:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "At least one dropdown option value is required.")
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would select live browser dropdown options after approval.",
                {"live_session_id": live_session_id, "element_id": element_id, "values": values, "options_not_selected": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.select_option(live_session_id, element_id=element_id, values=values)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser dropdown selection failed.", error=str(exc))
        output["selected_option"]["reason"] = str(tool_input.get("reason", "")).strip()
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Selected options in {element_id} for live browser session {live_session_id}.", output)


class BrowserLiveDropdownOptionsTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_dropdown_options",
            description="List options for an observed live browser select/menu element without changing the page.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "element_id": {"type": "string", "description": "Observed live dropdown/select/menu element id."},
                    "max_options": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                required=["live_session_id", "element_id"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        element_id = str(tool_input.get("element_id", "")).strip()
        max_options = max(1, min(int(tool_input.get("max_options") or 50), 100))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would list live browser dropdown options.",
                {"live_session_id": live_session_id, "element_id": element_id, "dropdown_not_queried": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.dropdown_options(live_session_id, element_id=element_id, max_options=max_options)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser dropdown option listing failed.", error=str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Found {output['option_count']} dropdown option(s).", output)


class BrowserLivePressKeyTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_press_key",
            description="Press a keyboard shortcut in a live browser session after explicit approval.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "shortcut": {"type": "string", "description": "Playwright key or shortcut, such as Enter or Control+A."},
                    "element_id": {"type": "string", "description": "Optional observed live element id to focus before pressing."},
                    "reason": {"type": "string", "description": "Why this key press should be sent to the live page."},
                },
                required=["live_session_id", "shortcut", "reason"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        shortcut = str(tool_input.get("shortcut", "")).strip()
        element_id = str(tool_input.get("element_id", "")).strip() or None
        if not shortcut:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Keyboard shortcut is required.")
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would press a key in live browser after approval.",
                {"live_session_id": live_session_id, "shortcut": shortcut, "element_id": element_id or "", "key_not_pressed": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.press_key(live_session_id, shortcut=shortcut, element_id=element_id)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser key press failed.", error=str(exc))
        output["pressed_key"]["reason"] = str(tool_input.get("reason", "")).strip()
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Pressed {shortcut} in live browser session {live_session_id}.", output)


class BrowserLiveClickCoordinatesTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_click_coordinates",
            description="Click viewport coordinates in a live browser session after explicit approval.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "x": {"type": "integer", "minimum": 0, "description": "Viewport x coordinate."},
                    "y": {"type": "integer", "minimum": 0, "description": "Viewport y coordinate."},
                    "reason": {"type": "string", "description": "Why this coordinate click is needed."},
                },
                required=["live_session_id", "x", "y", "reason"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        x = max(0, int(tool_input.get("x", 0)))
        y = max(0, int(tool_input.get("y", 0)))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would click live browser coordinates after approval.",
                {"live_session_id": live_session_id, "x": x, "y": y, "coordinates_not_clicked": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.click_coordinates(live_session_id, x=x, y=y)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser coordinate click failed.", error=str(exc))
        output["clicked_coordinates"]["reason"] = str(tool_input.get("reason", "")).strip()
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Clicked coordinates ({x}, {y}) in live browser session {live_session_id}.", output)


class BrowserLiveHoverTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_hover",
            description="Hover over an observed live browser element id to reveal menus, tooltips, or hover state.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "element_id": {"type": "string", "description": "Observed live element id, for example live:0."},
                },
                required=["live_session_id", "element_id"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        element_id = str(tool_input.get("element_id", "")).strip()
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would hover over a live browser element.",
                {"live_session_id": live_session_id, "element_id": element_id, "hover_not_performed": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.hover(live_session_id, element_id=element_id)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser hover failed.", error=str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Hovered over {element_id} in live browser session {live_session_id}.", output)


class BrowserLiveDragCoordinatesTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_drag_coordinates",
            description="Drag from one viewport coordinate to another in a live browser session after explicit approval.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "start_x": {"type": "integer", "minimum": 0, "description": "Start viewport x coordinate."},
                    "start_y": {"type": "integer", "minimum": 0, "description": "Start viewport y coordinate."},
                    "end_x": {"type": "integer", "minimum": 0, "description": "End viewport x coordinate."},
                    "end_y": {"type": "integer", "minimum": 0, "description": "End viewport y coordinate."},
                    "reason": {"type": "string", "description": "Why this drag action is needed."},
                },
                required=["live_session_id", "start_x", "start_y", "end_x", "end_y", "reason"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        start_x = max(0, int(tool_input.get("start_x", 0)))
        start_y = max(0, int(tool_input.get("start_y", 0)))
        end_x = max(0, int(tool_input.get("end_x", 0)))
        end_y = max(0, int(tool_input.get("end_y", 0)))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would drag between live browser coordinates after approval.",
                {
                    "live_session_id": live_session_id,
                    "start": {"x": start_x, "y": start_y},
                    "end": {"x": end_x, "y": end_y},
                    "drag_not_performed": True,
                },
            )
        try:
            output = LIVE_BROWSER_MANAGER.drag_coordinates(live_session_id, start_x=start_x, start_y=start_y, end_x=end_x, end_y=end_y)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser coordinate drag failed.", error=str(exc))
        output["dragged_coordinates"]["reason"] = str(tool_input.get("reason", "")).strip()
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Dragged live browser coordinates ({start_x}, {start_y}) to ({end_x}, {end_y}).", output)


class BrowserLiveScrollToTextTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_scroll_to_text",
            description="Scroll a live browser page to matching visible text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "text": {"type": "string", "description": "Visible text to scroll into view."},
                    "exact": {"type": "boolean", "description": "Require exact text match when true."},
                },
                required=["live_session_id", "text"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        text = str(tool_input.get("text", "")).strip()
        exact = bool(tool_input.get("exact", False))
        if not text:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Scroll-to-text value is required.")
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would scroll live browser to text.",
                {"live_session_id": live_session_id, "text": text, "exact": exact, "scroll_not_performed": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.scroll_to_text(live_session_id, text=text, exact=exact)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser scroll-to-text failed.", error=str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Scrolled live browser session {live_session_id} to text.", output)


class BrowserLiveUploadFileTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_upload_file",
            description="Upload a local file from an allowed read root into an observed live browser file input after explicit approval.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "element_id": {"type": "string", "description": "Observed live file input element id, for example live:4."},
                    "path": {"type": "string", "description": "Workspace-relative or allowed absolute file path to upload."},
                    "reason": {"type": "string", "description": "Why this local file should be uploaded to the page."},
                },
                required=["live_session_id", "element_id", "path", "reason"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        element_id = str(tool_input.get("element_id", "")).strip()
        path, error = _resolve_live_upload_path(config, tool_input.get("path"))
        if error:
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, error, error=error)
        assert path is not None
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would upload an allowed local file after approval.",
                {
                    "live_session_id": live_session_id,
                    "element_id": element_id,
                    "filename": path.name,
                    "size_bytes": path.stat().st_size,
                    "file_not_uploaded": True,
                    "path_returned": False,
                },
            )
        try:
            output = LIVE_BROWSER_MANAGER.upload_file(live_session_id, element_id=element_id, path=path)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser file upload failed.", error=str(exc))
        output["uploaded_file"]["reason"] = str(tool_input.get("reason", "")).strip()
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Uploaded {path.name} in live browser session {live_session_id}.", output)


class BrowserLiveDownloadTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_download",
            description="Click an observed live browser element and save the resulting download under the local data directory after explicit approval.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "element_id": {"type": "string", "description": "Observed live element expected to trigger a download."},
                    "timeout_ms": {"type": "integer", "minimum": 500, "maximum": 60000},
                    "reason": {"type": "string", "description": "Why this download should be triggered and saved."},
                },
                required=["live_session_id", "element_id", "reason"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        element_id = str(tool_input.get("element_id", "")).strip()
        timeout_ms = max(500, min(int(tool_input.get("timeout_ms") or 15000), 60000))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would trigger and save a live browser download after approval.",
                {"live_session_id": live_session_id, "element_id": element_id, "download_not_started": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.download_from_element(
                live_session_id,
                element_id=element_id,
                target_dir=_live_browser_downloads_dir(config),
                timeout_ms=timeout_ms,
            )
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser download failed.", error=str(exc))
        output["reason"] = str(tool_input.get("reason", "")).strip()
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Saved live browser download to {output.get('path')}.", output)


class BrowserLiveSavePdfTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_save_pdf",
            description="Save the current live browser page as a PDF under the local data directory after explicit approval.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "filename": {"type": "string", "description": "Optional safe PDF filename."},
                    "print_background": {"type": "boolean", "description": "Include CSS backgrounds in the exported PDF."},
                    "reason": {"type": "string", "description": "Why this page should be saved as PDF."},
                },
                required=["live_session_id", "reason"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        filename = _safe_browser_artifact_filename(
            str(tool_input.get("filename", "")).strip() or f"live-browser-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pdf",
            default_suffix=".pdf",
        )
        path = _unique_path(_live_browser_pdfs_dir(config) / filename)
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would save the live browser page as PDF after approval.",
                {"live_session_id": live_session_id, "filename": path.name, "pdf_not_saved": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.save_pdf(live_session_id, path=path, print_background=bool(tool_input.get("print_background", True)))
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser PDF export failed.", error=str(exc))
        output["reason"] = str(tool_input.get("reason", "")).strip()
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Saved live browser PDF to {path}.", output)


class BrowserLiveEvaluateJsTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_evaluate_js",
            description="Evaluate bounded JavaScript in a live browser page context after explicit approval.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "code": {"type": "string", "description": "JavaScript expression or function accepted by Playwright page.evaluate."},
                    "max_chars": {"type": "integer", "minimum": 1, "maximum": LIVE_JS_RESULT_MAX_CHARS},
                    "reason": {"type": "string", "description": "Why JavaScript evaluation is needed."},
                },
                required=["live_session_id", "code", "reason"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        code = str(tool_input.get("code", ""))
        if len(code) > LIVE_JS_MAX_CHARS:
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "JavaScript exceeds configured evaluation limit.")
        max_chars = max(1, min(int(tool_input.get("max_chars") or 2000), LIVE_JS_RESULT_MAX_CHARS))
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would evaluate JavaScript in the live browser after approval.",
                {
                    "live_session_id": live_session_id,
                    "code_length": len(code),
                    "js_not_evaluated": True,
                    "result_returned": False,
                },
            )
        try:
            output = LIVE_BROWSER_MANAGER.evaluate_js(live_session_id, code=code, max_chars=max_chars)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser JavaScript evaluation failed.", error=str(exc))
        output["reason"] = str(tool_input.get("reason", "")).strip()
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, "Evaluated JavaScript in live browser session.", output)


class BrowserLiveScreenshotTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_screenshot",
            description="Save a screenshot of a Playwright-backed live browser session after explicit approval.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "full_page": {"type": "boolean", "description": "Capture the full page instead of viewport only."},
                    "reason": {"type": "string", "description": "Why a live browser screenshot is needed."},
                },
                required=["live_session_id", "reason"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would capture live browser screenshot after approval.",
                {"live_session_id": live_session_id, "image_bytes_served": False, "screenshot_not_captured": True},
            )
        path = _live_browser_screenshots_dir(config) / f"live-browser-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
        try:
            output = LIVE_BROWSER_MANAGER.screenshot(live_session_id, path=path, full_page=bool(tool_input.get("full_page", False)))
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser screenshot failed.", error=str(exc))
        output["reason"] = str(tool_input.get("reason", "")).strip()
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Saved live browser screenshot to {path}.", output)


class BrowserLiveCloseTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser_live_close",
            description="Close a Playwright-backed live browser session.",
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string", "description": "Live browser session id to close."},
                    "reason": {"type": "string", "description": "Why this live browser session should be closed."},
                },
                required=["live_session_id"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        live_session_id = str(tool_input.get("live_session_id", "")).strip()
        reason = str(tool_input.get("reason", "")).strip()
        if not live_session_id:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser session id is required.")
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would close a live browser session.",
                {"live_session_id": live_session_id, "reason": reason, "browser_not_closed": True},
            )
        try:
            output = LIVE_BROWSER_MANAGER.close(live_session_id)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Live browser close failed.", error=str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Closed live browser session {live_session_id}.", output)
