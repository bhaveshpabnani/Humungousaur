from __future__ import annotations

from .common import MICROSOFT_365_FILES_SCOPE, Microsoft365BridgeCollector


MICROSOFT_POWERPOINT_COLLECTOR = Microsoft365BridgeCollector(
    app="powerpoint",
    required_scopes=(MICROSOFT_365_FILES_SCOPE,),
    description="Collects PowerPoint deck authoring, delivery, export, and sharing events from Graph file changes plus Office add-in ingress.",
    source_channel="drive_delta+powerpoint_addin+change_notifications",
    implementation_level="drive_derived_and_addin_ingress",
    poller_supported=True,
    webhook_supported=True,
    derived_from=("onedrive", "sharepoint"),
)
