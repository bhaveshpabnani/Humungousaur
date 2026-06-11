# App Collector Architecture

Humungousaur should treat OS collectors as layer 1, not the whole perception
system. A useful personal activity graph needs OS events, browser events, app
events, SaaS events, and knowledge-work semantics flowing into one durable local
event stream.

The important rule is: app integrations are source emitters, not a separate
pipeline. A Google Sheets collector, Slack collector, VS Code extension, or
GitHub webhook adapter should emit the same `CollectorEventEnvelope` used by the
native OS helpers. The durable SQLite WAL bus, offsets, retry/dead-letter
handling, attention batching, semantic consumers, memory consumers, and UI stream
consumers remain owned by the Python runtime.

Direct source emitters must pass the shared source-ingestion gate before writing
to the event log. The gate preserves first-run local ingest, then honors the
saved collector profile once it exists: disabled collectors are rejected,
duplicates are suppressed, per-minute budgets are enforced, and local activity
policy exclusions block matching events.

## Layer Model

```text
OS/device helper
browser extension
desktop app helper
SaaS API poller/webhook
IDE/editor plugin
        |
        v
source-specific app collector
        |
        v
CollectorEventEnvelope
        |
        v
SQLite WAL event log
        |
        +--> attention batch consumer
        +--> semantic event consumer
        +--> UI stream consumer
        +--> memory consumer
        +--> autonomous trigger consumer
```

Humungousaur should keep four conceptual layers:

1. Device and OS collectors: active app, windows, files, notifications, devices,
   focus state, browser foreground metadata, and local system context.
2. Application collectors: app-specific workflow events from desktop apps,
   browser apps, IDEs, collaboration tools, and productivity suites.
3. Knowledge collectors: work-product events such as documents, sheets, issues,
   PRs, meetings, notes, tasks, designs, CRM records, incidents, and dashboards.
4. AI understanding layer: compact event windows into "what the human is doing"
   without sending raw private content by default.

## Collector Definitions vs Source Integrations

Collector definitions describe the normalized activity contract. Source
integrations describe where the event came from.

Example: Google Sheets should usually not introduce a separate top-level
`google_sheets_activity` collector. It should emit existing spreadsheet workflow
collectors such as:

- `spreadsheet_editing_activity` for `sheet_created`, `row_inserted`,
  `cell_range_edited`, and related editing events.
- `spreadsheet_formula_activity` for `formula_entered`, `calculation_failed`,
  and formula-error events.
- `spreadsheet_data_analysis_activity` for `filter_applied`, `chart_created`,
  and pivot-table events.
- `spreadsheet_import_export_activity` for `sheet_shared`,
  `permissions_changed`, imports, exports, and data refreshes.

The envelope source should identify the implementation:

```json
{
  "collector": "spreadsheet_editing_activity",
  "source": "google_sheets",
  "stimulus_type": "sheet_created",
  "text": "Spreadsheet sheet was created",
  "privacy_tier": "sensitive_metadata",
  "metadata": {
    "provider": "google_workspace",
    "app": "google_sheets",
    "object_type": "spreadsheet",
    "object_id_hash": "sha256:...",
    "title_redacted": true,
    "sheet_name_redacted": true
  },
  "payload": {}
}
```

If an app produces a real event that has no matching `stimulus_type`, add the
missing stimulus to the closest existing collector definition and test it. Add a
new collector definition only when the activity family is genuinely new.

## Source Integration Types

- Native desktop helper: AppKit/Accessibility/iWork helpers on macOS, UI
  Automation/COM/Add-ins on Windows, DBus/AT-SPI/desktop portals on Linux.
- Browser extension: Chrome, Edge, Brave, Firefox, and Safari WebExtensions for
  tabs, URLs, downloads, web-app operations, form submits, and browser-app
  context.
- SaaS API poller: periodic metadata fetch using provider APIs where webhooks are
  unavailable or too coarse.
- SaaS webhook receiver: provider event callbacks normalized into local events.
  On desktop, this can be routed through the local API daemon or a paired cloud
  relay that only forwards metadata.
- IDE/editor plugin: VS Code, JetBrains, Xcode, and terminal integrations for
  editor and build/test/debug events.
- Local hook: Git hooks, shell integrations, file watcher helpers, and local app
  plugin hooks.

## Privacy Contract

Default behavior must be metadata-first.

- Do not emit raw document text, cell values, formulas, email bodies, chat
  messages, screenshots, transcripts, clipboard values, SQL results, customer
  data, credentials, or file contents unless the user explicitly enables
  `rich_capture`.
- Prefer IDs, hashes, buckets, booleans, MIME types, coarse action labels,
  redacted titles, app names, provider names, and explicit `*_redacted` /
  `*_omitted` flags.
- Use `metadata` for safe local facts, `sensitive_metadata` for facts that can
  reveal private work context, and `rich_capture` only for explicit opt-in.
- Every app collector should emit helper health or source health when
  authentication, permissions, rate limits, webhook delivery, or local extension
  connectivity degrades.
- Attention batches should receive compact activity summaries, not raw app
  payloads.

## App Collector Catalog

This is the build map for app and SaaS collectors. Each source should map into
the existing collector definitions wherever possible.

| Domain | Sources | Event families to emit |
| --- | --- | --- |
| Browsers | Chrome, Edge, Brave, Firefox, Safari | tab/window/profile changes, URL changes with redaction, downloads, uploads, form submits, page errors, extension actions, installed web apps, reader/find/zoom/mute/PiP/translation modes |
| Google Workspace | Drive, Docs, Sheets, Slides, Gmail, Calendar, Meet, Keep, Tasks | file created/modified/shared, document editing/review/export, spreadsheet editing/formulas/analysis/share, presentation authoring/delivery/export, mail composition/labels, calendar invites/reminders, meetings |
| Microsoft 365 | OneDrive, SharePoint, Word, Excel, PowerPoint, Outlook, Teams, OneNote, To Do, Loop | drive changes, Office document/sheet/deck workflows, email/calendar, chat/thread/channel/presence, meetings, notes, tasks |
| Apple apps | Finder, Mail, Calendar, Notes, Reminders, Messages, Pages, Numbers, Keynote, Preview, Photos | file/navigation/share, mail/calendar workflow, notes/tasks, document/spreadsheet/presentation workflow, PDF review, photo import/export metadata |
| Developer tools | VS Code, JetBrains IDEs, Xcode, Terminal, Git, GitHub, GitLab, Bitbucket | active files, saves, diagnostics, tests, debug sessions, build tasks, package manager events, local services, commits, branches, PRs, reviews, CI, issues |
| Planning and work tracking | Linear, Jira, Asana, Trello, ClickUp, Monday, Todoist | task/issue created, assigned, moved, commented, completed, priority changed, due date changed, sprint/project navigation |
| Communication | Slack, Microsoft Teams, Discord, Gmail, Outlook, Telegram, WhatsApp, Signal | message sent/edited/deleted, draft started, thread opened/replied/resolved, channel/workspace navigation, presence/DND, attachments, labels |
| Meetings | Zoom, Google Meet, Teams, Webex, Discord calls | meeting joined/left, waiting room, mic/camera/caption controls, screen share, recording state, transcript/summary/action-item availability |
| Knowledge bases | Notion, Confluence, Coda, Obsidian, Evernote, Apple Notes, OneNote | page/note created/updated, database/table changed, task completed, comment added, link/backlink created, vault/workspace opened |
| Design and whiteboards | Figma, FigJam, Miro, Canva, Adobe XD, Sketch | file/design created, frame/board/component added, prototype presented, comment added, export generated, template used |
| Cloud files | Dropbox, Box, iCloud Drive, Google Drive, OneDrive, SharePoint | file/folder created, renamed, moved, deleted, shared, permission changed, sync error, conflict, restore/version event |
| Business operations | Salesforce, HubSpot, Zendesk, Intercom, Freshdesk, Stripe, Shopify, QuickBooks, Xero | CRM record viewed/updated, support ticket opened/replied/resolved, dashboard viewed, invoice/payment/customer/order events, export/report events |
| Data and analytics | BigQuery, Snowflake, Databricks, Tableau, Looker, Metabase, Power BI, Supabase, Neon, MongoDB Atlas | query run/failed, dashboard opened/exported, chart updated, dataset refreshed, connection failed, notebook/job run state |
| Cloud and incidents | AWS, Azure, GCP, Docker Desktop, Kubernetes tools, Datadog, Sentry, PagerDuty, Opsgenie | console/resource viewed, deploy started/failed, container/VM state, alert triggered/acknowledged/resolved, incident created/escalated |
| AI assistants | ChatGPT, Claude, Gemini, Copilot, Cursor, Cody, local LLM tools | chat opened, prompt submitted metadata, response received metadata, file context attached redacted, code suggestion accepted/rejected, model/tool error |

## Priority Build Order

Build source integrations in this order because they cover the largest share of
knowledge-worker activity while exercising the architecture across browsers,
desktop apps, SaaS APIs, webhooks, and plugins.

1. Browser extension baseline: Chrome first, then Edge/Brave/Firefox/Safari.
2. Google Drive, Docs, Sheets, Slides, Gmail, and Calendar.
3. Microsoft Graph: OneDrive, SharePoint, Word, Excel, PowerPoint, Outlook, and
   Teams.
4. VS Code and JetBrains IDEs, plus local Git hooks.
5. GitHub, GitLab, Bitbucket, Linear, and Jira.
6. Slack, Teams chat, Discord, Zoom, and Google Meet.
7. Notion, Confluence, Obsidian, Figma, FigJam, Miro, and Canva.
8. Dropbox, Box, iCloud Drive, and cloud sync health.
9. Salesforce, HubSpot, Zendesk, Intercom, Stripe, Shopify, QuickBooks, and Xero.
10. Data/cloud/incident tools: BigQuery, Snowflake, Databricks, Tableau, Looker,
    AWS, Azure, GCP, Datadog, Sentry, PagerDuty, and Docker/Kubernetes tools.

## Implementation Checklist

Every app collector should ship with:

- A source manifest naming provider, app, auth method, scopes/permissions, event
  coverage, rate limits, and webhook/polling behavior.
- A mapping table from provider-native events into Humungousaur collector names
  and stimulus types.
- Envelope emission using the shared schema.
- Stable dedupe signatures that do not include raw private text.
- Redaction tests for titles, paths, URLs, participants, message bodies, cell
  values, formulas, document bodies, SQL, logs, and customer records.
- Source health events for auth failures, permission failures, rate limits,
  webhook disconnects, local extension disconnects, and stale cursors.
- Source-ingestion gate coverage for collector enablement, duplicate signatures,
  rate limits, and local activity-policy exclusions.
- Offset/cursor persistence so API pollers can resume after restart.
- Retry/backoff behavior for provider failures.
- Dead-letter handling for malformed events.
- Focused tests proving source events enter the durable event log and reach the
  intended consumer without bypassing privacy gates.

## Developer Tools Implementation

The developer source integration lives under
`humungousaur/collectors/sources/developer/`, with separate modules for IDEs,
terminal/shell integrations, local Git, and hosted Git providers.

Current source behavior:

- Accepts VS Code/Cursor, JetBrains, Xcode, Terminal/shell, local Git, GitHub,
  GitLab, Bitbucket, and Azure DevOps metadata through `/connectors/source-events`,
  `workspace_connector_source_event_ingest`, or local Python source helpers.
- Treats VS Code, JetBrains, Xcode, Terminal, and local Git as local
  extension/hook collectors that do not require OAuth connector readiness.
- Treats GitHub, GitLab, Bitbucket, and Azure DevOps as connector-backed
  webhook/API sources before pollers access provider APIs. Webhook receivers use
  provider-native event names and append metadata through the shared
  source-ingestion gate without reading connector tokens.
- Normalizes official provider webhook surfaces: GitHub `pull_request`,
  `pull_request_review`, `check_run`, `workflow_run`, `issues`,
  `issue_comment`, push/create/delete events; GitLab merge request, push, note,
  issue, pipeline, and job events; Bitbucket Cloud `X-Event-Key` events such as
  `repo:push`, `pullrequest:*`, `issue:*`, and commit-status events; and Azure
  DevOps service-hook event IDs for pull requests, pushes, builds/pipelines, and
  work items.
- Provides connector-runtime pollers for configured `poll_targets`: GitHub repo
  events and Actions runs, GitLab project events and pipelines, Bitbucket PRs
  and Pipelines, and Azure DevOps Repos PRs plus Build runs. Pollers persist
  seen-event IDs in `collector_consumer_state` and do not call provider APIs
  when connector readiness is missing.
- Maps active-file, save, diagnostic, test, debug, build, package-manager,
  local-service, commit, branch, PR/MR, review, CI, and issue events into
  existing collector definitions where possible.
- Adds `code_hosting_activity` for provider-neutral PR/MR, review, branch,
  commit-push, CI, and comment metadata so GitLab, Bitbucket, and Azure DevOps
  do not have to masquerade as `github_activity`.
- Keeps raw file paths, branch names, commit messages, URLs, diagnostics, test
  names, logs, stack frames, variable values, and issue/PR content redacted by
  default.
- Records source health through the same collector event log helper-health path
  used by other source collectors.

## Communication Implementation

The communication source integration lives under
`humungousaur/collectors/sources/communication/`, with one module per app:
Slack, Microsoft Teams, Discord, Google Chat, Gmail, Outlook, Telegram,
WhatsApp, and Signal.
It provides connector-backed webhook/poller ingress plus browser, app-extension,
or local bridge ingress without creating a parallel event pipeline.

Current source behavior:

- Accepts metadata-first events through `/collectors/communication`, the local
  Python API, or the generic `workspace_connector_source_event_ingest` tool.
- Maps chat apps into `channel_activity`, `chat_composition_activity`,
  `chat_thread_activity`, `chat_channel_navigation_activity`, and
  `chat_presence_activity`.
- Maps Gmail and Outlook into `mail_activity`, `mail_composition_activity`, and
  `mail_organization_activity`.
- Covers message sent/edited/deleted, draft started/updated, thread
  opened/replied/resolved, workspace or channel navigation, presence/DND,
  attachment metadata, and mail labels.
- Keeps message bodies, subjects, participants, channel/workspace names,
  attachment filenames, label names, URLs, and paths redacted or hashed before
  append by default.
- Uses Slack Events API or Socket Mode, Microsoft Graph change notifications,
  Discord Gateway events, Telegram Bot API updates, WhatsApp Cloud API webhooks,
  Gmail push/History API, Outlook Graph notifications/delta queries, and
  signal-cli JSON-RPC/local bridges as documented source lanes.
- Provides provider-native normalizers for Slack Events API, Teams Graph chat
  notifications, Discord Gateway dispatches, Google Chat Workspace/Chat events,
  Telegram Bot API updates, WhatsApp Cloud API webhook changes, and signal-cli
  receive envelopes. These normalizers call `ConnectorRuntime.readiness(...)`
  before connector-backed webhook ingest and never read token or vault files
  directly.
- Records source health and dead letters through the existing collector event
  log, so attention batching, semantic consumers, memory consumers, UI streams,
  and autonomous triggers consume the same durable event stream.

## Google Sheets Example

Recommended source shape:

```text
Google Workspace API / browser extension / Sheets add-on
        |
        v
google_sheets source adapter
        |
        v
spreadsheet_* CollectorEventEnvelope records
        |
        v
SQLite WAL event log
```

Example mappings:

| Google Sheets event | Humungousaur collector | Stimulus type |
| --- | --- | --- |
| Spreadsheet opened | `spreadsheet_activity` | `workbook_opened` |
| Sheet created | `spreadsheet_editing_activity` | `sheet_created` |
| Row inserted | `spreadsheet_editing_activity` | `row_inserted` |
| Range edited | `spreadsheet_editing_activity` | `cell_range_edited` |
| Formula entered | `spreadsheet_formula_activity` | `formula_entered` |
| Formula error observed | `spreadsheet_formula_activity` | `formula_error_detected` |
| Filter applied | `spreadsheet_data_analysis_activity` | `filter_applied` |
| Chart created | `spreadsheet_data_analysis_activity` | `chart_created` |
| CSV imported | `spreadsheet_import_export_activity` | `csv_imported` |
| Sheet shared | `spreadsheet_import_export_activity` | `sheet_shared` |
| Permissions changed | `spreadsheet_import_export_activity` | `permissions_changed` |

The source should not emit cell values or formulas by default. It can emit
metadata such as row/column counts, coarse range size, operation type,
spreadsheet ID hash, sheet ID hash, and whether title/formula/value fields were
redacted.

## Browser Source Implementation

The browser source integration lives under
`humungousaur/collectors/sources/browser/`, with one module per supported
browser and shared ingress/redaction in `events.py`.

The real browser emitter lives under
`browser_extensions/humungousaur_collector/`. It is a shared WebExtension source
package with browser-specific manifests:

- `manifest.chrome.json`, `manifest.edge.json`, and `manifest.brave.json` use
  Chromium MV3 background service workers plus `tabs`, `windows`,
  `webNavigation`, `downloads`, `tabGroups`, and content-script APIs.
- `manifest.firefox.json` uses the Firefox WebExtensions background-script
  shape with `tabs`, `webNavigation`, `downloads`, content scripts, commands,
  and local host permissions.
- `manifest.safari.json` provides the Safari Web Extension source bundle that
  can be wrapped by Xcode's Safari Web Extension tooling.
- `scripts/build.py` builds loadable extension directories for all five browser
  targets.

Current browser source behavior:

- Supports Chrome, Edge, Brave, Firefox, and Safari as first-class app collector
  records.
- Accepts metadata-first browser extension or native-messaging events through
  `/collectors/browsers`; the WebExtension emitter posts directly to this local
  endpoint and retries failed sends from extension storage.
- Reports source status through `/collectors/browsers/status` and helper health
  through `/collectors/browsers/health`.
- Maps tab lifecycle, URL navigation, window lifecycle, profile changes,
  downloads/uploads, form changes/submits, page and console errors, extension
  actions, installed web apps, tab groups, bookmark/history, autofill, network
  errors, and reader/find/zoom/mute/PiP/translation modes into existing
  collector definitions.
- Emits directly observable events from browser APIs: tab open/close/switch,
  URL changes, navigation errors, download lifecycle, window focus/open/close,
  tab groups where supported, extension action clicks, zoom and mute state, and
  profile-context activation.
- Emits page-surface events from the content script: form submit/change, file
  upload counts, link clicks, resource/script errors, selected-text length
  buckets, web-app install/open/offline-ready signals, and
  picture-in-picture events.
- Emits reader/find/translation and non-observable built-in browser mode changes
  through explicit extension command events when the browser does not expose a
  native event API for those actions.
- Redacts raw URLs, titles, paths, query strings, fragments, selected text, form
  values, console messages, profile/account names, extension names, file names,
  and page text before writing events to the collector event log.
- Stores only bounded metadata such as booleans, counts, coarse state, URL
  hashes, host hashes, tab/window/profile/extension ID hashes, and source
  channel identifiers.
- Does not use OAuth tokens. The source is a local permission/extension bridge;
  browser extensions or native messaging hosts emit events into the same durable
  `CollectorEventEnvelope` path as native helpers and SaaS pollers.

## Google Workspace Implementation

The Google Workspace source integration lives under
`humungousaur/collectors/sources/google/`, with one module per Google app and a
compatibility shim at `humungousaur/collectors/sources/google_workspace.py`.
It provides local ingress for connector-backed pollers, webhook relays, browser
extensions, or Workspace add-ons without creating a parallel event pipeline.

Current source behavior:

- Accepts metadata-first events through `/collectors/google-workspace` or the
  local Python API.
- Maps Drive, Docs, Sheets, Slides, Gmail, Calendar, Meet, Chat, Contacts, Keep,
  and Tasks into existing collector definitions.
- Keeps Drive, Gmail, and Calendar as direct connector-backed pollers.
- Keeps Docs, Sheets, and Slides as explicit app modules whose file-level events
  are derived from Drive changes, with add-on/webhook ingress for richer app
  actions.
- Keeps Tasks, Keep, and Contacts as scope-gated pollers: if the Google OAuth
  grant has the optional scope, they poll metadata; otherwise they remain ready
  for webhook/add-on/browser-extension events without making unauthorized API
  calls.
- Keeps Meet and Chat as explicit app modules for browser extension, add-on, or
  webhook events because Calendar/Chat metadata cannot safely infer local
  join/leave/mute/message-body behavior.
- Normalizes source events into `CollectorEventEnvelope` records and appends
  them directly to the SQLite WAL event log.
- Keeps downstream memory mirroring, attention batching, semantic consumers, UI
  streams, autonomous triggers, retry state, and offsets on the regular
  collector event-log path.
- Redacts raw titles, subjects, message bodies, cell values, formulas, document
  text, URLs, paths, participants, attendees, locations, and filenames before
  events enter the collector runtime.
- Writes rejected or malformed source events to
  `data_dir/collector_sources/google_workspace/dead_letters.jsonl`.
- Reports source status at `/collectors/google-workspace/status` and through
  `collector_status(...).capabilities.sources.google_workspace`.
- Records source health through `/collectors/google-workspace/health` using the
  existing collector helper-health table.

Google API calls go through `ConnectorRuntime.execute_operation(...)`, which
uses the configured connector profile, token vault, refresh path, and scope
policy. The collector package does not read OAuth secrets directly.

## Cloud Files Implementation

The cloud-file source integration lives under
`humungousaur/collectors/sources/cloud_files/`. It covers Dropbox, Box, and
iCloud Drive directly, while Google Drive cloud-file events are mapped through
the Google Workspace source and OneDrive/SharePoint events are mapped through the
Microsoft 365 source.

Current source behavior:

- Maps file/folder create, rename, move, delete, share, permission-change, sync
  failure, sync conflict, restore, and version events into `cloud_sync_activity`.
- Keeps Dropbox as a cursor poller using `files/list_folder/get_latest_cursor`
  and `files/list_folder/continue`; Dropbox webhooks should wake the local
  poller rather than carrying raw paths or filenames through the webhook body.
- Keeps Box as an Events API stream-position poller using `/2.0/events`;
  provider webhooks can trigger focused polling and direct metadata-first
  ingestion.
- Keeps iCloud Drive as local bridge ingress through macOS File Provider or
  CloudDocs metadata; the collector does not read Apple account secrets.
- Adds explicit Google Drive `drive_cloud_*` mappings and Microsoft
  OneDrive/SharePoint mappings for the same cloud-file event families.
- Redacts raw paths, filenames, names, URLs, shared links, emails, owners, and
  participant fields before events enter the collector runtime.
- Stores cursors in `CollectorEventLog` consumer state under
  `connector_sources.sources.<provider>`.
- Reports source health through the existing connector source health table and
  status through `/collectors/cloud-files/status` or `/connectors/sources`.

## Planning and Work Tracking Implementation

The planning source integration lives under
`humungousaur/collectors/sources/planning/`, with one small collector module per
provider: Linear, Jira, Asana, Trello, ClickUp, Monday.com, and Todoist.

Current source behavior:

- Accepts metadata-first events through `/collectors/planning` or the generic
  `/connectors/source-events` API.
- Maps provider-native issue/task/webhook events into existing
  `issue_tracker_activity` and `task_manager_activity` collectors.
- Covers task and issue creation, assignment, movement/status changes, comments,
  completion/reopen, priority changes, due-date changes, sprint changes, and
  project navigation/change events.
- Keeps provider-specific polling as future adapter work; current collectors are
  webhook, browser-extension, or local relay ingress with connector-readiness
  health.
- Redacts titles, summaries, names, descriptions, comments, URLs, assignees,
  reporters, participants, and labels by default, while hashing provider IDs and
  retaining safe buckets such as priority/status buckets.
- Emits source health through the shared connector source status surface and
  writes malformed provider events to provider-specific dead-letter files.

## Microsoft 365 Implementation

The Microsoft 365 source integration lives under
`humungousaur/collectors/sources/microsoft/`, with one module per Microsoft app
surface and a compatibility shim at
`humungousaur/collectors/sources/microsoft_365.py`. It uses Microsoft Graph
metadata APIs and connector readiness for pollers, while keeping richer
workflow events available through Graph change notifications, Office add-ins,
Teams app/browser ingress, or local browser extensions.

Current source behavior:

- Accepts metadata-first events through `workspace_connector_source_event_ingest`
  or the local Python API.
- Maps OneDrive, SharePoint, Word, Excel, PowerPoint, Outlook, Teams, OneNote,
  To Do, and Loop into existing collector definitions.
- Keeps OneDrive as a direct Graph `driveItem` delta poller and lets Office file
  MIME types derive Word, Excel, PowerPoint, and OneNote workflow events without
  exposing filenames or paths.
- Keeps SharePoint as a configured document-library delta poller when a site or
  drive cursor is configured; otherwise it remains ready for Graph change
  notifications.
- Keeps Outlook Mail and Outlook Calendar as direct Graph delta pollers for
  message and calendar metadata.
- Keeps Teams as a webhook/app-ingress collector with optional
  `Presence.Read` polling for coarse presence changes; chat/channel/thread and
  meeting events are not inferred from message bodies or transcripts.
- Keeps OneNote and To Do as scope-gated pollers: if the grant lacks
  `Notes.Read` or `Tasks.Read`, they accept add-in/webhook/browser events
  without making unauthorized API calls.
- Keeps Loop as browser/app ingress because Microsoft Graph does not currently
  expose a stable first-class Loop delta surface for these collector semantics.
- Normalizes source events into `CollectorEventEnvelope` records and appends
  them directly to the SQLite WAL event log.
- Redacts raw titles, subjects, message bodies, document text, cell values,
  formulas, file paths, URLs, participants, attendees, channel/team names,
  locations, and filenames before events enter the collector runtime.
- Writes rejected or malformed source events to
  `data_dir/collector_sources/microsoft_365/dead_letters.jsonl`.
- Reports source status through the Microsoft 365 source package and helper
  health through the existing collector helper-health table.

Microsoft Graph calls go through `ConnectorRuntime.execute_operation(...)`.
The collector package never reads access tokens, refresh tokens, client secrets,
auth codes, or vault files directly.

## Business Operations Source Implementation

Business operations source integrations live under
`humungousaur/collectors/sources/business_operations/` and reuse existing
collector families instead of introducing provider-specific collectors:

- `crm_activity` for Salesforce and HubSpot record views, record updates, lead
  creation, deal stage changes, customer notes, and follow-ups.
- `support_desk_activity` for Zendesk, Intercom, Freshdesk, and HubSpot ticket
  opened, assigned, updated, replied, resolved, escalated, and SLA metadata.
- `analytics_activity` for dashboard views and report exports from Salesforce,
  HubSpot, Stripe, Shopify, QuickBooks, and Xero.
- `finance_activity` for Stripe, QuickBooks, and Xero payment, invoice,
  customer, and refund metadata.
- `commerce_activity` for Shopify orders, customers, subscriptions, refunds,
  and fulfillment metadata, plus Stripe subscription metadata.

Current source behavior:

- Registers Salesforce, HubSpot, Zendesk, Intercom, Freshdesk, Stripe,
  Shopify, QuickBooks, and Xero as connector source manifests.
- Accepts metadata-first source events through the shared
  `workspace_connector_source_event_ingest` path or the local
  `append_business_operations_event(...)` Python ingress.
- Uses provider-prefixed source events such as `salesforce_record_updated`,
  `zendesk_ticket_resolved`, `stripe_invoice_created`, and
  `shopify_order_created` to avoid collisions across business apps.
- Treats provider webhooks or change streams as the source for record/ticket,
  invoice/payment/customer/order mutations.
- Treats CRM record viewed, support ticket opened by an agent UI, dashboard
  viewed, and report export UI events as browser-extension or app-bridge
  ingress unless a provider emits that event natively.
- Redacts customer names, emails, ticket subjects, message bodies, amounts,
  URLs, account names, report names, raw payload bodies, and provider object IDs
  before appending `CollectorEventEnvelope` records.
- Writes malformed business-operation source payloads to
  `data_dir/collector_sources/business_operations/dead_letters.jsonl`.
- Reports source health through the same connector helper-health table used by
  other app collectors.

## Design And Whiteboard Source Implementation

Design and whiteboard source integrations live under
`humungousaur/collectors/sources/design/` and reuse existing visual-work
collector families:

- `creative_activity` for Figma, Canva, Sketch, and Adobe XD file, comment,
  component, prototype, and export metadata.
- `whiteboard_activity` for FigJam and Miro board, item, sticky, collaborator,
  comment, share, and export metadata.

Current source behavior:

- Registers Figma, FigJam, Miro, Canva, Sketch, and Adobe XD as connector source
  manifests.
- Accepts metadata-first events through `/collectors/design`,
  `workspace_connector_source_event_ingest`, provider webhooks, design plugins,
  or local app bridges.
- Uses provider-prefixed source events such as `figma_design_file_updated`,
  `miro_board_edited`, and `canva_design_exported`.
- Redacts design file names, board names, comments, URLs, paths, participant
  names, actor names, and raw provider payloads before appending envelopes.
- Reports status at `/collectors/design/status` and source health at
  `/collectors/design/health`.

## Data And Analytics Source Implementation

Data and analytics source integrations live under
`humungousaur/collectors/sources/data_analytics/`:

- `database_activity` for BigQuery, Snowflake, Databricks, Postgres, Supabase,
  MySQL, and MongoDB Atlas connection, query, schema, and migration metadata.
- `analytics_activity` for Tableau, Looker, Metabase, Power BI, Google
  Analytics, Mixpanel, and Amplitude dashboard, filter, export, alert, query
  result, and chart drill-down metadata.

Current source behavior:

- Registers SaaS analytics/data providers plus local database clients as source
  manifests.
- Accepts metadata-first events through `/collectors/data-analytics`,
  `workspace_connector_source_event_ingest`, audit logs, webhooks, API pollers,
  or local SQL-client bridges.
- Keeps Postgres and MySQL local bridge sources independent of connector token
  readiness.
- Redacts SQL, query text, dashboard/report names, result values, paths, URLs,
  user names, emails, and raw data rows before appending envelopes.
- Reports status at `/collectors/data-analytics/status` and source health at
  `/collectors/data-analytics/health`.

## Operations And Incident Source Implementation

Operations source integrations live under
`humungousaur/collectors/sources/operations/`:

- `incident_activity` for PagerDuty, Opsgenie, Datadog, Grafana, and Sentry
  alerts, incidents, acknowledgements, escalations, resolutions, runbooks, and
  status-page metadata.
- `cloud_console_activity` for AWS, Azure, Google Cloud, Cloudflare, Vercel, and
  Netlify resource, deployment, secret, billing, and permission metadata.
- `virtual_runtime_activity` for Docker Hub and Kubernetes image/container
  lifecycle metadata.

Current source behavior:

- Registers observability, incident, cloud, deployment, and runtime providers as
  source manifests.
- Accepts metadata-first events through `/collectors/operations`,
  `workspace_connector_source_event_ingest`, provider webhooks, audit/event
  streams, CLI relays, or local cluster bridges.
- Keeps Kubernetes local watch/bridge sources independent of connector token
  readiness.
- Redacts incident titles, alert messages, logs, resource names, secret names,
  paths, URLs, emails, and raw event bodies before appending envelopes.
- Reports status at `/collectors/operations/status` and source health at
  `/collectors/operations/health`.

## Meeting Source Implementation

Meeting source integrations live under
`humungousaur/collectors/sources/meetings/` and reuse the existing normalized
meeting collectors instead of introducing provider-specific collector families:

- `meeting_app_activity` for join/leave, waiting room, participants, breakout
  rooms, and recording state.
- `call_control_activity` for microphone, camera, captions, hand, reaction, and
  chat-panel control metadata.
- `meeting_presentation_activity` for screen share, window share, presentation,
  presenter, and remote-control state.
- `meeting_artifact_activity` for recording, transcript, summary, action-item,
  notes, whiteboard, and follow-up availability.

Current source coverage:

- Zoom uses meeting webhooks plus desktop/browser bridge ingress for in-call
  controls.
- Google Meet uses Workspace/Meet conference records, Workspace Events,
  Calendar context, add-on or browser-extension ingress.
- Microsoft Teams uses Microsoft Graph online-meeting, transcript, recording,
  attendance, and change-notification surfaces plus app/native bridge ingress.
- Webex uses Meetings APIs, Events API, transcript/recording APIs, and
  desktop/browser bridge ingress.
- Discord calls use Gateway voice-state or Social SDK events for join, leave,
  mute, video, and stream state; transcript/summary/action-item availability is
  accepted only from an opt-in bot or local bridge.

Provider-native normalizers cover Zoom meeting webhooks, Google Meet Workspace
Events or Meet API events, Microsoft Graph Teams meeting notifications, Webex
webhooks, and Discord Gateway voice-state dispatches. They call
`ConnectorRuntime.readiness(...)` before connector-backed webhook ingest and
never read token or vault files directly.

All meeting sources append redacted `CollectorEventEnvelope` records through the
workspace connector source manifest. Meeting titles, participant names,
chat/caption/transcript bodies, URLs, artifact contents, and email addresses are
redacted by default. IDs are hashed and event payloads are compacted before they
enter the durable collector log.

## Generic Workspace Connector Sources

Connectors and collectors have separate jobs. A connector makes a provider
connection ready for use by tools and collectors: provider metadata, OAuth setup,
token storage, refresh, redacted status, scoped HTTP execution, and readiness
checks live under `humungousaur/connectors/`.

Collection is not a connector responsibility. Source event mappings,
metadata-first redaction, helper health, cursor ticks, and durable
`CollectorEventEnvelope` appends live under
`humungousaur/collectors/sources/workspace_connectors.py`. Collector source
adapters can consult `ConnectorRuntime.readiness(...)` before polling a provider,
but they own event normalization and event-log writes.

It currently maps Google Workspace, Microsoft 365, Zoom, Webex, Discord, Slack,
Linear, GitHub, and developer source events into existing collector definitions
and exposes:

- `workspace_connector_source_manifest` for provider-to-collector mappings.
- `workspace_connector_source_status` for source health and mapping status.
- `workspace_connector_source_tick` for metadata-only poller ticks and cursor
  state.
- `workspace_connector_source_event_ingest` for webhook/poller adapters that
  append redacted `CollectorEventEnvelope` records.
- `workspace_connector_source_health` for OAuth, permission, webhook, rate
  limit, and API health.

The local API mirrors this through `/connectors/sources`,
`/connectors/sources/manifest`, `/connectors/sources/tick`,
`/connectors/source-events`, and `/connectors/source-health`.

Future app connectors should add provider metadata in
`humungousaur/connectors/providers/` and, separately, source mappings under the
owning collector source package. Tools and collector adapters should use
`ConnectorRuntime` only as the connection-readiness boundary.

## AI Assistant Implementation

The AI assistant source integration lives under
`humungousaur/collectors/sources/ai_assistants/`, with explicit app collector
records for ChatGPT, Claude, Gemini, Copilot, Cursor, Cody, and local LLM tools.
It is a local bridge/app-plugin source rather than an OAuth connector: browser
extensions, desktop helpers, IDE extensions, CLI hooks, or local LLM wrappers
emit metadata-only events into the regular collector log.

Current source behavior:

- Accepts metadata-first events through `/collectors/ai-assistants` or the local
  Python API.
- Maps source events into the existing `ai_assistant_activity` collector:
  `chat_opened`, `prompt_submitted_metadata`, `response_received_metadata`,
  `file_context_attached_redacted`, `code_suggestion_accepted`,
  `code_suggestion_rejected`, `model_error`, and `tool_error`.
- Keeps compatibility bridge stimuli for `ai_tool_call_started`,
  `ai_tool_call_failed`, `ai_suggestion_accepted`, and conversation exports.
- Redacts prompt bodies, response bodies, code context, file paths, URLs, titles,
  tool payloads, and model/tool names before appending events.
- Stores only hashes, counts, buckets, booleans, source channel, assistant name,
  and coarse error metadata by default.
- Reports source health at `/collectors/ai-assistants/health` and status at
  `/collectors/ai-assistants/status` plus
  `collector_status(...).capabilities.sources.ai_assistants`.

## Knowledge Base Implementation

The knowledge-base source integration lives under
`humungousaur/collectors/sources/knowledge_base/`, with app collector records for
Notion, Confluence, Coda, Obsidian, Evernote, Apple Notes, and OneNote.

Current source behavior:

- Accepts metadata-first events through `/collectors/knowledge-bases`,
  `workspace_connector_source_event_ingest`, local app bridges, browser
  extensions, webhooks, or source-specific Python helpers.
- Maps Notion, Confluence, Coda, Obsidian, Evernote, Apple Notes, and OneNote
  provider events into existing `knowledge_base_activity`, `notes_activity`, and
  `task_manager_activity` collectors.
- Covers page/note create/update, database/table changes, task completion,
  comments, links/backlinks, vault opens, and workspace opens.
- Treats Obsidian and Apple Notes as local bridge/plugin sources that do not
  require OAuth connector readiness.
- Treats Notion, Confluence, Coda, Evernote, and OneNote as connector-backed
  webhook/API/browser-extension sources before any poller accesses provider
  APIs.
- Redacts page titles, note titles, bodies, comments, URLs, paths, workspace
  names, vault names, authors, participants, and raw provider payloads before
  appending events.
- Stores only hashes, counts, coarse object types, source channel, app/provider
  names, booleans, and redaction flags by default.
- Reports source health at `/collectors/knowledge-bases/health` and status at
  `/collectors/knowledge-bases/status` plus
  `collector_status(...).capabilities.sources.knowledge_bases`.

## Prompt Template For One App Collector

Use this when asking Claude Code or another coding agent to implement a specific
source collector.

```text
Implement the <APP_OR_PROVIDER> app collector for Humungousaur.

Repository context:
- Collector architecture: docs/COLLECTOR_ARCHITECTURE.md
- App collector architecture: docs/APP_COLLECTOR_ARCHITECTURE.md
- Shared envelope: humungousaur/collectors/envelope.py and collectors/shared/event-envelope.schema.json
- Definitions: humungousaur/collectors/definitions.py
- Runtime event log: humungousaur/collectors/event_log.py
- Adapters live under humungousaur/collectors/adapters/

Requirements:
1. Treat <APP_OR_PROVIDER> as a source integration, not a separate event pipeline.
2. Map provider-native events into existing CollectorDefinition names and stimulus types.
3. If a necessary stimulus type is missing, add it to the closest existing collector definition with tests.
4. Emit CollectorEventEnvelope records with source="<SOURCE_NAME>".
5. Keep the collector metadata-first. Do not emit raw titles, message bodies, document text, cell values, formulas, file paths, URLs, participants, logs, SQL, customer data, or credentials unless an existing contract explicitly requires rich opt-in.
6. Add stable dedupe signatures, source health reporting, offset/cursor persistence, retry/backoff, and dead-letter behavior where the source needs it.
7. Add focused tests proving valid events are accepted, sensitive fields are redacted, invalid events are rejected/dead-lettered, and source health is visible.
8. Do not add root-level adapter files under humungousaur/collectors. Keep adapter code under humungousaur/collectors/adapters/ or source-specific native/app folders.
9. Run:
   PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_collectors.py tests/test_collector_event_log.py tests/test_api.py -q

First inspect existing collector definitions and choose the mapping table before coding.
```

## Provider References

- [Google Drive push notifications](https://developers.google.com/workspace/drive/api/guides/push)
- [Google Drive Activity API](https://developers.google.com/workspace/drive/activity/v2)
- [Gmail push notifications](https://developers.google.com/workspace/gmail/api/guides/push)
- [Google Calendar push notifications](https://developers.google.com/workspace/calendar/api/guides/push)
- [Microsoft Graph change notifications](https://learn.microsoft.com/en-us/graph/change-notifications-overview)
- [Microsoft Graph driveItem delta](https://learn.microsoft.com/en-us/graph/api/driveitem-delta)
- [Microsoft Graph message delta](https://learn.microsoft.com/en-us/graph/delta-query-messages)
- [Microsoft Graph calendar delta](https://learn.microsoft.com/en-us/graph/delta-query-events)
- [Microsoft Graph Excel APIs](https://learn.microsoft.com/en-us/graph/excel-concept-overview)
- [Microsoft Graph presence API](https://learn.microsoft.com/en-us/graph/api/resources/presence)
- [Slack Events API](https://docs.slack.dev/apis/events-api/)
- [GitHub webhooks](https://docs.github.com/en/webhooks)
- [Linear webhooks](https://linear.app/developers/webhooks)
- [Jira webhooks](https://developer.atlassian.com/cloud/jira/platform/webhooks/)
- [Asana webhooks](https://developers.asana.com/docs/webhooks-guide)
- [Notion webhooks](https://developers.notion.com/reference/webhooks)
- [Confluence Cloud REST API v2](https://developer.atlassian.com/cloud/confluence/rest/v2/)
- [Coda API](https://coda.io/developers/apis/v1)
- [Obsidian plugin docs](https://docs.obsidian.md/Plugins/Getting+started/Plugin+structure)
- [Evernote developer docs](https://dev.evernote.com/doc/)
- [Microsoft Graph OneNote API](https://learn.microsoft.com/en-us/graph/api/resources/onenote-api-overview)
- [Apple ScriptingBridge](https://developer.apple.com/documentation/scriptingbridge)
- [Figma webhooks](https://developers.figma.com/docs/rest-api/webhooks/)
- [Zoom webhooks](https://developers.zoom.us/docs/api/webhooks/)
- [Google Meet API](https://developers.google.com/workspace/meet/api/guides/overview)
- [Microsoft Teams meeting transcripts and recordings](https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/meeting-transcripts/overview-transcripts)
- [Webex meeting transcripts](https://developer.webex.com/docs/api/v1/meeting-transcripts)
- [Discord voice resource](https://docs.discord.com/developers/resources/voice)
- [Dropbox files/list_folder](https://www.dropbox.com/developers/documentation/http/documentation#files-list_folder)
- [Dropbox webhooks](https://www.dropbox.com/developers/reference/webhooks)
- [Box Events API](https://developer.box.com/reference/get-events/)
- [Box webhooks](https://developer.box.com/guides/webhooks)
- [Apple File Provider](https://developer.apple.com/documentation/fileprovider)
- [Salesforce Change Data Capture](https://developer.salesforce.com/docs/atlas.en-us.change_data_capture.meta/change_data_capture/cdc_intro.htm)
- [HubSpot webhooks](https://developers.hubspot.com/docs/api-reference/legacy/webhooks/guide)
- [Zendesk webhooks](https://developer.zendesk.com/documentation/webhooks/)
- [Intercom webhooks](https://developers.intercom.com/docs/references/webhooks/)
- [Freshdesk API](https://developers.freshdesk.com/api/)
- [Stripe webhooks](https://docs.stripe.com/webhooks)
- [Shopify webhooks](https://shopify.dev/docs/apps/build/webhooks)
- [QuickBooks Online webhooks](https://developer.intuit.com/app/developer/qbo/docs/develop/webhooks)
- [Xero webhooks](https://developer.xero.com/documentation/guides/webhooks/overview/)
