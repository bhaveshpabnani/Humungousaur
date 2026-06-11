from __future__ import annotations

from .common import GOOGLE_WORKSPACE_DRIVE_SCOPE, GoogleWorkspaceBridgeCollector


GOOGLE_SHEETS_COLLECTOR = GoogleWorkspaceBridgeCollector(
    app="sheets",
    required_scopes=(GOOGLE_WORKSPACE_DRIVE_SCOPE,),
    description="Collects Google Sheets edits, formulas, analysis, import/export, and sharing metadata from Drive changes, add-ons, and webhooks.",
    source_channel="drive_changes+sheets_addon+webhook",
    implementation_level="drive_derived_and_addon_ingress",
    poller_supported=True,
    webhook_supported=True,
    derived_from=("drive",),
)
