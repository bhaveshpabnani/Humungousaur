using System.Net.Http.Json;
using System.Text;
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

    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(300) };
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

    public Task<JsonObject> GetChannelStatusAsync(string channelId, AppSettings settings)
    {
        var payload = RuntimePayload(settings);
        payload["channel_id"] = channelId;
        return PostJsonObjectAsync("channels/status", payload);
    }

    public Task<JsonObject> GetChannelDoctorAsync(string channelId, AppSettings settings)
    {
        var payload = RuntimePayload(settings);
        payload["channel_id"] = channelId;
        return PostJsonObjectAsync("channels/doctor", payload);
    }

    public Task<JsonObject> GetChannelRequirementsAsync(string channelId)
    {
        return GetJsonObjectAsync($"channels/requirements?channel_id={Uri.EscapeDataString(channelId)}");
    }

    public Task<JsonObject> RunChannelSmokeAsync(string channelId, AppSettings settings)
    {
        var payload = RuntimePayload(settings);
        payload["channel_id"] = channelId;
        payload["prepare_messages"] = true;
        payload["dry_run_sends"] = true;
        return PostJsonObjectAsync("channels/smoke", payload);
    }

    public Task<JsonObject> GetChannelListenersAsync(string channelId, AppSettings settings)
    {
        var payload = RuntimePayload(settings);
        payload["channel_id"] = channelId;
        return PostJsonObjectAsync("channels/listeners", payload);
    }

    public Task<JsonObject> TickChannelListenerAsync(ChannelInfo channel, AppSettings settings)
    {
        var payload = RuntimePayload(settings);
        payload["channel_id"] = channel.ChannelId;
        payload["limit"] = 10;
        payload["prepare_replies"] = true;
        return PostJsonObjectAsync("channels/listeners/tick", payload);
    }

    public Task<JsonObject> SaveChannelSetupAsync(ChannelInfo channel, ChannelSetup setup)
    {
        var payload = new JsonObject
        {
            ["channel_id"] = channel.ChannelId,
            ["enabled"] = setup.Enabled && setup.ListenEnabled,
            ["conversation_defaults"] = new JsonObject
            {
                ["conversation_id"] = setup.ConversationId,
                ["conversation_type"] = setup.ConversationType,
            },
            ["secret_refs"] = ChannelSecretRefs(setup),
            ["secret_configured"] = ChannelSecretConfigured(setup),
            ["allowlist"] = StringArray(setup.Allowlist ?? []),
            ["group_allowlist"] = StringArray(setup.GroupAllowlist ?? []),
            ["notes"] = setup.Notes,
        };
        return PostJsonObjectAsync("channels/setup", payload);
    }

    public Task<JsonObject> PrepareChannelMessageAsync(ChannelInfo channel, ChannelSetup setup, string text, AppSettings settings)
    {
        var payload = RuntimePayload(settings);
        payload["channel_id"] = channel.ChannelId;
        payload["conversation_id"] = string.IsNullOrWhiteSpace(setup.ConversationId) ? "windows-app-preview" : setup.ConversationId;
        payload["text"] = text;
        payload["reason"] = "Prepared from the Windows app channel panel.";
        payload["metadata"] = new JsonObject
        {
            ["source"] = "windows_app",
            ["conversation_type"] = setup.ConversationType,
        };
        return PostJsonObjectAsync("channels/message/prepare", payload);
    }

    public Task<JsonObject> SendChannelMessageAsync(ChannelInfo channel, ChannelSetup setup, string text, AppSettings settings)
    {
        var payload = RuntimePayload(settings);
        payload["channel_id"] = channel.ChannelId;
        payload["conversation_id"] = string.IsNullOrWhiteSpace(setup.ConversationId) ? "windows-app-preview" : setup.ConversationId;
        payload["text"] = text;
        payload["reason"] = "Approval-gated send from the Windows app channel panel.";
        payload["approve_high_risk"] = settings.ApproveHighRisk;
        payload["metadata"] = new JsonObject
        {
            ["source"] = "windows_app",
            ["conversation_type"] = setup.ConversationType,
        };
        return PostJsonObjectAsync("channels/message/send", payload);
    }

    public async Task<ToolCatalog> GetToolsAsync()
    {
        return await GetAsync<ToolCatalog>("tools") ?? new ToolCatalog();
    }

    public Task<JsonObject> GetVoiceStatusAsync(AppSettings settings) => PostJsonObjectAsync("voice/status", RuntimePayload(settings));

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
            payload["model_api_key_env"] = ModelApiKeyName(settings.ModelProvider);
        }
        if (!string.IsNullOrWhiteSpace(settings.ModelName))
        {
            payload["model"] = settings.ModelName;
        }
        if (!string.IsNullOrWhiteSpace(settings.ModelBaseUrl))
        {
            payload["model_base_url"] = settings.ModelBaseUrl;
        }
        var secrets = RuntimeSecrets(settings);
        if (secrets.Count > 0)
        {
            payload["runtime_secrets"] = secrets;
        }
        return payload;
    }

    private static JsonObject RuntimeSecrets(AppSettings settings)
    {
        var secrets = new JsonObject();
        AddSecret(secrets, ModelApiKeyName(settings.ModelProvider), settings.ModelApiKey);
        AddSecret(secrets, "DEEPGRAM_API_KEY", settings.DeepgramApiKey);
        AddSecret(secrets, "ELEVENLABS_API_KEY", settings.ElevenLabsApiKey);
        AddSecret(secrets, "ELEVENLABS_VOICE_ID", settings.VoiceId);
        AddSecret(secrets, "ELEVENLABS_MODEL_ID", settings.ElevenLabsModel);
        foreach (var channel in settings.Channels)
        {
            if (!string.IsNullOrWhiteSpace(channel.SecretName) && !string.IsNullOrWhiteSpace(channel.SecretValue))
            {
                AddSecret(secrets, channel.SecretName, channel.SecretValue);
            }
            foreach (var item in channel.SecretValues ?? [])
            {
                AddSecret(secrets, item.Key, item.Value);
            }
        }
        return secrets;
    }

    private static JsonObject ChannelSecretRefs(ChannelSetup setup)
    {
        var refs = new JsonObject();
        if (!string.IsNullOrWhiteSpace(setup.SecretName))
        {
            refs["primary"] = setup.SecretName;
        }
        foreach (var item in setup.SecretValues ?? [])
        {
            refs[item.Key] = item.Key;
        }
        return refs;
    }

    private static JsonObject ChannelSecretConfigured(ChannelSetup setup)
    {
        var configured = new JsonObject();
        if (!string.IsNullOrWhiteSpace(setup.SecretName))
        {
            configured["primary"] = setup.SecretConfigured || !string.IsNullOrWhiteSpace(setup.SecretValue);
        }
        foreach (var item in setup.SecretValues ?? [])
        {
            configured[item.Key] = !string.IsNullOrWhiteSpace(item.Value);
        }
        return configured;
    }

    private static JsonArray StringArray(IEnumerable<string> values)
    {
        var array = new JsonArray();
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value))
            {
                array.Add(value.Trim());
            }
        }
        return array;
    }

    private static void AddSecret(JsonObject secrets, string name, string value)
    {
        if (!string.IsNullOrWhiteSpace(name) && !string.IsNullOrWhiteSpace(value))
        {
            secrets[name.Trim()] = value;
        }
    }

    private static string ModelApiKeyName(string provider)
    {
        return provider switch
        {
            "openai" or "openai-responses" or "openai-chat" => "OPENAI_API_KEY",
            "groq" => "GROQ_API_KEY",
            "grok" => "XAI_API_KEY",
            "ollama" => "OLLAMA_API_KEY",
            "local-openai" => "LOCAL_LLM_API_KEY",
            _ => "OPENAI_API_KEY",
        };
    }

    private async Task<T?> GetAsync<T>(string route)
    {
        using var response = await _http.GetAsync(new Uri(_baseUri, route));
        await EnsureSuccessAsync(response, route);
        return await response.Content.ReadFromJsonAsync<T>(JsonOptions);
    }

    private async Task<JsonObject> GetJsonObjectAsync(string route)
    {
        using var response = await _http.GetAsync(new Uri(_baseUri, route));
        await EnsureSuccessAsync(response, route);
        var node = await response.Content.ReadFromJsonAsync<JsonObject>(JsonOptions);
        return node ?? [];
    }

    private async Task<JsonObject> PostJsonObjectAsync(string route, JsonObject payload)
    {
        using var content = new StringContent(payload.ToJsonString(JsonOptions), Encoding.UTF8, "application/json");
        using var response = await _http.PostAsync(new Uri(_baseUri, route), content);
        await EnsureSuccessAsync(response, route);
        var node = await response.Content.ReadFromJsonAsync<JsonObject>(JsonOptions);
        return node ?? [];
    }

    private static async Task EnsureSuccessAsync(HttpResponseMessage response, string route)
    {
        if (response.IsSuccessStatusCode)
        {
            return;
        }

        var body = await response.Content.ReadAsStringAsync();
        var detail = ExtractErrorDetail(body);
        throw new HttpRequestException(
            string.IsNullOrWhiteSpace(detail)
                ? $"{route} failed with HTTP {(int)response.StatusCode} {response.ReasonPhrase}."
                : $"{route} failed with HTTP {(int)response.StatusCode} {response.ReasonPhrase}: {detail}",
            null,
            response.StatusCode);
    }

    private static string ExtractErrorDetail(string body)
    {
        if (string.IsNullOrWhiteSpace(body))
        {
            return "";
        }

        try
        {
            var node = JsonNode.Parse(body);
            return node?["error"]?.GetValue<string>() ?? node?["message"]?.GetValue<string>() ?? body;
        }
        catch (JsonException)
        {
            return body.Length > 1200 ? body[..1200] : body;
        }
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
