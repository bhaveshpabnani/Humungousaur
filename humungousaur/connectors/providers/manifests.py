from __future__ import annotations

from ..models import ConnectorProviderManifest


_CORE_PROVIDER_MANIFESTS: tuple[ConnectorProviderManifest, ...] = (
    ConnectorProviderManifest(
        provider_id="google_workspace",
        display_name="Google Workspace",
        category="workspace_suite",
        api_base_url="https://www.googleapis.com",
        default_scopes=(
            "openid",
            "email",
            "profile",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/tasks.readonly",
            "https://www.googleapis.com/auth/chat.messages.readonly",
            "https://www.googleapis.com/auth/contacts.readonly",
        ),
        workspace_apps=("Drive", "Docs", "Sheets", "Slides", "Gmail", "Calendar", "Meet", "Chat", "Contacts", "Tasks"),
        tool_hints=(
            "google_workspace_operation_prepare",
            "gmail_draft_prepare",
            "email_draft_prepare",
            "xlsx_workbook_create",
            "docx_document_create",
            "pptx_deck_create",
            "google_meet_context_prepare",
            "googlechat",
        ),
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        credential_fields=("client_id", "client_secret"),
        supports_pkce=True,
        docs_url="https://developers.google.com/workspace/guides/create-credentials",
    ),
    ConnectorProviderManifest(
        provider_id="microsoft_365",
        display_name="Microsoft 365",
        category="workspace_suite",
        api_base_url="https://graph.microsoft.com",
        default_scopes=(
            "offline_access",
            "User.Read",
            "Mail.Read",
            "Calendars.Read",
            "Files.Read.All",
            "Sites.Read.All",
            "Tasks.Read",
            "Notes.Read",
            "Chat.Read",
            "ChannelMessage.Read.All",
            "Presence.Read",
        ),
        workspace_apps=("Outlook", "Calendar", "OneDrive", "SharePoint", "Word", "Excel", "PowerPoint", "Teams", "OneNote", "To Do", "Loop", "Planner"),
        tool_hints=("email_draft_prepare", "xlsx_workbook_create", "docx_document_create", "pptx_deck_create", "msteams"),
        auth_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        credential_fields=("client_id", "client_secret"),
        supports_pkce=True,
        docs_url="https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app",
    ),
    ConnectorProviderManifest(
        provider_id="slack",
        display_name="Slack",
        category="communication",
        api_base_url="https://slack.com/api",
        default_scopes=("channels:history", "channels:read", "chat:write", "files:read", "users:read"),
        workspace_apps=("Slack",),
        tool_hints=("channel_catalog", "channel_message_prepare", "channel_message_send", "channel_listener_tick"),
        auth_url="https://slack.com/oauth/v2/authorize",
        token_url="https://slack.com/api/oauth.v2.access",
        credential_fields=("client_id", "client_secret"),
        supports_pkce=False,
        docs_url="https://api.slack.com/authentication/oauth-v2",
    ),
    ConnectorProviderManifest(
        provider_id="linear",
        display_name="Linear",
        category="planning",
        api_base_url="https://api.linear.app",
        default_scopes=("read", "write"),
        workspace_apps=("Linear",),
        tool_hints=("kanban_create", "kanban_comment", "kanban_complete", "kanban_link"),
        auth_url="https://linear.app/oauth/authorize",
        token_url="https://api.linear.app/oauth/token",
        credential_fields=("client_id", "client_secret"),
        supports_pkce=False,
        docs_url="https://developers.linear.app/docs/oauth/authentication",
    ),
    ConnectorProviderManifest(
        provider_id="github",
        display_name="GitHub",
        category="developer_platform",
        api_base_url="https://api.github.com",
        default_scopes=("repo", "read:org", "workflow"),
        workspace_apps=("GitHub", "Issues", "Pull Requests", "Actions"),
        tool_hints=("github_repo_state_report_create", "github_pr_packet_create", "github_issue_packet_create", "ci_failure_report_create"),
        auth_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        credential_fields=("client_id", "client_secret"),
        supports_pkce=False,
        docs_url="https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps",
    ),
    ConnectorProviderManifest(
        provider_id="gitlab",
        display_name="GitLab",
        category="developer_platform",
        api_base_url="https://gitlab.com/api/v4",
        default_scopes=("read_api", "read_user"),
        workspace_apps=("GitLab", "Merge Requests", "Issues", "Pipelines"),
        tool_hints=("workspace_connector_status", "ci_failure_report_create"),
        auth_url="https://gitlab.com/oauth/authorize",
        token_url="https://gitlab.com/oauth/token",
        credential_fields=("client_id", "client_secret"),
        supports_pkce=False,
        docs_url="https://docs.gitlab.com/user/project/integrations/webhooks/",
    ),
    ConnectorProviderManifest(
        provider_id="bitbucket",
        display_name="Bitbucket",
        category="developer_platform",
        api_base_url="https://api.bitbucket.org",
        default_scopes=("repository", "pullrequest", "pipeline", "issue"),
        workspace_apps=("Bitbucket", "Pull Requests", "Issues", "Pipelines"),
        tool_hints=("workspace_connector_status", "ci_failure_report_create"),
        auth_url="https://bitbucket.org/site/oauth2/authorize",
        token_url="https://bitbucket.org/site/oauth2/access_token",
        credential_fields=("client_id", "client_secret"),
        supports_pkce=False,
        docs_url="https://support.atlassian.com/bitbucket-cloud/docs/manage-webhooks/",
    ),
    ConnectorProviderManifest(
        provider_id="azure_devops",
        display_name="Azure DevOps",
        category="developer_platform",
        api_base_url="https://dev.azure.com",
        default_scopes=("vso.code", "vso.build", "vso.work"),
        workspace_apps=("Azure Repos", "Azure Boards", "Azure Pipelines"),
        tool_hints=("workspace_connector_status", "ci_failure_report_create"),
        auth_type="api_key",
        credential_fields=("profile_name", "api_key"),
        supports_pkce=False,
        docs_url="https://learn.microsoft.com/en-us/azure/devops/service-hooks/events?view=azure-devops",
    ),
    ConnectorProviderManifest(
        provider_id="dropbox",
        display_name="Dropbox",
        category="cloud_files",
        api_base_url="https://api.dropboxapi.com",
        default_scopes=("files.metadata.read", "sharing.read"),
        workspace_apps=("Dropbox", "Dropbox Files"),
        tool_hints=("read_file", "write_file", "search_files", "summarize_pdfs", "media_store_import"),
        auth_url="https://www.dropbox.com/oauth2/authorize",
        token_url="https://api.dropboxapi.com/oauth2/token",
        credential_fields=("client_id", "client_secret"),
        supports_pkce=True,
        docs_url="https://developers.dropbox.com/oauth-guide",
    ),
    ConnectorProviderManifest(
        provider_id="box",
        display_name="Box",
        category="cloud_files",
        api_base_url="https://api.box.com",
        default_scopes=("root_readonly",),
        workspace_apps=("Box", "Box Files"),
        tool_hints=("read_file", "write_file", "search_files", "summarize_pdfs", "media_store_import"),
        auth_url="https://account.box.com/api/oauth2/authorize",
        token_url="https://api.box.com/oauth2/token",
        credential_fields=("client_id", "client_secret"),
        supports_pkce=False,
        docs_url="https://developer.box.com/guides/authentication/oauth2/",
    ),
)


_CHANNEL_PROVIDERS: tuple[tuple[str, str], ...] = (
    ("whatsapp", "WhatsApp"),
    ("telegram", "Telegram"),
    ("discord", "Discord"),
    ("signal", "Signal"),
    ("googlechat", "Google Chat"),
    ("msteams", "Microsoft Teams"),
    ("sms", "SMS"),
    ("webchat", "WebChat"),
    ("voice_call", "Voice Call"),
    ("matrix", "Matrix"),
    ("imessage", "iMessage"),
    ("feishu", "Feishu/Lark"),
    ("line", "LINE"),
    ("mattermost", "Mattermost"),
    ("nextcloud_talk", "Nextcloud Talk"),
    ("irc", "IRC"),
    ("twitch", "Twitch"),
    ("wechat", "WeChat"),
    ("qqbot", "QQ Bot"),
    ("zalo", "Zalo"),
    ("zalo_personal", "Zalo Personal"),
    ("nostr", "Nostr"),
    ("tlon", "Tlon"),
    ("synology_chat", "Synology Chat"),
    ("clickclack", "ClickClack"),
    ("qa_channel", "QA Channel"),
    ("yuanbao", "Yuanbao"),
)

_TOOL_SURFACE_PROVIDERS: tuple[tuple[str, str, str], ...] = (
    ("airtable", "Airtable", "business_data"),
    ("apple_local", "Apple Local Apps", "local_apps"),
    ("browser_use", "Browser Use", "browser"),
    ("homeassistant", "Home Assistant", "automation"),
    ("hugging_face", "Hugging Face", "mlops"),
    ("mcp", "MCP Servers", "tool_runtime"),
    ("notion", "Notion", "knowledge_base"),
    ("onepassword", "1Password", "credentials"),
    ("screenpipe", "Screenpipe", "local_capture"),
    ("shopify", "Shopify", "commerce"),
    ("spotify", "Spotify", "media"),
)

_FUTURE_PROVIDERS: tuple[tuple[str, str, str], ...] = (
    ("jira", "Jira", "planning"),
    ("asana", "Asana", "planning"),
    ("trello", "Trello", "planning"),
    ("clickup", "ClickUp", "planning"),
    ("monday", "Monday.com", "planning"),
    ("atlassian", "Atlassian", "planning"),
    ("todoist", "Todoist", "planning"),
    ("zoho", "Zoho", "workspace_suite"),
    ("gitlab", "GitLab", "developer_platform"),
    ("bitbucket", "Bitbucket", "developer_platform"),
    ("azure_devops", "Azure DevOps", "developer_platform"),
    ("sentry", "Sentry", "observability"),
    ("datadog", "Datadog", "observability"),
    ("grafana", "Grafana", "observability"),
    ("pagerduty", "PagerDuty", "incident_management"),
    ("opsgenie", "Opsgenie", "incident_management"),
    ("aws", "AWS", "cloud"),
    ("azure", "Azure", "cloud"),
    ("gcp", "Google Cloud", "cloud"),
    ("vercel", "Vercel", "developer_platform"),
    ("netlify", "Netlify", "developer_platform"),
    ("cloudflare", "Cloudflare", "cloud"),
    ("docker_hub", "Docker Hub", "developer_platform"),
    ("kubernetes", "Kubernetes", "cloud"),
    ("dropbox", "Dropbox", "cloud_files"),
    ("box", "Box", "cloud_files"),
    ("nextcloud", "Nextcloud", "workspace_suite"),
    ("icloud", "iCloud", "workspace_suite"),
    ("notion_projects", "Notion Projects", "planning"),
    ("confluence", "Confluence", "knowledge_base"),
    ("coda", "Coda", "knowledge_base"),
    ("obsidian", "Obsidian", "knowledge_base"),
    ("evernote", "Evernote", "knowledge_base"),
    ("onenote", "OneNote", "knowledge_base"),
    ("siyuan", "SiYuan", "knowledge_base"),
    ("canvas_lms", "Canvas LMS", "knowledge_base"),
    ("figma", "Figma", "design"),
    ("figjam", "FigJam", "design"),
    ("miro", "Miro", "design"),
    ("canva", "Canva", "design"),
    ("adobe_xd", "Adobe XD", "design"),
    ("sketch", "Sketch", "design"),
    ("zoom", "Zoom", "meetings"),
    ("webex", "Webex", "meetings"),
    ("hubspot", "HubSpot", "crm"),
    ("salesforce", "Salesforce", "crm"),
    ("pipedrive", "Pipedrive", "crm"),
    ("zendesk", "Zendesk", "support"),
    ("intercom", "Intercom", "support"),
    ("freshdesk", "Freshdesk", "support"),
    ("stripe", "Stripe", "commerce"),
    ("paypal", "PayPal", "commerce"),
    ("square", "Square", "commerce"),
    ("quickbooks", "QuickBooks", "finance"),
    ("xero", "Xero", "finance"),
    ("plaid", "Plaid", "finance"),
    ("wise", "Wise", "finance"),
    ("mercury", "Mercury", "finance"),
    ("brex", "Brex", "finance"),
    ("ramp", "Ramp", "finance"),
    ("mailchimp", "Mailchimp", "marketing"),
    ("postgres", "Postgres", "data"),
    ("supabase", "Supabase", "data"),
    ("mysql", "MySQL", "data"),
    ("bigquery", "BigQuery", "data"),
    ("snowflake", "Snowflake", "data"),
    ("databricks", "Databricks", "data"),
    ("chroma", "Chroma", "data"),
    ("tableau", "Tableau", "analytics"),
    ("looker", "Looker", "analytics"),
    ("metabase", "Metabase", "analytics"),
    ("power_bi", "Power BI", "analytics"),
    ("google_analytics", "Google Analytics", "analytics"),
    ("mixpanel", "Mixpanel", "analytics"),
    ("amplitude", "Amplitude", "analytics"),
    ("mongodb_atlas", "MongoDB Atlas", "data"),
    ("brave_search", "Brave Search", "research"),
    ("exa", "Exa", "research"),
    ("tavily", "Tavily", "research"),
    ("firecrawl", "Firecrawl", "research"),
    ("searxng", "SearXNG", "research"),
    ("duckduckgo", "DuckDuckGo", "research"),
    ("arxiv", "arXiv", "research"),
    ("crossref", "Crossref", "research"),
    ("rss", "RSS", "research"),
    ("polymarket", "Polymarket", "research"),
    ("x_twitter", "X/Twitter", "research"),
    ("openai", "OpenAI", "ai"),
    ("anthropic", "Anthropic", "ai"),
    ("gemini", "Gemini", "ai"),
    ("grok_xai", "Grok/xAI", "ai"),
    ("groq", "Groq", "ai"),
    ("ollama", "Ollama", "ai"),
    ("fal", "Fal", "mlops"),
    ("replicate", "Replicate", "mlops"),
    ("stability_ai", "Stability AI", "mlops"),
    ("modal", "Modal", "mlops"),
    ("lambda_labs", "Lambda Labs", "mlops"),
    ("wandb", "Weights & Biases", "mlops"),
    ("pinecone", "Pinecone", "mlops"),
    ("qdrant", "Qdrant", "mlops"),
    ("hugging_face_datasets", "Hugging Face Datasets", "mlops"),
    ("youtube", "YouTube", "media"),
    ("hyperframes", "HyperFrames", "media"),
    ("blender", "Blender", "media"),
    ("comfyui", "ComfyUI", "media"),
    ("deepgram", "Deepgram", "media"),
    ("elevenlabs", "ElevenLabs", "media"),
    ("cursor", "Cursor", "developer_tool"),
    ("vscode", "VS Code", "developer_tool"),
    ("jetbrains", "JetBrains", "developer_tool"),
    ("xcode", "Xcode", "developer_tool"),
)


def _provider_ids(providers: tuple[ConnectorProviderManifest, ...]) -> set[str]:
    return {provider.provider_id for provider in providers}


def _credential_fields(provider_id: str, category: str) -> tuple[str, ...]:
    if provider_id in {"apple_local", "browser_use", "screenpipe", "mcp"}:
        return ("connection_name",)
    if provider_id in {
        "whatsapp",
        "telegram",
        "discord",
        "signal",
        "msteams",
        "googlechat",
        "mattermost",
        "nextcloud_talk",
        "slack",
    }:
        return ("bot_name", "bot_token")
    if category in {"commerce", "finance", "ai", "mlops", "research", "data", "analytics", "observability", "developer_platform"}:
        return ("profile_name", "api_key")
    if category in {"cloud", "cloud_files", "credentials"}:
        return ("profile_name", "access_token")
    if category in {"local_apps", "browser", "local_capture", "tool_runtime", "developer_tool"}:
        return ("connection_name",)
    return ("profile_name", "api_key")


def _auth_type(provider_id: str, category: str) -> str:
    if provider_id in {"apple_local"}:
        return "local_permission"
    if provider_id in {"browser_use"}:
        return "browser_session"
    if provider_id in {"mcp"}:
        return "mcp_oauth"
    if category in {"local_apps", "local_capture", "developer_tool"}:
        return "local_permission"
    return "api_key"


def _api_key_provider(provider_id: str, display_name: str, category: str, *, app: str | None = None) -> ConnectorProviderManifest:
    auth_type = _auth_type(provider_id, category)
    return ConnectorProviderManifest(
        provider_id=provider_id,
        display_name=display_name,
        category=category,
        api_base_url=f"https://connectors.local/{provider_id}",
        default_scopes=(),
        workspace_apps=(app or display_name,),
        tool_hints=("workspace_connector_status",),
        auth_type=auth_type,
        credential_fields=_credential_fields(provider_id, category),
        supports_pkce=False,
        docs_url="https://humungousaur.local/connectors",
    )


_core_ids = _provider_ids(_CORE_PROVIDER_MANIFESTS)
_channel_manifests = tuple(
    _api_key_provider(provider_id, display_name, "communication", app=display_name)
    for provider_id, display_name in _CHANNEL_PROVIDERS
    if provider_id not in _core_ids
)
_surface_ids = _core_ids | _provider_ids(_channel_manifests)
_tool_surface_manifests = tuple(
    _api_key_provider(provider_id, display_name, category)
    for provider_id, display_name, category in _TOOL_SURFACE_PROVIDERS
    if provider_id not in _surface_ids
)
_future_ids = _surface_ids | _provider_ids(_tool_surface_manifests)
_future_manifests = tuple(
    _api_key_provider(provider_id, display_name, category)
    for provider_id, display_name, category in _FUTURE_PROVIDERS
    if provider_id not in _future_ids
)

PROVIDER_MANIFESTS: tuple[ConnectorProviderManifest, ...] = (
    *_CORE_PROVIDER_MANIFESTS,
    *_channel_manifests,
    *_tool_surface_manifests,
    *_future_manifests,
)


__all__ = ["PROVIDER_MANIFESTS"]
