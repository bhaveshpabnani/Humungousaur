# Workspace Connector Tool Matrix

Last checked: 2026-06-11

This is the connector backlog for turning Humungousaur into a one-click desktop workspace hub. It is based on the current native catalog:

- 527 registered native tools.
- 28 communication channel manifests.
- 152 connector provider manifests.
- 11 connector tools: `workspace_connector_catalog`, `workspace_connector_status`, `workspace_connector_configure`, `workspace_connector_connect_prepare`, `workspace_connector_refresh`, `workspace_connector_disconnect`, `workspace_connector_source_manifest`, `workspace_connector_source_status`, `workspace_connector_source_tick`, `workspace_connector_source_event_ingest`, `workspace_connector_source_health`.

The important product boundary is:

- A connector authenticates and stores provider grants locally so tools and
  collector adapters can ask, "is this provider connection ready?"
- Domain tools keep their current ownership. Office stays in `office` and `productivity`; chat stays in `channels`; GitHub stays in `github`; model/MLOps stays in `mlops`; media stays in `media`.
- A connector adapter should expose read/list/search/create/update/send methods only where there is already a native tool family or channel surface that can use it.
- Collector source adapters own provider-event mapping, metadata-first
  redaction, helper health, cursor state, and `CollectorEventEnvelope` writes.
  They may use connector readiness before polling or accepting webhooks, but
  they are not implemented inside the connector runtime.
- OAuth connectors should default to product-managed OAuth: Humungousaur or its
  backend owns the provider client registration and users only click Connect.
  Manual client ID/secret setup is an advanced self-hosted/development fallback,
  not the consumer product path.
- Live sends, posts, purchases, destructive edits, external workflow writes, and privileged browser/OS actions remain approval-gated.

## Current Connector Base

The shared connector registry now covers the app/provider surfaces exposed by
the current native tool and channel catalog. These are connection manifests:
provider identity, setup/auth type, scopes or credential fields, API base,
surface names, and native tool hints. Provider-specific read/write/list/send
adapters still belong to the owning tool packages.

| Category | Provider ids |
| --- | --- |
| AI providers | `anthropic`, `gemini`, `grok_xai`, `groq`, `ollama`, `openai` |
| Analytics | `amplitude`, `google_analytics`, `looker`, `metabase`, `mixpanel`, `power_bi`, `tableau` |
| Apple/local | `apple_local`, `icloud`, `imessage` |
| Browser/collector/MCP | `browser_use`, `screenpipe`, `mcp` |
| Business/support | `freshdesk`, `hubspot`, `intercom`, `pipedrive`, `salesforce`, `zendesk` |
| Commerce/finance | `brex`, `mercury`, `paypal`, `plaid`, `quickbooks`, `ramp`, `shopify`, `square`, `stripe`, `wise`, `xero` |
| Communications | `clickclack`, `discord`, `feishu`, `googlechat`, `irc`, `line`, `matrix`, `mattermost`, `msteams`, `nextcloud_talk`, `nostr`, `qa_channel`, `qqbot`, `signal`, `slack`, `sms`, `synology_chat`, `telegram`, `tlon`, `twitch`, `voice_call`, `webchat`, `wechat`, `whatsapp`, `yuanbao`, `zalo`, `zalo_personal` |
| Data | `airtable`, `bigquery`, `chroma`, `databricks`, `mongodb_atlas`, `mysql`, `postgres`, `snowflake`, `supabase` |
| Developer/devops | `azure_devops`, `bitbucket`, `cloudflare`, `datadog`, `docker_hub`, `github`, `gitlab`, `grafana`, `kubernetes`, `netlify`, `opsgenie`, `pagerduty`, `sentry`, `vercel` |
| Developer tools | `cursor`, `jetbrains`, `vscode`, `xcode` |
| Design/meetings | `adobe_xd`, `canva`, `figjam`, `figma`, `miro`, `sketch`, `webex`, `zoom` |
| Files/knowledge/education | `box`, `canvas_lms`, `coda`, `confluence`, `dropbox`, `evernote`, `notion`, `obsidian`, `onenote`, `siyuan` |
| Media/voice/ML ops | `blender`, `comfyui`, `deepgram`, `elevenlabs`, `fal`, `hugging_face`, `hugging_face_datasets`, `hyperframes`, `lambda_labs`, `modal`, `pinecone`, `qdrant`, `replicate`, `spotify`, `stability_ai`, `wandb`, `youtube` |
| Office/planning | `asana`, `atlassian`, `clickup`, `google_workspace`, `icloud`, `jira`, `linear`, `microsoft_365`, `monday`, `nextcloud`, `notion_projects`, `todoist`, `trello`, `zoho` |
| Research/social/security/IoT | `arxiv`, `brave_search`, `crossref`, `duckduckgo`, `exa`, `firecrawl`, `homeassistant`, `onepassword`, `polymarket`, `rss`, `searxng`, `tavily`, `x_twitter` |

## Connector Runtime Pieces Needed For Every Provider

| Runtime piece | Purpose | Native owner |
| --- | --- | --- |
| Provider manifests | Provider identity, OAuth endpoints, API base URL, scopes, apps, and native tool hints | `humungousaur/connectors/providers/` |
| Managed OAuth + advanced client setup | Use product-owned OAuth clients or brokered auth for one-click user connect; keep manual client id/secret storage only as advanced self-hosted fallback | `humungousaur/connectors/oauth.py` |
| Token vault | Store access/refresh tokens behind a vault abstraction with redacted status responses | `humungousaur/connectors/vault.py` |
| Profile/state store | Persist connector profiles, OAuth states, token references, and operation audit rows | `humungousaur/connectors/store.py` |
| Runtime facade | Single connection-readiness API for tools, collectors, API routes, and desktop UI | `humungousaur/connectors/runtime.py` |
| Provider API adapter | Execute provider calls with scoped token and typed request/response envelopes | `humungousaur/connectors/http.py` plus provider packages |
| Tool bridge | Convert native tool input into provider calls or operation packets | owning tool package |
| Sync cache | Store bounded metadata, cursors, ETags, page tokens, and webhook receipts | owning integration package |
| Webhook/listener | Receive provider events and normalize them into channel or activity events | `channels`, `collectors`, or provider package |
| Source collector manifest | Map provider-native events into existing `CollectorEventEnvelope` collectors and stimulus types | owning collector source package, currently `humungousaur/collectors/sources/workspace_connectors.py` |
| Audit trail | Record external reads/writes/sends, token refreshes, and approval decisions | runtime/audit |
| Desktop UI | Configure, connect, refresh, disconnect, show scopes/status/tool mapping | macOS and Windows shells |
| Permission policy | Read scopes, write scopes, destructive operations, send gates, and data-retention boundary | `security`, `permissions`, `approvals` |

## Priority 0: Shared Control Plane

These are not app connectors; they are the platform features needed before provider count grows.

| Connector/platform feature | Why it is required | Tool integration |
| --- | --- | --- |
| Connector credential profiles | Multiple workspaces/accounts per provider, active account selection, redacted status | `workspace_connector_status`, desktop Connectors view |
| Scope-to-tool policy | Tool should know whether the active grant can read, write, send, or only draft | `tool_search`, `tool_describe`, `native_security_policy`, `approval_policy_review_create` |
| Provider call executor | Generic HTTP call wrapper with retry, pagination, refresh, rate-limit handling | `api_operation_inspect`, domain adapters |
| Webhook ingress registry | Slack/Discord/Linear/GitHub/Teams/Twilio events need one normalized entry point | `channel_webhook_ingest`, `activity_ingest`, `collector_status` |
| Sync jobs | Background refresh for mail, calendar, issues, PRs, tasks, and files | `cronjob`, `automation_daemon_tick`, `activity_search` |
| Connector health checks | Per-provider doctor with token validity, scopes, API reachability, webhook health | `channel_doctor`, `http_endpoint_check`, `workspace_connector_status` |
| Collector source ingestion | Webhook/poller events enter the durable collector event log with metadata-first redaction after connector-readiness checks | `workspace_connector_source_event_ingest`, `/connectors/source-events`, `/connectors/sources` |
| Connector data export/delete | User can inspect and remove local connector cache/token data | `activity_prune`, `plugin_state`, `workspace_connector_disconnect` |

## Priority 1: Core Workspace Suites

| Connector | Apps/surfaces | Native tools and channels to integrate | Adapter work |
| --- | --- | --- | --- |
| Google Workspace | Gmail, Calendar, Drive, Docs, Sheets, Slides, Meet, Chat, Contacts, Tasks | `google_workspace_operation_prepare`, `gmail_draft_prepare`, `email_draft_prepare`, `xlsx_workbook_create`, `docx_document_create`, `pptx_deck_create`, `google_meet_context_prepare`, `googlechat`, `research_web_pages` | Gmail read/search/draft/send, Calendar list/create/update, Drive search/read/upload, Docs export/import, Sheets read/write, Slides export/create, Meet context, Chat webhook/bot |
| Microsoft 365 | Outlook, Calendar, OneDrive, SharePoint, Word, Excel, PowerPoint, Teams, OneNote, To Do, Loop, Planner | `email_draft_prepare`, `xlsx_workbook_create`, `docx_document_create`, `pptx_deck_create`, `msteams`, `channel_message_prepare`, `channel_listener_tick` | Graph mail/calendar/files/sites deltas, Office add-in/webhook workflow events, Teams chat/channel/thread/presence/meeting ingress, OneNote page metadata, To Do task deltas, Loop browser/app ingress |
| Apple/iCloud local apps | Mail, Calendar, Contacts, Notes, Reminders, Messages, Find My, Files | `apple_notes_search`, `apple_notes_create`, `apple_reminders_list`, `apple_reminders_create`, `imessage_draft_create`, `imessage_send_prepare`, `find_my_open`, `find_my_location_request_prepare`, `macos_app_workflow_prepare` | Native app automation, local permissions, per-app read/write approvals, optional iCloud account awareness |
| Zoho Workplace | Mail, Calendar, WorkDrive, Writer, Sheet, Show, Cliq, Projects | `email_draft_prepare`, `xlsx_workbook_create`, `docx_document_create`, `pptx_deck_create`, `channel_catalog`, `kanban_create` | OAuth, mail/calendar/files/docs adapters, Cliq channel, Projects tasks |
| Nextcloud | Files, Calendar, Contacts, Deck, Talk, Notes | `nextcloud_talk`, `email_draft_prepare`, `kanban_create`, `read_file`, `write_file` | WebDAV files, CalDAV/CardDAV, Deck kanban, Talk channel, Notes sync |

## Priority 1: Communication Connectors

These should be owned by `channels` unless a provider already has a dedicated package.

| Connector | Current local surface | Native tools to integrate | Adapter work |
| --- | --- | --- | --- |
| Slack | `slack` channel plus connector OAuth | `channel_message_prepare`, `channel_message_send`, `channel_listener_status`, `channel_listener_tick`, `channel_action_prepare`, `channel_outbox` | Web API send/list/search, Events API, Socket Mode, reactions, threads, files, user/team lookup |
| Microsoft Teams | `msteams` channel | `channel_message_prepare`, `channel_message_send`, `channel_listener_status`, `channel_webhook_ingest`, Microsoft 365 connector | Bot Framework, incoming webhook, Graph channel messages, Teams app install status |
| Google Chat | `googlechat` channel | `channel_message_prepare`, `channel_message_send`, `channel_listener_status`, Google Workspace connector | Webhook send, Chat app events, spaces/members |
| Discord | `discord`, `discord_admin`, `discord` channel | `channel_message_send`, `channel_action_prepare`, `discord_admin`, `channel_listener_tick` | Bot token, gateway events, slash commands, roles/moderation, threads/forums |
| Telegram | `telegram` channel | `channel_listener_tick`, `channel_message_send`, `channel_doctor` | Bot API send, long polling, webhook mode, files, topics |
| WhatsApp | `whatsapp` channel | `channel_message_send`, `channel_webhook_ingest`, `channel_pairing_prepare` | Cloud API send, webhook verify, media templates, QR bridge for personal accounts |
| Signal | `signal` channel | `channel_message_prepare`, `channel_pairing_prepare`, `channel_listener_status` | `signal-cli` account pairing, group list/send, attachment handling |
| iMessage | `imessage` channel plus Apple tools | `imessage_draft_create`, `imessage_send_prepare`, `imessage_transcript_request_prepare` | macOS Messages bridge, transcript access policy, relay mode |
| SMS | `sms` channel | `telephony_call_prepare`, `channel_message_send`, `channel_webhook_ingest` | Twilio/Plivo SMS send, inbound webhook, phone-number allowlists |
| Voice Call | `voice_call` channel | `telephony_call_prepare`, `voice_transcribe`, `voice_speak`, `channel_webhook_ingest` | Twilio/Plivo call control, STT/TTS bridge, call summaries |
| Meeting sources | `zoom`, `google_workspace` Meet, `microsoft_365` Teams, `webex`, `discord` calls | `workspace_connector_source_event_ingest`, `workspace_connector_source_status`, `meeting_followup_packet_create`, `voice_transcribe`, `channel_listener_tick` | Map webhook/API/gateway/browser-bridge events into `meeting_app_activity`, `call_control_activity`, `meeting_presentation_activity`, and `meeting_artifact_activity` with titles, participants, transcript bodies, URLs, and artifact contents redacted by default |
| Design sources | `figma`, `figjam`, `miro`, `canva`, `sketch`, `adobe_xd` | `workspace_connector_source_event_ingest`, `workspace_connector_source_status` | Map webhook/plugin/local bridge events into `creative_activity` and `whiteboard_activity`; file names, board names, comments, URLs, paths, participants, and actor names are redacted by default |
| Data and analytics sources | `bigquery`, `snowflake`, `databricks`, `postgres`, `supabase`, `mysql`, `mongodb_atlas`, `tableau`, `looker`, `metabase`, `power_bi`, `google_analytics`, `mixpanel`, `amplitude` | `workspace_connector_source_event_ingest`, `workspace_connector_source_status` | Map audit-log/API/local bridge events into `database_activity` and `analytics_activity`; SQL, query text, result values, dashboard/report names, URLs, paths, and user identifiers are redacted by default |
| Operations sources | `sentry`, `datadog`, `grafana`, `pagerduty`, `opsgenie`, `aws`, `azure`, `gcp`, `cloudflare`, `vercel`, `netlify`, `docker_hub`, `kubernetes` | `workspace_connector_source_event_ingest`, `workspace_connector_source_status` | Map webhooks, audit streams, deploy events, and local cluster bridges into `incident_activity`, `cloud_console_activity`, `analytics_activity`, and `virtual_runtime_activity`; alert bodies, logs, resource names, secret names, URLs, and paths are redacted by default |
| Matrix | `matrix` channel | `channel_message_send`, `channel_listener_status` | Homeserver token, room list, encrypted DM boundary |
| Mattermost | `mattermost` channel | `channel_message_send`, `channel_listener_status` | Bot API, WebSocket listen, channel/thread send |
| Nextcloud Talk | `nextcloud_talk` channel | `channel_message_send`, `channel_listener_status` | Talk room APIs, webhook integration |
| Feishu/Lark | `feishu` channel and `feishu_*` tools | `feishu_doc_read`, `feishu_drive_add_comment`, `feishu_drive_list_comments`, `feishu_drive_reply_comment`, `channel_message_send` | Bot auth, Docs/Drive comments, chat send/listen |
| LINE | `line` channel | `channel_message_send`, `channel_webhook_ingest` | Messaging API, webhook verification |
| WeChat | `wechat` channel | `channel_message_prepare`, `channel_pairing_prepare` | QR bridge or official account bot, message/event adapter |
| QQ Bot | `qqbot` channel | `channel_message_send`, `channel_listener_status` | QQ Bot API send/listen |
| Zalo | `zalo`, `zalo_personal` channels | `channel_message_send`, `channel_pairing_prepare` | Bot API plus personal QR bridge |
| IRC | `irc` channel | `channel_message_send`, `channel_listener_tick` | IRC connection manager, TLS/password, room join |
| Twitch Chat | `twitch` channel | `channel_message_send`, `channel_listener_tick` | IRC chat bot, stream/channel context |
| Nostr | `nostr` channel | `channel_message_send`, `channel_listener_status` | Relay list, encrypted DM keys, event signing |
| Tlon/Urbit | `tlon` channel | `channel_message_send`, `channel_listener_status` | Ship URL/session, channel/DM adapter |
| Synology Chat | `synology_chat` channel | `channel_message_send`, `channel_listener_status` | Incoming/outgoing webhooks |
| ClickClack | `clickclack` channel | `channel_message_send`, `channel_listener_status` | Bridge URL/token, private/group rooms |
| Yuanbao | `yuanbao` channel and `yb_*` tools | `yb_send_dm`, `yb_send_sticker`, `yb_query_group_info`, `yb_query_group_members`, `yb_search_sticker` | Bot bridge token, DM/sticker/group APIs |

Communication collector status: Slack, Microsoft Teams, Discord, Gmail,
Outlook, Telegram, WhatsApp, and Signal now have collector-owned source
manifests and a shared `/collectors/communication` ingress. Events are normalized
into existing communication and mail collectors for message sent/edited/deleted,
draft, thread, navigation, presence/DND, attachment, and label workflows with
raw message bodies, participant names, channel/workspace names, filenames, and
labels redacted by default. The group tick is available through
`workspace_connector_source_tick` with `provider_id=communication`.

## Priority 1: Planning, Issue, and Kanban Connectors

| Connector | Native tools to integrate | Adapter work |
| --- | --- | --- |
| Linear | `kanban_create`, `kanban_comment`, `kanban_complete`, `kanban_block`, `kanban_link`, `lobster_workflow_start`, `multi_agent_coordinate` | Issues/projects/cycles/team sync, comments, assignment, status updates, webhook events |
| Jira | `kanban_create`, `kanban_comment`, `kanban_complete`, `kanban_link`, `business_report_create` | Cloud OAuth, projects/issues/sprints, comments, status transitions, webhooks |
| Asana | `kanban_create`, `kanban_comment`, `kanban_complete`, `daily_plan_create` | Workspaces/projects/tasks, comments, assignees, due dates |
| Trello | `kanban_create`, `kanban_comment`, `kanban_complete`, `kanban_list` | Boards/lists/cards, comments, checklist items |
| ClickUp | `kanban_create`, `kanban_comment`, `kanban_complete`, `business_report_create` | Spaces/folders/lists/tasks, custom fields, comments |
| Monday.com | `kanban_create`, `business_report_create`, `chart_artifact_create` | Boards/items/columns, status changes, updates |
| Notion Projects | `notion_operation_prepare`, `kanban_create`, `memory_wiki_entry_prepare` | Database/page create/update/query, comments, project templates |
| GitHub Issues/Projects | `github_issue_packet_create`, `github_issue_draft_create`, `kanban_link`, `ci_failure_report_create` | Issues, project v2 fields, comments, labels, milestones |
| GitLab Issues | `kanban_create`, `kanban_comment`, `ci_failure_report_create`, `gitnexus_repo_intel_prepare` | Issues/MRs/pipelines, comments, labels, epics |
| Azure DevOps Boards | `kanban_create`, `kanban_comment`, `ci_failure_report_create` | Work items, boards, repos, pipelines |

Collector source status: Linear, Jira, Asana, Trello, ClickUp, Monday.com, and
Todoist now have metadata-first planning source manifests and dedicated
`humungousaur.collectors.sources.planning` ingress. The first implemented lane is
webhook, browser-extension, or local relay ingestion for task/issue created,
assigned, moved, commented, completed/reopened, priority changed, due date
changed, sprint changed, and project navigation/change events. Provider-specific
pollers remain adapter work.

## Priority 1: Developer Platform Connectors

| Connector | Native tools to integrate | Adapter work |
| --- | --- | --- |
| GitHub | `github_repo_state_report_create`, `github_pr_packet_create`, `github_pr_summary_create`, `github_issue_packet_create`, `github_artifact_inspect`, `github_workflow_artifact_inspect`, `ci_failure_report_create` | REST/GraphQL adapters, repo/PR/issue/actions sync, review comments, artifact downloads, and collector source mappings for PRs, reviews, branches, CI, issues, and comments |
| GitLab | `gitnexus_repo_intel_prepare`, `ci_failure_report_create`, `oss_forensics_report_create`, `dependency_inventory_create` | Projects/MRs/issues/pipelines/jobs/artifacts plus collector source mappings for MRs, reviews, branches, CI, issues, and comments |
| Bitbucket | `gitnexus_repo_intel_prepare`, `ci_failure_report_create` | Repositories/PRs/pipelines plus collector source mappings for PRs, reviews, branches, CI, issues, and comments |
| Azure DevOps Repos/Pipelines | `gitnexus_repo_intel_prepare`, `ci_failure_report_create`, `github_workflow_artifact_inspect` equivalent | Repos, PRs, builds/pipelines, work items, artifacts, and collector source mappings for service-hook PR, push, build/pipeline, issue/work-item, and comment metadata |
| Sentry | `domain_intel_report_create`, `business_report_create`, `prompt_injection_review_create` | Issues/events/releases/projects, alert webhooks |
| Datadog | `business_report_create`, `chart_artifact_create`, `http_endpoint_check` | Metrics/logs/traces/monitors, dashboards |
| Grafana | `chart_artifact_create`, `business_report_create`, `http_endpoint_check` | Dashboards, datasources, alerts |
| PagerDuty/Opsgenie | `channel_message_send`, `daily_plan_create`, `business_report_create` | Incidents, on-call, acknowledgements, notes |
| Vercel | `http_endpoint_check`, `ci_failure_report_create`, `business_report_create` | Deployments, projects, logs, domains |
| Netlify | `http_endpoint_check`, `ci_failure_report_create` | Sites/deploys/functions/logs |
| Cloudflare | `dns_lookup`, `http_endpoint_check`, `domain_intel_report_create` | DNS, zones, Pages, Workers, WAF events |
| Docker Hub/GHCR | `docker_container_list`, `docker_compose_prepare`, `dependency_inventory_create` | Images/tags/vulns, registry auth |
| Kubernetes | `docker_container_list`, `s6_service_prepare`, `watcher_create` | Cluster contexts, pods/services/deployments, events |

## Priority 2: Documents, Notes, Knowledge, and Files

| Connector | Native tools to integrate | Adapter work |
| --- | --- | --- |
| Notion | `notion_operation_prepare`, `api_operation_inspect`, `memory_wiki_entry_prepare`, `memory_wiki_search`, `writing_draft_create` | Pages/databases/blocks/comments, templates, read/write sync, collector source events for page/database/task/comment/link/workspace metadata |
| Airtable | `airtable_operation_prepare`, `api_operation_inspect`, `csv_dataset_profile`, `business_report_create` | Bases/tables/records/schema, attachments |
| Dropbox | `read_file`, `write_file`, `search_files`, `summarize_pdfs`, `media_store_import` | Files/list/search/download/upload/share links plus cloud-file collector mappings for create/rename/move/delete/share/permission/sync/conflict/restore/version metadata |
| Box | `read_file`, `write_file`, `summarize_pdfs`, `media_store_import` | Files/folders/comments/tasks plus Box Events collector mappings for create/rename/move/delete/share/permission/restore/version metadata |
| OneDrive/SharePoint | Microsoft 365 connector plus `read_file`, `write_file`, `docx_document_create`, `xlsx_workbook_create`, `pptx_deck_create` | Graph files/sites/lists, permissions, comments, drive delta/change-notification collector mappings |
| Google Drive | Google Workspace connector plus `read_file`, `write_file`, `summarize_pdfs`, `media_store_import` | Search/download/upload/export, permissions, Drive changes/watch collector mappings |
| Confluence | `writing_draft_create`, `literature_set_create`, `memory_wiki_entry_prepare`, `business_report_create` | Spaces/pages/comments/attachments plus collector source events for page/database/comment/link/workspace metadata |
| Coda | `notion_operation_prepare` style, `xlsx_workbook_create`, `business_report_create` | Docs/tables/rows/buttons plus collector source events for page/table/task/comment/link/workspace metadata |
| Obsidian vault | `read_file`, `write_file`, `search_workspace`, `memory_wiki_entry_prepare` | Local vault roots, markdown backlinks, tags plus local plugin/bridge collector source events for note/task/link/backlink/vault metadata |
| Evernote | `memory_wiki_entry_prepare`, `memory_wiki_search`, `writing_draft_create` | Notes/notebooks/tasks plus collector source events for note/task/comment/link/workspace metadata |
| Apple Notes | `apple_notes_search`, `apple_notes_create`, `memory_wiki_entry_prepare` | Local Notes automation plus local bridge collector source events for note/checklist/link/workspace metadata |
| OneNote | Microsoft 365 connector plus `memory_wiki_entry_prepare`, `memory_wiki_search`, `writing_draft_create` | Graph notebooks/sections/pages plus collector source events for page/section/comment/link/workspace metadata |
| SiYuan | `siyuan_note_prepare`, `memory_wiki_entry_prepare` | Blocks/notebooks/assets |
| Canvas LMS | `canvas_course_packet_prepare`, `writing_draft_create`, `daily_plan_create` | Courses/assignments/pages/submissions |

## Priority 2: Mail, Calendar, Contacts, and CRM

| Connector | Native tools to integrate | Adapter work |
| --- | --- | --- |
| Gmail | Google Workspace plus `gmail_draft_prepare`, `email_draft_prepare`, `meeting_followup_packet_create` | Search/read labels/threads, draft/send, attachments |
| Outlook Mail | Microsoft 365 plus `email_draft_prepare`, `meeting_followup_packet_create` | Search/read folders/threads, draft/send, attachments |
| IMAP/SMTP | `email_draft_prepare`, `himalaya_email_operation_prepare`, `agentmail_operation_prepare` | Mailbox search/read, SMTP send, folder moves |
| Google Calendar | Google Workspace plus `daily_plan_create`, `meeting_followup_packet_create` | Events/free-busy/create/update/invite |
| Outlook Calendar | Microsoft 365 plus `daily_plan_create`, `meeting_followup_packet_create` | Events/free-busy/create/update/invite |
| Apple Calendar/Contacts | Apple connector plus `daily_plan_create`, `contact_note_create` | Event/contact local app adapters |
| HubSpot | `contact_note_create`, `business_report_create`, `email_draft_prepare` | Contacts/companies/deals/tickets/timeline plus collector source events for CRM records, tickets, dashboards, and report exports |
| Salesforce | `business_report_create`, `contact_note_create`, `chart_artifact_create` | Leads/accounts/opportunities/cases/reports plus collector source events for CRM record updates/views, dashboards, and report exports |
| Pipedrive | `business_report_create`, `contact_note_create` | Deals/contacts/activities |
| Zendesk | `channel_message_prepare`, `business_report_create`, `contact_note_create` | Tickets/users/comments/macros plus collector source events for ticket opened/assigned/updated/replied/resolved/escalated/SLA metadata |
| Intercom | `channel_message_prepare`, `business_report_create`, `contact_note_create` | Conversations/contacts/tickets plus collector source events for conversation and ticket lifecycle metadata |
| Freshdesk | `channel_message_prepare`, `business_report_create`, `contact_note_create` | Tickets/users/replies/SLA plus collector source events for ticket lifecycle metadata |

## Priority 2: Data, Analytics, and Warehouse Connectors

| Connector | Native tools to integrate | Adapter work |
| --- | --- | --- |
| Postgres/Supabase | `csv_dataset_profile`, `chart_artifact_create`, `business_report_create`, `python_interpreter` | Read-only query, schema inspect, approved write packets |
| MySQL/MariaDB | `csv_dataset_profile`, `chart_artifact_create`, `business_report_create` | Query/schema connector |
| SQLite local | `csv_dataset_profile`, `python_interpreter`, `read_file` | Local DB inspect/query helpers |
| BigQuery | `csv_dataset_profile`, `chart_artifact_create`, `business_report_create` | Datasets/tables/query jobs |
| Snowflake | `csv_dataset_profile`, `chart_artifact_create`, `business_report_create` | Warehouses/databases/query jobs |
| Redshift | `csv_dataset_profile`, `chart_artifact_create`, `business_report_create` | Clusters/schemas/query |
| Databricks | `jupyter_live_kernel_execute_prepare`, `model_training_plan_create`, `csv_dataset_profile` | SQL warehouses/jobs/notebooks |
| Airtable data | `airtable_operation_prepare`, `csv_dataset_profile`, `chart_artifact_create` | Already listed, but important for lightweight ops data |
| Google Analytics | `business_report_create`, `chart_artifact_create` | Properties/reports/realtime |
| Mixpanel | `business_report_create`, `chart_artifact_create` | Events/cohorts/funnels |
| Amplitude | `business_report_create`, `chart_artifact_create` | Charts/cohorts/events |
| Segment | `business_report_create`, `dependency_inventory_create` | Sources/destinations/schema |
| Looker | `business_report_create`, `chart_artifact_create` | Looks/dashboards/explores |
| Tableau | `business_report_create`, `chart_artifact_create` | Workbooks/views/datasources |
| Power BI | Microsoft 365 plus `business_report_create`, `chart_artifact_create` | Datasets/reports/dashboards |
| Metabase | `business_report_create`, `chart_artifact_create` | Questions/dashboards/query cards |

## Priority 2: Commerce, Finance, and Business Ops

| Connector | Native tools to integrate | Adapter work |
| --- | --- | --- |
| Shopify | `shopify_operation_prepare`, `shop_app_order_prepare`, `purchase_intent_prepare`, `shopping_comparison_create` | Products/orders/customers/inventory/fulfillment plus collector source events for order/customer/refund/fulfillment/report metadata |
| Stripe | `finance_model_create`, `business_report_create`, `purchase_intent_prepare` | Customers/payments/subscriptions/invoices/balances plus collector source events for payment/invoice/customer/subscription/refund/report metadata |
| PayPal | `purchase_intent_prepare`, `finance_model_create` | Orders/payments/payouts |
| Square | `purchase_intent_prepare`, `finance_model_create` | Payments/orders/customers/catalog |
| QuickBooks | `finance_model_create`, `business_report_create`, `xlsx_workbook_create` | Invoices/customers/accounts/reports plus collector source events for invoice/payment/customer/report metadata |
| Xero | `finance_model_create`, `business_report_create` | Invoices/contacts/accounts/reports plus collector source events for invoice/payment/customer/report metadata |
| Plaid | `finance_model_create`, `business_report_create` | Accounts/transactions/balances |
| Wise | `finance_model_create`, `business_report_create` | Balances/transfers/recipients |
| Mercury/Brex/Ramp | `finance_model_create`, `business_report_create` | Accounts/cards/transactions/receipts |
| Mailchimp | `writing_draft_create`, `business_report_create`, `email_draft_prepare` | Campaigns/audiences/reports |

## Priority 2: Research, Web, and Knowledge Providers

| Connector | Native tools to integrate | Adapter work |
| --- | --- | --- |
| Brave Search | `web_provider_request_prepare`, `research_web_pages`, `web_search` | Search API adapter, citation canonicalization |
| Exa | `web_provider_request_prepare`, `research_web_pages` | Search/crawl/content adapter |
| Tavily | `web_provider_request_prepare`, `research_web_pages` | Search/extract adapter |
| Firecrawl | `web_provider_request_prepare`, `scrapling_scrape_prepare`, `web_readability_extract` | Crawl/scrape/extract jobs |
| SearXNG | `searxng_search_prepare`, `web_provider_request_prepare` | Endpoint config/search |
| DuckDuckGo | `duckduckgo_search_prepare`, `web_search` | Prepared search plus live browser fallback |
| RSS feeds | `rss_feed_read`, `rss_watch_prepare`, `rss_watch_list` | Feed subscriptions and watch ticks |
| X/Twitter | `x_search`, `x_social_post_prepare`, `channel_message_prepare` | Search/timeline/post/thread adapter |
| Polymarket | `polymarket_query_prepare`, `business_report_create` | Market lookup and evidence |
| Crossref | `citation_bibliography_create`, `literature_set_create` | DOI metadata lookup |
| arXiv | `literature_set_create`, `parallel_research_plan_create` | Paper search/download metadata |
| Semantic Scholar | `literature_set_create`, `citation_bibliography_create` | Paper graph and citations |
| PubMed | `literature_set_create`, `bioinformatics_pipeline_prepare` | Biomedical literature lookup |
| ORCID | `citation_bibliography_create` | Author identity and works |
| WHOIS/DNS/cert providers | `domain_intel_report_create`, `dns_lookup`, `http_endpoint_check` | Domain ownership and certificate evidence |

## Priority 2: Media, Creative, and Publishing

| Connector | Native tools to integrate | Adapter work |
| --- | --- | --- |
| Spotify | `spotify_search`, `spotify_playlists`, `spotify_albums`, `spotify_library`, `spotify_devices`, `spotify_playback`, `spotify_queue` | Full OAuth token adapter, playback control, playlist/library writes |
| YouTube | `transcript_summary_create`, `video_analyze`, `media_remote_fetch_plan`, `writing_draft_create` | Search/video metadata/transcripts/upload comments |
| TikTok | `video_analyze`, `writing_draft_create`, `x_social_post_prepare` equivalent | Profile/video/post scheduling if available |
| Instagram | `media_reference_create`, `writing_draft_create`, `outbound_attachment_prepare` | Media library, post/comment/DM boundary |
| LinkedIn | `writing_draft_create`, `business_report_create`, `x_social_post_prepare` | Posts/company pages/comments |
| Canva | `media_storyboard_create`, `infographic_plan_create`, `pptx_deck_create` | Design export/import, template creation |
| Figma | `design_brief_create`, `diagram_artifact_create`, `media_reference_create` | File nodes/comments/export images |
| Adobe Creative Cloud | `media_store_import`, `media_reference_create`, `image_generate` | Asset libraries, files, exports |
| Blender MCP | `blender_mcp_command_prepare`, `media_storyboard_create` | MCP session bridge and asset export |
| ComfyUI | `comfyui_workflow_prepare`, `image_generate`, `video_generate` | Workflow queue/results |
| HyperFrames | `hyperframes_composition_prepare`, `video_generate` | Composition render/status/export |
| TouchDesigner | `touchdesigner_network_prepare`, `media_storyboard_create` | Network operation packets |
| OpenHue/Philips Hue | `openhue_scene_prepare`, `ha_call_service` | Bridge pairing, lights/scenes |
| Home Assistant | `ha_list_entities`, `ha_get_state`, `ha_call_service`, `ha_list_services` | Long-lived token, entity/service adapters |

## Priority 2: AI, MLOps, and Compute

| Connector | Native tools to integrate | Adapter work |
| --- | --- | --- |
| Hugging Face | `hugging_face_operation_prepare`, `model_inference_plan_create`, `model_training_plan_create` | Hub model/dataset/spaces/jobs API |
| Weights and Biases | `wandb_run_prepare`, `model_training_plan_create`, `business_report_create` | Runs/sweeps/artifacts/reports |
| Modal | `modal_job_prepare`, `model_training_plan_create` | Jobs/secrets/logs/artifacts |
| Lambda Labs | `lambda_labs_instance_prepare` | Instance lifecycle and SSH handoff |
| Pinecone | `pinecone_index_prepare`, `model_inference_plan_create` | Index create/query/upsert |
| Qdrant | `qdrant_collection_prepare`, `model_inference_plan_create` | Collections/query/upsert |
| Chroma | `chroma_collection_prepare`, `model_inference_plan_create` | Local/remote collections |
| FAISS local | `faiss_index_prepare`, `read_file`, `python_interpreter` | Local index build/query |
| Jupyter | `jupyter_live_kernel_execute_prepare`, `python_interpreter` | Kernel/session bridge |
| OpenAI compatible providers | `native_provider_registry`, `native_provider_request_prepare`, `provider_registry`, `llm_task_json` | Model provider credentials, base URLs, request packets |
| Ollama/LM Studio/local LLMs | `native_provider_registry`, `native_provider_request_prepare`, `model_inference_plan_create` | Local endpoint discovery/status |
| AI assistant activity sources | `/collectors/ai-assistants`, `collector_status`, `activity_ingest` | ChatGPT, Claude, Gemini, Copilot, Cursor, Cody, and local LLM chat/prompt/response/file-context/code-suggestion/error metadata |
| Whisper/STT providers | `whisper_transcription_prepare`, `voice_transcribe` | Local/API transcription adapters |

## Priority 2: Security, Secrets, and Identity

| Connector | Native tools to integrate | Adapter work |
| --- | --- | --- |
| 1Password | `onepassword_item_request_prepare`, `credential_file_policy`, `secret_scan_report_create` | CLI/API item lookup without exposing raw secrets |
| Bitwarden | `onepassword_item_request_prepare` equivalent, `credential_file_policy` | Vault unlock/session, item request packets |
| HashiCorp Vault | `credential_file_policy`, `native_provider_config_prepare` | Secret read/write policy, token renewal |
| Doppler | `credential_file_policy`, `optional_dependency_installer` | Project/config secret sync |
| AWS Secrets Manager | `credential_file_policy`, cloud connectors | Secret get/list with policy |
| GCP Secret Manager | `credential_file_policy`, Google connector | Secret get/list with policy |
| Azure Key Vault | `credential_file_policy`, Microsoft connector | Secret/cert/key get/list |
| Okta/Auth0 | `approval_policy_review_create`, `security_review_inspect` | Users/apps/logs/groups, SSO context |
| Cloudflare Zero Trust | `security_review_inspect`, `domain_intel_report_create` | Access apps/logs/tunnels |

## Priority 2: Cloud, Infra, and Network

| Connector | Native tools to integrate | Adapter work |
| --- | --- | --- |
| AWS | `http_endpoint_check`, `dns_lookup`, `docker_compose_prepare`, `business_report_create` | Account/region/STSes, EC2/S3/Lambda/CloudWatch/IAM read packets |
| Google Cloud | `http_endpoint_check`, `business_report_create`, Google connector | Projects/IAM/Cloud Run/GCS/Logging |
| Azure | `http_endpoint_check`, `business_report_create`, Microsoft connector | Subscriptions/resource groups/functions/storage/logs |
| Cloudflare | `dns_lookup`, `domain_intel_report_create`, `http_endpoint_check` | DNS/zones/pages/workers/tunnels |
| DigitalOcean | `http_endpoint_check`, `business_report_create` | Droplets/apps/databases |
| Fly.io | `http_endpoint_check`, `watcher_create` | Apps/machines/logs |
| Railway/Render | `http_endpoint_check`, `watcher_create` | Services/deploys/logs |
| Pinggy/ngrok/tunnel providers | `pinggy_tunnel_prepare`, `http_endpoint_check` | Tunnel lifecycle/status |

## Priority 3: Local App and Browser Connectors

These are connectors because they bind a local app/session to the agent, even without OAuth.

| Connector | Native tools to integrate | Adapter work |
| --- | --- | --- |
| Chrome profile | `browser_live_open`, `browser_live_observe`, `browser_live_click`, `browser_live_type`, `browser_live_download`, `browser_live_screenshot` | Profile/session selection, extension bridge, cookie-safe boundaries |
| Safari/Edge | Browser tools | Browser automation backend adapters |
| macOS desktop apps | `macos_app_workflow_prepare`, `apple_*`, `imessage_*`, `screenshot_capture` | Accessibility permissions, app-specific commands |
| Windows UI Automation | `os_windows`, `os_ui_observe`, `os_ui_action`, `os_window_state` | App selection, UIA element maps, approval boundaries |
| Local file systems | `list_files`, `read_file`, `write_file`, `search_workspace`, `file_index` | Root picker, per-root permissions, sync exclusion |
| Screen/audio/activity collectors | `activity_ingest`, `activity_search`, `collector_status`, `screenpipe_search` | Collector profile UI, privacy filters, retention |
| MCP servers | `mcp_server_catalog`, `mcp_server_manifest`, `mcp_server_launch`, `plugin_catalog` | Server install/config/state/status |

## Integration Order

1. Finish the shared connector execution contract: token lookup, refresh-on-401, API request wrapper, pagination, rate-limit backoff, audit events.
2. Promote the 5 current providers from OAuth-only to read/write adapters: Google Workspace, Microsoft 365, Slack, Linear, GitHub.
3. Connect communication channels to OAuth where available: Slack, Teams, Google Chat, Discord, Telegram, WhatsApp, SMS.
4. Add planning/task connectors: Jira, Asana, Trello, ClickUp, Monday, GitLab, Azure DevOps.
5. Add document/file/knowledge connectors: Notion, Airtable, Dropbox, Box, Confluence, Nextcloud, Canvas.
6. Add data/analytics connectors: Supabase/Postgres, BigQuery, Snowflake, Databricks, GA, Mixpanel, Amplitude, Looker/Power BI/Tableau.
7. Add business/media/MLOps connectors where matching native tools already exist: Shopify, Stripe, Spotify, YouTube, Canva, Figma, Hugging Face, W&B, Modal, Pinecone, Qdrant.
8. Add secrets/cloud/local app connectors last, because they need stricter permission and audit UX.

## Acceptance Checklist For Each Connector

- It appears in `workspace_connector_catalog` or the channel/plugin catalog with redacted status.
- It has a desktop setup surface on macOS and Windows.
- It declares required scopes and maps scopes to native tool capabilities.
- It supports connect, refresh/status, and disconnect.
- Read operations are bounded and summarized.
- Write/send/destructive operations require approval.
- Webhooks or polling are normalized into channel/activity events.
- Token and cache storage are local, redacted in logs, and removable.
- Tests cover catalog presence, missing credential behavior, redaction, and at least one prepared operation.
