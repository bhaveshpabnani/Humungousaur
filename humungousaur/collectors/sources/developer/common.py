from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any


LOCAL_DEVELOPER_PROVIDER_IDS = {"terminal", "git", "vscode", "jetbrains", "xcode"}
CODE_HOSTING_PROVIDER_IDS = {"github", "gitlab", "bitbucket", "azure_devops"}
DEVELOPER_PROVIDER_IDS = LOCAL_DEVELOPER_PROVIDER_IDS | CODE_HOSTING_PROVIDER_IDS
DEVELOPER_CONSUMER = "developer_sources"
DEVELOPER_MAX_EVENTS_PER_PROVIDER = 25


@dataclass(frozen=True, slots=True)
class DeveloperAppCollector:
    provider_id: str
    app: str
    description: str
    source_channel: str
    implementation_level: str
    poller_supported: bool = False
    webhook_supported: bool = False
    required_scopes: tuple[str, ...] = ()
    official_docs: tuple[str, ...] = ()

    def to_record(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "app": self.app,
            "description": self.description,
            "source_channel": self.source_channel,
            "implementation_level": self.implementation_level,
            "poller_supported": self.poller_supported,
            "webhook_supported": self.webhook_supported,
            "required_scopes": list(self.required_scopes),
            "official_docs": list(self.official_docs),
        }


def source_result(
    provider_id: str,
    status: str,
    message: str,
    *,
    events_appended: int = 0,
    source_channel: str = "",
    implementation_level: str = "",
) -> dict[str, Any]:
    return {
        "provider_id": provider_id,
        "status": status,
        "message": message[:500],
        "events_appended": int(events_appended),
        "source_channel": source_channel,
        "implementation_level": implementation_level,
    }


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
