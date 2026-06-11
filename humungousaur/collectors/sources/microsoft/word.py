from __future__ import annotations

from .common import MICROSOFT_365_FILES_SCOPE, Microsoft365BridgeCollector


MICROSOFT_WORD_COLLECTOR = Microsoft365BridgeCollector(
    app="word",
    required_scopes=(MICROSOFT_365_FILES_SCOPE,),
    description="Collects Word document workflow events from Graph drive changes, Office add-ins, browser extensions, or webhook ingress.",
    source_channel="drive_delta+word_addin+change_notifications",
    implementation_level="drive_derived_and_addin_ingress",
    poller_supported=True,
    webhook_supported=True,
    derived_from=("onedrive", "sharepoint"),
)
