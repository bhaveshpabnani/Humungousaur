from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.integrations.workspace_connectors import (
    configure_connector_client,
    connector_catalog,
    connector_status,
    disconnect_connector,
    prepare_connector_authorization,
    refresh_connector_token,
)
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


class WorkspaceConnectorCatalogTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="workspace_connector_catalog",
            description="List supported one-click workspace app connectors, OAuth scopes, mapped apps, and native tool hints.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(),
            capability_group="connectors",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        payload = connector_catalog(config)
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Listed {payload['provider_count']} workspace connectors.", payload)


class WorkspaceConnectorStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="workspace_connector_status",
            description="Show configured and connected status for workspace app connectors without exposing tokens.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"provider_id": {"type": "string", "description": "Optional provider id."}}),
            capability_group="connectors",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        provider_id = str(tool_input.get("provider_id") or "").strip() or None
        try:
            payload = connector_status(config, provider_id=provider_id)
        except KeyError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Checked {payload['connector_count']} connector(s).", payload)


class WorkspaceConnectorConfigureTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="workspace_connector_configure",
            description="Store OAuth client metadata for a workspace connector. Client secrets are kept in the local connector config file.",
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "provider_id": {"type": "string"},
                    "client_id": {"type": "string"},
                    "client_secret": {"type": "string"},
                    "redirect_uri": {"type": "string"},
                },
                required=["provider_id", "client_id"],
            ),
            capability_group="connectors",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        try:
            payload = configure_connector_client(
                config,
                str(tool_input.get("provider_id") or "").strip(),
                client_id=str(tool_input.get("client_id") or "").strip(),
                client_secret=str(tool_input.get("client_secret") or "").strip(),
                redirect_uri=str(tool_input.get("redirect_uri") or "").strip(),
            )
        except (KeyError, ValueError) as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Configured {payload['provider_id']} OAuth client.", payload)


class WorkspaceConnectorConnectPrepareTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="workspace_connector_connect_prepare",
            description="Create an OAuth authorization URL for a workspace connector so the desktop app can open it in the browser.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "provider_id": {"type": "string"},
                    "scopes": {"type": "array", "items": {"type": "string"}},
                    "redirect_uri": {"type": "string"},
                },
                required=["provider_id"],
            ),
            capability_group="connectors",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        raw_scopes = tool_input.get("scopes")
        scopes = [str(item) for item in raw_scopes] if isinstance(raw_scopes, list) else None
        try:
            payload = prepare_connector_authorization(
                config,
                str(tool_input.get("provider_id") or "").strip(),
                scopes=scopes,
                redirect_uri=str(tool_input.get("redirect_uri") or "").strip(),
            )
        except (KeyError, ValueError) as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Prepared {payload['display_name']} OAuth authorization.", payload)


class WorkspaceConnectorRefreshTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="workspace_connector_refresh",
            description="Refresh a stored workspace connector token when the provider issued a refresh token.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema({"provider_id": {"type": "string"}}, required=["provider_id"]),
            capability_group="connectors",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        try:
            payload = refresh_connector_token(config, str(tool_input.get("provider_id") or "").strip())
        except (KeyError, ValueError) as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Refreshed {payload['display_name']} connector.", payload)


class WorkspaceConnectorDisconnectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="workspace_connector_disconnect",
            description="Remove a locally stored workspace connector token.",
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
            input_schema=object_input_schema({"provider_id": {"type": "string"}}, required=["provider_id"]),
            capability_group="connectors",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        try:
            payload = disconnect_connector(config, str(tool_input.get("provider_id") or "").strip())
        except KeyError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Disconnected {payload['display_name']} connector.", payload)


class WorkspaceConnectorSourceManifestTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="workspace_connector_source_manifest",
            description="List collector-owned source mappings that use connector readiness and emit normalized CollectorEventEnvelope records.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"provider_id": {"type": "string"}}),
            capability_group="connectors",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        from humungousaur.collectors.sources import connector_source_manifest_records

        try:
            payload = connector_source_manifest_records(str(tool_input.get("provider_id") or "").strip() or None)
        except KeyError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Listed {payload['source_count']} connector source manifest(s).", payload)


class WorkspaceConnectorSourceStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="workspace_connector_source_status",
            description="Show collector-owned source health, provider-to-collector mappings, and connector readiness.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"provider_id": {"type": "string"}}),
            capability_group="connectors",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        from humungousaur.collectors.sources import connector_source_status

        try:
            payload = connector_source_status(config, str(tool_input.get("provider_id") or "").strip() or None)
        except KeyError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Checked {payload['source_count']} connector source collector(s).", payload)


class WorkspaceConnectorSourceTickTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="workspace_connector_source_tick",
            description="Run metadata-only collector source ticks after checking connector readiness, then update source health/cursors.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "provider_id": {"type": "string"},
                    "dry_run": {"type": "boolean"},
                }
            ),
            capability_group="connectors",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        from humungousaur.collectors.sources import run_connector_source_tick

        try:
            payload = run_connector_source_tick(
                config,
                provider_id=str(tool_input.get("provider_id") or "").strip() or None,
                dry_run=bool(tool_input.get("dry_run", False)),
            )
        except KeyError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Ran {payload['source_count']} connector source collector(s).", payload)


class WorkspaceConnectorSourceEventIngestTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="workspace_connector_source_event_ingest",
            description=(
                "Ingest one provider-native app event through the collector source path as a metadata-only CollectorEventEnvelope. "
                "Use for webhook/poller adapters; raw titles, bodies, participants, URLs, paths, and customer data are redacted."
            ),
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "provider_id": {"type": "string"},
                    "source_event": {"type": "string"},
                    "object_type": {"type": "string"},
                    "object_id": {"type": "string"},
                    "metadata": {"type": "object"},
                    "payload": {"type": "object"},
                    "occurred_at": {"type": "string"},
                },
                required=["provider_id", "source_event"],
            ),
            capability_group="connectors",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        from humungousaur.collectors.sources import append_connector_source_event

        try:
            payload = append_connector_source_event(
                config,
                provider_id=str(tool_input.get("provider_id") or "").strip(),
                source_event=str(tool_input.get("source_event") or "").strip(),
                object_type=str(tool_input.get("object_type") or "").strip(),
                object_id=str(tool_input.get("object_id") or "").strip(),
                metadata=tool_input.get("metadata") if isinstance(tool_input.get("metadata"), dict) else {},
                payload=tool_input.get("payload") if isinstance(tool_input.get("payload"), dict) else {},
                occurred_at=str(tool_input.get("occurred_at") or "").strip(),
            )
        except (KeyError, ValueError) as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Ingested {payload['provider_id']} connector source event.", payload)


class WorkspaceConnectorSourceHealthTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="workspace_connector_source_health",
            description="Record collector source health for connector readiness, API polling, webhook, rate-limit, or permission states.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "provider_id": {"type": "string"},
                    "status": {"type": "string", "enum": ["starting", "running", "degraded", "permission_denied", "rate_limited", "stopped", "failed"]},
                    "message": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                required=["provider_id", "status"],
            ),
            capability_group="connectors",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        from humungousaur.collectors.sources import record_connector_source_health

        try:
            payload = record_connector_source_health(
                config,
                provider_id=str(tool_input.get("provider_id") or "").strip(),
                status=str(tool_input.get("status") or "").strip(),
                message=str(tool_input.get("message") or "").strip(),
                metadata=tool_input.get("metadata") if isinstance(tool_input.get("metadata"), dict) else {},
            )
        except (KeyError, ValueError) as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Recorded {payload['provider_id']} connector source health.", payload)


def default_connector_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        WorkspaceConnectorCatalogTool(),
        WorkspaceConnectorStatusTool(),
        WorkspaceConnectorConfigureTool(),
        WorkspaceConnectorConnectPrepareTool(),
        WorkspaceConnectorRefreshTool(),
        WorkspaceConnectorDisconnectTool(),
        WorkspaceConnectorSourceManifestTool(),
        WorkspaceConnectorSourceStatusTool(),
        WorkspaceConnectorSourceTickTool(),
        WorkspaceConnectorSourceEventIngestTool(),
        WorkspaceConnectorSourceHealthTool(),
    ]
    return {tool.name: tool for tool in tools}
