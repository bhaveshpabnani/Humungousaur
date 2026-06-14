# App Connector, Collector, Tool, And Channel Doc Validation

Last updated: 2026-06-13

This document tracks the manual implementation audit against official app docs. A provider is marked validated only when the connector manifest/runtime and the collector/tool/channel surface were inspected against vendor docs. "Partial" means the implemented surface is real but narrower than the full vendor platform. "Remaining" means the provider is cataloged or partially wired but still needs more runtime work before it should be considered end-to-end complete.

## Validated And Fixed In This Pass

| Area | Providers | Doc result | Implementation changes |
|---|---|---|---|
| Workspace and planning | Linear, Google Workspace, Microsoft 365, Slack | Validated core OAuth/API/source paths; Slack remains Events API/webhook-first, not a Socket Mode client. | Linear API base now points to `https://api.linear.app/graphql`; Google Gmail/Contacts/Tasks/Keep collectors preserve documented pagination cursors; Slack docs use current docs host and Slack webhook signatures are verified when `SLACK_SIGNING_SECRET` is configured. |
| Business, commerce, finance, marketing | Salesforce, HubSpot, Zendesk, Intercom, Freshdesk, Stripe, Shopify, Square, PayPal, QuickBooks, Xero, Plaid, Wise, Mercury, Brex, Ramp, Mailchimp | Validated as metadata-first webhook/browser/API-ingress collectors, not native full pollers for every app. | Added missing collector/source manifests for Square, PayPal, Plaid, Wise, Mercury, Brex, Ramp, and Mailchimp; added event aliases and redaction coverage. Fixed Shopify versioned Admin API base, Stripe auth docs, Plaid JSON-body credentials, Mercury bearer auth, and PagerDuty token auth. |
| Data, analytics, operations | Datadog, Opsgenie, Snowflake, Tableau, PagerDuty, Cloudflare, Vercel, Netlify, Metabase, Amplitude, Sentry, Grafana and related sources | Validated connector/auth shape where implemented; many collectors are metadata-ingress shells, not full native pollers. | Replaced stale official docs URLs for Opsgenie, Snowflake, Tableau, X, iCloud, HyperFrames, local QA/ClickClack. Added PagerDuty token auth. |
| Channels | Slack, Telegram, Discord, WhatsApp, Google Chat, Microsoft Teams, SMS, Signal plus long-tail catalog channels | Validated implemented sends/listeners vs prepared-only surfaces. Long-tail channels remain explicit prepared/catalog surfaces when `official_send=false`. | Added Slack Events API signature verification with replay-window check; Nextcloud Talk now sends required `OCS-APIRequest: true`; local docs markers used for local-only channels. |
| Design/media/research/AI | Figma, FigJam, Canva, YouTube, Readwise, OpenRouter, Perplexity, LiteLLM, OpenAI, Anthropic, Gemini, Groq, Exa, Fal, Spotify | Validated connector-level auth/base where implemented; some are connector credentials for existing tool/model surfaces, not collectors. | Figma/FigJam source scopes now match granular Figma scopes; Canva connector includes `design:content:read`; YouTube API key uses query `key`; added connector manifests for Readwise, OpenRouter, Perplexity, and LiteLLM; Readwise uses `Authorization: Token` and now has collector source mappings/ingress; Spotify native tools now accept connector-runtime readiness instead of env-only `SPOTIFY_ACCESS_TOKEN`. |
| Cloud files and knowledge bases | Dropbox, Box, iCloud Drive, Nextcloud Files, Notion, Confluence, Coda, Obsidian, Evernote, Readwise, Apple Notes, OneNote | Validated metadata-first collector manifests and ingress aliases against provider docs where available. Nextcloud is registered as WebDAV/OCS relay/local bridge ingress, not an OCS-rooted full file poller. | Added Nextcloud WebDAV/OCS cloud-file source mappings, redacted Nextcloud ingress aliases, Readwise knowledge-source mappings, Readwise collector status/tick coverage, and source tests for both. |
| Developer platforms | GitHub, GitLab, Bitbucket, Azure DevOps | Validated webhook/API source shape. | GitHub `pull_request.closed` now maps to merged only when `pull_request.merged=true`; unmerged closes become issue/status changes. |

## Remaining Partial Or Explicitly Limited Surfaces

| Provider group | Remaining work |
|---|---|
| Slack / Discord / Teams | Slack Socket Mode, Discord Gateway session management, and Teams Bot Framework/Graph send are not implemented as live connection managers. Current support is webhook/polling/send where wired plus redacted ingress. |
| WhatsApp / Twilio | WhatsApp text send and Twilio SMS are wired; broader template/media/status handling and provider webhook signature validation are still limited. |
| Data and observability | BigQuery audit logs, Snowflake event-table polling, Databricks audit-log polling, Tableau PAT sign-in exchange, Looker login/token exchange, Power BI client-credential acquisition, AWS SigV4 request signing, and Kubernetes watch/kubeconfig loading remain partial. |
| Knowledge/design/local | Evernote OAuth1 runtime, Obsidian plugin bridge fixtures, Adobe XD bridge tests, Blender/ComfyUI/HyperFrames live bridge execution are not complete. |
| Cloud files | Dropbox is strongest; Box has an Events poller; iCloud and Nextcloud are connector/source registered as local/WebDAV/OCS ingress but still need more provider-specific fixtures or native bridge tests before they count as full live pollers. |
| Model/search providers | OpenRouter, Perplexity, LiteLLM, and Readwise now have connector manifests; Spotify service tools consume connector readiness. Remaining model/search client code still needs a follow-up pass to consume connector-vault credentials everywhere instead of env-only paths. |
| Confluence | OAuth client field shape is fixed to support authorization-code setup plus `cloud_id`, but full API-token-basic and OAuth cloud-id discovery flows need dedicated tests. |

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_workspace_connectors.py -q` -> 63 passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_workspace_connectors.py tests/test_channel_tools.py tests/test_tools.py tests/test_api.py -q` -> 172 passed, 3 skipped.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_workspace_connectors.py::WorkspaceConnectorTests::test_connector_source_manifest_mappings_target_existing_collectors tests/test_workspace_connectors.py::WorkspaceConnectorTests::test_cloud_file_source_manifests_cover_requested_providers tests/test_workspace_connectors.py::WorkspaceConnectorTests::test_cloud_file_ingress_accepts_google_and_microsoft_drive_aliases tests/test_workspace_connectors.py::WorkspaceConnectorTests::test_knowledge_base_source_events_enter_collector_log_with_redaction tests/test_workspace_connectors.py::WorkspaceConnectorTests::test_knowledge_base_source_tick_covers_local_and_saas_apps tests/test_tools.py::ToolTests::test_spotify_tools_accept_connector_runtime_credentials -q` -> 6 passed.
- `swift build --package-path apps/macos` -> passed.
- `dotnet build apps/windows/Humungousaur.App/Humungousaur.App.csproj -p:EnableWindowsTargeting=true` -> blocked on macOS because WinUI's `XamlCompiler.exe` is a Windows executable.
