from __future__ import annotations

import html
import ipaddress
import re
import socket
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlencode, urlparse

WEB_TIMEOUT_SECONDS = 10
WEB_MAX_LINKS = 25
WEB_MAX_IMAGES = 25
WEB_TEXT_LIMIT_CHARS = 20_000
LIVE_JS_MAX_CHARS = 4_000
LIVE_JS_RESULT_MAX_CHARS = 8_000
LIVE_BROWSER_UNAVAILABLE = "Playwright is not installed. Install Playwright and browser binaries to use live browser control."
URL_PATTERN = re.compile(r"https?://[^\s<>'\")]+", re.IGNORECASE)
LINK_ELEMENT_PATTERN = re.compile(r"^link:(\d+)$")
FORM_FIELD_ELEMENT_PATTERN = re.compile(r"^form:(\d+):field:(.+)$")
LIVE_ELEMENT_PATTERN = re.compile(r"^live:(\d+)$")

class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self._chunks: list[str] = []
        self.links: list[dict[str, str]] = []
        self.images: list[dict[str, str]] = []
        self.forms: list[dict[str, Any]] = []
        self._current_form: dict[str, Any] | None = None
        self._current_textarea: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        attr_map = {name.lower(): value or "" for name, value in attrs}
        if lowered in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if lowered == "title":
            self._in_title = True
        if lowered == "a":
            href = attr_map.get("href", "").strip()
            if href and len(self.links) < WEB_MAX_LINKS:
                self.links.append({"href": href, "text": ""})
        if lowered == "img":
            src = attr_map.get("src", "").strip()
            if src and len(self.images) < WEB_MAX_IMAGES:
                self.images.append(
                    {
                        "src": src,
                        "alt": attr_map.get("alt", "").strip(),
                        "title": attr_map.get("title", "").strip(),
                    }
                )
        if lowered == "form":
            self._current_form = {
                "action": attr_map.get("action", "").strip(),
                "method": (attr_map.get("method", "get") or "get").strip().lower(),
                "inputs": [],
            }
        elif self._current_form is not None and lowered == "input":
            name = attr_map.get("name", "").strip()
            if name:
                self._current_form["inputs"].append(
                    {
                        "name": name,
                        "type": (attr_map.get("type", "text") or "text").strip().lower(),
                        "value": attr_map.get("value", ""),
                    }
                )
        elif self._current_form is not None and lowered == "textarea":
            name = attr_map.get("name", "").strip()
            if name:
                self._current_textarea = {"name": name, "type": "textarea", "value": ""}

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if lowered == "title":
            self._in_title = False
        if lowered == "textarea" and self._current_form is not None and self._current_textarea is not None:
            self._current_form["inputs"].append(self._current_textarea)
            self._current_textarea = None
        if lowered == "form" and self._current_form is not None:
            self.forms.append(self._current_form)
            self._current_form = None
        if lowered in {"p", "div", "section", "article", "li", "br", "h1", "h2", "h3"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        cleaned = " ".join(html.unescape(data).split())
        if not cleaned or self._skip_depth:
            return
        if self._in_title:
            self.title = f"{self.title} {cleaned}".strip()
            return
        if self._current_textarea is not None:
            self._current_textarea["value"] = f"{self._current_textarea['value']} {cleaned}".strip()
        self._chunks.append(cleaned)
        if self.links and not self.links[-1]["text"]:
            self.links[-1]["text"] = cleaned[:160]

    @property
    def text(self) -> str:
        return "\n".join(line.strip() for line in " ".join(self._chunks).splitlines() if line.strip())


def extract_urls(text: str) -> list[str]:
    return [match.group(0).rstrip(".,;:") for match in URL_PATTERN.finditer(text)]

def _validate_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return "Only HTTP(S) web pages can be fetched."
    if parsed.username or parsed.password:
        return "URLs with embedded credentials are blocked."
    if not parsed.hostname:
        return "URL must include a hostname."
    try:
        port = parsed.port
    except ValueError:
        return "URL port is invalid."
    if port is not None and not 1 <= port <= 65535:
        return "URL port is invalid."
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError as exc:
        return f"Hostname could not be resolved: {exc}"
    for item in addresses:
        address = item[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return "Hostname resolved to an invalid address."
        if ip.is_loopback:
            continue
        if not ip.is_global:
            return "Private, local, multicast, or reserved network addresses are blocked."
    return None


def _fetch_page(url: str, max_bytes: int) -> dict[str, Any]:
    opener = urllib.request.build_opener(_NoRedirectHandler)
    request = urllib.request.Request(url, headers={"User-Agent": "UmangLocalAssistant/0.1"})
    try:
        with opener.open(request, timeout=WEB_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("content-type", "")
            if not _is_supported_content_type(content_type):
                raise ValueError(f"Unsupported content type: {content_type or 'unknown'}")
            raw = response.read(max_bytes + 1)
            final_url = response.geturl()
            charset = response.headers.get_content_charset("utf-8")
    except urllib.error.HTTPError as exc:
        raise ValueError(f"HTTP error {exc.code}") from exc
    truncated = len(raw) > max_bytes
    body = raw[:max_bytes].decode(charset or "utf-8", errors="replace")
    if "html" in content_type.lower():
        parser = _HTMLTextExtractor()
        parser.feed(body)
        title = parser.title
        text = parser.text
        links = parser.links
        images = parser.images
        forms = parser.forms
    else:
        title = ""
        text = body
        links = []
        images = []
        forms = []
    return {
        "url": final_url,
        "title": title,
        "text": text,
        "links": links,
        "images": images,
        "forms": forms,
        "content_type": content_type,
        "truncated": truncated,
    }


def _submit_form(url: str, method: str, values: dict[str, str], max_bytes: int) -> dict[str, Any]:
    if method == "get":
        separator = "&" if urlparse(url).query else "?"
        return _fetch_page(f"{url}{separator}{urlencode(values)}", max_bytes=max_bytes)
    opener = urllib.request.build_opener(_NoRedirectHandler)
    encoded = urlencode(values).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=encoded,
        headers={
            "User-Agent": "UmangLocalAssistant/0.1",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with opener.open(request, timeout=WEB_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("content-type", "")
            if not _is_supported_content_type(content_type):
                raise ValueError(f"Unsupported content type: {content_type or 'unknown'}")
            raw = response.read(max_bytes + 1)
            final_url = response.geturl()
            charset = response.headers.get_content_charset("utf-8")
    except urllib.error.HTTPError as exc:
        raise ValueError(f"HTTP error {exc.code}") from exc
    truncated = len(raw) > max_bytes
    body = raw[:max_bytes].decode(charset or "utf-8", errors="replace")
    if "html" in content_type.lower():
        parser = _HTMLTextExtractor()
        parser.feed(body)
        return {
            "url": final_url,
            "title": parser.title,
            "text": parser.text,
            "links": parser.links,
            "images": parser.images,
            "forms": parser.forms,
            "content_type": content_type,
            "truncated": truncated,
        }
    return {
        "url": final_url,
        "title": "",
        "text": body,
        "links": [],
        "images": [],
        "forms": [],
        "content_type": content_type,
        "truncated": truncated,
    }


def _is_supported_content_type(content_type: str) -> bool:
    lowered = content_type.lower()
    return not lowered or lowered.startswith("text/") or "html" in lowered or "json" in lowered
