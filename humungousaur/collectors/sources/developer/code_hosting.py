from __future__ import annotations

from collections.abc import Iterable
import hashlib
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorOperationRequest, ConnectorRuntime

from ..workspace_connectors import ConnectorEventMapping
from .common import DEVELOPER_MAX_EVENTS_PER_PROVIDER, DeveloperAppCollector, source_result


CODE_HOSTING_SOURCE_MANIFESTS = (
    DeveloperAppCollector(
        provider_id="github",
        app="GitHub",
        description="GitHub webhook and API metadata for pull requests, reviews, issues, branches, and Actions checks.",
        source_channel="github_webhook_or_api_poller",
        implementation_level="saas_webhook_or_connector_poller",
        poller_supported=True,
        webhook_supported=True,
        required_scopes=("repo", "workflow"),
        official_docs=("https://docs.github.com/en/webhooks/webhook-events-and-payloads",),
    ),
    DeveloperAppCollector(
        provider_id="gitlab",
        app="GitLab",
        description="GitLab webhook and API metadata for merge requests, approvals, issues, branches, pipelines, and jobs.",
        source_channel="gitlab_webhook_or_api_poller",
        implementation_level="saas_webhook_or_connector_poller",
        poller_supported=True,
        webhook_supported=True,
        required_scopes=("read_api",),
        official_docs=(
            "https://docs.gitlab.com/user/project/integrations/webhook_events/",
            "https://docs.gitlab.com/user/project/integrations/webhooks/",
        ),
    ),
    DeveloperAppCollector(
        provider_id="bitbucket",
        app="Bitbucket",
        description="Bitbucket Cloud webhook and API metadata for pull requests, reviews, issues, branches, and Pipelines.",
        source_channel="bitbucket_webhook_or_api_poller",
        implementation_level="saas_webhook_or_connector_poller",
        poller_supported=True,
        webhook_supported=True,
        required_scopes=("repository", "pullrequest", "pipeline", "issue"),
        official_docs=(
            "https://support.atlassian.com/bitbucket-cloud/docs/manage-webhooks/",
            "https://support.atlassian.com/bitbucket-cloud/docs/event-payloads/",
        ),
    ),
    DeveloperAppCollector(
        provider_id="azure_devops",
        app="Azure DevOps",
        description="Azure DevOps service-hook and REST API metadata for repos, pull requests, comments, work items, builds, and pipelines.",
        source_channel="azure_devops_service_hook_or_api_poller",
        implementation_level="saas_webhook_or_connector_poller",
        poller_supported=True,
        webhook_supported=True,
        required_scopes=("vso.code", "vso.build", "vso.work"),
        official_docs=(
            "https://learn.microsoft.com/en-us/azure/devops/service-hooks/events?view=azure-devops",
            "https://learn.microsoft.com/en-us/azure/devops/service-hooks/overview?view=azure-devops",
        ),
    ),
)

CODE_HOSTING_EVENT_MAPPINGS = (
    ConnectorEventMapping("pull_request_opened", "code_hosting_activity", "pr_opened", "Pull request was opened"),
    ConnectorEventMapping("merge_request_opened", "code_hosting_activity", "pr_opened", "Merge request was opened"),
    ConnectorEventMapping("pull_request_updated", "code_hosting_activity", "pr_updated", "Pull request was updated"),
    ConnectorEventMapping("merge_request_updated", "code_hosting_activity", "pr_updated", "Merge request was updated"),
    ConnectorEventMapping("review_requested", "code_hosting_activity", "review_requested", "Code review was requested"),
    ConnectorEventMapping("pull_request_review_submitted", "code_hosting_activity", "review_submitted", "Pull request review was submitted"),
    ConnectorEventMapping("merge_request_review_submitted", "code_hosting_activity", "review_submitted", "Merge request review was submitted"),
    ConnectorEventMapping("review_approved", "code_hosting_activity", "review_approved", "Code review was approved"),
    ConnectorEventMapping("review_changes_requested", "code_hosting_activity", "review_changes_requested", "Code review requested changes"),
    ConnectorEventMapping("pull_request_merged", "code_hosting_activity", "pr_merged", "Pull request was merged"),
    ConnectorEventMapping("merge_request_merged", "code_hosting_activity", "pr_merged", "Merge request was merged"),
    ConnectorEventMapping("merge_ready", "code_hosting_activity", "merge_ready", "Code review is merge ready"),
    ConnectorEventMapping("branch_created", "code_hosting_activity", "branch_created", "Remote branch was created"),
    ConnectorEventMapping("branch_deleted", "code_hosting_activity", "branch_deleted", "Remote branch was deleted"),
    ConnectorEventMapping("commit_pushed", "code_hosting_activity", "commit_pushed", "Commit was pushed"),
    ConnectorEventMapping("ci_started", "code_hosting_activity", "ci_started", "CI run started"),
    ConnectorEventMapping("pipeline_started", "code_hosting_activity", "ci_started", "CI pipeline started"),
    ConnectorEventMapping("ci_passed", "code_hosting_activity", "ci_passed", "CI run passed"),
    ConnectorEventMapping("pipeline_succeeded", "code_hosting_activity", "ci_passed", "CI pipeline succeeded"),
    ConnectorEventMapping("ci_failed", "code_hosting_activity", "ci_failed", "CI run failed"),
    ConnectorEventMapping("pipeline_failed", "code_hosting_activity", "ci_failed", "CI pipeline failed"),
    ConnectorEventMapping("ci_canceled", "code_hosting_activity", "ci_canceled", "CI run was canceled"),
    ConnectorEventMapping("pipeline_canceled", "code_hosting_activity", "ci_canceled", "CI pipeline was canceled"),
    ConnectorEventMapping("issue_created", "issue_tracker_activity", "issue_created", "Issue was created"),
    ConnectorEventMapping("issue_assigned", "issue_tracker_activity", "issue_assigned", "Issue was assigned"),
    ConnectorEventMapping("issue_status_changed", "issue_tracker_activity", "issue_status_changed", "Issue status changed"),
    ConnectorEventMapping("issue_comment_received", "issue_tracker_activity", "issue_comment_received", "Issue received a comment"),
    ConnectorEventMapping("comment_received", "code_hosting_activity", "comment_received", "Code-hosting comment metadata was received"),
)


_GITHUB_EVENT_BY_ACTION = {
    ("pull_request", "opened"): "pull_request_opened",
    ("pull_request", "edited"): "pull_request_updated",
    ("pull_request", "synchronize"): "pull_request_updated",
    ("pull_request", "reopened"): "pull_request_updated",
    ("pull_request", "closed"): "pull_request_merged",
    ("pull_request_review", "submitted"): "pull_request_review_submitted",
    ("pull_request_review", "edited"): "pull_request_review_submitted",
    ("pull_request_review", "dismissed"): "review_changes_requested",
    ("check_run", "created"): "ci_started",
    ("check_run", "completed"): "ci_passed",
    ("workflow_run", "requested"): "ci_started",
    ("workflow_run", "completed"): "ci_passed",
    ("issues", "opened"): "issue_created",
    ("issues", "assigned"): "issue_assigned",
    ("issues", "closed"): "issue_status_changed",
    ("issues", "reopened"): "issue_status_changed",
    ("issue_comment", "created"): "issue_comment_received",
    ("pull_request_review_comment", "created"): "comment_received",
}

_GITLAB_EVENT_BY_KIND_ACTION = {
    ("merge_request", "open"): "merge_request_opened",
    ("merge_request", "update"): "merge_request_updated",
    ("merge_request", "approval"): "review_approved",
    ("merge_request", "approved"): "review_approved",
    ("merge_request", "unapproval"): "review_changes_requested",
    ("merge_request", "unapproved"): "review_changes_requested",
    ("merge_request", "merge"): "merge_request_merged",
    ("pipeline", "success"): "pipeline_succeeded",
    ("pipeline", "failed"): "pipeline_failed",
    ("pipeline", "canceled"): "pipeline_canceled",
    ("job", "success"): "pipeline_succeeded",
    ("job", "failed"): "pipeline_failed",
    ("issue", "open"): "issue_created",
    ("issue", "update"): "issue_status_changed",
    ("issue", "close"): "issue_status_changed",
    ("note", ""): "comment_received",
    ("push", ""): "commit_pushed",
}

_BITBUCKET_EVENT_BY_KEY = {
    "repo:push": "commit_pushed",
    "pullrequest:created": "pull_request_opened",
    "pullrequest:updated": "pull_request_updated",
    "pullrequest:approved": "review_approved",
    "pullrequest:unapproved": "review_changes_requested",
    "pullrequest:fulfilled": "pull_request_merged",
    "pullrequest:comment_created": "comment_received",
    "pullrequest:comment_updated": "comment_received",
    "issue:created": "issue_created",
    "issue:updated": "issue_status_changed",
    "issue:comment_created": "issue_comment_received",
    "repo:commit_status_created": "ci_started",
    "repo:commit_status_updated": "ci_passed",
}

_AZURE_EVENT_BY_TYPE = {
    "git.pullrequest.created": "pull_request_opened",
    "git.pullrequest.updated": "pull_request_updated",
    "git.pullrequest.merged": "pull_request_merged",
    "git.pullrequest.commented-on": "comment_received",
    "git.push": "commit_pushed",
    "tfvc.checkin": "commit_pushed",
    "build.complete": "ci_passed",
    "ms.vss-pipelines.run-state-changed-event": "ci_passed",
    "workitem.created": "issue_created",
    "workitem.updated": "issue_status_changed",
    "workitem.commented": "issue_comment_received",
}


def normalize_code_hosting_webhook(
    provider_id: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider = _provider_alias(provider_id)
    if provider == "github":
        return _normalize_github_webhook(payload, headers or {})
    if provider == "gitlab":
        return _normalize_gitlab_webhook(payload, headers or {})
    if provider == "bitbucket":
        return _normalize_bitbucket_webhook(payload, headers or {})
    if provider == "azure_devops":
        return _normalize_azure_devops_webhook(payload, headers or {})
    raise ValueError(f"unsupported code-hosting provider: {provider_id or '<empty>'}")


def append_code_hosting_webhook_event(
    config: AgentConfig,
    provider_id: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from ..workspace_connectors import append_connector_source_event

    normalized = normalize_code_hosting_webhook(provider_id, payload, headers=headers)
    return append_connector_source_event(config, **normalized)


def poll_code_hosting_provider(
    config: AgentConfig,
    runtime: ConnectorRuntime,
    provider_id: str,
    readiness: dict[str, Any],
    provider_state: dict[str, Any],
    *,
    dry_run: bool = False,
    max_events: int = DEVELOPER_MAX_EVENTS_PER_PROVIDER,
) -> dict[str, Any]:
    provider = _provider_alias(provider_id)
    if provider not in {"github", "gitlab", "bitbucket", "azure_devops"}:
        return source_result(provider, "failed", f"Unsupported code-hosting provider: {provider_id}")
    if not readiness.get("collector_ready"):
        return source_result(provider, "permission_denied", f"{provider} connector is not connected.", source_channel=f"{provider}_api_poller")

    targets = _poll_targets(provider_state)
    if not targets:
        provider_state.setdefault("seen_event_ids", [])
        return source_result(
            provider,
            "running",
            "Connector is ready; add poll_targets to the developer source state to enable API polling.",
            source_channel=f"{provider}_api_poller",
            implementation_level="connector_poller_ready",
        )

    from ..workspace_connectors import append_connector_source_event

    seen = set(str(item) for item in provider_state.setdefault("seen_event_ids", []))
    appended = 0
    operations = 0
    for target in targets:
        for operation in _poll_operations(provider, target, max_events=max_events):
            if dry_run:
                continue
            result = runtime.execute_operation(operation)
            operations += 1
            for event in _events_from_poll_response(provider, operation.operation, result.get("response"), target):
                event_id = _event_identity(provider, event)
                if event_id in seen:
                    continue
                append_result = append_connector_source_event(config, **event)
                seen.add(event_id)
                if append_result.get("accepted"):
                    appended += 1
                if appended >= max_events:
                    break
            if appended >= max_events:
                break
        if appended >= max_events:
            break
    provider_state["seen_event_ids"] = sorted(seen)[-500:]
    provider_state["last_operation_count"] = operations
    status = "running" if appended or targets else "degraded"
    return source_result(
        provider,
        status,
        f"{provider} connector poll completed.",
        events_appended=appended,
        source_channel=f"{provider}_api_poller",
        implementation_level="connector_poller",
    )


def _normalize_github_webhook(payload: dict[str, Any], headers: dict[str, Any]) -> dict[str, Any]:
    event_name = _header(headers, "x-github-event") or str(payload.get("event") or "")
    action = str(payload.get("action") or "").strip().lower()
    source_event = _GITHUB_EVENT_BY_ACTION.get((event_name, action), "")
    if event_name == "pull_request" and action == "closed":
        pull_request = payload.get("pull_request") if isinstance(payload.get("pull_request"), dict) else {}
        source_event = "pull_request_merged" if bool(pull_request.get("merged")) else "issue_status_changed"
    if event_name == "push":
        source_event = "commit_pushed"
    if event_name == "create" and str(payload.get("ref_type") or "") == "branch":
        source_event = "branch_created"
    if event_name == "delete" and str(payload.get("ref_type") or "") == "branch":
        source_event = "branch_deleted"
    if event_name in {"check_run", "workflow_run"} and action == "completed":
        conclusion = _nested(payload, event_name, "conclusion") or _nested(payload, event_name, "status")
        source_event = _ci_event_from_status(conclusion)
    if not source_event:
        raise ValueError(f"unsupported GitHub webhook event: {event_name}/{action}")
    obj = payload.get("pull_request") or payload.get("issue") or payload.get("check_run") or payload.get("workflow_run") or payload
    return _normalized_event(
        "github",
        source_event,
        object_type=event_name,
        object_id=_first_text(obj, "id", "node_id", "number", "after", "ref"),
        metadata={
            "provider_event_type": event_name,
            "provider_action": action,
            "delivery_id": _header(headers, "x-github-delivery"),
            "repository_id": _nested(payload, "repository", "id"),
            "repository_name": _nested(payload, "repository", "full_name"),
            "sender_id": _nested(payload, "sender", "id"),
            "branch_name": payload.get("ref"),
            "title": _first_text(obj, "title", "name"),
            "url": _first_text(obj, "html_url", "url"),
            "status_bucket": _status_bucket(_first_text(obj, "conclusion", "status", "state")),
            "commit_count": _count(payload.get("commits")),
        },
        occurred_at=_first_text(obj, "updated_at", "created_at", "pushed_at", "run_started_at"),
    )


def _normalize_gitlab_webhook(payload: dict[str, Any], headers: dict[str, Any]) -> dict[str, Any]:
    kind = str(payload.get("object_kind") or payload.get("event_type") or _header(headers, "x-gitlab-event") or "").strip().lower()
    kind = kind.replace(" ", "_").replace("_hook", "")
    attrs = payload.get("object_attributes") if isinstance(payload.get("object_attributes"), dict) else {}
    action = str(attrs.get("action") or attrs.get("status") or payload.get("object_attributes", {}).get("state") if isinstance(payload.get("object_attributes"), dict) else "").strip().lower()
    source_event = _GITLAB_EVENT_BY_KIND_ACTION.get((kind, action), "") or _GITLAB_EVENT_BY_KIND_ACTION.get((kind, ""), "")
    if kind == "pipeline":
        source_event = _ci_event_from_status(attrs.get("status"))
    if not source_event:
        raise ValueError(f"unsupported GitLab webhook event: {kind}/{action}")
    return _normalized_event(
        "gitlab",
        source_event,
        object_type=kind,
        object_id=_first_text(attrs, "id", "iid", "head_pipeline_id", "commit_id") or _first_text(payload, "checkout_sha", "after"),
        metadata={
            "provider_event_type": kind,
            "provider_action": action,
            "repository_id": _nested(payload, "project", "id"),
            "repository_name": _nested(payload, "project", "path_with_namespace"),
            "branch_name": attrs.get("source_branch") or payload.get("ref"),
            "user_id": _nested(payload, "user", "id"),
            "title": attrs.get("title"),
            "url": attrs.get("url"),
            "status_bucket": _status_bucket(attrs.get("status") or attrs.get("state")),
            "commit_count": _count(payload.get("commits")),
        },
        occurred_at=_first_text(attrs, "updated_at", "created_at", "finished_at", "actioned_at"),
    )


def _normalize_bitbucket_webhook(payload: dict[str, Any], headers: dict[str, Any]) -> dict[str, Any]:
    event_key = _header(headers, "x-event-key") or str(payload.get("event_key") or "")
    source_event = _BITBUCKET_EVENT_BY_KEY.get(event_key, "")
    if event_key == "repo:commit_status_updated":
        source_event = _ci_event_from_status(_nested(payload, "commit_status", "state"))
    if not source_event:
        raise ValueError(f"unsupported Bitbucket webhook event: {event_key or '<empty>'}")
    obj = payload.get("pullrequest") or payload.get("issue") or payload.get("commit_status") or payload.get("push") or payload
    return _normalized_event(
        "bitbucket",
        source_event,
        object_type=event_key.replace(":", "_"),
        object_id=_first_text(obj, "id", "uuid", "hash") or _nested(payload, "push", "changes", 0, "new", "target", "hash"),
        metadata={
            "provider_event_type": event_key,
            "repository_id": _nested(payload, "repository", "uuid"),
            "repository_name": _nested(payload, "repository", "full_name"),
            "actor_id": _nested(payload, "actor", "account_id"),
            "branch_name": _nested(payload, "push", "changes", 0, "new", "name"),
            "title": _first_text(obj, "title", "name"),
            "url": _nested(obj, "links", "html", "href"),
            "status_bucket": _status_bucket(_first_text(obj, "state")),
            "commit_count": _count(_nested(payload, "push", "changes")),
        },
        occurred_at=_first_text(obj, "updated_on", "created_on"),
    )


def _normalize_azure_devops_webhook(payload: dict[str, Any], headers: dict[str, Any]) -> dict[str, Any]:
    event_type = str(payload.get("eventType") or payload.get("event_type") or _header(headers, "x-vss-event") or "").strip()
    source_event = _AZURE_EVENT_BY_TYPE.get(event_type, "")
    resource = payload.get("resource") if isinstance(payload.get("resource"), dict) else {}
    if event_type in {"build.complete", "ms.vss-pipelines.run-state-changed-event"}:
        source_event = _ci_event_from_status(resource.get("status") or resource.get("result") or resource.get("state"))
    if not source_event:
        raise ValueError(f"unsupported Azure DevOps service-hook event: {event_type or '<empty>'}")
    return _normalized_event(
        "azure_devops",
        source_event,
        object_type=event_type.replace(".", "_"),
        object_id=_first_text(resource, "id", "pullRequestId", "buildNumber", "workItemId") or str(payload.get("id") or ""),
        metadata={
            "provider_event_type": event_type,
            "publisher_id": payload.get("publisherId"),
            "repository_id": _nested(resource, "repository", "id"),
            "repository_name": _nested(resource, "repository", "name"),
            "project_id": _nested(resource, "project", "id"),
            "branch_name": _first_text(resource, "sourceRefName", "targetRefName", "refUpdates"),
            "title": _first_text(resource, "title", "name", "message"),
            "url": _first_text(resource, "url", "_links"),
            "status_bucket": _status_bucket(_first_text(resource, "status", "result", "state")),
        },
        occurred_at=_first_text(resource, "creationDate", "finishTime", "closedDate") or str(payload.get("createdDate") or ""),
    )


def _poll_operations(provider: str, target: dict[str, Any], *, max_events: int) -> Iterable[ConnectorOperationRequest]:
    if provider == "github":
        repository = str(target.get("repository") or target.get("repo") or "").strip("/")
        if repository:
            yield ConnectorOperationRequest(
                provider_id="github",
                operation="developer_github_repo_events",
                path=f"/repos/{repository}/events",
                query={"per_page": max(1, min(max_events, 100))},
                required_scopes=("repo",),
                reason="Poll GitHub repo metadata for developer source collectors.",
            )
            yield ConnectorOperationRequest(
                provider_id="github",
                operation="developer_github_actions_runs",
                path=f"/repos/{repository}/actions/runs",
                query={"per_page": max(1, min(max_events, 100))},
                required_scopes=("repo", "workflow"),
                reason="Poll GitHub Actions run metadata for developer source collectors.",
            )
    elif provider == "gitlab":
        project_id = str(target.get("project_id") or target.get("project") or "").strip("/")
        if project_id:
            yield ConnectorOperationRequest(
                provider_id="gitlab",
                operation="developer_gitlab_project_events",
                path=f"/projects/{project_id}/events",
                query={"per_page": max(1, min(max_events, 100))},
                required_scopes=("read_api",),
                reason="Poll GitLab project event metadata for developer source collectors.",
            )
            yield ConnectorOperationRequest(
                provider_id="gitlab",
                operation="developer_gitlab_pipelines",
                path=f"/projects/{project_id}/pipelines",
                query={"per_page": max(1, min(max_events, 100))},
                required_scopes=("read_api",),
                reason="Poll GitLab pipeline metadata for developer source collectors.",
            )
    elif provider == "bitbucket":
        workspace = str(target.get("workspace") or "").strip("/")
        repo = str(target.get("repo_slug") or target.get("repository") or "").strip("/")
        if workspace and repo:
            yield ConnectorOperationRequest(
                provider_id="bitbucket",
                operation="developer_bitbucket_pullrequests",
                path=f"/2.0/repositories/{workspace}/{repo}/pullrequests",
                query={"pagelen": max(1, min(max_events, 100))},
                required_scopes=("pullrequest",),
                reason="Poll Bitbucket pull request metadata for developer source collectors.",
            )
            yield ConnectorOperationRequest(
                provider_id="bitbucket",
                operation="developer_bitbucket_pipelines",
                path=f"/2.0/repositories/{workspace}/{repo}/pipelines",
                query={"pagelen": max(1, min(max_events, 100))},
                required_scopes=("pipeline",),
                reason="Poll Bitbucket Pipelines metadata for developer source collectors.",
            )
    elif provider == "azure_devops":
        organization = str(target.get("organization") or "").strip("/")
        project = str(target.get("project") or "").strip("/")
        repository = str(target.get("repository_id") or target.get("repository") or "").strip("/")
        if organization and project and repository:
            yield ConnectorOperationRequest(
                provider_id="azure_devops",
                operation="developer_azure_devops_pullrequests",
                path=f"/{organization}/{project}/_apis/git/repositories/{repository}/pullrequests",
                query={"api-version": "7.1", "$top": max(1, min(max_events, 100))},
                required_scopes=("vso.code",),
                reason="Poll Azure DevOps pull request metadata for developer source collectors.",
            )
            yield ConnectorOperationRequest(
                provider_id="azure_devops",
                operation="developer_azure_devops_builds",
                path=f"/{organization}/{project}/_apis/build/builds",
                query={"api-version": "7.1", "$top": max(1, min(max_events, 100))},
                required_scopes=("vso.build",),
                reason="Poll Azure DevOps build metadata for developer source collectors.",
            )


def _events_from_poll_response(provider: str, operation: str, response: Any, target: dict[str, Any]) -> list[dict[str, Any]]:
    items = _response_items(response)
    events = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if provider == "github":
            events.append(_github_poll_event(operation, item, target))
        elif provider == "gitlab":
            events.append(_gitlab_poll_event(operation, item, target))
        elif provider == "bitbucket":
            events.append(_bitbucket_poll_event(operation, item, target))
        elif provider == "azure_devops":
            events.append(_azure_poll_event(operation, item, target))
    return [event for event in events if event]


def _github_poll_event(operation: str, item: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    if operation == "developer_github_actions_runs":
        source_event = _ci_event_from_status(item.get("conclusion") or item.get("status"))
        object_type = "workflow_run"
    else:
        source_event = _GITHUB_EVENT_BY_ACTION.get((str(item.get("type") or "").replace("Event", "").lower(), ""), "")
        object_type = str(item.get("type") or "repo_event")
        source_event = {
            "PullRequestEvent": "pull_request_updated",
            "IssuesEvent": "issue_status_changed",
            "IssueCommentEvent": "issue_comment_received",
            "PushEvent": "commit_pushed",
            "CreateEvent": "branch_created",
            "DeleteEvent": "branch_deleted",
        }.get(str(item.get("type") or ""), source_event or "comment_received")
    return _normalized_event(
        "github",
        source_event,
        object_type=object_type,
        object_id=_first_text(item, "id", "node_id", "run_number"),
        metadata={
            "repository_name": target.get("repository") or _nested(item, "repo", "name"),
            "provider_event_type": object_type,
            "status_bucket": _status_bucket(_first_text(item, "conclusion", "status", "state")),
            "url": _first_text(item, "html_url", "url"),
        },
        occurred_at=_first_text(item, "created_at", "updated_at", "run_started_at"),
    )


def _gitlab_poll_event(operation: str, item: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    source_event = _ci_event_from_status(item.get("status")) if operation == "developer_gitlab_pipelines" else "comment_received"
    if str(item.get("action_name") or "").lower() == "pushed to":
        source_event = "commit_pushed"
    return _normalized_event(
        "gitlab",
        source_event,
        object_type=operation.replace("developer_gitlab_", ""),
        object_id=_first_text(item, "id", "iid", "push_data"),
        metadata={
            "project_id": target.get("project_id") or target.get("project"),
            "provider_event_type": operation,
            "status_bucket": _status_bucket(item.get("status")),
            "branch_name": item.get("ref_name") or item.get("ref"),
            "url": item.get("web_url"),
        },
        occurred_at=_first_text(item, "created_at", "updated_at"),
    )


def _bitbucket_poll_event(operation: str, item: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    source_event = _ci_event_from_status(item.get("state") or item.get("result", {}).get("name")) if operation == "developer_bitbucket_pipelines" else "pull_request_updated"
    return _normalized_event(
        "bitbucket",
        source_event,
        object_type=operation.replace("developer_bitbucket_", ""),
        object_id=_first_text(item, "id", "uuid", "build_number"),
        metadata={
            "repository_name": target.get("repository") or target.get("repo_slug"),
            "workspace": target.get("workspace"),
            "provider_event_type": operation,
            "status_bucket": _status_bucket(_first_text(item, "state")),
            "title": item.get("title"),
            "url": _nested(item, "links", "html", "href"),
        },
        occurred_at=_first_text(item, "updated_on", "created_on", "created_at"),
    )


def _azure_poll_event(operation: str, item: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    source_event = _ci_event_from_status(item.get("result") or item.get("status")) if operation == "developer_azure_devops_builds" else "pull_request_updated"
    return _normalized_event(
        "azure_devops",
        source_event,
        object_type=operation.replace("developer_azure_devops_", ""),
        object_id=_first_text(item, "pullRequestId", "id", "buildNumber"),
        metadata={
            "organization": target.get("organization"),
            "project_id": target.get("project"),
            "repository_id": target.get("repository_id") or target.get("repository"),
            "provider_event_type": operation,
            "status_bucket": _status_bucket(_first_text(item, "result", "status")),
            "branch_name": _first_text(item, "sourceRefName", "targetRefName", "sourceBranch"),
            "title": _first_text(item, "title", "buildNumber"),
            "url": item.get("url"),
        },
        occurred_at=_first_text(item, "creationDate", "finishTime", "closedDate", "startTime"),
    )


def _normalized_event(
    provider_id: str,
    source_event: str,
    *,
    object_type: str,
    object_id: Any,
    metadata: dict[str, Any],
    occurred_at: str = "",
) -> dict[str, Any]:
    return {
        "provider_id": provider_id,
        "source_event": source_event,
        "object_type": object_type,
        "object_id": str(object_id or ""),
        "metadata": {
            "source_channel": f"{provider_id}_webhook_or_api_poller",
            **metadata,
        },
        "payload": {},
        "occurred_at": occurred_at,
    }


def _poll_targets(provider_state: dict[str, Any]) -> list[dict[str, Any]]:
    targets = provider_state.get("poll_targets")
    if not isinstance(targets, list):
        targets = provider_state.get("targets")
    if not isinstance(targets, list):
        return []
    return [target for target in targets if isinstance(target, dict)]


def _response_items(response: Any) -> list[Any]:
    if isinstance(response, list):
        return response
    if not isinstance(response, dict):
        return []
    for key in ("workflow_runs", "pipelines", "values", "value", "pullRequests", "builds", "events"):
        value = response.get(key)
        if isinstance(value, list):
            return value
    return [response] if response else []


def _event_identity(provider: str, event: dict[str, Any]) -> str:
    body = repr(
        (
            provider,
            event.get("source_event"),
            event.get("object_type"),
            event.get("object_id"),
            event.get("occurred_at"),
        )
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _ci_event_from_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status in {"success", "succeeded", "passed", "completed", "completed_successfully"}:
        return "ci_passed"
    if status in {"failure", "failed", "error", "timedout", "partiallysucceeded"}:
        return "ci_failed"
    if status in {"canceled", "cancelled", "stopped", "abandoned"}:
        return "ci_canceled"
    return "ci_started"


def _status_bucket(value: Any) -> str:
    return _ci_event_from_status(value).replace("ci_", "") if str(value or "").strip() else ""


def _provider_alias(provider_id: str) -> str:
    cleaned = str(provider_id or "").strip().lower().replace("-", "_").replace(" ", "_")
    if cleaned in {"azure", "ado", "azuredevops"}:
        return "azure_devops"
    return cleaned


def _header(headers: dict[str, Any], name: str) -> str:
    lower = name.lower()
    for key, value in headers.items():
        if str(key).lower() == lower:
            return str(value or "").strip()
    return ""


def _nested(value: Any, *keys: Any) -> Any:
    current = value
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list) and isinstance(key, int) and 0 <= key < len(current):
            current = current[key]
        else:
            return ""
    return current


def _first_text(value: Any, *keys: str) -> str:
    if not isinstance(value, dict):
        return ""
    for key in keys:
        item = value.get(key)
        if item is not None and not isinstance(item, (dict, list)):
            text = str(item).strip()
            if text:
                return text
    return ""


def _count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0
