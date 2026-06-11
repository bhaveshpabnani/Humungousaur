from .models import (
    JanusDecision,
    JanusEpisode,
    JanusRoute,
    JanusStatus,
    DeepDiveRequest,
    MutedScope,
    TaskContext,
)
from .store import JanusStore

_SERVICE_EXPORTS = {
    "janus_status",
    "janus_privacy_delete",
    "janus_privacy_export",
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
    "run_janus_eval",
    "update_deep_dive_request",
}


def __getattr__(name: str):
    if name == "JanusEventRouter":
        from .router import JanusEventRouter

        return JanusEventRouter
    if name in _SERVICE_EXPORTS:
        from . import service

        return getattr(service, name)
    raise AttributeError(name)

__all__ = [
    "JanusDecision",
    "JanusEpisode",
    "JanusRoute",
    "JanusStatus",
    "JanusEventRouter",
    "JanusStore",
    "janus_status",
    "janus_privacy_delete",
    "janus_privacy_export",
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
    "run_janus_eval",
    "update_deep_dive_request",
    "DeepDiveRequest",
    "MutedScope",
    "TaskContext",
]
