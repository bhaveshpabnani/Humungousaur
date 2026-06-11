using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.Json.Serialization;
using Microsoft.UI;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;

namespace Humungousaur.App.Models;

public sealed class ChannelInfo
{
    [JsonPropertyName("channel_id")]
    public string ChannelId { get; set; } = "";

    [JsonPropertyName("display_name")]
    public string DisplayName { get; set; } = "";

    [JsonPropertyName("transport")]
    public string Transport { get; set; } = "";

    [JsonPropertyName("plugin_kind")]
    public string PluginKind { get; set; } = "";

    [JsonPropertyName("setup_kind")]
    public string SetupKind { get; set; } = "";

    [JsonPropertyName("conversation_types")]
    public List<string> ConversationTypes { get; set; } = [];

    [JsonPropertyName("supports_text")]
    public bool SupportsText { get; set; }

    [JsonPropertyName("supports_media")]
    public bool SupportsMedia { get; set; }

    [JsonPropertyName("supports_reactions")]
    public bool SupportsReactions { get; set; }

    [JsonPropertyName("setup")]
    public JsonObject? Setup { get; set; }

    [JsonPropertyName("delivery")]
    public JsonObject? Delivery { get; set; }

    [JsonPropertyName("policies")]
    public JsonObject? Policies { get; set; }

    [JsonPropertyName("runtime")]
    public JsonObject? Runtime { get; set; }
}

public sealed class ToolCatalog
{
    [JsonPropertyName("tool_count")]
    public int ToolCount { get; set; }

    [JsonPropertyName("groups")]
    public List<ToolGroup> Groups { get; set; } = [];

    [JsonPropertyName("tools")]
    public List<ToolInfo> Tools { get; set; } = [];
}

public sealed class ToolGroup
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("tool_count")]
    public int ToolCount { get; set; }
}

public sealed class ToolInfo
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("description")]
    public string Description { get; set; } = "";

    [JsonPropertyName("risk_level")]
    public string RiskLevel { get; set; } = "";

    [JsonPropertyName("requires_approval")]
    public bool RequiresApproval { get; set; }

    [JsonPropertyName("capability_group")]
    public string CapabilityGroup { get; set; } = "";
}

public sealed class ModelProviderCatalog
{
    [JsonPropertyName("provider_count")]
    public int ProviderCount { get; set; }

    [JsonPropertyName("providers")]
    public List<ModelProviderInfo> Providers { get; set; } = [];
}

public sealed class ModelProviderInfo
{
    [JsonPropertyName("provider_id")]
    public string ProviderId { get; set; } = "";

    [JsonPropertyName("label")]
    public string Label { get; set; } = "";

    [JsonPropertyName("transport")]
    public string Transport { get; set; } = "";

    [JsonPropertyName("default_model")]
    public string DefaultModel { get; set; } = "";

    [JsonPropertyName("model_env")]
    public string ModelEnv { get; set; } = "";

    [JsonPropertyName("api_key_envs")]
    public List<string> ApiKeyEnvs { get; set; } = [];

    [JsonPropertyName("base_url_env")]
    public string BaseUrlEnv { get; set; } = "";

    [JsonPropertyName("default_base_url")]
    public string DefaultBaseUrl { get; set; } = "";

    [JsonPropertyName("aliases")]
    public List<string> Aliases { get; set; } = [];

    public string DisplayLabel => string.IsNullOrWhiteSpace(Label) ? ProviderId : Label;
}

public sealed class OutboxEnvelope
{
    [JsonPropertyName("messages")]
    public List<JsonObject> Messages { get; set; } = [];
}

public sealed class ConnectorCatalog
{
    [JsonPropertyName("provider_count")]
    public int ProviderCount { get; set; }

    [JsonPropertyName("providers")]
    public List<ConnectorProvider> Providers { get; set; } = [];

    [JsonPropertyName("redirect_uri")]
    public string RedirectUri { get; set; } = "";
}

public sealed class ConnectorProvider
{
    [JsonPropertyName("provider_id")]
    public string ProviderId { get; set; } = "";

    [JsonPropertyName("display_name")]
    public string DisplayName { get; set; } = "";

    [JsonPropertyName("category")]
    public string Category { get; set; } = "";

    [JsonPropertyName("auth_type")]
    public string AuthType { get; set; } = "";

    [JsonPropertyName("credential_fields")]
    public List<string> CredentialFields { get; set; } = [];

    [JsonPropertyName("oauth_management")]
    public string OAuthManagement { get; set; } = "";

    [JsonPropertyName("managed_oauth_available")]
    public bool ManagedOAuthAvailable { get; set; }

    [JsonPropertyName("advanced_client_config")]
    public bool AdvancedClientConfig { get; set; }

    [JsonPropertyName("advanced_client_configured")]
    public bool AdvancedClientConfigured { get; set; }

    [JsonPropertyName("default_scopes")]
    public List<string> DefaultScopes { get; set; } = [];

    [JsonPropertyName("workspace_apps")]
    public List<string> WorkspaceApps { get; set; } = [];

    [JsonPropertyName("tool_hints")]
    public List<string> ToolHints { get; set; } = [];

    [JsonPropertyName("docs_url")]
    public string DocsUrl { get; set; } = "";

    [JsonPropertyName("icon")]
    public string Icon { get; set; } = "";

    [JsonPropertyName("brand_color")]
    public string BrandColor { get; set; } = "#64748B";

    [JsonPropertyName("logo_asset")]
    public string LogoAsset { get; set; } = "";

    [JsonPropertyName("logo_url")]
    public string LogoUrl { get; set; } = "";

    [JsonPropertyName("configured")]
    public bool Configured { get; set; }

    [JsonPropertyName("client_id")]
    public string ClientId { get; set; } = "";

    [JsonPropertyName("connected")]
    public bool Connected { get; set; }

    [JsonPropertyName("connected_at")]
    public string ConnectedAt { get; set; } = "";

    [JsonPropertyName("expires_at")]
    public double ExpiresAt { get; set; }

    [JsonPropertyName("has_refresh_token")]
    public bool HasRefreshToken { get; set; }

    [JsonPropertyName("collector_source")]
    public ConnectorCollectorSource? CollectorSource { get; set; }

    public bool UsesOAuth => AuthType == "oauth2_authorization_code";
    public string StatusText => Connected
        ? "Connected"
        : UsesOAuth
            ? ManagedOAuthAvailable || Configured ? "Ready to connect" : "Managed OAuth unavailable"
            : Configured ? "Credentials saved" : "Needs credentials";
    public string AppsText => WorkspaceApps.Count == 0 ? "-" : string.Join(", ", WorkspaceApps);
    public string AuthModeText => Humanize(AuthType);
    public string SetupTitle => UsesOAuth ? "Advanced OAuth Client" : CredentialFields.Count <= 1 ? "Local Connection" : CredentialFields.Contains("bot_token") ? "Bot Credentials" : "Connection Credentials";
    public string SetupCaption => UsesOAuth
        ? $"Managed OAuth is the normal user path. Use these fields only for self-hosted or development builds. {(DefaultScopes.Count == 0 ? "OAuth scopes: none declared" : $"OAuth scopes: {string.Join(", ", DefaultScopes)}")}"
        : CredentialFields.Count <= 1
            ? "No provider API secret is required here. Save a local connection name so tools and collectors can check readiness."
            : $"Credential fields: {string.Join(", ", CredentialFields.Select(Humanize))}";
    public string PrimaryCredentialLabel => CredentialFields.Count > 0 ? Humanize(CredentialFields[0]) : UsesOAuth ? "Client ID" : "Connection ID";
    public string SecondaryCredentialLabel => UsesOAuth && SupportsPkce ? "Client Secret (optional)" : CredentialFields.Count > 1 ? Humanize(CredentialFields[1]) : UsesOAuth ? "Client secret" : "Secret or token";
    public string SaveButtonLabel => UsesOAuth ? "Save Advanced OAuth Client" : "Save Credentials";
    public string ConnectionButtonLabel => UsesOAuth ? Connected ? "Reconnect" : "Connect" : Configured ? "Check Readiness" : "Show Setup";
    public string LogoInitial => string.IsNullOrWhiteSpace(DisplayName) ? "?" : DisplayName.Trim()[0].ToString().ToUpperInvariant();
    public ImageSource? LogoImageSource => ConnectorLogoSource(LogoAsset);
    public Visibility LogoImageVisibility => LogoImageSource is null ? Visibility.Collapsed : Visibility.Visible;
    public Visibility LogoInitialVisibility => LogoImageSource is null ? Visibility.Visible : Visibility.Collapsed;
    public SolidColorBrush LogoTileBackground => LogoImageSource is null ? ConnectorBrush(BrandColor) : new SolidColorBrush(Colors.White);
    public SolidColorBrush LogoInitialForeground => new(LogoImageSource is null ? Colors.White : Colors.Black);
    public string CollectorSourceText
    {
        get
        {
            if (CollectorSource is null)
            {
                return "-";
            }

            var modes = new List<string>();
            if (CollectorSource.PollerSupported)
            {
                modes.Add("poller");
            }
            if (CollectorSource.WebhookSupported)
            {
                modes.Add("webhook");
            }

            var mappings = CollectorSource.CollectorMappings
                .Take(8)
                .Select(mapping => $"{Humanize(mapping.SourceEvent)} -> {Humanize(mapping.Collector)} / {Humanize(mapping.StimulusType)}");
            return string.Join(Environment.NewLine, new[]
            {
                Humanize(CollectorSource.SourceType),
                modes.Count == 0 ? "" : $"Modes: {string.Join(", ", modes)}",
                string.Join(Environment.NewLine, mappings),
            }.Where(line => !string.IsNullOrWhiteSpace(line)));
        }
    }

    private static string Humanize(string value)
    {
        return string.IsNullOrWhiteSpace(value) ? "-" : value.Replace("_", " ");
    }

    private static ImageSource? ConnectorLogoSource(string asset)
    {
        if (string.IsNullOrWhiteSpace(asset))
        {
            return null;
        }
        var cleanAsset = asset.Replace("/", "").Replace("\\", "");
        var localPath = Path.Combine(AppContext.BaseDirectory, "Assets", "ConnectorLogos", cleanAsset);
        var uri = File.Exists(localPath)
            ? new Uri(localPath)
            : new Uri($"ms-appx:///Assets/ConnectorLogos/{cleanAsset}");
        return cleanAsset.EndsWith(".svg", StringComparison.OrdinalIgnoreCase)
            ? new SvgImageSource(uri)
            : new BitmapImage(uri);
    }

    private static SolidColorBrush ConnectorBrush(string hex)
    {
        var clean = (hex ?? "").Trim().TrimStart('#');
        if (clean.Length == 6 && uint.TryParse(clean, System.Globalization.NumberStyles.HexNumber, System.Globalization.CultureInfo.InvariantCulture, out var value))
        {
            var red = (byte)((value >> 16) & 0xFF);
            var green = (byte)((value >> 8) & 0xFF);
            var blue = (byte)(value & 0xFF);
            return new SolidColorBrush(ColorHelper.FromArgb(255, red, green, blue));
        }
        return new SolidColorBrush(Colors.SlateGray);
    }
}

public sealed class ConnectorCollectorSource
{
    [JsonPropertyName("source_type")]
    public string SourceType { get; set; } = "";

    [JsonPropertyName("poller_supported")]
    public bool PollerSupported { get; set; }

    [JsonPropertyName("webhook_supported")]
    public bool WebhookSupported { get; set; }

    [JsonPropertyName("collector_mappings")]
    public List<ConnectorCollectorMapping> CollectorMappings { get; set; } = [];
}

public sealed class ConnectorCollectorMapping
{
    [JsonPropertyName("source_event")]
    public string SourceEvent { get; set; } = "";

    [JsonPropertyName("collector")]
    public string Collector { get; set; } = "";

    [JsonPropertyName("stimulus_type")]
    public string StimulusType { get; set; } = "";
}

public sealed class ConnectorAuthorization
{
    [JsonPropertyName("provider_id")]
    public string ProviderId { get; set; } = "";

    [JsonPropertyName("display_name")]
    public string DisplayName { get; set; } = "";

    [JsonPropertyName("authorization_url")]
    public string AuthorizationUrl { get; set; } = "";

    [JsonPropertyName("state")]
    public string State { get; set; } = "";

    [JsonPropertyName("redirect_uri")]
    public string RedirectUri { get; set; } = "";

    [JsonPropertyName("scopes")]
    public List<string> Scopes { get; set; } = [];
}

public sealed class ActiveAgentStatusResponse
{
    [JsonPropertyName("routes")]
    public List<ActiveAgentRecord> Routes { get; set; } = [];

    [JsonPropertyName("decisions")]
    public List<ActiveAgentRecord> Decisions { get; set; } = [];

    [JsonPropertyName("activations")]
    public List<ActiveAgentRecord> Activations { get; set; } = [];

    [JsonPropertyName("memory_candidates")]
    public List<ActiveAgentRecord> MemoryCandidates { get; set; } = [];

    [JsonPropertyName("task_contexts")]
    public List<ActiveAgentRecord> TaskContexts { get; set; } = [];

    [JsonPropertyName("muted_scopes")]
    public List<ActiveAgentRecord> MutedScopes { get; set; } = [];

    [JsonPropertyName("deep_dive_requests")]
    public List<ActiveAgentRecord> DeepDiveRequests { get; set; } = [];

    [JsonPropertyName("deep_dive_results")]
    public List<ActiveAgentRecord> DeepDiveResults { get; set; } = [];

    [JsonPropertyName("activation_responses")]
    public List<ActiveAgentRecord> ActivationResponses { get; set; } = [];

    [JsonPropertyName("episode_links")]
    public List<ActiveAgentRecord> EpisodeLinks { get; set; } = [];

    [JsonPropertyName("privacy_actions")]
    public List<ActiveAgentRecord> PrivacyActions { get; set; } = [];

    [JsonPropertyName("eval_runs")]
    public List<ActiveAgentRecord> EvalRuns { get; set; } = [];

    [JsonPropertyName("context_window")]
    public JsonObject? ContextWindow { get; set; }

    [JsonPropertyName("context_windows")]
    public List<ActiveAgentRecord> ContextWindows { get; set; } = [];

    [JsonPropertyName("context_boundaries")]
    public List<ActiveAgentRecord> ContextBoundaries { get; set; } = [];

    [JsonPropertyName("resume_capsules")]
    public List<ActiveAgentRecord> ResumeCapsules { get; set; } = [];

    [JsonPropertyName("explanations")]
    public List<ActiveAgentRecord> Explanations { get; set; } = [];

    [JsonPropertyName("corrections")]
    public List<ActiveAgentRecord> Corrections { get; set; } = [];

    public (string TargetType, string TargetId)? LatestTarget
    {
        get
        {
            if (Activations.FirstOrDefault() is { Id.Length: > 0 } activation)
            {
                return ("activation", activation.Id);
            }
            if (MemoryCandidates.FirstOrDefault() is { Id.Length: > 0 } memory)
            {
                return ("memory_candidate", memory.Id);
            }
            if (Decisions.FirstOrDefault() is { Id.Length: > 0 } decision)
            {
                return ("decision", decision.Id);
            }
            if (Explanations.FirstOrDefault() is { Id.Length: > 0 } explanation)
            {
                return ("explanation", explanation.Id);
            }
            if (Routes.FirstOrDefault() is { Id.Length: > 0 } route)
            {
                return ("route", route.Id);
            }
            return null;
        }
    }

    public string LatestPosture =>
        Activations.FirstOrDefault()?.ActivationDisplayStatus
        ?? Decisions.FirstOrDefault()?.StringValue("posture")
        ?? Routes.FirstOrDefault()?.StringValue("route_class")
        ?? "listening";
}

public sealed class ActiveAgentRecord
{
    [JsonExtensionData]
    public Dictionary<string, JsonElement> Values { get; set; } = [];

    public string Id =>
        StringValue("activation_id")
        ?? StringValue("candidate_id")
        ?? StringValue("decision_id")
        ?? StringValue("route_id")
        ?? StringValue("explanation_id")
        ?? StringValue("correction_id")
        ?? StringValue("task_context_id")
        ?? StringValue("scope_id")
            ?? StringValue("request_id")
            ?? StringValue("result_id")
            ?? StringValue("response_id")
            ?? StringValue("link_id")
            ?? StringValue("action_id")
            ?? StringValue("eval_id")
            ?? StringValue("boundary_id")
            ?? StringValue("capsule_id")
            ?? StringValue("id")
        ?? "";

    public string RecordTitle =>
        StringValue("user_visible_text")
        ?? StringValue("reason")
        ?? StringValue("summary")
        ?? StringValue("purpose")
        ?? StringValue("action_taken")
        ?? StringValue("scenario")
        ?? StringValue("note")
        ?? Humanize(StringValue("route_class") ?? "")
        ?? Id;

    public string RecordSubtitle
    {
        get
        {
            var parts = new[]
            {
                Humanize(StringValue("collector") ?? ""),
                Humanize(StringValue("source") ?? ""),
                Humanize(StringValue("stimulus_type") ?? ""),
                StringValue("created_at") ?? "",
            }.Where(value => !string.IsNullOrWhiteSpace(value));
            return string.Join(" / ", parts);
        }
    }

    public string RecordStatus =>
        Humanize(StringValue("status") ?? "")
        ?? Humanize(StringValue("posture") ?? "")
        ?? Humanize(StringValue("route_class") ?? "")
        ?? Humanize(StringValue("correction_type") ?? "")
        ?? "Recorded";

    public string? ActivationDisplayStatus
    {
        get
        {
            if (StringValue("activation_id") is null)
            {
                return null;
            }
            var posture = Humanize(StringValue("posture") ?? "");
            var status = Humanize(StringValue("status") ?? "");
            if (!string.IsNullOrWhiteSpace(posture) && !string.IsNullOrWhiteSpace(status))
            {
                return $"{posture} / {status}";
            }
            return !string.IsNullOrWhiteSpace(status) ? status : posture;
        }
    }

    public string ShortId => Id.Length <= 18 ? Id : Id[..18];

    public string Detail => JsonSerializer.Serialize(Values, new JsonSerializerOptions { WriteIndented = true });

    public string? StringValue(string key)
    {
        if (!Values.TryGetValue(key, out var value))
        {
            return null;
        }
        return value.ValueKind switch
        {
            JsonValueKind.String => value.GetString(),
            JsonValueKind.Number => value.ToString(),
            JsonValueKind.True => "true",
            JsonValueKind.False => "false",
            _ => null,
        };
    }

    private static string? Humanize(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }
        return CultureInfo.CurrentCulture.TextInfo.ToTitleCase(value.Replace("_", " ").Replace("-", " "));
    }
}

public sealed class CollectorStatusResponse
{
    [JsonPropertyName("profile")]
    public JsonObject? Profile { get; set; }

    [JsonPropertyName("capabilities")]
    public JsonObject? Capabilities { get; set; }

    [JsonPropertyName("event_log")]
    public JsonObject? EventLog { get; set; }

    [JsonPropertyName("recent_events")]
    public List<JsonObject> RecentEvents { get; set; } = [];

    [JsonPropertyName("state")]
    public JsonObject? State { get; set; }

    public string SummaryText
    {
        get
        {
            var enabled = EnabledCollectors().Count;
            var total = (Profile?["collectors"] as JsonObject)?.Count ?? 0;
            var eventCount = IntValue(EventLog, "event_count");
            var deadLetters = IntValue(EventLog, "dead_letter_count");
            return $"Collectors {enabled}/{total}; events {eventCount}; dead letters {deadLetters}";
        }
    }

    public List<CollectorHealthItem> HealthItems
    {
        get
        {
            var enabled = EnabledCollectors();
            var capabilities = Capabilities?["collectors"] as JsonObject;
            var items = new List<CollectorHealthItem>();

            foreach (var name in enabled.OrderBy(value => value, StringComparer.OrdinalIgnoreCase))
            {
                var record = capabilities?[name] as JsonObject;
                items.Add(new CollectorHealthItem
                {
                    Name = Humanize(name),
                    Source = Humanize(StringValue(record, "source")),
                    Status = Humanize(StringValue(record, "status") ?? "enabled"),
                    Subtitle = CollectorSubtitle(record),
                    Detail = $"Collector {name}; source {StringValue(record, "source") ?? "-"}; rich capture {(BoolValue(record, "rich_capture_required") ? "approval required" : "not required")}.",
                });
            }

            foreach (var helper in HelperHealth().Take(6))
            {
                var collector = StringValue(helper, "collector") ?? "helper";
                items.Add(new CollectorHealthItem
                {
                    Name = Humanize(collector),
                    Source = Humanize(StringValue(helper, "platform")),
                    Status = Humanize(StringValue(helper, "status") ?? "helper"),
                    Subtitle = $"Helper {StringValue(helper, "helper_id") ?? "-"} / permission {StringValue(helper, "permission_state") ?? "-"}",
                    Detail = $"Helper health for {collector}; raw status fields only.",
                });
            }

            foreach (var source in SourceStatus().Take(8))
            {
                items.Add(source);
            }

            return items.Count == 0
                ? new List<CollectorHealthItem> { new() { Name = "Collectors", Source = "-", Status = "No Status", Subtitle = "Collector status is not available yet.", Detail = "" } }
                : items;
        }
    }

    private List<string> EnabledCollectors()
    {
        var collectors = Profile?["collectors"] as JsonObject;
        if (collectors is null)
        {
            return [];
        }

        return collectors
            .Where(item => BoolNode(item.Value))
            .Select(item => item.Key)
            .ToList();
    }

    private IEnumerable<JsonObject> HelperHealth()
    {
        var helpers = EventLog?["helper_health"] as JsonArray;
        return helpers?.OfType<JsonObject>() ?? Enumerable.Empty<JsonObject>();
    }

    private IEnumerable<CollectorHealthItem> SourceStatus()
    {
        var sources = Capabilities?["sources"] as JsonObject;
        if (sources is null)
        {
            yield break;
        }

        foreach (var item in sources.OrderBy(item => item.Key, StringComparer.OrdinalIgnoreCase))
        {
            var node = item.Value as JsonObject;
            if (node is null)
            {
                continue;
            }
            yield return new CollectorHealthItem
            {
                Name = Humanize(item.Key),
                Source = "Source",
                Status = Humanize(StringValue(node, "status") ?? StringValue(node, "readiness") ?? "registered"),
                Subtitle = SourceSubtitle(node),
                Detail = $"Source {item.Key}; status metadata only.",
            };
        }
    }

    private static string CollectorSubtitle(JsonObject? record)
    {
        if (record is null)
        {
            return "Enabled collector";
        }

        var family = Humanize(StringValue(record, "family"));
        var sensitive = BoolValue(record, "sensitive") ? "sensitive" : "metadata";
        var bridge = BoolValue(record, "bridge_supported") ? "bridge" : "poller";
        return string.Join(" / ", new[] { family, sensitive, bridge }.Where(value => !string.IsNullOrWhiteSpace(value)));
    }

    private static string SourceSubtitle(JsonObject node)
    {
        var parts = new[]
        {
            StringValue(node, "provider_id"),
            StringValue(node, "source_type"),
            StringValue(node, "permission_state"),
            StringValue(node, "message"),
        }.Where(value => !string.IsNullOrWhiteSpace(value));
        return string.Join(" / ", parts);
    }

    private static int IntValue(JsonObject? node, string key)
    {
        if (node is null || !node.TryGetPropertyValue(key, out var value) || value is null)
        {
            return 0;
        }
        try
        {
            return value.GetValueKind() == JsonValueKind.Number ? value.GetValue<int>() : 0;
        }
        catch (InvalidOperationException)
        {
            return 0;
        }
        catch (FormatException)
        {
            return 0;
        }
    }

    private static bool BoolValue(JsonObject? node, string key)
    {
        if (node is null || !node.TryGetPropertyValue(key, out var value))
        {
            return false;
        }
        return BoolNode(value);
    }

    private static bool BoolNode(JsonNode? value)
    {
        if (value is null)
        {
            return false;
        }
        return value.GetValueKind() switch
        {
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            JsonValueKind.String => string.Equals(value.GetValue<string>(), "true", StringComparison.OrdinalIgnoreCase),
            _ => false,
        };
    }

    private static string? StringValue(JsonObject? node, string key)
    {
        if (node is null || !node.TryGetPropertyValue(key, out var value) || value is null)
        {
            return null;
        }
        return value.GetValueKind() switch
        {
            JsonValueKind.String => value.GetValue<string>(),
            JsonValueKind.Number => value.ToJsonString(),
            JsonValueKind.True => "true",
            JsonValueKind.False => "false",
            _ => null,
        };
    }

    private static string Humanize(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }
        return CultureInfo.CurrentCulture.TextInfo.ToTitleCase(value.Replace("_", " ").Replace("-", " "));
    }
}

public sealed class CollectorHealthItem
{
    public string Name { get; init; } = "";
    public string Source { get; init; } = "";
    public string Status { get; init; } = "";
    public string Subtitle { get; init; } = "";
    public string Detail { get; init; } = "";
}

public sealed class UpdateInfo
{
    [JsonPropertyName("current_version")]
    public string CurrentVersion { get; set; } = "";

    [JsonPropertyName("latest_version")]
    public string LatestVersion { get; set; } = "";

    [JsonPropertyName("latest_tag")]
    public string LatestTag { get; set; } = "";

    [JsonPropertyName("update_available")]
    public bool UpdateAvailable { get; set; }

    [JsonPropertyName("release_url")]
    public string ReleaseUrl { get; set; } = "";

    [JsonPropertyName("platform")]
    public string Platform { get; set; } = "";

    [JsonPropertyName("platform_download_url")]
    public string PlatformDownloadUrl { get; set; } = "";

    [JsonPropertyName("checksum_url")]
    public string ChecksumUrl { get; set; } = "";

    [JsonPropertyName("source")]
    public string Source { get; set; } = "";

    [JsonPropertyName("error")]
    public string Error { get; set; } = "";

    public string StatusText =>
        UpdateAvailable
            ? $"Update {LatestTag} is available"
            : string.IsNullOrWhiteSpace(Error)
                ? $"Current version {CurrentVersion}"
                : $"Using {CurrentVersion}; release check unavailable";

    public string DownloadUrl => string.IsNullOrWhiteSpace(PlatformDownloadUrl) ? ReleaseUrl : PlatformDownloadUrl;
}

public sealed class RuntimeRunItem
{
    [JsonPropertyName("run_id")]
    public string RunId { get; set; } = "";

    [JsonPropertyName("request")]
    public string Request { get; set; } = "";

    [JsonPropertyName("status")]
    public string Status { get; set; } = "";

    [JsonPropertyName("started_at")]
    public string StartedAt { get; set; } = "";

    [JsonPropertyName("finished_at")]
    public string? FinishedAt { get; set; }

    [JsonPropertyName("final_response")]
    public string? FinalResponse { get; set; }

    public string Title => $"{Status}  {ShortRunId}";
    public string Subtitle => string.IsNullOrWhiteSpace(Request) ? ShortRunId : Request;
    public string ShortRunId => RunId.Length <= 12 ? RunId : RunId[..12];
}

public sealed class ApprovalItem
{
    [JsonPropertyName("approval_token")]
    public string ApprovalToken { get; set; } = "";

    [JsonPropertyName("run_id")]
    public string RunId { get; set; } = "";

    [JsonPropertyName("request")]
    public string Request { get; set; } = "";

    [JsonPropertyName("tool_name")]
    public string ToolName { get; set; } = "";

    [JsonPropertyName("tool_input")]
    public JsonObject? ToolInput { get; set; }

    [JsonPropertyName("risk_level")]
    public string RiskLevel { get; set; } = "";

    [JsonPropertyName("reason")]
    public string Reason { get; set; } = "";

    [JsonPropertyName("status")]
    public string Status { get; set; } = "";

    [JsonPropertyName("created_at")]
    public string CreatedAt { get; set; } = "";

    public string Title => $"{ToolName}  {RiskLevel}";
    public string Subtitle => string.IsNullOrWhiteSpace(Reason) ? Request : Reason;
    public string ShortToken => ApprovalToken.Length <= 12 ? ApprovalToken : ApprovalToken[..12];
}

public sealed class ChatLogItem
{
    public string Speaker { get; init; } = "";
    public string Text { get; init; } = "";
    public string Tone { get; init; } = "neutral";
    public DateTimeOffset Timestamp { get; init; } = DateTimeOffset.Now;
    public string TimeText => Timestamp.ToLocalTime().ToString("h:mm tt");
}

public sealed class AgentStreamEvent
{
    public string Event { get; init; } = "";
    public JsonObject Data { get; init; } = [];
}
