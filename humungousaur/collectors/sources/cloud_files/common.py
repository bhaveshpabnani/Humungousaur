from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any

from humungousaur.connectors import ConnectorOperationRequest, ConnectorRuntime


CLOUD_FILE_CONSUMER = "connector_sources"
CLOUD_FILE_MAX_EVENTS_PER_PROVIDER = 20

DROPBOX_PROVIDER_ID = "dropbox"
BOX_PROVIDER_ID = "box"
ICLOUD_PROVIDER_ID = "icloud"
GOOGLE_WORKSPACE_PROVIDER_ID = "google_workspace"
MICROSOFT_365_PROVIDER_ID = "microsoft_365"
NEXTCLOUD_PROVIDER_ID = "nextcloud"
CLOUD_FILE_PROVIDER_IDS = (
    DROPBOX_PROVIDER_ID,
    BOX_PROVIDER_ID,
    ICLOUD_PROVIDER_ID,
    GOOGLE_WORKSPACE_PROVIDER_ID,
    MICROSOFT_365_PROVIDER_ID,
    NEXTCLOUD_PROVIDER_ID,
)

DROPBOX_METADATA_SCOPES = ("files.metadata.read", "sharing.read")
BOX_METADATA_SCOPES = ("root_readonly",)
NEXTCLOUD_METADATA_SCOPES: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CloudFileTickResult:
    provider_id: str
    status: str
    message: str
    events_appended: int = 0
    cursor_present: bool = False
    source_channel: str = ""
    implementation_level: str = "poller"

    def to_record(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "status": self.status,
            "message": self.message[:500],
            "events_appended": int(self.events_appended),
            "cursor_present": self.cursor_present,
            "source_channel": self.source_channel,
            "implementation_level": self.implementation_level,
        }


def connector_request(
    runtime: ConnectorRuntime,
    *,
    provider_id: str,
    operation: str,
    method: str = "GET",
    path: str,
    query: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    required_scopes: tuple[str, ...],
) -> dict[str, Any]:
    return runtime.execute_operation(
        ConnectorOperationRequest(
            provider_id=provider_id,
            operation=operation,
            method=method,
            path=path,
            query=query or {},
            body=body,
            required_scopes=required_scopes,
            reason="Poll cloud-file metadata changes for local collector events.",
        )
    )


def app_result(
    provider_id: str,
    status: str,
    message: str,
    *,
    events_appended: int = 0,
    cursor: str = "",
    source_channel: str = "",
    implementation_level: str = "poller",
) -> dict[str, Any]:
    return CloudFileTickResult(
        provider_id=provider_id,
        status=status,
        message=message,
        events_appended=events_appended,
        cursor_present=bool(cursor),
        source_channel=source_channel,
        implementation_level=implementation_level,
    ).to_record()


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def clean_token(value: Any) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", "_").replace(".", "_").split())


def hash_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def path_fingerprint(path: Any) -> dict[str, str]:
    text = str(path or "").strip()
    if not text:
        return {}
    pieces = [piece for piece in text.replace("\\", "/").split("/") if piece]
    return {
        "path_hash": hash_text(text),
        "parent_path_hash": hash_text("/".join(pieces[:-1])) if pieces[:-1] else "",
        "basename_hash": hash_text(pieces[-1]) if pieces else "",
    }
