from __future__ import annotations

from .common import PlanningWebhookCollector


TODOIST_COLLECTOR = PlanningWebhookCollector(
    provider_id="todoist",
    app="todoist",
    description="Accepts Todoist Sync API, browser-extension, or local relay task, project, comment, and due-date events.",
    source_channel="todoist_sync_api+browser_extension",
)
