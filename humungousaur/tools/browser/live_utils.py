from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.tools.file_tools import _is_within, _relative, _resolve_workspace_path

from .common import LIVE_ELEMENT_PATTERN

def _live_interactive_elements(page: Any, max_elements: int) -> list[dict[str, Any]]:
    script = """
    ({ maxElements }) => {
      const cssEscape = (value) => {
        if (window.CSS && CSS.escape) return CSS.escape(value);
        return String(value).replace(/[^a-zA-Z0-9_-]/g, (char) => `\\${char}`);
      };
      const labelFor = (el) => {
        const aria = el.getAttribute("aria-label") || "";
        const title = el.getAttribute("title") || "";
        const placeholder = el.getAttribute("placeholder") || "";
        const text = (el.innerText || el.textContent || "").replace(/\\s+/g, " ").trim();
        const labelledBy = el.getAttribute("aria-labelledby") || "";
        const labelledText = labelledBy
          .split(/\\s+/)
          .map((id) => document.getElementById(id)?.innerText || "")
          .join(" ")
          .replace(/\\s+/g, " ")
          .trim();
        return (aria || labelledText || title || placeholder || text || el.getAttribute("name") || el.id || "").slice(0, 180);
      };
      const selectorFor = (el) => {
        const tag = el.tagName.toLowerCase();
        if (el.id) return `#${cssEscape(el.id)}`;
        const name = el.getAttribute("name");
        if (name) return `${tag}[name="${String(name).replace(/"/g, '\\"')}"]`;
        const role = el.getAttribute("role");
        if (role) return `${tag}[role="${String(role).replace(/"/g, '\\"')}"]:nth-of-type(${Array.from(el.parentElement?.children || []).filter((child) => child.tagName === el.tagName).indexOf(el) + 1})`;
        return `${tag}:nth-of-type(${Array.from(el.parentElement?.children || []).filter((child) => child.tagName === el.tagName).indexOf(el) + 1})`;
      };
      return Array.from(document.querySelectorAll(
        'a,button,input,textarea,select,summary,[role="button"],[role="link"],[role="checkbox"],[role="tab"],[contenteditable="true"]'
      ))
        .filter((el) => {
          const rect = el.getBoundingClientRect();
          const style = window.getComputedStyle(el);
          return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
        })
        .slice(0, maxElements)
        .map((el, index) => {
          const rect = el.getBoundingClientRect();
          const tag = el.tagName.toLowerCase();
          const inputType = (el.getAttribute("type") || "").toLowerCase();
          const isPassword = inputType === "password";
          return {
            element_id: `live:${index}`,
            tag,
            role: el.getAttribute("role") || "",
            name: el.getAttribute("name") || "",
            input_type: inputType,
            text: labelFor(el),
            href: tag === "a" ? el.getAttribute("href") || "" : "",
            value_present: isPassword ? Boolean(el.value) : Boolean(el.value),
            value_redacted: isPassword,
            selector: selectorFor(el),
            bounds: {
              x: Math.round(rect.x),
              y: Math.round(rect.y),
              width: Math.round(rect.width),
              height: Math.round(rect.height),
            },
            action_tool: tag === "input" || tag === "textarea" || tag === "select" || el.isContentEditable
              ? "browser_live_type"
              : "browser_live_click",
          };
        });
    }
    """
    raw_elements = page.evaluate(script, {"maxElements": max(1, min(max_elements, 100))})
    elements: list[dict[str, Any]] = []
    for raw in raw_elements or []:
        element = dict(raw)
        selector = str(element.get("selector", "")).strip()
        if not selector:
            continue
        elements.append(element)
    return elements


def _live_tabs(session: dict[str, Any]) -> list[dict[str, Any]]:
    pages = list(session["context"].pages)
    active_page = session["page"]
    tabs: list[dict[str, Any]] = []
    for index, page in enumerate(pages):
        try:
            url = page.url
            title = page.title()
        except Exception:
            url = ""
            title = ""
        tabs.append(
            {
                "index": index,
                "active": page == active_page,
                "url": url,
                "title": title,
            }
        )
    return tabs


def _live_selector_elements(page: Any, selector: str, max_elements: int) -> list[dict[str, Any]]:
    script = """
    ({ selector, maxElements }) => {
      const elements = Array.from(document.querySelectorAll(selector)).slice(0, maxElements);
      return elements.map((el, index) => {
        const rect = el.getBoundingClientRect();
        const tag = el.tagName.toLowerCase();
        const inputType = (el.getAttribute("type") || "").toLowerCase();
        const isPassword = inputType === "password";
        return {
          index,
          tag,
          id: el.id || "",
          name: el.getAttribute("name") || "",
          role: el.getAttribute("role") || "",
          input_type: inputType,
          text: ((el.innerText || el.textContent || "").replace(/\\s+/g, " ").trim()).slice(0, 500),
          href: tag === "a" ? el.getAttribute("href") || "" : "",
          value_present: isPassword ? Boolean(el.value) : Boolean(el.value),
          value_redacted: isPassword,
          bounds: {
            x: Math.round(rect.x),
            y: Math.round(rect.y),
            width: Math.round(rect.width),
            height: Math.round(rect.height),
          },
        };
      });
    }
    """
    if not selector:
        raise ValueError("CSS selector is required.")
    return list(page.evaluate(script, {"selector": selector, "maxElements": max(1, min(max_elements, 100))}) or [])


def _live_element_by_id(session: dict[str, Any], element_id: str) -> dict[str, Any]:
    match = LIVE_ELEMENT_PATTERN.match(element_id)
    if not match:
        raise ValueError("Element id must identify an observed live browser element such as live:0.")
    for element in session.get("last_elements", []):
        if element.get("element_id") == element_id:
            return element
    raise KeyError(f"Observed live browser element does not exist in this session: {element_id}")


def _live_browser_screenshots_dir(config: AgentConfig) -> Path:
    return config.data_dir / "browser-live-screenshots"


def _live_browser_downloads_dir(config: AgentConfig) -> Path:
    return config.data_dir / "browser-live-downloads"


def _live_browser_pdfs_dir(config: AgentConfig) -> Path:
    return config.data_dir / "browser-live-pdfs"


def _resolve_live_upload_path(config: AgentConfig, raw_path: Any) -> tuple[Path | None, str | None]:
    path = _resolve_workspace_path(config, str(raw_path or ""))
    if not _is_within(path, config.allowed_read_roots):
        return None, "Upload file path is outside allowed read roots."
    if not path.exists() or not path.is_file():
        return None, f"Upload file does not exist: {_relative(path, config)}"
    if path.stat().st_size > config.max_file_bytes:
        return None, "Upload file exceeds configured read limit."
    return path, None


def _safe_browser_artifact_filename(raw_name: str, default_suffix: str) -> str:
    candidate = Path(raw_name).name.strip()
    candidate = re.sub(r"[^A-Za-z0-9._-]+", "-", candidate).strip(".-")
    if not candidate:
        candidate = f"browser-artifact{default_suffix}"
    suffix = Path(candidate).suffix.lower()
    if not suffix:
        candidate = f"{candidate}{default_suffix}"
    return candidate[:120]


def _unique_path(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(1, 1000):
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    return path.with_name(f"{stem}-{uuid.uuid4().hex[:8]}{suffix}")
