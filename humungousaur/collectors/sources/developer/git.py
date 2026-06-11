from __future__ import annotations

from ..workspace_connectors import ConnectorEventMapping
from .common import DeveloperAppCollector


GIT_SOURCE_MANIFESTS = (
    DeveloperAppCollector(
        provider_id="git",
        app="Git",
        description="Local Git hook and polling events for branch, commit, rebase, merge, stash, and worktree state.",
        source_channel="git_hook_or_polling_bridge",
        implementation_level="local_hook_and_polling_ingress",
        poller_supported=True,
        official_docs=("https://git-scm.com/docs/githooks",),
    ),
)

GIT_EVENT_MAPPINGS = (
    ConnectorEventMapping("git_branch_changed", "git_activity", "git_branch_changed", "Git branch changed"),
    ConnectorEventMapping("branch_changed", "git_activity", "git_branch_changed", "Git branch changed"),
    ConnectorEventMapping("commit_created", "git_activity", "commit_created", "Git commit was created"),
    ConnectorEventMapping("merge_conflict_detected", "git_activity", "merge_conflict_detected", "Git merge conflict detected"),
    ConnectorEventMapping("stash_created", "git_activity", "stash_created", "Git stash was created"),
    ConnectorEventMapping("rebase_started", "git_activity", "rebase_started", "Git rebase started"),
    ConnectorEventMapping("rebase_conflict_detected", "git_activity", "rebase_conflict_detected", "Git rebase conflict detected"),
    ConnectorEventMapping("merge_completed", "git_activity", "merge_completed", "Git merge completed"),
    ConnectorEventMapping("working_tree_dirty", "git_activity", "working_tree_dirty", "Git working tree became dirty"),
    ConnectorEventMapping("working_tree_clean", "git_activity", "working_tree_clean", "Git working tree became clean"),
)
