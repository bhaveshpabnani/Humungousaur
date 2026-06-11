from __future__ import annotations

from .common import MICROSOFT_365_FILES_SCOPE, Microsoft365BridgeCollector


MICROSOFT_EXCEL_COLLECTOR = Microsoft365BridgeCollector(
    app="excel",
    required_scopes=(MICROSOFT_365_FILES_SCOPE,),
    description="Collects Excel workbook, sheet, formula, chart, pivot, import/export, and sharing events from Graph file changes plus Office add-in ingress.",
    source_channel="drive_delta+excel_addin+workbook_webhook",
    implementation_level="drive_derived_and_addin_ingress",
    poller_supported=True,
    webhook_supported=True,
    derived_from=("onedrive", "sharepoint"),
)
