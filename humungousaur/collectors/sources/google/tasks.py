from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime

from .common import GOOGLE_WORKSPACE_TASKS_SCOPE, _app_result, _connector_request, _scope_gated_result, _utc_now
from .events import append_google_workspace_event


class TasksCollector:
    app = "tasks"
    required_scopes = (GOOGLE_WORKSPACE_TASKS_SCOPE,)
    description = "Polls Google Tasks metadata when scoped, and accepts task webhook/add-on events."
    source_channel = "tasks_api+webhook"
    implementation_level = "scope_gated_poller_and_webhook_ingress"
    poller_supported = True
    webhook_supported = True
    derived_from: tuple[str, ...] = ()

    def collect(
        self,
        config: AgentConfig,
        runtime: ConnectorRuntime,
        readiness: dict[str, Any],
        app_state: dict[str, Any],
        *,
        dry_run: bool,
        max_events: int,
    ) -> dict[str, Any]:
        gated = _scope_gated_result(self.app, readiness, self.required_scopes, self.source_channel)
        if gated is not None:
            return gated
        if dry_run:
            return _app_result("tasks", "running", "Dry run skipped Google Tasks API calls.", cursor=app_state.get("updated_min", ""), source_channel=self.source_channel, implementation_level=self.implementation_level)
        updated_min = str(app_state.get("updated_min") or "").strip()
        if not updated_min:
            app_state["updated_min"] = _utc_now()
            app_state["baseline_at"] = app_state["updated_min"]
            return _app_result("tasks", "running", "Google Tasks updatedMin baseline recorded.", cursor=app_state["updated_min"], source_channel=self.source_channel, implementation_level=self.implementation_level)

        page_token = str(app_state.get("page_token") or "").strip()
        query = {
            "updatedMin": updated_min,
            "showCompleted": "true",
            "showDeleted": "true",
            "showHidden": "true",
            "maxResults": max_events,
            "fields": "items(id,status,updated,due,completed,deleted),nextPageToken",
        }
        if page_token:
            query["pageToken"] = page_token
        response = _connector_request(
            runtime,
            operation="tasks_list",
            path="/tasks/v1/lists/@default/tasks",
            query=query,
            required_scopes=self.required_scopes,
        )
        body = response.get("response") if isinstance(response.get("response"), dict) else {}
        events_appended = 0
        max_updated = updated_min
        for item in body.get("items") if isinstance(body.get("items"), list) else []:
            if events_appended >= max_events:
                break
            append_google_workspace_event(config, _task_item_to_event(item))
            events_appended += 1
            max_updated = max(max_updated, str(item.get("updated") or ""))
        next_page = str(body.get("nextPageToken") or "")
        if next_page:
            app_state["page_token"] = next_page
        else:
            app_state.pop("page_token", None)
            app_state["updated_min"] = max_updated or _utc_now()
        app_state["last_polled_at"] = _utc_now()
        return _app_result("tasks", "running", "Google Tasks metadata polled.", cursor=app_state.get("page_token") or app_state.get("updated_min", ""), events_appended=events_appended, source_channel=self.source_channel, implementation_level=self.implementation_level)


def _task_item_to_event(item: Any) -> dict[str, Any]:
    payload = item if isinstance(item, dict) else {}
    event_type = "task_completed" if str(payload.get("status") or "") == "completed" else "task_updated"
    if payload.get("deleted"):
        event_type = "task_updated"
    return {
        "app": "tasks",
        "event_type": event_type,
        "object_type": "task",
        "object_id": str(payload.get("id") or ""),
        "task_id": str(payload.get("id") or ""),
        "provider_event_id": f"tasks:{payload.get('id') or ''}:{payload.get('updated') or ''}",
        "occurred_at": str(payload.get("updated") or ""),
        "metadata": {
            "source_channel": "tasks_api",
            "has_due_date": bool(payload.get("due")),
            "completed": bool(payload.get("completed")),
            "deleted": bool(payload.get("deleted")),
        },
    }


GOOGLE_TASKS_COLLECTOR = TasksCollector()
