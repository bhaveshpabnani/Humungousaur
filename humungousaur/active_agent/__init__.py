from .models import (
    ActiveAgentDecision,
    ActiveEpisode,
    ActiveAgentRoute,
    ActiveAgentStatus,
    DeepDiveRequest,
    MutedScope,
    TaskContext,
)
from .store import ActiveAgentStore

_SERVICE_EXPORTS = {
    "active_agent_status",
    "active_agent_privacy_delete",
    "active_agent_privacy_export",
    "apply_episode_operation",
    "approve_deep_dive_request",
    "cancel_muted_scope",
    "create_deep_dive_request",
    "create_muted_scope",
    "declare_task_context",
    "execute_deep_dive_request",
    "reject_deep_dive_request",
    "record_user_correction",
    "respond_to_activation",
    "run_active_agent_eval",
    "update_deep_dive_request",
}


def __getattr__(name: str):
    if name == "ActiveEventRouter":
        from .router import ActiveEventRouter

        return ActiveEventRouter
    if name in _SERVICE_EXPORTS:
        from . import service

        return getattr(service, name)
    raise AttributeError(name)

__all__ = [
    "ActiveAgentDecision",
    "ActiveEpisode",
    "ActiveAgentRoute",
    "ActiveAgentStatus",
    "ActiveEventRouter",
    "ActiveAgentStore",
    "active_agent_status",
    "active_agent_privacy_delete",
    "active_agent_privacy_export",
    "apply_episode_operation",
    "approve_deep_dive_request",
    "cancel_muted_scope",
    "create_deep_dive_request",
    "create_muted_scope",
    "declare_task_context",
    "execute_deep_dive_request",
    "reject_deep_dive_request",
    "record_user_correction",
    "respond_to_activation",
    "run_active_agent_eval",
    "update_deep_dive_request",
    "DeepDiveRequest",
    "MutedScope",
    "TaskContext",
]
