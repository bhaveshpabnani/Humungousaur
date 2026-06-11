from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


BROWSER_SOURCE_ID = "browsers"
BROWSER_CONSUMER = "browser_sources"
BROWSER_PRIVACY_TIER = "sensitive_metadata"


@dataclass(frozen=True, slots=True)
class BrowserAppCollector:
    browser: str
    display_name: str
    engine: str
    extension_family: str
    description: str
    source_channel: str = "browser_extension"
    implementation_level: str = "extension_or_native_messaging_ingress"
    supported_events: tuple[str, ...] = ()

    def status_record(self) -> dict[str, Any]:
        return {
            "browser": self.browser,
            "display_name": self.display_name,
            "engine": self.engine,
            "extension_family": self.extension_family,
            "description": self.description,
            "source_channel": self.source_channel,
            "implementation_level": self.implementation_level,
            "supported_events": list(self.supported_events),
            "connector_boundary": "local extension/native messaging source; no OAuth token access",
        }


BROWSER_EVENT_FAMILIES = (
    "tab_lifecycle",
    "window_lifecycle",
    "profile",
    "url_navigation",
    "downloads_uploads",
    "forms",
    "page_errors",
    "extension_actions",
    "installed_web_apps",
    "view_modes",
    "tab_groups",
    "bookmarks_history",
)


def app_result(browser: str, status: str, message: str, *, events_appended: int = 0) -> dict[str, Any]:
    return {
        "browser": browser,
        "status": status,
        "message": message[:500],
        "events_appended": int(events_appended),
    }


def clean_token(value: Any) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", "_").replace(".", "_").split())


def hash_value(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def safe_url_metadata(url: Any, *, prefix: str = "url") -> dict[str, Any]:
    text = str(url or "").strip()
    if not text:
        return {}
    parsed = urlparse(text)
    metadata: dict[str, Any] = {
        f"{prefix}_hash": hash_value(text),
        f"{prefix}_redacted": True,
    }
    if parsed.scheme:
        metadata[f"{prefix}_scheme"] = clean_token(parsed.scheme)
    if parsed.netloc:
        metadata[f"{prefix}_host_hash"] = hash_value(parsed.netloc.lower())
    if parsed.path:
        metadata[f"{prefix}_path_redacted"] = True
    if parsed.query:
        metadata[f"{prefix}_query_redacted"] = True
    if parsed.fragment:
        metadata[f"{prefix}_fragment_redacted"] = True
    metadata[f"{prefix}_is_secure"] = parsed.scheme == "https"
    return metadata


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
