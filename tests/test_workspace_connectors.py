import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorOperationRequest, ConnectorRuntime
from humungousaur.connectors.http import ConnectorHttpClient
from humungousaur.connectors import oauth as connector_oauth
from humungousaur.connectors.registry import DEFAULT_CONNECTOR_REGISTRY
from humungousaur.collectors import query_collector_events
from humungousaur.collectors.definitions import DEFINITIONS_BY_NAME
from humungousaur.collectors.event_log import CollectorEventLog
from humungousaur.collectors.sources import (
    append_business_operations_event,
    append_cloud_file_event,
    append_code_hosting_webhook_event,
    append_connector_source_event,
    append_data_analytics_event,
    append_developer_source_event,
    append_design_event,
    append_discord_call_gateway_event,
    append_discord_gateway_event,
    append_google_chat_event,
    append_google_meet_event,
    append_knowledge_base_event,
    append_meeting_source_event,
    append_microsoft_365_event,
    append_operations_event,
    append_planning_event,
    append_signal_cli_receive,
    append_slack_events_api_event,
    append_teams_graph_chat_notification,
    append_teams_meeting_graph_event,
    append_telegram_bot_update,
    append_webex_webhook_event,
    append_whatsapp_cloud_webhook,
    append_zoom_webhook_event,
    business_operations_app_status_records,
    business_operations_source_status,
    connector_source_manifest_records,
    connector_source_status,
    data_analytics_app_status_records,
    data_analytics_source_status,
    design_app_status_records,
    design_source_status,
    microsoft_365_source_status,
    meeting_app_status_records,
    meeting_source_status,
    operations_app_status_records,
    operations_source_status,
    planning_source_status,
    record_connector_source_health,
    run_business_operations_source_tick,
    run_connector_source_tick,
    run_data_analytics_source_tick,
    run_developer_source_tick,
    run_design_source_tick,
    run_meeting_source_tick,
    run_operations_source_tick,
    run_planning_source_tick,
)
from humungousaur.integrations.workspace_connectors import (
    configure_connector_client,
    connector_catalog,
    connector_status,
    disconnect_connector,
    prepare_connector_authorization,
)
from humungousaur.collectors.sources.google.contacts import GOOGLE_CONTACTS_COLLECTOR
from humungousaur.schemas import ActionStatus
from humungousaur.tools import default_tools
from humungousaur.tools.connectors import (
    WorkspaceConnectorCatalogTool,
    WorkspaceConnectorConnectPrepareTool,
    WorkspaceConnectorSourceEventIngestTool,
    WorkspaceConnectorSourceManifestTool,
    WorkspaceConnectorSourceStatusTool,
    WorkspaceConnectorSourceTickTool,
    WorkspaceConnectorStatusTool,
)


class WorkspaceConnectorTests(unittest.TestCase):
    def test_catalog_contains_priority_workspace_apps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            catalog = connector_catalog(config)

        provider_ids = {provider["provider_id"] for provider in catalog["providers"]}
        self.assertIn("google_workspace", provider_ids)
        self.assertIn("microsoft_365", provider_ids)
        self.assertIn("slack", provider_ids)
        self.assertIn("linear", provider_ids)
        self.assertEqual(catalog["redirect_uri"], "http://127.0.0.1:8765/connectors/callback")
        self.assertTrue(all(provider["api_base_url"] for provider in catalog["providers"]))
        self.assertTrue(all("connection_ready" in provider for provider in catalog["providers"]))
        self.assertTrue(all("tool_ready" in provider for provider in catalog["providers"]))
        self.assertTrue(all("collector_ready" in provider for provider in catalog["providers"]))
        self.assertTrue(all(provider["auth_type"] for provider in catalog["providers"]))
        self.assertTrue(all(provider["credential_fields"] for provider in catalog["providers"]))
        self.assertTrue(all("managed_oauth_available" in provider for provider in catalog["providers"]))
        self.assertTrue(all("advanced_client_config" in provider for provider in catalog["providers"]))
        self.assertTrue(all(provider["icon"] for provider in catalog["providers"]))
        self.assertTrue(all(provider["brand_color"].startswith("#") for provider in catalog["providers"]))
        logos = {provider["provider_id"]: provider["logo_asset"] for provider in catalog["providers"]}
        self.assertEqual(logos["slack"], "tool-logos-slack.png")
        self.assertEqual(logos["google_workspace"], "tool-logos-google.png")
        self.assertEqual(logos["microsoft_365"], "tool-logos-outlook.png")
        self.assertEqual(logos["groq"], "provider-logos-groq.png")
        google = next(provider for provider in catalog["providers"] if provider["provider_id"] == "google_workspace")
        self.assertNotIn("https://www.googleapis.com/auth/keep.readonly", google["default_scopes"])
        self.assertNotIn("Keep", google["workspace_apps"])

    def test_connector_catalog_covers_registered_channel_apps_and_tool_surfaces(self) -> None:
        provider_ids = {provider.provider_id for provider in DEFAULT_CONNECTOR_REGISTRY.providers()}
        channel_catalog = json.loads((Path(__file__).resolve().parents[1] / "humungousaur" / "resources" / "channel_catalog.json").read_text())
        channel_ids = {str(channel["channel_id"]) for channel in channel_catalog["channels"]}
        expected_tool_surfaces = {
            "airtable",
            "apple_local",
            "browser_use",
            "github",
            "google_workspace",
            "homeassistant",
            "hugging_face",
            "mcp",
            "microsoft_365",
            "notion",
            "onepassword",
            "screenpipe",
            "shopify",
            "spotify",
        }

        self.assertEqual(channel_ids - provider_ids, set())
        self.assertEqual(expected_tool_surfaces - provider_ids, set())
        self.assertGreaterEqual(len(provider_ids), 100)

    def test_connector_runtime_uses_sqlite_profiles_and_secret_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            runtime = ConnectorRuntime(config)
            configured = runtime.configure_client(
                "slack",
                client_id="client-123456",
                client_secret="client-secret-value",
                redirect_uri="http://127.0.0.1:8765/connectors/callback",
            )
            catalog = runtime.catalog()
            sqlite_exists = (Path(tmp_dir) / "artifacts" / "connectors" / "connectors.sqlite3").exists()
            vault_exists = (Path(tmp_dir) / "artifacts" / "connectors" / "secrets.json").exists()

        self.assertTrue(configured["configured"])
        self.assertTrue(sqlite_exists)
        self.assertTrue(vault_exists)
        slack = next(provider for provider in catalog["providers"] if provider["provider_id"] == "slack")
        self.assertEqual(slack["client_id"], "clie...3456")
        self.assertNotIn("client-secret-value", str(catalog))

    def test_configure_and_prepare_authorization_url_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            configured = configure_connector_client(config, "google_workspace", client_id="client-123")
            prepared = prepare_connector_authorization(config, "google_workspace")
            status = connector_status(config, provider_id="google_workspace")

        parsed = urlparse(prepared["authorization_url"])
        query = parse_qs(parsed.query)
        self.assertTrue(configured["configured"])
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(query["client_id"], ["client-123"])
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(query["state"], [prepared["state"]])
        self.assertIn("code_challenge", query)
        self.assertTrue(status["connectors"][0]["configured"])
        self.assertFalse(status["connectors"][0]["managed_oauth_available"])
        self.assertTrue(status["connectors"][0]["advanced_client_configured"])
        self.assertFalse(status["connectors"][0]["connected"])

    def test_env_oauth_client_allows_google_connect_without_manual_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, patch.dict(
            os.environ,
            {
                "HUMUNGOUSAUR_GOOGLE_WORKSPACE_CLIENT_ID": "env-client-123.apps.googleusercontent.com",
                "HUMUNGOUSAUR_GOOGLE_WORKSPACE_CLIENT_SECRET": "env-client-secret",
            },
        ):
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            catalog = connector_catalog(config)
            prepared = prepare_connector_authorization(config, "google_workspace")
            status = connector_status(config, provider_id="google_workspace")

        parsed = urlparse(prepared["authorization_url"])
        query = parse_qs(parsed.query)
        google = next(provider for provider in catalog["providers"] if provider["provider_id"] == "google_workspace")
        self.assertTrue(google["configured"])
        self.assertTrue(google["managed_oauth_available"])
        self.assertFalse(google["advanced_client_configured"])
        self.assertTrue(google["client_id"].startswith("env-"))
        self.assertTrue(google["client_id"].endswith(".com"))
        self.assertEqual(query["client_id"], ["env-client-123.apps.googleusercontent.com"])
        self.assertEqual(query["redirect_uri"], ["http://127.0.0.1:8765/connectors/callback"])
        self.assertTrue(status["connectors"][0]["configured"])
        self.assertNotIn("env-client-secret", str({"catalog": catalog, "status": status, "prepared_keys": sorted(prepared)}))

    def test_connector_https_uses_certifi_bundle_when_available(self) -> None:
        request = connector_oauth.Request("https://oauth2.googleapis.com/token")
        opener = Mock()
        opener.open.return_value = "response"
        with patch.object(connector_oauth, "certifi") as certifi, patch.object(
            connector_oauth.ssl,
            "create_default_context",
        ) as create_context, patch.object(connector_oauth, "HTTPSHandler") as https_handler, patch.object(
            connector_oauth,
            "build_opener",
            return_value=opener,
        ):
            certifi.where.return_value = "/tmp/cacert.pem"

            result = connector_oauth._open_connector_url(request, timeout=3)

        self.assertEqual(result, "response")
        create_context.assert_called_once_with(cafile="/tmp/cacert.pem")
        https_handler.assert_called_once_with(context=create_context.return_value)
        opener.open.assert_called_once_with(request, timeout=3)

    def test_connector_http_allows_same_api_family_absolute_urls(self) -> None:
        client = ConnectorHttpClient(Mock())

        url = client._url(
            "https://www.googleapis.com",
            "https://people.googleapis.com/v1/people/me/connections",
            {"pageSize": 1},
        )

        self.assertEqual(url, "https://people.googleapis.com/v1/people/me/connections?pageSize=1")
        with self.assertRaises(ValueError):
            client._url("https://www.googleapis.com", "https://example.com/steal", {})

    def test_google_contacts_collector_uses_people_api_host(self) -> None:
        class FakeRuntime:
            request = None

            def execute_operation(self, request) -> dict[str, object]:  # type: ignore[no-untyped-def]
                self.request = request
                return {"provider_id": request.provider_id, "operation": request.operation, "status_code": 200, "response": {"connections": []}}

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            runtime = FakeRuntime()
            result = GOOGLE_CONTACTS_COLLECTOR.collect(
                config,
                runtime,  # type: ignore[arg-type]
                {"scopes": ["https://www.googleapis.com/auth/contacts.readonly"]},
                {"baseline_at": "2026-06-11T00:00:00Z", "seen_people": {}},
                dry_run=False,
                max_events=1,
            )

        self.assertEqual(result["status"], "running")
        self.assertEqual(runtime.request.path, "https://people.googleapis.com/v1/people/me/connections")

    def test_managed_oauth_broker_allows_google_connect_without_local_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, patch.dict(
            os.environ,
            {"HUMUNGOUSAUR_CONNECTOR_OAUTH_BROKER_URL": "https://auth.humungousaur.example"},
            clear=False,
        ):
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            catalog = connector_catalog(config)
            prepared = prepare_connector_authorization(config, "google_workspace")
            status = connector_status(config, provider_id="google_workspace")

        parsed = urlparse(prepared["authorization_url"])
        query = parse_qs(parsed.query)
        google = next(provider for provider in catalog["providers"] if provider["provider_id"] == "google_workspace")
        self.assertFalse(google["configured"])
        self.assertTrue(google["managed_oauth_available"])
        self.assertFalse(google["advanced_client_configured"])
        self.assertEqual(parsed.netloc, "auth.humungousaur.example")
        self.assertEqual(parsed.path, "/connectors/oauth/start")
        self.assertEqual(query["provider_id"], ["google_workspace"])
        self.assertEqual(query["redirect_uri"], ["http://127.0.0.1:8765/connectors/callback"])
        self.assertEqual(query["state"], [prepared["state"]])
        self.assertTrue(prepared["uses_broker"])
        self.assertTrue(status["connectors"][0]["managed_oauth_available"])

    def test_non_oauth_connector_uses_stored_credentials_for_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            runtime = ConnectorRuntime(config)
            configured = runtime.configure_client("telegram", client_id="telegram-bot", client_secret="bot-secret-token")
            status = runtime.status(provider_id="telegram")

            with self.assertRaises(ValueError):
                runtime.prepare_authorization("telegram")

            disconnected = runtime.disconnect("telegram")
            disconnected_status = runtime.status(provider_id="telegram")

        serialized = str({"configured": configured, "status": status})
        self.assertTrue(status["connectors"][0]["configured"])
        self.assertTrue(status["connectors"][0]["connected"])
        self.assertTrue(status["connectors"][0]["connection_ready"])
        self.assertTrue(disconnected["removed"])
        self.assertFalse(disconnected_status["connectors"][0]["configured"])
        self.assertFalse(disconnected_status["connectors"][0]["connected"])
        self.assertNotIn("bot-secret-token", serialized)

    def test_disconnect_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            result = disconnect_connector(config, "slack")

        self.assertFalse(result["connected"])
        self.assertFalse(result["removed"])

    def test_connector_tools_are_in_global_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            tools = default_tools(config)

        self.assertIn("workspace_connector_catalog", tools)
        self.assertIn("workspace_connector_status", tools)
        self.assertIn("workspace_connector_configure", tools)
        self.assertIn("workspace_connector_connect_prepare", tools)
        self.assertIn("workspace_connector_source_manifest", tools)
        self.assertIn("workspace_connector_source_status", tools)
        self.assertIn("workspace_connector_source_tick", tools)
        self.assertIn("workspace_connector_source_event_ingest", tools)
        self.assertIn("workspace_connector_source_health", tools)
        self.assertEqual(tools["workspace_connector_catalog"].capability_group, "connectors")

    def test_connector_tool_prepare_reports_missing_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            result = WorkspaceConnectorConnectPrepareTool().execute({"provider_id": "linear"}, config)

        self.assertEqual(result.status, ActionStatus.FAILED)
        self.assertIn("managed OAuth is not configured", result.summary)

    def test_connector_tool_catalog_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            catalog = WorkspaceConnectorCatalogTool().execute({}, config)
            status = WorkspaceConnectorStatusTool().execute({"provider_id": "slack"}, config)

        self.assertEqual(catalog.status, ActionStatus.SUCCEEDED)
        self.assertEqual(status.status, ActionStatus.SUCCEEDED)
        self.assertEqual(status.output["connector_count"], 1)

    def test_connector_source_manifest_mappings_target_existing_collectors(self) -> None:
        manifest = connector_source_manifest_records()
        invalid: list[str] = []
        for source in manifest["sources"]:
            for mapping in source["collector_mappings"]:
                definition = DEFINITIONS_BY_NAME.get(mapping["collector"])
                if definition is None or mapping["stimulus_type"] not in definition.stimulus_types:
                    invalid.append(f"{source['provider_id']}:{mapping['source_event']}->{mapping['collector']}/{mapping['stimulus_type']}")

        self.assertEqual(invalid, [])
        self.assertGreaterEqual(manifest["source_count"], 5)
        self.assertEqual(manifest["owner"], "humungousaur.collectors.sources.workspace_connectors")
        provider_ids = {source["provider_id"] for source in manifest["sources"]}
        for provider_id in {"linear", "jira", "asana", "trello", "clickup", "monday", "todoist"}:
            self.assertIn(provider_id, provider_ids)

    def test_business_operations_source_manifests_cover_requested_apps(self) -> None:
        expected = {"salesforce", "hubspot", "zendesk", "intercom", "freshdesk", "stripe", "shopify", "quickbooks", "xero"}
        manifest = connector_source_manifest_records()
        source_ids = {source["provider_id"] for source in manifest["sources"]}
        business_apps = {record["provider_id"] for record in business_operations_app_status_records()}

        self.assertEqual(expected - source_ids, set())
        self.assertEqual(expected - business_apps, set())
        self.assertIn("ticket_resolved", DEFINITIONS_BY_NAME["support_desk_activity"].stimulus_types)
        self.assertIn("invoice_created", DEFINITIONS_BY_NAME["finance_activity"].stimulus_types)
        self.assertIn("order_created", DEFINITIONS_BY_NAME["commerce_activity"].stimulus_types)

    def test_cloud_file_source_manifests_cover_requested_providers(self) -> None:
        manifest = connector_source_manifest_records()
        sources = {source["provider_id"]: source for source in manifest["sources"]}

        for provider_id in ("dropbox", "box", "icloud", "google_workspace", "microsoft_365"):
            self.assertIn(provider_id, sources)

        dropbox_events = {mapping["source_event"] for mapping in sources["dropbox"]["collector_mappings"]}
        microsoft_events = {mapping["source_event"] for mapping in sources["microsoft_365"]["collector_mappings"]}
        google_events = {mapping["source_event"] for mapping in sources["google_workspace"]["collector_mappings"]}
        for event_name in (
            "dropbox_file_created",
            "dropbox_file_renamed",
            "dropbox_file_moved",
            "dropbox_file_deleted",
            "dropbox_file_shared",
            "dropbox_permission_changed",
            "dropbox_sync_failed",
            "dropbox_sync_conflict_detected",
            "dropbox_file_restored",
            "dropbox_file_version_event",
        ):
            self.assertIn(event_name, dropbox_events)
        self.assertIn("drive_cloud_permission_changed", google_events)
        self.assertIn("onedrive_file_version_event", microsoft_events)
        self.assertIn("sharepoint_file_restored", microsoft_events)
        self.assertFalse(sources["icloud"]["requires_connector"])

    def test_connector_source_event_enters_collector_log_with_redacted_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            result = append_connector_source_event(
                config,
                provider_id="google_workspace",
                source_event="sheets_range_edited",
                object_type="spreadsheet",
                object_id="spreadsheet-secret-id",
                metadata={
                    "spreadsheet_id": "spreadsheet-secret-id",
                    "title": "Confidential model",
                    "cell_value": "9000000",
                    "formula": '=IMPORTDATA("secret")',
                    "range_cell_count": 12,
                    "participants": ["person@example.com"],
                },
                payload={"event_id": "provider-event-secret", "body": "raw body"},
                occurred_at="2026-06-11T00:00:00+00:00",
            )
            events = query_collector_events(config, collector="spreadsheet_editing_activity", limit=5)["events"]

        serialized = str({"result": result, "events": events})
        self.assertTrue(result["accepted"])
        self.assertEqual(result["collector"], "spreadsheet_editing_activity")
        self.assertEqual(result["stimulus_type"], "cell_range_edited")
        self.assertEqual(events[0]["privacy_tier"], "sensitive_metadata")
        self.assertIn("spreadsheet_id_hash", events[0]["metadata"])
        self.assertTrue(events[0]["metadata"]["title_redacted"])
        self.assertTrue(events[0]["metadata"]["cell_value_redacted"])
        self.assertTrue(events[0]["metadata"]["formula_redacted"])
        self.assertTrue(events[0]["payload"]["event_id_hash"])
        self.assertTrue(events[0]["payload"]["body_redacted"])
        self.assertNotIn("Confidential model", serialized)
        self.assertNotIn("9000000", serialized)
        self.assertNotIn("IMPORTDATA", serialized)
        self.assertNotIn("person@example.com", serialized)

    def test_cloud_file_source_event_redacts_paths_names_and_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            result = append_cloud_file_event(
                config,
                {
                    "provider_id": "dropbox",
                    "event_type": "file_shared",
                    "object_id": "file-secret-id",
                    "path": "/Secret/Payroll.xlsx",
                    "file_name": "Payroll.xlsx",
                    "shared_link": "https://example.invalid/private",
                    "email": "person@example.com",
                    "permission_role": "viewer",
                    "occurred_at": "2026-06-11T00:00:00+00:00",
                },
            )
            events = query_collector_events(config, collector="cloud_sync_activity", limit=5)["events"]

        serialized = str({"result": result, "events": events})
        self.assertTrue(result["accepted"])
        self.assertEqual(result["stimulus_type"], "cloud_file_shared")
        self.assertEqual(events[0]["source"], "dropbox")
        self.assertIn("object_id_hash", events[0]["metadata"])
        self.assertTrue(events[0]["metadata"]["path_redacted"])
        self.assertTrue(events[0]["metadata"]["file_name_redacted"])
        self.assertTrue(events[0]["metadata"]["shared_link_redacted"])
        self.assertEqual(events[0]["metadata"]["permission_role"], "viewer")
        self.assertNotIn("Payroll.xlsx", serialized)
        self.assertNotIn("person@example.com", serialized)
        self.assertNotIn("example.invalid", serialized)

    def test_cloud_file_ingress_accepts_google_and_microsoft_drive_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            google = append_cloud_file_event(
                config,
                {
                    "provider_id": "google_drive",
                    "event_type": "file_created",
                    "file_id": "drive-file-1",
                    "file_name": "Strategy.docx",
                },
            )
            microsoft = append_cloud_file_event(
                config,
                {
                    "provider_id": "sharepoint",
                    "event_type": "file_moved",
                    "item_id": "sharepoint-item-1",
                    "path": "/Secret/Board.pdf",
                },
            )
            events = query_collector_events(config, collector="cloud_sync_activity", limit=10)["events"]

        serialized = str(events)
        self.assertTrue(google["accepted"])
        self.assertTrue(microsoft["accepted"])
        self.assertEqual(google["provider_id"], "google_workspace")
        self.assertEqual(google["source_event"], "drive_cloud_file_created")
        self.assertEqual(microsoft["provider_id"], "microsoft_365")
        self.assertEqual(microsoft["source_event"], "sharepoint_file_moved")
        self.assertNotIn("Strategy.docx", serialized)
        self.assertNotIn("Board.pdf", serialized)

    def test_design_data_and_operations_source_manifests_cover_requested_apps(self) -> None:
        manifest = connector_source_manifest_records()
        source_ids = {source["provider_id"] for source in manifest["sources"]}

        expected_design = {"figma", "figjam", "miro", "canva", "sketch", "adobe_xd"}
        expected_data = {
            "bigquery",
            "snowflake",
            "databricks",
            "postgres",
            "supabase",
            "mysql",
            "mongodb_atlas",
            "tableau",
            "looker",
            "metabase",
            "power_bi",
            "google_analytics",
            "mixpanel",
            "amplitude",
        }
        expected_operations = {
            "sentry",
            "datadog",
            "grafana",
            "pagerduty",
            "opsgenie",
            "aws",
            "azure",
            "gcp",
            "cloudflare",
            "vercel",
            "netlify",
            "docker_hub",
            "kubernetes",
        }

        self.assertEqual(expected_design - source_ids, set())
        self.assertEqual(expected_data - source_ids, set())
        self.assertEqual(expected_operations - source_ids, set())
        self.assertEqual(expected_design - {record["provider_id"] for record in design_app_status_records()}, set())
        self.assertEqual(expected_data - {record["provider_id"] for record in data_analytics_app_status_records()}, set())
        self.assertEqual(expected_operations - {record["provider_id"] for record in operations_app_status_records()}, set())

    def test_design_data_and_operations_events_enter_log_with_redaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            design = append_design_event(
                config,
                {
                    "provider_id": "figma",
                    "event_type": "file_version_update",
                    "file_key": "figma-file-1",
                    "file_name": "Secret App.fig",
                    "comment": "make it pop",
                },
            )
            data = append_data_analytics_event(
                config,
                {
                    "provider_id": "snowflake",
                    "event_type": "query_failed",
                    "query_id": "query-1",
                    "sql": "select * from payroll",
                    "result": "private rows",
                },
            )
            ops = append_operations_event(
                config,
                {
                    "provider_id": "pagerduty",
                    "event_type": "incident_triggered",
                    "incident_id": "incident-1",
                    "title": "Production private outage",
                    "message": "raw incident details",
                },
            )
            creative_events = query_collector_events(config, collector="creative_activity", limit=5)["events"]
            database_events = query_collector_events(config, collector="database_activity", limit=5)["events"]
            incident_events = query_collector_events(config, collector="incident_activity", limit=5)["events"]

        serialized = str({"creative": creative_events, "database": database_events, "incident": incident_events})
        self.assertTrue(design["accepted"])
        self.assertEqual(design["stimulus_type"], "design_file_updated")
        self.assertTrue(data["accepted"])
        self.assertEqual(data["stimulus_type"], "query_failed")
        self.assertTrue(ops["accepted"])
        self.assertEqual(ops["stimulus_type"], "incident_declared")
        self.assertTrue(creative_events[0]["metadata"]["file_name_redacted"])
        self.assertTrue(creative_events[0]["metadata"]["comment_redacted"])
        self.assertTrue(database_events[0]["metadata"]["sql_redacted"])
        self.assertTrue(database_events[0]["metadata"]["result_redacted"])
        self.assertTrue(incident_events[0]["metadata"]["title_redacted"])
        self.assertTrue(incident_events[0]["metadata"]["message_redacted"])
        self.assertNotIn("Secret App", serialized)
        self.assertNotIn("payroll", serialized)
        self.assertNotIn("Production private outage", serialized)

    def test_design_data_and_operations_status_and_ticks_are_registered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            design_status = design_source_status(config, provider_id="figma")
            data_status = data_analytics_source_status(config, provider_id="postgres")
            operations_status = operations_source_status(config, provider_id="kubernetes")
            design_tick = run_design_source_tick(config, provider_id="figma", dry_run=True)
            data_tick = run_data_analytics_source_tick(config, provider_id="postgres", dry_run=True)
            operations_tick = run_operations_source_tick(config, provider_id="kubernetes", dry_run=True)
            generic_design_tick = run_connector_source_tick(config, provider_id="figma", dry_run=True)
            generic_data_tick = run_connector_source_tick(config, provider_id="postgres", dry_run=True)
            generic_operations_tick = run_connector_source_tick(config, provider_id="kubernetes", dry_run=True)

        self.assertEqual(design_status["source_count"], 1)
        self.assertEqual(data_status["source_count"], 1)
        self.assertEqual(operations_status["source_count"], 1)
        self.assertEqual(design_tick["owner"], "humungousaur.collectors.sources.design")
        self.assertEqual(data_tick["owner"], "humungousaur.collectors.sources.data_analytics")
        self.assertEqual(operations_tick["owner"], "humungousaur.collectors.sources.operations")
        self.assertEqual(generic_design_tick["owner"], "humungousaur.collectors.sources.design")
        self.assertEqual(generic_data_tick["owner"], "humungousaur.collectors.sources.data_analytics")
        self.assertEqual(generic_operations_tick["owner"], "humungousaur.collectors.sources.operations")

    def test_planning_source_events_enter_issue_and_task_collectors_with_redaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            jira_result = append_planning_event(
                config,
                {
                    "provider_id": "jira",
                    "event_type": "issue_priority_changed",
                    "issue_id": "issue-secret-id",
                    "project_id": "project-secret-id",
                    "summary": "Private customer escalation",
                    "comment_body": "Raw private comment",
                    "priority_bucket": "high",
                    "occurred_at": "2026-06-11T00:00:00+00:00",
                },
            )
            trello_result = append_planning_event(
                config,
                {
                    "provider_id": "trello",
                    "action": "commentCard",
                    "card_id": "card-secret-id",
                    "board_id": "board-secret-id",
                    "title": "Secret launch card",
                    "text": "Raw card comment",
                    "occurred_at": "2026-06-11T00:01:00+00:00",
                },
            )
            issue_events = query_collector_events(config, collector="issue_tracker_activity", limit=5)["events"]
            task_events = query_collector_events(config, collector="task_manager_activity", limit=5)["events"]
            status = planning_source_status(config, provider_id="jira")

        serialized = json.dumps({"jira": jira_result, "trello": trello_result, "issue": issue_events, "task": task_events, "status": status}, ensure_ascii=False)
        self.assertEqual(jira_result["collector"], "issue_tracker_activity")
        self.assertEqual(jira_result["stimulus_type"], "issue_priority_changed")
        self.assertEqual(trello_result["collector"], "task_manager_activity")
        self.assertEqual(trello_result["stimulus_type"], "task_comment_added")
        self.assertEqual(issue_events[0]["source"], "jira")
        self.assertIn("issue_id_hash", issue_events[0]["metadata"])
        self.assertEqual(issue_events[0]["metadata"]["priority_bucket"], "high")
        self.assertTrue(issue_events[0]["metadata"]["summary_redacted"])
        self.assertTrue(task_events[0]["metadata"]["title_redacted"])
        self.assertEqual(status["sources"][0]["mapping_count"], 12)
        self.assertNotIn("Private customer escalation", serialized)
        self.assertNotIn("Raw private comment", serialized)
        self.assertNotIn("Secret launch card", serialized)
        self.assertNotIn("Raw card comment", serialized)

    def test_planning_source_tick_reports_disconnected_connector_without_api_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            dry_tick = run_planning_source_tick(config, provider_id="clickup", dry_run=True)
            tick = run_connector_source_tick(config, provider_id="clickup")
            state = CollectorEventLog(config.collector_events_db_path).consumer_state("connector_sources")

        self.assertEqual(dry_tick["sources"][0]["provider_id"], "clickup")
        self.assertEqual(dry_tick["sources"][0]["status"], "permission_denied")
        self.assertEqual(tick["sources"][0]["events_appended"], 0)
        self.assertIn("clickup", state["sources"])

    def test_business_operations_events_enter_log_with_customer_data_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            crm_result = append_business_operations_event(
                config,
                {
                    "provider": "salesforce",
                    "event_type": "record_viewed",
                    "object_type": "account",
                    "record_id": "acct-secret-id",
                    "account_name": "Very Secret Account",
                    "customer_email": "buyer@example.com",
                    "metadata": {"dashboard_id": "dash-secret", "status_bucket": "open"},
                    "payload": {"body": "raw customer detail", "amount": "$9000"},
                    "occurred_at": "2026-06-11T00:00:00+00:00",
                },
            )
            support_result = append_business_operations_event(
                config,
                {
                    "provider": "zendesk",
                    "event_type": "ticket_solved",
                    "ticket_id": "ticket-secret-id",
                    "subject": "Customer cannot pay",
                    "message": "Private support thread",
                    "occurred_at": "2026-06-11T00:01:00+00:00",
                },
            )
            finance_result = append_business_operations_event(
                config,
                {
                    "provider": "stripe",
                    "event_type": "invoice.created",
                    "invoice_id": "invoice-secret-id",
                    "customer_email": "payer@example.com",
                    "amount": "12345",
                    "occurred_at": "2026-06-11T00:02:00+00:00",
                },
            )
            commerce_result = append_business_operations_event(
                config,
                {
                    "provider": "shopify",
                    "topic": "orders/create",
                    "order_id": "order-secret-id",
                    "customer_name": "Private Buyer",
                    "occurred_at": "2026-06-11T00:03:00+00:00",
                },
            )
            crm_events = query_collector_events(config, collector="crm_activity", limit=5)["events"]
            support_events = query_collector_events(config, collector="support_desk_activity", limit=5)["events"]
            finance_events = query_collector_events(config, collector="finance_activity", limit=5)["events"]
            commerce_events = query_collector_events(config, collector="commerce_activity", limit=5)["events"]

        serialized = str(
            {
                "results": [crm_result, support_result, finance_result, commerce_result],
                "crm": crm_events,
                "support": support_events,
                "finance": finance_events,
                "commerce": commerce_events,
            }
        )
        self.assertEqual(crm_result["collector"], "crm_activity")
        self.assertEqual(crm_events[0]["stimulus_type"], "record_opened")
        self.assertEqual(support_result["stimulus_type"], "ticket_resolved")
        self.assertEqual(finance_result["stimulus_type"], "invoice_created")
        self.assertEqual(commerce_result["stimulus_type"], "order_created")
        self.assertIn("record_id_hash", crm_events[0]["metadata"])
        self.assertTrue(crm_events[0]["metadata"]["account_name_redacted"])
        self.assertTrue(support_events[0]["metadata"]["subject_redacted"])
        self.assertTrue(finance_events[0]["metadata"]["customer_email_redacted"])
        self.assertTrue(commerce_events[0]["metadata"]["customer_name_redacted"])
        self.assertNotIn("Very Secret Account", serialized)
        self.assertNotIn("buyer@example.com", serialized)
        self.assertNotIn("Private support thread", serialized)
        self.assertNotIn("payer@example.com", serialized)
        self.assertNotIn("Private Buyer", serialized)

    def test_business_operations_status_and_tick_cover_all_apps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            status = business_operations_source_status(config)
            tick = run_business_operations_source_tick(config, dry_run=True)
            generic_tick = run_connector_source_tick(config, provider_id="shopify", dry_run=True)

        self.assertEqual(status["source_count"], 9)
        self.assertEqual(len(status["app_collectors"]), 9)
        self.assertEqual(tick["source_count"], 9)
        self.assertEqual(tick["aggregate_status"], "running")
        self.assertEqual(generic_tick["owner"], "humungousaur.collectors.sources.business_operations")
        self.assertEqual(generic_tick["sources"][0]["provider_id"], "shopify")

    def test_knowledge_base_source_events_enter_collector_log_with_redaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            accepted = append_knowledge_base_event(
                config,
                {
                    "app": "notion",
                    "event_type": "database_changed",
                    "database_id": "notion-secret-db",
                    "title": "Acquisition pipeline",
                    "url": "https://notion.so/secret",
                    "body": "raw private page body",
                    "participants": ["person@example.com"],
                    "row_count": 8,
                    "occurred_at": "2026-06-11T00:00:00+00:00",
                },
            )
            events = query_collector_events(config, collector="knowledge_base_activity", limit=5)["events"]

        serialized = json.dumps({"accepted": accepted, "events": events}, ensure_ascii=False)
        self.assertTrue(accepted["accepted"])
        self.assertEqual(accepted["provider_id"], "notion")
        self.assertEqual(events[0]["source"], "notion")
        self.assertEqual(events[0]["stimulus_type"], "database_changed")
        self.assertIn("database_id_hash", events[0]["metadata"])
        self.assertEqual(events[0]["metadata"]["app"], "notion")
        self.assertEqual(events[0]["metadata"]["row_count"], 8)
        self.assertTrue(events[0]["metadata"]["title_redacted"])
        self.assertTrue(events[0]["metadata"]["url_redacted"])
        self.assertTrue(events[0]["metadata"]["body_redacted"])
        self.assertNotIn("notion-secret-db", serialized)
        self.assertNotIn("Acquisition pipeline", serialized)
        self.assertNotIn("raw private page body", serialized)
        self.assertNotIn("person@example.com", serialized)

    def test_knowledge_base_source_tick_covers_local_and_saas_apps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            obsidian_tick = run_connector_source_tick(config, provider_id="obsidian")
            notion_tick = run_connector_source_tick(config, provider_id="notion", dry_run=True)
            status = connector_source_status(config, provider_id="obsidian")

        self.assertEqual(obsidian_tick["sources"][0]["status"], "running")
        self.assertTrue(obsidian_tick["sources"][0]["local_bridge_supported"])
        self.assertEqual(obsidian_tick["sources"][0]["apps"][0]["app"], "obsidian")
        self.assertEqual(notion_tick["sources"][0]["provider_id"], "notion")
        self.assertEqual(notion_tick["sources"][0]["apps"][0]["app"], "notion")
        self.assertTrue(status["sources"][0]["connector_readiness"]["local_bridge"])

    def test_communication_provider_webhooks_use_connector_readiness_and_redact(self) -> None:
        class ReadyRuntime:
            def __init__(self, config) -> None:  # type: ignore[no-untyped-def]
                self.config = config

            def readiness(self, provider_id: str) -> dict[str, object]:
                return {"provider_id": provider_id, "connected": True, "connection_ready": True, "collector_ready": True}

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with patch("humungousaur.collectors.sources.communication.common.ConnectorRuntime", ReadyRuntime):
                results = [
                    append_slack_events_api_event(
                        config,
                        {
                            "type": "event_callback",
                            "team_id": "team-secret",
                            "event_id": "slack-event-1",
                            "event": {
                                "type": "message",
                                "subtype": "message_changed",
                                "channel": "secret-channel",
                                "user": "secret-user",
                                "ts": "1800000000.000001",
                                "text": "secret slack body",
                            },
                        },
                    ),
                    append_teams_graph_chat_notification(
                        config,
                        {
                            "value": [
                                {
                                    "changeType": "created",
                                    "resource": "chats/secret-chat/messages/secret-message",
                                    "resourceData": {"id": "teams-message-secret", "@odata.type": "#microsoft.graph.chatMessage"},
                                    "tenantId": "tenant-secret",
                                }
                            ]
                        },
                    ),
                    append_discord_gateway_event(
                        config,
                        {
                            "t": "MESSAGE_CREATE",
                            "s": 42,
                            "d": {
                                "id": "discord-message-secret",
                                "channel_id": "discord-channel-secret",
                                "guild_id": "discord-guild-secret",
                                "content": "secret discord body",
                                "author": {"id": "discord-user-secret", "username": "SecretUser"},
                            },
                        },
                    ),
                    append_google_chat_event(
                        config,
                        {
                            "eventType": "google.workspace.chat.message.v1.created",
                            "messageId": "pubsub-google-chat-secret",
                            "space": {"name": "spaces/google-chat-space-secret", "displayName": "Secret Chat Space"},
                            "message": {
                                "name": "spaces/google-chat-space-secret/messages/google-chat-message-secret",
                                "text": "secret google chat body",
                                "sender": {"name": "users/google-chat-user-secret", "displayName": "Secret Google Chat User"},
                            },
                        },
                    ),
                    append_telegram_bot_update(
                        config,
                        {
                            "update_id": 101,
                            "message": {
                                "message_id": 102,
                                "date": 1800000001,
                                "chat": {"id": "telegram-chat-secret", "type": "private", "title": "Secret Telegram"},
                                "text": "secret telegram body",
                            },
                        },
                    ),
                    append_whatsapp_cloud_webhook(
                        config,
                        {
                            "entry": [
                                {
                                    "id": "waba-secret",
                                    "changes": [
                                        {
                                            "value": {
                                                "metadata": {"phone_number_id": "phone-secret", "display_phone_number": "secret-number"},
                                                "messages": [{"id": "whatsapp-message-secret", "timestamp": "1800000002", "type": "text", "text": {"body": "secret whatsapp body"}}],
                                                "contacts": [{"profile": {"name": "Secret WhatsApp"}}],
                                            }
                                        }
                                    ],
                                }
                            ]
                        },
                    ),
                    append_signal_cli_receive(
                        config,
                        {
                            "method": "receive",
                            "params": {
                                "envelope": {
                                    "sourceNumber": "+15555550123",
                                    "sourceUuid": "signal-user-secret",
                                    "timestamp": 1800000003,
                                    "dataMessage": {
                                        "timestamp": 1800000003,
                                        "message": "secret signal body",
                                        "groupInfo": {"groupId": "signal-group-secret", "name": "Secret Signal Group"},
                                    },
                                }
                            },
                        },
                    ),
                ]
            events = query_collector_events(config, limit=20)["events"]

        serialized = json.dumps({"results": results, "events": events}, ensure_ascii=False)
        self.assertTrue(all(result["accepted"] for result in results))
        self.assertEqual(len(events), 7)
        for secret in (
            "secret slack body",
            "secret-channel",
            "secret-chat",
            "secret discord body",
            "SecretUser",
            "Secret Chat Space",
            "secret google chat body",
            "Secret Google Chat User",
            "secret telegram body",
            "Secret Telegram",
            "secret whatsapp body",
            "Secret WhatsApp",
            "secret signal body",
            "Secret Signal Group",
        ):
            self.assertNotIn(secret, serialized)

    def test_meeting_source_manifest_covers_requested_apps_and_events(self) -> None:
        manifest = connector_source_manifest_records()
        sources = {source["provider_id"]: source for source in manifest["sources"]}

        self.assertIn("zoom", sources)
        self.assertIn("google_workspace", sources)
        self.assertIn("microsoft_365", sources)
        self.assertIn("webex", sources)
        self.assertIn("discord", sources)
        app_records = {record["provider_id"]: record for record in meeting_app_status_records()}
        self.assertEqual(set(app_records), {"zoom", "google_workspace", "microsoft_365", "webex", "discord"})

        required = {
            "meeting_joined",
            "meeting_left",
            "waiting_room_joined",
            "microphone_muted",
            "camera_enabled",
            "captions_enabled",
            "screen_share_started",
            "remote_control_requested",
            "meeting_recording_available",
            "meeting_transcript_available",
            "meeting_summary_generated",
            "meeting_action_items_detected",
        }
        provider_events = {
            "zoom": "zoom_joined",
            "google_workspace": "meet_joined",
            "microsoft_365": "teams_joined",
            "webex": "webex_joined",
            "discord": "discord_call_joined",
        }
        for provider_id, joined_event in provider_events.items():
            mappings = sources[provider_id]["collector_mappings"]
            stimuli = {mapping["stimulus_type"] for mapping in mappings}
            source_events = {mapping["source_event"] for mapping in mappings}
            self.assertEqual(required - stimuli, set())
            self.assertIn(joined_event, source_events)

    def test_meeting_source_ingest_aliases_and_redacts_sensitive_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            result = append_meeting_source_event(
                config,
                {
                    "provider": "teams",
                    "event_type": "summary_generated",
                    "meeting_id": "meeting-secret-id",
                    "transcript_id": "transcript-secret-id",
                    "metadata": {
                        "title": "Confidential Roadmap Sync",
                        "participants": ["a@example.com", "b@example.com"],
                        "meeting_url": "https://teams.example/private",
                        "has_summary": True,
                        "has_action_items": True,
                    },
                    "payload": {"summary_text": "Ship the secret plan", "artifact_url": "https://example.invalid/secret"},
                    "occurred_at": "2026-06-11T00:00:00Z",
                },
            )
            events = query_collector_events(config, collector="meeting_artifact_activity", limit=5)["events"]

        serialized = str({"result": result, "events": events})
        self.assertTrue(result["accepted"])
        self.assertEqual(result["provider_id"], "microsoft_365")
        self.assertEqual(result["source_event"], "teams_summary_generated")
        self.assertEqual(result["stimulus_type"], "meeting_summary_generated")
        self.assertEqual(events[0]["source"], "microsoft_365")
        self.assertIn("meeting_id_hash", events[0]["metadata"])
        self.assertIn("transcript_id_hash", events[0]["metadata"])
        self.assertTrue(events[0]["metadata"]["title_redacted"])
        self.assertTrue(events[0]["metadata"]["participants_redacted"])
        self.assertTrue(events[0]["metadata"]["meeting_url_redacted"])
        self.assertTrue(events[0]["payload"]["summary_text_redacted"])
        self.assertTrue(events[0]["payload"]["artifact_url_redacted"])
        self.assertNotIn("Confidential Roadmap Sync", serialized)
        self.assertNotIn("a@example.com", serialized)
        self.assertNotIn("Ship the secret plan", serialized)
        self.assertNotIn("teams.example", serialized)

    def test_meeting_provider_webhooks_use_connector_readiness_and_redact(self) -> None:
        class ReadyRuntime:
            def __init__(self, config) -> None:  # type: ignore[no-untyped-def]
                self.config = config

            def readiness(self, provider_id: str) -> dict[str, object]:
                return {"provider_id": provider_id, "connected": True, "connection_ready": True, "collector_ready": True}

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with patch("humungousaur.collectors.sources.meetings.events.ConnectorRuntime", ReadyRuntime):
                results = [
                    append_zoom_webhook_event(
                        config,
                        {
                            "event": "meeting.participant_joined",
                            "account_id": "zoom-account-secret",
                            "payload": {
                                "object": {
                                    "id": "zoom-meeting-secret",
                                    "uuid": "zoom-uuid-secret",
                                    "topic": "Secret Zoom Roadmap",
                                    "participant": {"user_id": "zoom-user-secret", "user_name": "Secret Zoom User"},
                                }
                            },
                        },
                    ),
                    append_google_meet_event(
                        config,
                        {
                            "eventType": "google.workspace.meet.conference.v2.recording.fileGenerated",
                            "resource": {
                                "name": "conferenceRecords/google-conference-secret/recordings/google-recording-secret",
                                "space": "google-space-secret",
                            },
                        },
                    ),
                    append_teams_meeting_graph_event(
                        config,
                        {
                            "value": [
                                {
                                    "changeType": "created",
                                    "resource": "communications/onlineMeetings/teams-meeting-secret/transcripts/teams-transcript-secret",
                                    "resourceData": {"id": "teams-transcript-secret", "transcriptId": "teams-transcript-secret"},
                                }
                            ]
                        },
                    ),
                    append_webex_webhook_event(
                        config,
                        {
                            "id": "webex-webhook-secret",
                            "resource": "meetingTranscripts",
                            "event": "created",
                            "data": {
                                "meetingId": "webex-meeting-secret",
                                "transcriptId": "webex-transcript-secret",
                                "meetingTitle": "Secret Webex Sync",
                            },
                        },
                    ),
                    append_discord_call_gateway_event(
                        config,
                        {
                            "t": "VOICE_STATE_UPDATE",
                            "s": 7,
                            "d": {
                                "session_id": "discord-voice-secret",
                                "guild_id": "discord-guild-secret",
                                "channel_id": "discord-voice-channel-secret",
                                "user_id": "discord-user-secret",
                                "self_mute": True,
                            },
                        },
                    ),
                ]
            events = query_collector_events(config, limit=20)["events"]

        serialized = json.dumps({"results": results, "events": events}, ensure_ascii=False)
        self.assertTrue(all(result["accepted"] for result in results))
        self.assertEqual(len(events), 5)
        self.assertIn("participant_joined", {event["stimulus_type"] for event in events})
        self.assertIn("meeting_recording_available", {event["stimulus_type"] for event in events})
        self.assertIn("meeting_transcript_available", {event["stimulus_type"] for event in events})
        self.assertIn("microphone_muted", {event["stimulus_type"] for event in events})
        for secret in (
            "Secret Zoom Roadmap",
            "Secret Zoom User",
            "google-conference-secret",
            "teams-transcript-secret",
            "Secret Webex Sync",
            "discord-voice-channel-secret",
        ):
            self.assertNotIn(secret, serialized)

    def test_meeting_source_status_and_tick_use_existing_connector_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            status = meeting_source_status(config, provider_id="zoom")
            dry_tick = run_meeting_source_tick(config, provider_id="zoom", dry_run=True)
            state_after_dry_run = CollectorEventLog(config.collector_events_db_path).consumer_state("connector_sources")
            tick = run_meeting_source_tick(config, provider_id="zoom")
            state_after_tick = CollectorEventLog(config.collector_events_db_path).consumer_state("connector_sources")

        self.assertEqual(status["source_count"], 1)
        self.assertEqual(status["sources"][0]["provider_id"], "zoom")
        self.assertEqual(status["sources"][0]["meeting_app"], "zoom")
        self.assertEqual(dry_tick["sources"][0]["events_appended"], 0)
        self.assertEqual(state_after_dry_run, {})
        self.assertIn("zoom", state_after_tick["sources"])
        self.assertEqual(tick["sources"][0]["provider_id"], "zoom")

    def test_connector_source_health_and_tick_use_collector_event_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            health = record_connector_source_health(
                config,
                provider_id="slack",
                status="running",
                message="Slack Events API connected.",
                metadata={"last_event_at": "2026-06-11T00:00:00+00:00", "team_id": "team-secret"},
            )
            status = connector_source_status(config, provider_id="slack")
            dry_tick = run_connector_source_tick(config, provider_id="slack", dry_run=True)
            state_after_dry_run = CollectorEventLog(config.collector_events_db_path).consumer_state("connector_sources")
            tick = run_connector_source_tick(config, provider_id="slack")
            state_after_tick = CollectorEventLog(config.collector_events_db_path).consumer_state("connector_sources")

        self.assertTrue(health["accepted"])
        self.assertGreater(status["sources"][0]["health_count"], 0)
        self.assertIn("team_id_hash", status["sources"][0]["helper_health"][0]["metadata"])
        self.assertEqual(dry_tick["sources"][0]["events_appended"], 0)
        self.assertEqual(state_after_dry_run, {})
        self.assertIn("slack", state_after_tick["sources"])
        self.assertEqual(tick["sources"][0]["events_appended"], 0)

    def test_dropbox_source_tick_uses_cursor_and_appends_redacted_cloud_events(self) -> None:
        class FakeDropboxRuntime:
            operations: list[str] = []

            def __init__(self, config: AgentConfig) -> None:
                self.config = config

            def readiness(self, provider_id: str) -> dict[str, object]:
                return {
                    "provider_id": provider_id,
                    "configured": True,
                    "connected": True,
                    "collector_ready": True,
                    "scopes": ["files.metadata.read", "sharing.read"],
                    "expires_at": 0,
                }

            def execute_operation(self, request) -> dict[str, object]:  # type: ignore[no-untyped-def]
                self.operations.append(request.operation)
                return {
                    "provider_id": request.provider_id,
                    "operation": request.operation,
                    "status_code": 200,
                    "response": {
                        "cursor": "dropbox-next",
                        "has_more": False,
                        "entries": [
                            {
                                ".tag": "file",
                                "id": "id:secret-file",
                                "path_lower": "/secret/payroll.xlsx",
                                "name": "Payroll.xlsx",
                                "server_modified": "2026-06-11T00:01:00Z",
                                "rev": "rev-1",
                                "has_explicit_shared_members": True,
                            },
                            {
                                ".tag": "deleted",
                                "path_lower": "/secret/old.xlsx",
                            },
                        ],
                    },
                }

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            log = CollectorEventLog(config.collector_events_db_path)
            log.save_consumer_state("connector_sources", {"sources": {"dropbox": {"cursor": "dropbox-cursor"}}})

            with patch("humungousaur.collectors.sources.cloud_files.registry.ConnectorRuntime", FakeDropboxRuntime):
                tick = run_connector_source_tick(config, provider_id="dropbox")
            events = query_collector_events(config, collector="cloud_sync_activity", limit=10)["events"]
            state = CollectorEventLog(config.collector_events_db_path).consumer_state("connector_sources")

        serialized = str({"tick": tick, "events": events, "state": state})
        self.assertEqual(tick["sources"][0]["provider_id"], "dropbox")
        self.assertEqual(tick["sources"][0]["events_appended"], 3)
        self.assertEqual(FakeDropboxRuntime.operations, ["dropbox_list_folder_continue"])
        self.assertEqual(state["sources"]["dropbox"]["cursor"], "dropbox-next")
        self.assertEqual({event["stimulus_type"] for event in events}, {"cloud_file_created", "cloud_file_deleted", "cloud_file_shared"})
        self.assertNotIn("Payroll.xlsx", serialized)
        self.assertNotIn("/secret", serialized)

    def test_connector_source_tools_report_status_and_ingest_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            manifest = WorkspaceConnectorSourceManifestTool().execute({"provider_id": "github"}, config)
            status = WorkspaceConnectorSourceStatusTool().execute({"provider_id": "github"}, config)
            tick = WorkspaceConnectorSourceTickTool().execute({"provider_id": "github", "dry_run": True}, config)
            ingest = WorkspaceConnectorSourceEventIngestTool().execute(
                {"provider_id": "github", "source_event": "ci_failed", "object_id": "run-secret", "metadata": {"repository_id": "repo-secret"}},
                config,
            )

        self.assertEqual(manifest.status, ActionStatus.SUCCEEDED)
        self.assertEqual(status.status, ActionStatus.SUCCEEDED)
        self.assertEqual(tick.status, ActionStatus.SUCCEEDED)
        self.assertEqual(ingest.status, ActionStatus.SUCCEEDED)
        self.assertEqual(ingest.output["collector"], "github_activity")

    def test_developer_source_collectors_cover_local_ides_git_and_code_hosts(self) -> None:
        manifest = connector_source_manifest_records()
        sources = {source["provider_id"]: source for source in manifest["sources"]}

        for provider in ("vscode", "jetbrains", "xcode", "terminal", "git", "github", "gitlab", "bitbucket", "azure_devops"):
            self.assertIn(provider, sources)

        self.assertFalse(sources["vscode"]["requires_connector"])
        self.assertFalse(sources["terminal"]["requires_connector"])
        self.assertFalse(sources["git"]["requires_connector"])
        self.assertTrue(sources["gitlab"]["requires_connector"])
        self.assertTrue(sources["azure_devops"]["requires_connector"])
        self.assertIn("active_file_changed", {mapping["source_event"] for mapping in sources["vscode"]["collector_mappings"]})
        self.assertIn("merge_request_opened", {mapping["source_event"] for mapping in sources["gitlab"]["collector_mappings"]})
        self.assertIn("pipeline_failed", {mapping["source_event"] for mapping in sources["bitbucket"]["collector_mappings"]})
        self.assertIn("pull_request_opened", {mapping["source_event"] for mapping in sources["azure_devops"]["collector_mappings"]})
        self.assertTrue(any("code.visualstudio.com" in url for url in sources["vscode"]["official_docs"]))
        self.assertTrue(any("learn.microsoft.com" in url for url in sources["azure_devops"]["official_docs"]))

    def test_code_hosting_webhook_normalizers_ingest_azure_devops_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            result = append_code_hosting_webhook_event(
                config,
                "azure_devops",
                {
                    "eventType": "git.pullrequest.created",
                    "publisherId": "tfs",
                    "resource": {
                        "pullRequestId": 42,
                        "title": "Secret customer payroll fix",
                        "url": "https://dev.azure.com/org/private/_git/repo/pullrequest/42",
                        "sourceRefName": "refs/heads/customer/payroll",
                        "repository": {"id": "repo-secret", "name": "private-repo"},
                        "project": {"id": "project-secret"},
                    },
                },
                headers={"X-VSS-Event": "git.pullrequest.created"},
            )
            events = query_collector_events(config, limit=10)["events"]

        serialized = json.dumps({"result": result, "events": events}, ensure_ascii=False)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["collector"], "code_hosting_activity")
        self.assertEqual(result["stimulus_type"], "pr_opened")
        self.assertEqual(events[0]["metadata"]["provider"], "azure_devops")
        self.assertTrue(events[0]["metadata"]["title_redacted"])
        self.assertTrue(events[0]["metadata"]["url_redacted"])
        self.assertTrue(events[0]["metadata"]["branch_name_redacted"])
        self.assertIn("repository_id_hash", events[0]["metadata"])
        self.assertNotIn("Secret customer", serialized)
        self.assertNotIn("customer/payroll", serialized)
        self.assertNotIn("dev.azure.com/org/private", serialized)

    def test_developer_code_hosting_tick_uses_connector_runtime_and_cursor_state(self) -> None:
        class FakeGitHubRuntime:
            operations: list[ConnectorOperationRequest] = []

            def __init__(self, config: AgentConfig) -> None:
                self.config = config

            def readiness(self, provider_id: str) -> dict[str, object]:
                return {
                    "provider_id": provider_id,
                    "configured": True,
                    "connected": True,
                    "connection_ready": True,
                    "collector_ready": True,
                    "scopes": ["repo", "workflow"],
                }

            def execute_operation(self, request: ConnectorOperationRequest) -> dict[str, object]:
                FakeGitHubRuntime.operations.append(request)
                if request.operation == "developer_github_repo_events":
                    return {
                        "response": [
                            {
                                "id": "evt-1",
                                "type": "PushEvent",
                                "repo": {"name": "example/private"},
                                "created_at": "2026-06-11T00:00:00Z",
                            }
                        ]
                    }
                return {
                    "response": {
                        "workflow_runs": [
                            {
                                "id": 7,
                                "conclusion": "failure",
                                "html_url": "https://github.com/example/private/actions/runs/7",
                                "created_at": "2026-06-11T00:01:00Z",
                            }
                        ]
                    }
                }

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            log = CollectorEventLog(config.collector_events_db_path)
            log.save_consumer_state("developer_sources", {"sources": {"github": {"poll_targets": [{"repository": "example/private"}]}}})

            with patch("humungousaur.collectors.sources.developer.registry.ConnectorRuntime", FakeGitHubRuntime):
                tick = run_developer_source_tick(config, provider_id="github")
            events = query_collector_events(config, limit=10)["events"]
            state = CollectorEventLog(config.collector_events_db_path).consumer_state("developer_sources")

        serialized = json.dumps({"tick": tick, "events": events}, ensure_ascii=False)
        self.assertEqual(tick["sources"][0]["status"], "running")
        self.assertEqual(tick["sources"][0]["events_appended"], 2)
        self.assertEqual([request.operation for request in FakeGitHubRuntime.operations], ["developer_github_repo_events", "developer_github_actions_runs"])
        self.assertEqual({event["stimulus_type"] for event in events}, {"commit_pushed", "ci_failed"})
        self.assertEqual({event["collector"] for event in events}, {"code_hosting_activity", "github_activity"})
        self.assertEqual(state["sources"]["github"]["last_operation_count"], 2)
        self.assertTrue(state["sources"]["github"]["seen_event_ids"])
        self.assertNotIn("https://github.com/example/private", serialized)

    def test_developer_source_events_enter_log_with_redacted_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            gitlab = append_connector_source_event(
                config,
                provider_id="gitlab",
                source_event="pipeline_failed",
                object_type="pipeline",
                object_id="pipeline-secret-id",
                metadata={
                    "repository_id": "repo-secret",
                    "branch_name": "customer/payroll-fix",
                    "commit_message": "leaky customer detail",
                    "pipeline_url": "https://gitlab.example/secret",
                    "failure_count": 2,
                },
                payload={"job_log": "raw stack trace", "job_id": "job-secret"},
                occurred_at="2026-06-11T00:00:00+00:00",
            )
            vscode = append_developer_source_event(
                config,
                {
                    "app": "VS Code",
                    "event_type": "save",
                    "object_type": "file",
                    "object_id": "file-secret-id",
                    "file_path": "/private/project/customer.py",
                    "metadata": {"workspace_path": "/private/project", "language_id": "python"},
                },
            )
            events = query_collector_events(config, limit=10)["events"]

        serialized = json.dumps({"gitlab": gitlab, "vscode": vscode, "events": events}, ensure_ascii=False)
        self.assertEqual(gitlab["collector"], "code_hosting_activity")
        self.assertEqual(gitlab["stimulus_type"], "ci_failed")
        self.assertEqual(vscode["collector"], "file_operation_activity")
        self.assertIn("repository_id_hash", events[1]["metadata"])
        self.assertTrue(events[1]["metadata"]["branch_name_redacted"])
        self.assertTrue(events[1]["metadata"]["pipeline_url_redacted"])
        self.assertTrue(events[0]["metadata"]["workspace_path_redacted"])
        self.assertNotIn("customer/payroll-fix", serialized)
        self.assertNotIn("leaky customer detail", serialized)
        self.assertNotIn("/private/project", serialized)
        self.assertNotIn("raw stack trace", serialized)

    def test_local_developer_source_tick_does_not_require_connector_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            tick = run_connector_source_tick(config, provider_id="vscode")
            status = connector_source_status(config, provider_id="vscode")

        self.assertEqual(tick["sources"][0]["status"], "running")
        self.assertTrue(tick["sources"][0]["connector_readiness"]["local_bridge"])
        self.assertEqual(status["sources"][0]["connector_readiness"]["connection_ready"], True)

    def test_google_workspace_source_tick_uses_connector_runtime_and_app_cursors(self) -> None:
        class FakeGoogleRuntime:
            operations: list[str] = []

            def __init__(self, config: AgentConfig) -> None:
                self.config = config

            def readiness(self, provider_id: str) -> dict[str, object]:
                return {
                    "provider_id": provider_id,
                    "configured": True,
                    "connected": True,
                    "collector_ready": True,
                    "scopes": [
                        "https://www.googleapis.com/auth/drive.metadata.readonly",
                        "https://www.googleapis.com/auth/gmail.readonly",
                        "https://www.googleapis.com/auth/calendar.readonly",
                    ],
                    "expires_at": 0,
                }

            def execute_operation(self, request) -> dict[str, object]:  # type: ignore[no-untyped-def]
                self.operations.append(request.operation)
                responses = {
                    "drive_changes_list": {
                        "changes": [
                            {
                                "fileId": "doc-secret-id",
                                "time": "2026-06-11T00:01:00Z",
                                "file": {
                                    "id": "doc-secret-id",
                                    "mimeType": "application/vnd.google-apps.document",
                                    "modifiedTime": "2026-06-11T00:01:00Z",
                                    "shared": True,
                                },
                            }
                        ],
                        "newStartPageToken": "drive-next",
                    },
                    "gmail_history_list": {
                        "history": [
                            {
                                "id": "102",
                                "messagesAdded": [
                                    {"message": {"id": "message-secret-id", "threadId": "thread-secret-id", "labelIds": ["INBOX"]}}
                                ],
                            }
                        ],
                        "historyId": "102",
                    },
                    "calendar_events_sync": {
                        "items": [
                            {
                                "id": "calendar-secret-id",
                                "status": "confirmed",
                                "created": "2026-06-11T00:02:00Z",
                                "updated": "2026-06-11T00:02:00Z",
                            }
                        ],
                        "nextSyncToken": "calendar-next",
                    },
                }
                return {"provider_id": request.provider_id, "operation": request.operation, "status_code": 200, "response": responses[request.operation]}

            def refresh_token(self, provider_id: str) -> dict[str, object]:
                return {"provider_id": provider_id, "connected": True}

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            log = CollectorEventLog(config.collector_events_db_path)
            log.save_consumer_state(
                "connector_sources",
                {
                    "sources": {
                        "google_workspace": {
                            "apps": {
                                "drive": {"page_token": "drive-cursor"},
                                "gmail": {"history_id": "101"},
                                "calendar": {"sync_token": "calendar-cursor"},
                            }
                        }
                    }
                },
            )

            with patch("humungousaur.collectors.sources.google_workspace.ConnectorRuntime", FakeGoogleRuntime):
                tick = run_connector_source_tick(config, provider_id="google_workspace")
            document_events = query_collector_events(config, collector="document_composition_activity", limit=5)["events"]
            mail_events = query_collector_events(config, collector="mail_activity", limit=5)["events"]
            calendar_events = query_collector_events(config, collector="calendar_scheduling_activity", limit=5)["events"]
            state = CollectorEventLog(config.collector_events_db_path).consumer_state("connector_sources")

        serialized = str({"tick": tick, "document_events": document_events, "mail_events": mail_events, "calendar_events": calendar_events})
        self.assertEqual(tick["sources"][0]["provider_id"], "google_workspace")
        self.assertEqual(tick["sources"][0]["events_appended"], 3)
        self.assertEqual(
            [app["app"] for app in tick["sources"][0]["apps"]],
            ["drive", "docs", "sheets", "slides", "gmail", "calendar", "meet", "chat", "contacts", "tasks", "keep"],
        )
        self.assertEqual(FakeGoogleRuntime.operations, ["drive_changes_list", "gmail_history_list", "calendar_events_sync"])
        self.assertEqual(document_events[0]["source"], "google_workspace")
        self.assertEqual(document_events[0]["stimulus_type"], "document_edited")
        self.assertEqual(mail_events[0]["stimulus_type"], "email_received")
        self.assertEqual(calendar_events[0]["stimulus_type"], "calendar_event_created")
        self.assertEqual(state["sources"]["google_workspace"]["apps"]["drive"]["page_token"], "drive-next")
        self.assertEqual(state["sources"]["google_workspace"]["apps"]["gmail"]["history_id"], "102")
        self.assertEqual(state["sources"]["google_workspace"]["apps"]["calendar"]["sync_token"], "calendar-next")
        self.assertNotIn("doc-secret-id", serialized)
        self.assertNotIn("message-secret-id", serialized)
        self.assertNotIn("thread-secret-id", serialized)
        self.assertNotIn("calendar-secret-id", serialized)

    def test_google_workspace_source_tick_reports_disconnected_connector_without_api_calls(self) -> None:
        class DisconnectedRuntime:
            operations = 0

            def __init__(self, config: AgentConfig) -> None:
                self.config = config

            def readiness(self, provider_id: str) -> dict[str, object]:
                return {"provider_id": provider_id, "configured": True, "connected": False, "collector_ready": False}

            def execute_operation(self, request) -> dict[str, object]:  # type: ignore[no-untyped-def]
                self.operations += 1
                return {}

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            with patch("humungousaur.collectors.sources.google_workspace.ConnectorRuntime", DisconnectedRuntime):
                tick = run_connector_source_tick(config, provider_id="google_workspace")

        self.assertEqual(tick["sources"][0]["status"], "permission_denied")
        self.assertEqual(tick["sources"][0]["events_appended"], 0)
        self.assertEqual(DisconnectedRuntime.operations, 0)

    def test_google_workspace_source_tick_scope_gates_missing_api_grants(self) -> None:
        class ScopedRuntime:
            operations: list[str] = []

            def __init__(self, config: AgentConfig) -> None:
                self.config = config

            def readiness(self, provider_id: str) -> dict[str, object]:
                return {
                    "provider_id": provider_id,
                    "configured": True,
                    "connected": True,
                    "collector_ready": True,
                    "scopes": ["https://www.googleapis.com/auth/drive.metadata.readonly"],
                    "expires_at": 0,
                }

            def execute_operation(self, request) -> dict[str, object]:  # type: ignore[no-untyped-def]
                self.operations.append(request.operation)
                return {
                    "provider_id": request.provider_id,
                    "operation": request.operation,
                    "status_code": 200,
                    "response": {"changes": [], "newStartPageToken": "drive-next"},
                }

            def refresh_token(self, provider_id: str) -> dict[str, object]:
                return {"provider_id": provider_id, "connected": True}

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            CollectorEventLog(config.collector_events_db_path).save_consumer_state(
                "connector_sources",
                {"sources": {"google_workspace": {"apps": {"drive": {"page_token": "drive-cursor"}, "gmail": {"history_id": "101"}, "calendar": {"sync_token": "calendar-cursor"}}}}},
            )

            with patch("humungousaur.collectors.sources.google_workspace.ConnectorRuntime", ScopedRuntime):
                tick = run_connector_source_tick(config, provider_id="google_workspace")

        apps = {app["app"]: app for app in tick["sources"][0]["apps"]}
        self.assertEqual(ScopedRuntime.operations, ["drive_changes_list"])
        self.assertEqual(apps["gmail"]["implementation_level"], "scope_gated_poller")
        self.assertEqual(apps["calendar"]["implementation_level"], "scope_gated_poller")
        self.assertEqual(tick["sources"][0]["events_appended"], 0)

    def test_microsoft_365_source_tick_uses_graph_delta_cursors_and_app_collectors(self) -> None:
        class FakeMicrosoftRuntime:
            operations: list[str] = []

            def __init__(self, config: AgentConfig) -> None:
                self.config = config

            def readiness(self, provider_id: str) -> dict[str, object]:
                return {
                    "provider_id": provider_id,
                    "configured": True,
                    "connected": True,
                    "collector_ready": True,
                    "scopes": [
                        "Files.Read.All",
                        "Sites.Read.All",
                        "Mail.Read",
                        "Calendars.Read",
                        "Tasks.Read",
                        "Notes.Read",
                        "Chat.Read",
                        "Presence.Read",
                    ],
                    "expires_at": 0,
                }

            def execute_operation(self, request) -> dict[str, object]:  # type: ignore[no-untyped-def]
                self.operations.append(request.operation)
                responses = {
                    "onedrive_delta": {
                        "value": [
                            {
                                "id": "word-secret-id",
                                "eTag": "etag-secret",
                                "lastModifiedDateTime": "2026-06-11T00:01:00Z",
                                "file": {"mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
                            }
                        ],
                        "@odata.deltaLink": "/v1.0/me/drive/root/delta?token=drive-next",
                    },
                    "outlook_mail_delta": {
                        "value": [
                            {
                                "id": "message-secret-id",
                                "conversationId": "thread-secret-id",
                                "receivedDateTime": "2026-06-11T00:02:00Z",
                                "lastModifiedDateTime": "2026-06-11T00:02:00Z",
                                "importance": "high",
                                "hasAttachments": True,
                            }
                        ],
                        "@odata.deltaLink": "/v1.0/me/mailFolders/inbox/messages/delta?token=mail-next",
                    },
                    "outlook_calendar_delta": {
                        "value": [
                            {
                                "id": "calendar-secret-id",
                                "createdDateTime": "2026-06-11T00:03:00Z",
                                "lastModifiedDateTime": "2026-06-11T00:03:00Z",
                                "isOnlineMeeting": True,
                            }
                        ],
                        "@odata.deltaLink": "/v1.0/me/calendarView/delta?token=calendar-next",
                    },
                    "teams_presence_get": {"availability": "Busy", "activity": "InAMeeting", "sequenceNumber": "presence-next"},
                    "onenote_pages_list": {
                        "value": [
                            {
                                "id": "onenote-secret-id",
                                "createdDateTime": "2026-06-11T00:04:00Z",
                                "lastModifiedDateTime": "2026-06-11T00:05:00Z",
                                "level": 1,
                            }
                        ]
                    },
                    "todo_tasks_delta": {
                        "value": [
                            {
                                "id": "todo-secret-id",
                                "createdDateTime": "2026-06-11T00:00:00Z",
                                "lastModifiedDateTime": "2026-06-11T00:06:00Z",
                                "status": "completed",
                            }
                        ],
                        "@odata.deltaLink": "/v1.0/me/todo/lists/list-secret/tasks/delta?token=todo-next",
                    },
                }
                return {"provider_id": request.provider_id, "operation": request.operation, "status_code": 200, "response": responses[request.operation]}

            def refresh_token(self, provider_id: str) -> dict[str, object]:
                return {"provider_id": provider_id, "connected": True}

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            log = CollectorEventLog(config.collector_events_db_path)
            log.save_consumer_state(
                "connector_sources",
                {
                    "sources": {
                        "microsoft_365": {
                            "apps": {
                                "onedrive": {"delta_link": "/v1.0/me/drive/root/delta?token=drive-cursor"},
                                "outlook": {"delta_link": "/v1.0/me/mailFolders/inbox/messages/delta?token=mail-cursor"},
                                "calendar": {"delta_link": "/v1.0/me/calendarView/delta?token=calendar-cursor"},
                                "teams": {"presence_sequence": "presence-old"},
                                "onenote": {"modified_min": "2026-06-11T00:00:00Z"},
                                "todo": {"list_id": "list-secret", "delta_link": "/v1.0/me/todo/lists/list-secret/tasks/delta?token=todo-cursor"},
                            }
                        }
                    }
                },
            )

            with patch("humungousaur.collectors.sources.microsoft_365.ConnectorRuntime", FakeMicrosoftRuntime):
                tick = run_connector_source_tick(config, provider_id="microsoft_365")
            document_events = query_collector_events(config, collector="document_composition_activity", limit=5)["events"]
            mail_events = query_collector_events(config, collector="mail_activity", limit=5)["events"]
            calendar_events = query_collector_events(config, collector="calendar_scheduling_activity", limit=5)["events"]
            presence_events = query_collector_events(config, collector="chat_presence_activity", limit=5)["events"]
            notes_events = query_collector_events(config, collector="notes_activity", limit=5)["events"]
            task_events = query_collector_events(config, collector="task_manager_activity", limit=5)["events"]
            status = microsoft_365_source_status(config)
            state = CollectorEventLog(config.collector_events_db_path).consumer_state("connector_sources")

        serialized = str(
            {
                "tick": tick,
                "document_events": document_events,
                "mail_events": mail_events,
                "calendar_events": calendar_events,
                "presence_events": presence_events,
                "notes_events": notes_events,
                "task_events": task_events,
                "status": status,
            }
        )
        self.assertEqual(tick["sources"][0]["provider_id"], "microsoft_365")
        self.assertEqual(tick["sources"][0]["events_appended"], 6)
        self.assertEqual(
            [app["app"] for app in tick["sources"][0]["apps"]],
            ["onedrive", "sharepoint", "word", "excel", "powerpoint", "outlook", "calendar", "teams", "onenote", "todo", "loop"],
        )
        self.assertEqual(
            FakeMicrosoftRuntime.operations,
            ["onedrive_delta", "outlook_mail_delta", "outlook_calendar_delta", "teams_presence_get", "onenote_pages_list", "todo_tasks_delta"],
        )
        self.assertEqual(document_events[0]["source"], "microsoft_365")
        self.assertEqual(document_events[0]["stimulus_type"], "document_edited")
        self.assertEqual(mail_events[0]["stimulus_type"], "important_email_received")
        self.assertEqual(calendar_events[0]["stimulus_type"], "calendar_event_created")
        self.assertEqual(presence_events[0]["stimulus_type"], "presence_changed")
        self.assertEqual(notes_events[0]["stimulus_type"], "note_edited")
        self.assertEqual(task_events[0]["stimulus_type"], "task_completed")
        self.assertEqual(state["sources"]["microsoft_365"]["apps"]["onedrive"]["delta_link"], "/v1.0/me/drive/root/delta?token=drive-next")
        self.assertEqual(status["app_collectors"][0]["app"], "onedrive")
        self.assertIn("loop", status["supported_apps"])
        self.assertNotIn("word-secret-id", serialized)
        self.assertNotIn("message-secret-id", serialized)
        self.assertNotIn("thread-secret-id", serialized)
        self.assertNotIn("calendar-secret-id", serialized)
        self.assertNotIn("onenote-secret-id", serialized)
        self.assertNotIn("todo-secret-id", serialized)

    def test_microsoft_365_ingest_redacts_office_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            result = append_microsoft_365_event(
                config,
                {
                    "app": "excel",
                    "event_type": "cell_range_edited",
                    "object_type": "spreadsheet",
                    "object_id": "workbook-secret-id",
                    "metadata": {"source_channel": "excel_addin"},
                    "title": "Secret workbook",
                    "cell_value": "classified value",
                    "formula": '=WEBSERVICE("secret")',
                    "participants": ["person@example.com"],
                    "payload": {"message_id": "provider-secret", "body": "raw body"},
                },
            )
            events = query_collector_events(config, collector="spreadsheet_editing_activity", limit=5)["events"]

        serialized = str({"result": result, "events": events})
        self.assertTrue(result["accepted"])
        self.assertEqual(result["source_event"], "excel_range_edited")
        self.assertEqual(events[0]["stimulus_type"], "cell_range_edited")
        self.assertTrue(events[0]["metadata"]["title_redacted"])
        self.assertTrue(events[0]["metadata"]["cell_value_redacted"])
        self.assertTrue(events[0]["metadata"]["formula_redacted"])
        self.assertTrue(events[0]["payload"]["message_id_hash"])
        self.assertTrue(events[0]["payload"]["body_redacted"])
        self.assertNotIn("Secret workbook", serialized)
        self.assertNotIn("classified value", serialized)
        self.assertNotIn("WEBSERVICE", serialized)
        self.assertNotIn("person@example.com", serialized)

    def test_microsoft_365_source_tick_reports_disconnected_connector_without_api_calls(self) -> None:
        class DisconnectedRuntime:
            operations = 0

            def __init__(self, config: AgentConfig) -> None:
                self.config = config

            def readiness(self, provider_id: str) -> dict[str, object]:
                return {"provider_id": provider_id, "configured": True, "connected": False, "collector_ready": False}

            def execute_operation(self, request) -> dict[str, object]:  # type: ignore[no-untyped-def]
                self.operations += 1
                return {}

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            with patch("humungousaur.collectors.sources.microsoft_365.ConnectorRuntime", DisconnectedRuntime):
                tick = run_connector_source_tick(config, provider_id="microsoft_365")

        self.assertEqual(tick["sources"][0]["status"], "permission_denied")
        self.assertEqual(tick["sources"][0]["events_appended"], 0)
        self.assertEqual(DisconnectedRuntime.operations, 0)

    def test_microsoft_365_source_tick_scope_gates_missing_graph_grants(self) -> None:
        class ScopedRuntime:
            operations: list[str] = []

            def __init__(self, config: AgentConfig) -> None:
                self.config = config

            def readiness(self, provider_id: str) -> dict[str, object]:
                return {
                    "provider_id": provider_id,
                    "configured": True,
                    "connected": True,
                    "collector_ready": True,
                    "scopes": ["Files.Read.All"],
                    "expires_at": 0,
                }

            def execute_operation(self, request) -> dict[str, object]:  # type: ignore[no-untyped-def]
                self.operations.append(request.operation)
                return {
                    "provider_id": request.provider_id,
                    "operation": request.operation,
                    "status_code": 200,
                    "response": {"value": [], "@odata.deltaLink": "/v1.0/me/drive/root/delta?token=drive-next"},
                }

            def refresh_token(self, provider_id: str) -> dict[str, object]:
                return {"provider_id": provider_id, "connected": True}

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            CollectorEventLog(config.collector_events_db_path).save_consumer_state(
                "connector_sources",
                {
                    "sources": {
                        "microsoft_365": {
                            "apps": {
                                "onedrive": {"delta_link": "/v1.0/me/drive/root/delta?token=drive-cursor"},
                                "outlook": {"delta_link": "/v1.0/me/mailFolders/inbox/messages/delta?token=mail-cursor"},
                                "calendar": {"delta_link": "/v1.0/me/calendarView/delta?token=calendar-cursor"},
                                "teams": {"presence_sequence": "presence-old"},
                            }
                        }
                    }
                },
            )

            with patch("humungousaur.collectors.sources.microsoft_365.ConnectorRuntime", ScopedRuntime):
                tick = run_connector_source_tick(config, provider_id="microsoft_365")

        apps = {app["app"]: app for app in tick["sources"][0]["apps"]}
        self.assertEqual(ScopedRuntime.operations, ["onedrive_delta"])
        self.assertEqual(apps["outlook"]["implementation_level"], "scope_gated_poller")
        self.assertEqual(apps["calendar"]["implementation_level"], "scope_gated_poller")
        self.assertEqual(apps["teams"]["implementation_level"], "scope_gated_poller")
        self.assertEqual(tick["sources"][0]["events_appended"], 0)

    def test_connector_runtime_operation_checks_connection_and_scopes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            runtime = ConnectorRuntime(config)

            with self.assertRaises(ValueError):
                runtime.execute_operation(
                    ConnectorOperationRequest(
                        provider_id="github",
                        operation="repo_state",
                        path="/repos/example/project",
                        required_scopes=("repo",),
                    )
                )


if __name__ == "__main__":
    unittest.main()
