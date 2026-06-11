from __future__ import annotations

from .common import BusinessOperationsCollector


SALESFORCE_COLLECTOR = BusinessOperationsCollector(
    provider_id="salesforce",
    app="salesforce",
    domain="crm",
    description="Accepts Salesforce Change Data Capture, Platform Event, report/dashboard, and browser-extension CRM activity metadata.",
    source_channel="change_data_capture+platform_events+browser_extension",
    docs_url="https://developer.salesforce.com/docs/atlas.en-us.change_data_capture.meta/change_data_capture/cdc_intro.htm",
    required_scopes=("api", "refresh_token"),
)
