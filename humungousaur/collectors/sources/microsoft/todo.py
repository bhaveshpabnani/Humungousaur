from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime

from .common import (
    MICROSOFT_365_TASKS_SCOPE,
    _app_result,
    _connector_request,
    _connector_request_from_link,
    _scope_gated_result,
    _store_delta_cursor,
    _utc_now,
)
from .events import append_microsoft_365_event


class ToDoCollector:
    app = "todo"
    required_scopes = (MICROSOFT_365_TASKS_SCOPE,)
    description = "Polls Microsoft To Do task-list task deltas when scoped, and accepts task webhooks/browser events."
    source_channel = "graph_todo_delta+webhook"
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
            return _app_result("todo", "running", "Dry run skipped Microsoft To Do calls.", cursor=app_state.get("delta_link", ""), source_channel=self.source_channel, implementation_level=self.implementation_level)
        list_id = str(app_state.get("list_id") or "").strip()
        if not list_id:
            response = _connector_request(
                runtime,
                operation="todo_lists",
                path="/v1.0/me/todo/lists",
                query={"$select": "id,wellknownListName", "$top": max_events},
                required_scopes=self.required_scopes,
            )
            body = response.get("response") if isinstance(response.get("response"), dict) else {}
            lists = body.get("value") if isinstance(body.get("value"), list) else []
            chosen = next((item for item in lists if isinstance(item, dict) and item.get("wellknownListName") == "defaultList"), lists[0] if lists else {})
            list_id = str(chosen.get("id") or "") if isinstance(chosen, dict) else ""
            if list_id:
                app_state["list_id"] = list_id
            app_state["baseline_at"] = _utc_now()
            return _app_result("todo", "running", "Microsoft To Do list baseline recorded.", cursor=list_id, source_channel=self.source_channel, implementation_level=self.implementation_level)

        delta_link = str(app_state.get("delta_link") or "").strip()
        if not delta_link:
            response = _connector_request(
                runtime,
                operation="todo_tasks_delta_baseline",
                path=f"/v1.0/me/todo/lists/{list_id}/tasks/delta",
                query={"$select": "id,status,createdDateTime,lastModifiedDateTime,dueDateTime,completedDateTime,importance", "$top": max_events},
                required_scopes=self.required_scopes,
            )
            body = response.get("response") if isinstance(response.get("response"), dict) else {}
            _store_delta_cursor(app_state, body)
            app_state["baseline_at"] = _utc_now()
            return _app_result("todo", "running", "Microsoft To Do task delta cursor baseline recorded.", cursor=app_state.get("delta_link", ""), source_channel=self.source_channel, implementation_level=self.implementation_level)

        response = _connector_request_from_link(runtime, operation="todo_tasks_delta", link=delta_link, required_scopes=self.required_scopes)
        body = response.get("response") if isinstance(response.get("response"), dict) else {}
        events_appended = 0
        for item in body.get("value") if isinstance(body.get("value"), list) else []:
            if events_appended >= max_events:
                break
            append_microsoft_365_event(config, _task_to_event(item))
            events_appended += 1
        _store_delta_cursor(app_state, body)
        app_state["last_polled_at"] = _utc_now()
        return _app_result("todo", "running", "Microsoft To Do task delta polled.", cursor=app_state.get("delta_link", ""), events_appended=events_appended, source_channel=self.source_channel, implementation_level=self.implementation_level)


def _task_to_event(item: Any) -> dict[str, Any]:
    payload = item if isinstance(item, dict) else {}
    task_id = str(payload.get("id") or "")
    created = str(payload.get("createdDateTime") or "")
    modified = str(payload.get("lastModifiedDateTime") or "")
    removed = isinstance(payload.get("@removed"), dict)
    status = str(payload.get("status") or "")
    if status == "completed":
        event_type = "task_completed"
    elif created and created == modified:
        event_type = "task_created"
    else:
        event_type = "task_updated"
    return {
        "app": "todo",
        "event_type": event_type,
        "object_type": "todo_task",
        "object_id": task_id,
        "task_id": task_id,
        "provider_event_id": f"todo-task:{task_id}:{modified}:{removed}",
        "occurred_at": modified or created,
        "metadata": {
            "source_channel": "graph_todo_delta",
            "completed": status == "completed",
            "deleted": removed,
            "has_due_date": bool(payload.get("dueDateTime")),
            "importance": str(payload.get("importance") or ""),
        },
    }


MICROSOFT_TODO_COLLECTOR = ToDoCollector()
