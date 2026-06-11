from __future__ import annotations

from .common import GOOGLE_WORKSPACE_DRIVE_SCOPE, GoogleWorkspaceBridgeCollector


GOOGLE_DOCS_COLLECTOR = GoogleWorkspaceBridgeCollector(
    app="docs",
    required_scopes=(GOOGLE_WORKSPACE_DRIVE_SCOPE,),
    description="Collects Google Docs workflow events from Drive file changes, Workspace add-ons, and webhook ingress.",
    source_channel="drive_changes+docs_addon+webhook",
    implementation_level="drive_derived_and_addon_ingress",
    poller_supported=True,
    webhook_supported=True,
    derived_from=("drive",),
)
