using System.Net.Http.Json;
using System.Runtime.CompilerServices;
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

    public async Task<UpdateInfo> GetLatestUpdateAsync()
    {
        return await GetAsync<UpdateInfo>("updates/latest?platform=windows") ?? new UpdateInfo();
    }

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

    public Task<JsonObject> TickAllChannelListenersAsync(AppSettings settings)
    {
        var payload = RuntimePayload(settings);
        payload["limit"] = 10;
        payload["prepare_replies"] = true;
        return PostJsonObjectAsync("channels/listeners/tick", payload);
    }

    public Task<JsonObject> SaveChannelSetupAsync(ChannelInfo channel, ChannelSetup setup)
    {
        var payload = new JsonObject
        {
            ["channel_id"] = channel.ChannelId,
            ["enabled"] = setup.Enabled,
            ["listen_enabled"] = setup.ListenEnabled,
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

    public async Task<ModelProviderCatalog> GetModelProvidersAsync()
    {
        return await GetAsync<ModelProviderCatalog>("model/providers") ?? new ModelProviderCatalog();
    }

    public Task<JsonObject> GetVoiceStatusAsync(AppSettings settings) => PostJsonObjectAsync("voice/status", RuntimePayload(settings));

    public Task<JsonObject> StopVoicePlaybackAsync(AppSettings settings)
    {
        var payload = RuntimePayload(settings);
        payload["reason"] = "Windows app voice stop phrase.";
        return PostJsonObjectAsync("voice/stop_playback", payload);
    }

    public Task<JsonObject> GetAutonomousStatusAsync() => GetJsonObjectAsync("autonomous/status?limit=8");

    public async Task<JanusStatusResponse> GetJanusStatusAsync(int limit = 20)
    {
        return await GetAsync<JanusStatusResponse>($"janus/status?limit={limit}") ?? new JanusStatusResponse();
    }

    public Task<JsonObject> GetJanusPlannerContextAsync(string request = "")
    {
        var suffix = string.IsNullOrWhiteSpace(request) ? "" : $"?request={Uri.EscapeDataString(request)}";
        return GetJsonObjectAsync($"janus/planner-context{suffix}");
    }

    public async Task<CollectorStatusResponse> GetCollectorStatusAsync(int limit = 12)
    {
        return await GetAsync<CollectorStatusResponse>($"collectors/status?limit={limit}") ?? new CollectorStatusResponse();
    }

    public Task<JsonObject> RecordJanusCorrectionAsync(
        string correctionType,
        string targetType,
        string targetId,
        string note,
        string userDeclaredGoal = "",
        string summary = "")
    {
        var payload = new JsonObject
        {
            ["correction_type"] = correctionType,
            ["target_type"] = targetType,
            ["target_id"] = targetId,
            ["note"] = note,
            ["source"] = "windows_app",
        };
        if (correctionType == "wrong_task" && (!string.IsNullOrWhiteSpace(userDeclaredGoal) || !string.IsNullOrWhiteSpace(summary)))
        {
            payload["task_context"] = new JsonObject
            {
                ["goal"] = userDeclaredGoal.Trim(),
                ["summary"] = string.IsNullOrWhiteSpace(summary) ? userDeclaredGoal.Trim() : summary.Trim(),
                ["source"] = "windows_app",
                ["privacy_mode"] = "metadata_first",
            };
        }
        return PostJsonObjectAsync("janus/corrections", payload);
    }

    public Task<JsonObject> CreateJanusMutedScopeAsync(
        string mode,
        string collector,
        string source,
        string stimulusType,
        IEnumerable<string> entityRefs,
        string reason)
    {
        var payload = new JsonObject
        {
            ["mode"] = mode,
            ["scope_type"] = "windows_app_manual",
            ["collector"] = collector.Trim(),
            ["source"] = source.Trim(),
            ["stimulus_type"] = stimulusType.Trim(),
            ["entity_refs"] = StringArray(entityRefs),
            ["reason"] = string.IsNullOrWhiteSpace(reason) ? "User created a scoped mute from the Windows Janus panel." : reason.Trim(),
        };
        return PostJsonObjectAsync("janus/muted-scopes", payload);
    }

    public Task<JsonObject> CancelJanusMutedScopeAsync(string scopeId, string reason)
    {
        return PostJsonObjectAsync("janus/muted-scopes/cancel", new JsonObject
        {
            ["scope_id"] = scopeId,
            ["reason"] = reason,
        });
    }

    public Task<JsonObject> ApproveJanusDeepDiveAsync(string requestId, string reason)
    {
        return PostJsonObjectAsync("janus/deep-dives/approve", new JsonObject
        {
            ["request_id"] = requestId,
            ["reason"] = reason,
        });
    }

    public Task<JsonObject> RejectJanusDeepDiveAsync(string requestId, string reason)
    {
        return PostJsonObjectAsync("janus/deep-dives/reject", new JsonObject
        {
            ["request_id"] = requestId,
            ["reason"] = reason,
        });
    }

    public async Task<OutboxEnvelope> GetOutboxAsync()
    {
        return await GetAsync<OutboxEnvelope>("channels/outbox") ?? new OutboxEnvelope();
    }

    public async Task<ConnectorCatalog> GetConnectorsAsync()
    {
        return await GetAsync<ConnectorCatalog>("connectors") ?? new ConnectorCatalog();
    }

    public Task<JsonObject> ConfigureConnectorAsync(ConnectorProvider connector, IReadOnlyDictionary<string, string> credentials, string redirectUri)
    {
        var credentialObject = new JsonObject();
        foreach (var item in credentials)
        {
            if (!string.IsNullOrWhiteSpace(item.Key) && !string.IsNullOrWhiteSpace(item.Value))
            {
                credentialObject[item.Key.Trim()] = item.Value.Trim();
            }
        }
        return PostJsonObjectAsync("connectors/configure", new JsonObject
        {
            ["provider_id"] = connector.ProviderId,
            ["credentials"] = credentialObject,
            ["redirect_uri"] = redirectUri,
        });
    }

    public async Task<ConnectorAuthorization> PrepareConnectorAsync(ConnectorProvider connector)
    {
        return await PostAsync<ConnectorAuthorization>("connectors/connect", new JsonObject { ["provider_id"] = connector.ProviderId })
            ?? new ConnectorAuthorization();
    }

    public Task<JsonObject> RefreshConnectorAsync(ConnectorProvider connector)
    {
        return PostJsonObjectAsync("connectors/refresh", new JsonObject { ["provider_id"] = connector.ProviderId });
    }

    public Task<JsonObject> DisconnectConnectorAsync(ConnectorProvider connector)
    {
        return PostJsonObjectAsync("connectors/disconnect", new JsonObject { ["provider_id"] = connector.ProviderId });
    }

    public async Task<List<RuntimeRunItem>> GetRunsAsync()
    {
        return await GetAsync<List<RuntimeRunItem>>("runs?limit=20") ?? [];
    }

    public async Task<List<ChatConversationItem>> GetChatConversationsAsync()
    {
        var envelope = await GetAsync<ChatConversationEnvelope>("chats?limit=80") ?? new ChatConversationEnvelope();
        return envelope.Conversations;
    }

    public async Task<ChatConversationItem> CreateChatAsync(string title = "New chat")
    {
        var response = await PostAsync<ChatConversationResponse>("chats", new JsonObject
        {
            ["title"] = title,
            ["source"] = "windows_app",
            ["metadata"] = new JsonObject { ["client"] = "windows" },
        }) ?? new ChatConversationResponse();
        return response.Conversation;
    }

    public async Task<ChatMessagesEnvelope> GetChatMessagesAsync(string conversationId)
    {
        return await GetAsync<ChatMessagesEnvelope>($"chats/{Uri.EscapeDataString(conversationId)}/messages?limit=300") ?? new ChatMessagesEnvelope();
    }

    public async Task<ChatRunQueuedResponse> StartChatRunAsync(string conversationId, string text, string source, string responseMode, AppSettings settings)
    {
        var payload = RuntimePayload(settings);
        payload["request"] = text;
        payload["display_text"] = text;
        payload["source"] = source;
        payload["response_mode"] = responseMode;
        payload["metadata"] = new JsonObject
        {
            ["response_mode"] = responseMode,
            ["tts_provider"] = settings.TtsProvider,
            ["voice_id"] = settings.VoiceId,
            ["client"] = "windows",
        };
        return await PostAsync<ChatRunQueuedResponse>($"chats/{Uri.EscapeDataString(conversationId)}/runs/async", payload) ?? new ChatRunQueuedResponse();
    }

    public async Task<List<JsonObject>> GetRunTimelineAsync(string runId)
    {
        return await GetAsync<List<JsonObject>>($"runs/{Uri.EscapeDataString(runId)}/timeline?limit=80") ?? [];
    }

    public async Task<List<ApprovalItem>> GetApprovalsAsync(string status = "pending")
    {
        return await GetAsync<List<ApprovalItem>>($"approvals?status={Uri.EscapeDataString(status)}&limit=20") ?? [];
    }

    public Task<JsonObject> ApproveAsync(string approvalToken, string note)
    {
        return PostJsonObjectAsync($"approvals/{Uri.EscapeDataString(approvalToken)}/approve", new JsonObject { ["note"] = note });
    }

    public Task<JsonObject> RejectAsync(string approvalToken, string note)
    {
        return PostJsonObjectAsync($"approvals/{Uri.EscapeDataString(approvalToken)}/reject", new JsonObject { ["note"] = note });
    }

    public Task<JsonObject> CancelRunAsync(string runId, string reason)
    {
        return PostJsonObjectAsync($"runs/{Uri.EscapeDataString(runId)}/cancel", new JsonObject { ["reason"] = reason });
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

    public async IAsyncEnumerable<AgentStreamEvent> StreamStimulusAsync(
        string text,
        string source,
        string responseMode,
        AppSettings settings,
        [EnumeratorCancellation] CancellationToken cancellationToken = default)
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

        using var request = new HttpRequestMessage(HttpMethod.Post, new Uri(_baseUri, "stimuli/stream"))
        {
            Content = new StringContent(payload.ToJsonString(JsonOptions), Encoding.UTF8, "application/json"),
        };
        using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        await EnsureSuccessAsync(response, "stimuli/stream");
        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        using var reader = new StreamReader(stream, Encoding.UTF8);
        var eventName = "message";
        var dataLines = new List<string>();
        while (!reader.EndOfStream && !cancellationToken.IsCancellationRequested)
        {
            var line = await reader.ReadLineAsync(cancellationToken) ?? "";
            if (line.StartsWith("event: ", StringComparison.Ordinal))
            {
                eventName = line["event: ".Length..].Trim();
                continue;
            }
            if (line.StartsWith("data: ", StringComparison.Ordinal))
            {
                dataLines.Add(line["data: ".Length..]);
                continue;
            }
            if (line.Length == 0 && dataLines.Count > 0)
            {
                var data = JsonNode.Parse(string.Join(Environment.NewLine, dataLines)) as JsonObject ?? [];
                yield return new AgentStreamEvent { Event = eventName, Data = data };
                eventName = "message";
                dataLines.Clear();
            }
        }
        if (dataLines.Count > 0)
        {
            var data = JsonNode.Parse(string.Join(Environment.NewLine, dataLines)) as JsonObject ?? [];
            yield return new AgentStreamEvent { Event = eventName, Data = data };
        }
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
            ["planner"] = AppRuntimeDefaults.EffectivePlanner(settings.Planner),
            ["approve_high_risk"] = settings.ApproveHighRisk,
            ["model_provider"] = AppRuntimeDefaults.EffectiveModelProvider(settings.ModelProvider),
            ["model"] = AppRuntimeDefaults.EffectiveModelName(settings.ModelName),
            ["model_api_key_env"] = AppRuntimeDefaults.ModelApiKeyName(settings.ModelProvider),
        };
        if (!string.IsNullOrWhiteSpace(settings.ModelBaseUrl))
        {
            payload["model_base_url"] = settings.ModelBaseUrl;
        }
        var activeProvider = AppRuntimeDefaults.EffectiveJanusModelProvider(settings.JanusModelProvider);
        if (!activeProvider.Equals("same-as-main", StringComparison.OrdinalIgnoreCase))
        {
            payload["janus_model_provider"] = AppRuntimeDefaults.CliJanusModelProvider(activeProvider);
            payload["janus_model_api_key_env"] = AppRuntimeDefaults.ModelApiKeyName(activeProvider);
            if (!string.IsNullOrWhiteSpace(settings.JanusModelName))
            {
                payload["janus_model"] = settings.JanusModelName;
            }
            if (!string.IsNullOrWhiteSpace(settings.JanusModelBaseUrl))
            {
                payload["janus_model_base_url"] = settings.JanusModelBaseUrl;
            }
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
        AddSecret(secrets, AppRuntimeDefaults.ModelApiKeyName(settings.ModelProvider), settings.ModelApiKey);
        var activeProvider = AppRuntimeDefaults.EffectiveJanusModelProvider(settings.JanusModelProvider);
        if (!activeProvider.Equals("same-as-main", StringComparison.OrdinalIgnoreCase))
        {
            AddSecret(secrets, AppRuntimeDefaults.ModelApiKeyName(activeProvider), settings.JanusModelApiKey);
        }
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

    private async Task<T?> PostAsync<T>(string route, JsonObject payload)
    {
        using var content = new StringContent(payload.ToJsonString(JsonOptions), Encoding.UTF8, "application/json");
        using var response = await _http.PostAsync(new Uri(_baseUri, route), content);
        await EnsureSuccessAsync(response, route);
        return await response.Content.ReadFromJsonAsync<T>(JsonOptions);
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
