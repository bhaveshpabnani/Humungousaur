using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Nodes;
using Humungousaur.App.Models;

namespace Humungousaur.App.Services;

public sealed class AgentApiClient
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        PropertyNameCaseInsensitive = true,
        WriteIndented = true,
    };

    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(60) };
    private Uri _baseUri = new("http://127.0.0.1:8765");

    public void SetBaseUrl(string baseUrl)
    {
        _baseUri = new Uri(baseUrl.TrimEnd('/') + "/");
    }

    public Task<JsonObject> GetHealthAsync() => GetJsonObjectAsync("health");

    public Task<JsonObject> GetSystemStatusAsync() => GetJsonObjectAsync("system/status");

    public async Task<List<ChannelInfo>> GetChannelsAsync()
    {
        return await GetAsync<List<ChannelInfo>>("channels") ?? [];
    }

    public Task<JsonObject> GetChannelStatusAsync(string channelId)
    {
        return GetJsonObjectAsync($"channels/status?channel_id={Uri.EscapeDataString(channelId)}");
    }

    public Task<JsonObject> GetChannelDoctorAsync(string channelId)
    {
        return GetJsonObjectAsync($"channels/doctor?channel_id={Uri.EscapeDataString(channelId)}");
    }

    public Task<JsonObject> SaveChannelSetupAsync(ChannelInfo channel, ChannelSetup setup)
    {
        var payload = new JsonObject
        {
            ["channel_id"] = channel.ChannelId,
            ["enabled"] = setup.Enabled,
            ["conversation_defaults"] = new JsonObject
            {
                ["conversation_id"] = setup.ConversationId,
                ["conversation_type"] = setup.ConversationType,
            },
            ["secret_refs"] = new JsonObject(),
            ["secret_configured"] = new JsonObject(),
            ["notes"] = setup.Notes,
        };
        if (!string.IsNullOrWhiteSpace(setup.SecretName))
        {
            payload["secret_refs"]!["primary"] = setup.SecretName;
            payload["secret_configured"]!["primary"] = setup.SecretConfigured;
        }
        return PostJsonObjectAsync("channels/setup", payload);
    }

    public async Task<ToolCatalog> GetToolsAsync()
    {
        return await GetAsync<ToolCatalog>("tools") ?? new ToolCatalog();
    }

    public Task<JsonObject> GetVoiceStatusAsync() => GetJsonObjectAsync("voice/status");

    public Task<JsonObject> GetAutonomousStatusAsync() => GetJsonObjectAsync("autonomous/status?limit=8");

    public async Task<OutboxEnvelope> GetOutboxAsync()
    {
        return await GetAsync<OutboxEnvelope>("channels/outbox") ?? new OutboxEnvelope();
    }

    public Task<JsonObject> SendStimulusAsync(string text, string source, string responseMode, AppSettings settings)
    {
        var payload = RuntimePayload(settings);
        payload["text"] = text;
        payload["source"] = source;
        payload["response_mode"] = responseMode;
        payload["metadata"] = new JsonObject
        {
            ["response_mode"] = responseMode,
            ["tts_provider"] = settings.TtsProvider,
            ["voice_id"] = settings.VoiceId,
        };
        return PostJsonObjectAsync("stimuli", payload);
    }

    public Task<JsonObject> SendChannelInboundAsync(ChannelInfo channel, ChannelSetup setup, string text, AppSettings settings)
    {
        var payload = RuntimePayload(settings);
        payload["channel_id"] = channel.ChannelId;
        payload["conversation_id"] = string.IsNullOrWhiteSpace(setup.ConversationId) ? "windows-app-preview" : setup.ConversationId;
        payload["conversation_type"] = string.IsNullOrWhiteSpace(setup.ConversationType) ? "dm" : setup.ConversationType;
        payload["sender_id"] = "windows-app";
        payload["text"] = text;
        payload["requires_response"] = true;
        payload["prepare_reply"] = true;
        return PostJsonObjectAsync("channels/inbound", payload);
    }

    public Task<JsonObject> RunAutonomousCycleAsync(AppSettings settings, bool allowInitiative, int maxCycles)
    {
        var payload = RuntimePayload(settings);
        payload["max_cycles"] = maxCycles;
        payload["idle_sleep_seconds"] = 0;
        payload["stop_after_idle_cycles"] = 1;
        payload["allow_initiative"] = allowInitiative;
        return PostJsonObjectAsync("autonomous/cycles", payload);
    }

    private static JsonObject RuntimePayload(AppSettings settings)
    {
        var payload = new JsonObject
        {
            ["planner"] = settings.Planner,
            ["approve_high_risk"] = settings.ApproveHighRisk,
        };
        if (!string.IsNullOrWhiteSpace(settings.ModelProvider))
        {
            payload["model_provider"] = settings.ModelProvider;
        }
        if (!string.IsNullOrWhiteSpace(settings.ModelName))
        {
            payload["model"] = settings.ModelName;
        }
        return payload;
    }

    private async Task<T?> GetAsync<T>(string route)
    {
        using var response = await _http.GetAsync(new Uri(_baseUri, route));
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<T>(JsonOptions);
    }

    private async Task<JsonObject> GetJsonObjectAsync(string route)
    {
        using var response = await _http.GetAsync(new Uri(_baseUri, route));
        response.EnsureSuccessStatusCode();
        var node = await response.Content.ReadFromJsonAsync<JsonObject>(JsonOptions);
        return node ?? [];
    }

    private async Task<JsonObject> PostJsonObjectAsync(string route, JsonObject payload)
    {
        using var response = await _http.PostAsJsonAsync(new Uri(_baseUri, route), payload, JsonOptions);
        response.EnsureSuccessStatusCode();
        var node = await response.Content.ReadFromJsonAsync<JsonObject>(JsonOptions);
        return node ?? [];
    }

    public static string Pretty(JsonNode? node)
    {
        if (node is null)
        {
            return "";
        }
        return node.ToJsonString(JsonOptions);
    }
}
