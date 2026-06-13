import Foundation

struct RuntimeSecrets {
    var modelAPIKey = ""
    var janusModelAPIKey = ""
    var deepgramAPIKey = ""
    var elevenLabsAPIKey = ""
}

@MainActor
final class AgentAPIClient {
    private var baseURL: URL
    private let decoder: JSONDecoder
    private let encoder = JSONEncoder()
    private let responseFormattingInstruction = """
    Respond with a detailed final answer in GitHub-flavored Markdown. Use clear sections, bullets, and tables where they make the answer easier to scan. Include caveats, source/tool evidence, and next steps when relevant. Do not return a single unformatted paragraph unless the user explicitly asks for a very short answer.
    """
    private let voiceResponseFormattingInstruction = """
    The user is speaking by voice. Reply warmly and conversationally in a voice-friendly style: lead with the direct answer, keep sentences short, use short paragraphs, avoid tables unless essential, and use bullets only when they make the spoken answer clearer. Keep the final answer easy to read aloud.
    """

    init(baseURL: String) {
        self.baseURL = AgentAPIClient.normalizedBaseURL(baseURL)
        decoder = JSONDecoder()
    }

    func setBaseURL(_ value: String) {
        baseURL = AgentAPIClient.normalizedBaseURL(value, fallback: baseURL)
    }

    func health() async throws -> HealthPayload {
        try await get("health")
    }

    func systemStatus() async throws -> JSONValue {
        try await get("system/status")
    }

    func latestUpdate() async throws -> UpdateInfo {
        try await get("updates/latest?platform=macos")
    }

    func tools() async throws -> ToolCatalog {
        try await get("tools")
    }

    func modelProviders() async throws -> ModelProviderCatalog {
        try await get("model/providers")
    }

    func runs() async throws -> [RunItem] {
        try await get("runs?limit=30")
    }

    func approvals() async throws -> [ApprovalItem] {
        try await get("approvals?status=pending&limit=30")
    }

    func channels() async throws -> [ChannelInfo] {
        try await get("channels")
    }

    func connectors() async throws -> ConnectorCatalog {
        try await get("connectors")
    }

    func configureConnector(providerID: String, clientID: String, clientSecret: String, redirectURI: String) async throws -> JSONValue {
        try await post(
            "connectors/configure",
            body: [
                "provider_id": providerID,
                "client_id": clientID,
                "client_secret": clientSecret,
                "redirect_uri": redirectURI
            ]
        )
    }

    func prepareConnector(providerID: String) async throws -> ConnectorAuthorization {
        try await post("connectors/connect", body: ["provider_id": providerID])
    }

    func refreshConnector(providerID: String) async throws -> JSONValue {
        try await post("connectors/refresh", body: ["provider_id": providerID])
    }

    func disconnectConnector(providerID: String) async throws -> JSONValue {
        try await post("connectors/disconnect", body: ["provider_id": providerID])
    }

    func outbox() async throws -> OutboxEnvelope {
        try await get("channels/outbox")
    }

    func channelStatus(channelID: String, settings: AppSettings, secrets: RuntimeSecrets) async throws -> JSONValue {
        var payload = runtimePayload(settings: settings, secrets: secrets)
        payload["channel_id"] = channelID
        return try await post("channels/status", body: payload)
    }

    func channelDoctor(channelID: String, settings: AppSettings, secrets: RuntimeSecrets) async throws -> JSONValue {
        var payload = runtimePayload(settings: settings, secrets: secrets)
        payload["channel_id"] = channelID
        return try await post("channels/doctor", body: payload)
    }

    func channelRequirements(channelID: String) async throws -> JSONValue {
        try await get("channels/requirements?channel_id=\(Self.urlEncode(channelID))")
    }

    func runChannelSmoke(channelID: String, settings: AppSettings, secrets: RuntimeSecrets) async throws -> JSONValue {
        var payload = runtimePayload(settings: settings, secrets: secrets)
        payload["channel_id"] = channelID
        payload["prepare_messages"] = true
        payload["dry_run_sends"] = true
        return try await post("channels/smoke", body: payload)
    }

    func channelListeners(channelID: String, settings: AppSettings, secrets: RuntimeSecrets) async throws -> JSONValue {
        var payload = runtimePayload(settings: settings, secrets: secrets)
        payload["channel_id"] = channelID
        return try await post("channels/listeners", body: payload)
    }

    func tickChannelListener(channelID: String, settings: AppSettings, secrets: RuntimeSecrets) async throws -> JSONValue {
        var payload = runtimePayload(settings: settings, secrets: secrets)
        payload["channel_id"] = channelID
        payload["limit"] = 10
        payload["prepare_replies"] = true
        return try await post("channels/listeners/tick", body: payload)
    }

    func tickAllChannelListeners(settings: AppSettings, secrets: RuntimeSecrets) async throws -> JSONValue {
        var payload = runtimePayload(settings: settings, secrets: secrets)
        payload["limit"] = 10
        payload["prepare_replies"] = true
        return try await post("channels/listeners/tick", body: payload)
    }

    func saveChannelSetup(channel: ChannelInfo, setup: ChannelSetup) async throws -> JSONValue {
        let payload: [String: Any] = [
            "channel_id": channel.channelId,
            "enabled": setup.enabled,
            "listen_enabled": setup.listenEnabled,
            "conversation_defaults": [
                "conversation_id": setup.conversationId,
                "conversation_type": setup.conversationType
            ],
            "secret_refs": channelSecretRefs(setup),
            "secret_configured": channelSecretConfigured(setup),
            "allowlist": cleanList(setup.allowlist),
            "group_allowlist": cleanList(setup.groupAllowlist),
            "notes": setup.notes
        ]
        return try await post("channels/setup", body: payload)
    }

    func prepareChannelMessage(channel: ChannelInfo, setup: ChannelSetup, text: String, settings: AppSettings, secrets: RuntimeSecrets) async throws -> JSONValue {
        var payload = runtimePayload(settings: settings, secrets: secrets)
        payload["channel_id"] = channel.channelId
        payload["conversation_id"] = setup.conversationId.isEmpty ? "mac-app-preview" : setup.conversationId
        payload["text"] = text
        payload["reason"] = "Prepared from the macOS app channel panel."
        payload["metadata"] = [
            "source": "macos_app",
            "conversation_type": setup.conversationType
        ]
        return try await post("channels/message/prepare", body: payload)
    }

    func sendChannelMessage(channel: ChannelInfo, setup: ChannelSetup, text: String, settings: AppSettings, secrets: RuntimeSecrets) async throws -> JSONValue {
        var payload = runtimePayload(settings: settings, secrets: secrets)
        payload["channel_id"] = channel.channelId
        payload["conversation_id"] = setup.conversationId.isEmpty ? "mac-app-preview" : setup.conversationId
        payload["text"] = text
        payload["reason"] = "Approval-gated send from the macOS app channel panel."
        payload["approve_high_risk"] = settings.approveHighRisk
        payload["metadata"] = [
            "source": "macos_app",
            "conversation_type": setup.conversationType
        ]
        return try await post("channels/message/send", body: payload)
    }

    func sendChannelInbound(channel: ChannelInfo, setup: ChannelSetup, text: String, settings: AppSettings, secrets: RuntimeSecrets) async throws -> JSONValue {
        var payload = runtimePayload(settings: settings, secrets: secrets)
        payload["channel_id"] = channel.channelId
        payload["conversation_id"] = setup.conversationId.isEmpty ? "mac-app-preview" : setup.conversationId
        payload["conversation_type"] = setup.conversationType.isEmpty ? "dm" : setup.conversationType
        payload["sender_id"] = "macos-app"
        payload["text"] = text
        payload["requires_response"] = true
        payload["prepare_reply"] = true
        return try await post("channels/inbound", body: payload)
    }

    func voiceStatus(settings: AppSettings, secrets: RuntimeSecrets) async throws -> JSONValue {
        try await post("voice/status", body: runtimePayload(settings: settings, secrets: secrets))
    }

    func speakText(_ text: String, settings: AppSettings, secrets: RuntimeSecrets) async throws -> JSONValue {
        var payload = runtimePayload(settings: settings, secrets: secrets)
        payload["text"] = text
        payload["provider"] = settings.ttsProvider
        payload["voice_id"] = settings.voiceId
        payload["model"] = settings.elevenLabsModel
        payload["reason"] = "macOS app is speaking the visible assistant response."
        payload["playback"] = true
        return try await post("voice/speak", body: payload)
    }

    func transcribeAudio(_ audioURL: URL, settings: AppSettings, secrets: RuntimeSecrets) async throws -> String {
        let audioData = try Data(contentsOf: audioURL)
        var payload = runtimePayload(settings: settings, secrets: secrets)
        payload["audio_base64"] = audioData.base64EncodedString()
        payload["filename"] = audioURL.lastPathComponent
        payload["provider"] = settings.sttProvider == "deepgram" ? "deepgram" : "local-whisper"
        payload["smart_format"] = true
        payload["mime_type"] = "audio/mp4"
        payload["reason"] = "macOS wake listener captured the user's post-wake task."
        let result: JSONValue = try await post("voice/transcribe", body: payload)
        let transcript = result["transcript"]?.stringValue?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        guard !transcript.isEmpty else {
            let summary = result["summary"]?.stringValue ?? "No transcript was returned."
            let providerErrors = result["provider_errors"]?.arrayValue?.compactMap { item in
                item["error"]?.stringValue
            }.joined(separator: " ")
            let detail = providerErrors?.isEmpty == false ? "\(summary) \(providerErrors ?? "")" : summary
            throw AgentAPIError.requestFailed(detail)
        }
        return transcript
    }

    func autonomousStatus() async throws -> JSONValue {
        try await get("autonomous/status?limit=10")
    }

    func janusStatus(limit: Int = 20) async throws -> JanusStatusResponse {
        try await get("janus/status?limit=\(limit)")
    }

    func janusPlannerContext(request: String = "") async throws -> JanusPlannerContextPreview {
        let encoded = request.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
        return try await get("janus/planner-context?request=\(encoded)")
    }

    func collectorStatus(limit: Int = 10) async throws -> CollectorStatusResponse {
        try await get("collectors/status?limit=\(limit)")
    }

    func declareJanusTaskContext(_ draft: JanusTaskContextDraft) async throws -> JSONValue {
        var payload: [String: Any] = [
            "goal": draft.goal,
            "summary": draft.summary,
            "privacy_mode": draft.privacyMode,
            "allowed_help": draft.allowedHelpList,
            "source": "macos_app"
        ]
        removeEmptyStrings(from: &payload)
        return try await post("janus/task-contexts", body: payload)
    }

    func createJanusMutedScope(_ draft: JanusMutedScopeDraft) async throws -> JSONValue {
        var payload: [String: Any] = [
            "mode": draft.mode,
            "scope_type": draft.scopeType,
            "entity_refs": draft.entityRefList,
            "collector": draft.collector,
            "source": draft.source,
            "stimulus_type": draft.stimulusType,
            "expires_at": draft.expiresAt,
            "reason": draft.reason
        ]
        removeEmptyStrings(from: &payload)
        return try await post("janus/muted-scopes", body: payload)
    }

    func approveJanusDeepDive(requestID: String, reason: String) async throws -> JSONValue {
        try await post(
            "janus/deep-dives/approve",
            body: [
                "request_id": requestID,
                "reason": reason
            ]
        )
    }

    func rejectJanusDeepDive(requestID: String, reason: String) async throws -> JSONValue {
        try await post(
            "janus/deep-dives/reject",
            body: [
                "request_id": requestID,
                "reason": reason
            ]
        )
    }

    func recordJanusCorrection(
        correctionType: String,
        targetType: String,
        targetID: String,
        note: String,
        taskContext: JanusTaskContextDraft? = nil,
        mutedScope: JanusMutedScopeDraft? = nil
    ) async throws -> JSONValue {
        var payload: [String: Any] = [
            "correction_type": correctionType,
            "target_type": targetType,
            "target_id": targetID,
            "note": note
        ]
        if let taskContext, taskContext.hasContext {
            payload["goal"] = taskContext.goal
            payload["summary"] = taskContext.summary
            payload["privacy_mode"] = taskContext.privacyMode
            payload["allowed_help"] = taskContext.allowedHelpList
        }
        if let mutedScope, mutedScope.hasScope {
            payload["mode"] = mutedScope.mode
            payload["scope_type"] = mutedScope.scopeType
            payload["entity_refs"] = mutedScope.entityRefList
            payload["collector"] = mutedScope.collector
            payload["source"] = mutedScope.source
            payload["stimulus_type"] = mutedScope.stimulusType
            payload["expires_at"] = mutedScope.expiresAt
        }
        removeEmptyStrings(from: &payload)
        return try await post(
            "janus/corrections",
            body: payload
        )
    }

    func cancelJanusMutedScope(scopeID: String, reason: String) async throws -> JSONValue {
        try await post(
            "janus/muted-scopes/cancel",
            body: [
                "scope_id": scopeID,
                "reason": reason
            ]
        )
    }

    func runAutonomousCycle(settings: AppSettings, secrets: RuntimeSecrets) async throws -> JSONValue {
        var payload = runtimePayload(settings: settings, secrets: secrets)
        payload["max_cycles"] = settings.maxCycles
        payload["idle_sleep_seconds"] = 0
        payload["stop_after_idle_cycles"] = 1
        payload["allow_initiative"] = settings.allowInitiative
        return try await post("autonomous/cycles", body: payload)
    }

    func sendStimulus(_ text: String, source: String, responseMode: String, settings: AppSettings, secrets: RuntimeSecrets) async throws -> AgentRunResponse {
        var payload = runtimePayload(settings: settings, secrets: secrets)
        let voiceFriendly = isVoiceRequest(source: source, responseMode: responseMode)
        payload["text"] = formattedRequestText(text, source: source, responseMode: responseMode)
        payload["source"] = source
        payload["response_mode"] = responseMode
        payload["metadata"] = [
            "response_mode": responseMode,
            "tts_provider": settings.ttsProvider,
            "voice_id": settings.voiceId,
            "response_format": "markdown",
            "response_detail": voiceFriendly ? "voice_friendly" : "detailed",
            "response_style": voiceFriendly ? "spoken_conversation" : "written_markdown"
        ]
        return try await post("stimuli", body: payload)
    }

    func streamStimulus(_ text: String, source: String, responseMode: String, settings: AppSettings, secrets: RuntimeSecrets) throws -> AsyncThrowingStream<AgentStreamEvent, Error> {
        var payload = runtimePayload(settings: settings, secrets: secrets)
        let voiceFriendly = isVoiceRequest(source: source, responseMode: responseMode)
        payload["text"] = formattedRequestText(text, source: source, responseMode: responseMode)
        payload["source"] = source
        payload["response_mode"] = responseMode
        payload["metadata"] = [
            "response_mode": responseMode,
            "tts_provider": settings.ttsProvider,
            "voice_id": settings.voiceId,
            "response_format": "markdown",
            "response_detail": voiceFriendly ? "voice_friendly" : "detailed",
            "response_style": voiceFriendly ? "spoken_conversation" : "written_markdown"
        ]

        var request = URLRequest(url: try routeURL("stimuli/stream"))
        request.httpMethod = "POST"
        request.timeoutInterval = 300
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: payload, options: [])

        return AsyncThrowingStream { continuation in
            let streamTask = Task {
                do {
                    let (bytes, response) = try await URLSession.shared.bytes(for: request)
                    if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
                        throw AgentAPIError.requestFailed("stimuli/stream failed with HTTP \(http.statusCode).")
                    }
                    var parser = ServerSentEventParser()
                    for try await line in bytes.lines {
                        if Task.isCancelled { break }
                        if let event = try parser.consume(line) {
                            continuation.yield(event)
                        }
                    }
                    if Task.isCancelled {
                        continuation.finish(throwing: CancellationError())
                        return
                    }
                    if let event = try parser.finish() {
                        continuation.yield(event)
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in
                streamTask.cancel()
            }
        }
    }

    func approve(_ token: String, note: String) async throws -> JSONValue {
        try await post("approvals/\(token)/approve", body: ["note": note])
    }

    func reject(_ token: String, note: String) async throws -> JSONValue {
        try await post("approvals/\(token)/reject", body: ["note": note])
    }

    func cancelRun(_ runID: String, reason: String) async throws -> JSONValue {
        try await post("runs/\(runID)/cancel", body: ["reason": reason])
    }

    func runTimeline(_ runID: String) async throws -> JSONValue {
        try await get("runs/\(runID)/timeline?limit=100")
    }

    private func get<T: Decodable>(_ route: String) async throws -> T {
        let request = URLRequest(url: try routeURL(route))
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response: response, data: data)
        return try decoder.decode(T.self, from: data)
    }

    private func post<T: Decodable>(_ route: String, body: [String: Any]) async throws -> T {
        var request = URLRequest(url: try routeURL(route))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body, options: [])
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response: response, data: data)
        return try decoder.decode(T.self, from: data)
    }

    private func routeURL(_ route: String) throws -> URL {
        guard let url = URL(string: route, relativeTo: baseURL)?.absoluteURL else {
            throw AgentAPIError.requestFailed("Invalid API route: \(route)")
        }
        return url
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            let message = String(data: data, encoding: .utf8) ?? "Request failed."
            throw AgentAPIError.requestFailed(message)
        }
    }

    private func formattedRequestText(_ text: String, source: String, responseMode: String) -> String {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return text }
        let instruction = isVoiceRequest(source: source, responseMode: responseMode)
            ? voiceResponseFormattingInstruction
            : responseFormattingInstruction
        return """
        \(trimmed)

        Response formatting requirements:
        \(instruction)
        """
    }

    private func isVoiceRequest(source: String, responseMode: String) -> Bool {
        let normalizedSource = source.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let normalizedMode = responseMode.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return normalizedSource.contains("voice") || normalizedMode.contains("voice")
    }

    private func runtimePayload(settings: AppSettings, secrets: RuntimeSecrets) -> [String: Any] {
        var payload: [String: Any] = [
            "planner": settings.planner,
            "approve_high_risk": settings.approveHighRisk,
            "model_provider": apiModelProvider(settings.modelProvider),
            "model": settings.modelName,
            "model_api_key_env": modelKeyName(settings.modelProvider)
        ]
        if !settings.modelBaseURL.isEmpty {
            payload["model_base_url"] = settings.modelBaseURL
        }
        let activeProvider = settings.janusModelProvider.trimmingCharacters(in: .whitespacesAndNewlines)
        if !activeProvider.isEmpty, activeProvider != "same-as-main" {
            payload["janus_model_provider"] = apiModelProvider(activeProvider)
            payload["janus_model_api_key_env"] = modelKeyName(activeProvider)
            if !settings.janusModelName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                payload["janus_model"] = settings.janusModelName
            }
            if !settings.janusModelBaseURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                payload["janus_model_base_url"] = settings.janusModelBaseURL
            }
        }

        var secretPayload: [String: String] = [:]
        addSecret(&secretPayload, name: modelKeyName(settings.modelProvider), value: secrets.modelAPIKey)
        if !activeProvider.isEmpty, activeProvider != "same-as-main" {
            addSecret(&secretPayload, name: modelKeyName(activeProvider), value: secrets.janusModelAPIKey)
        }
        addSecret(&secretPayload, name: "DEEPGRAM_API_KEY", value: secrets.deepgramAPIKey)
        addSecret(&secretPayload, name: "ELEVENLABS_API_KEY", value: secrets.elevenLabsAPIKey)
        addSecret(&secretPayload, name: "ELEVENLABS_VOICE_ID", value: settings.voiceId)
        addSecret(&secretPayload, name: "ELEVENLABS_MODEL_ID", value: settings.elevenLabsModel)
        for channel in settings.channels {
            addSecret(&secretPayload, name: channel.secretName, value: channel.secretValue)
            for item in channel.secretValues {
                addSecret(&secretPayload, name: item.key, value: item.value)
            }
        }
        if !secretPayload.isEmpty {
            payload["runtime_secrets"] = secretPayload
        }
        return payload
    }

    private func addSecret(_ secrets: inout [String: String], name: String, value: String) {
        let cleanName = name.trimmingCharacters(in: .whitespacesAndNewlines)
        let cleanValue = value.trimmingCharacters(in: .whitespacesAndNewlines)
        if !cleanName.isEmpty, !cleanValue.isEmpty {
            secrets[cleanName] = cleanValue
        }
    }

    private func modelKeyName(_ provider: String) -> String {
        switch provider {
        case "openrouter": "OPENROUTER_API_KEY"
        case "nous": "NOUS_API_KEY"
        case "novita": "NOVITA_API_KEY"
        case "lmstudio": "LM_API_KEY"
        case "anthropic": "ANTHROPIC_API_KEY"
        case "alibaba": "DASHSCOPE_API_KEY"
        case "groq": "GROQ_API_KEY"
        case "grok", "xai": "XAI_API_KEY"
        case "gemini": "GOOGLE_API_KEY"
        case "deepseek": "DEEPSEEK_API_KEY"
        case "mistral": "MISTRAL_API_KEY"
        case "cerebras": "CEREBRAS_API_KEY"
        case "ollama": "OLLAMA_API_KEY"
        case "ollama-cloud": "OLLAMA_API_KEY"
        case "local-openai": "LOCAL_LLM_API_KEY"
        case "vercel": "AI_GATEWAY_API_KEY"
        case "litellm": "LITELLM_API_KEY"
        case "nvidia": "NVIDIA_API_KEY"
        case "huggingface": "HF_TOKEN"
        case "zai": "GLM_API_KEY"
        case "kimi-coding": "KIMI_API_KEY"
        case "kimi-coding-cn": "KIMI_CN_API_KEY"
        case "stepfun": "STEPFUN_API_KEY"
        case "minimax": "MINIMAX_API_KEY"
        case "minimax-cn": "MINIMAX_CN_API_KEY"
        case "arcee": "ARCEEAI_API_KEY"
        case "gmi": "GMI_API_KEY"
        case "xiaomi": "XIAOMI_API_KEY"
        case "tencent-tokenhub": "TOKENHUB_API_KEY"
        case "opencode-zen": "OPENCODE_ZEN_API_KEY"
        case "opencode-go": "OPENCODE_GO_API_KEY"
        case "kilocode": "KILOCODE_API_KEY"
        case "azure-openai": "AZURE_OPENAI_API_KEY"
        case "azure-foundry": "AZURE_FOUNDRY_API_KEY"
        case "copilot", "copilot-acp": "GITHUB_TOKEN"
        case "bedrock": "AWS_ACCESS_KEY_ID"
        case "browser-use-cloud": "BROWSER_USE_API_KEY"
        default: "OPENAI_API_KEY"
        }
    }

    private func apiModelProvider(_ provider: String) -> String {
        provider == "openai" ? "openai-responses" : provider
    }

    private func channelSecretRefs(_ setup: ChannelSetup) -> [String: String] {
        var refs: [String: String] = [:]
        let primary = setup.secretName.trimmingCharacters(in: .whitespacesAndNewlines)
        if !primary.isEmpty {
            refs["primary"] = primary
        }
        for name in setup.secretNames + Array(setup.secretValues.keys) {
            let cleanName = name.trimmingCharacters(in: .whitespacesAndNewlines)
            if !cleanName.isEmpty, cleanName.localizedCaseInsensitiveCompare(primary) != .orderedSame {
                refs[cleanName] = cleanName
            }
        }
        return refs
    }

    private func channelSecretConfigured(_ setup: ChannelSetup) -> [String: Bool] {
        var configured: [String: Bool] = [:]
        let primary = setup.secretName.trimmingCharacters(in: .whitespacesAndNewlines)
        if !primary.isEmpty {
            configured["primary"] = setup.secretConfigured || !setup.secretValue.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }
        for name in setup.secretNames + Array(setup.secretValues.keys) {
            let cleanName = name.trimmingCharacters(in: .whitespacesAndNewlines)
            if !cleanName.isEmpty, cleanName.localizedCaseInsensitiveCompare(primary) != .orderedSame {
                configured[cleanName] = !setup.secretValues[cleanName, default: ""].trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            }
        }
        return configured
    }

    private func cleanList(_ values: [String]) -> [String] {
        values.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty }
    }

    private func removeEmptyStrings(from payload: inout [String: Any]) {
        for (key, value) in payload {
            if let string = value as? String, string.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                payload.removeValue(forKey: key)
            }
            if let strings = value as? [String], strings.isEmpty {
                payload.removeValue(forKey: key)
            }
        }
    }

    private static func normalizedBaseURL(_ value: String, fallback: URL = URL(string: "http://127.0.0.1:8765/")!) -> URL {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard !trimmed.isEmpty, let url = URL(string: "\(trimmed)/") else {
            return fallback
        }
        return url
    }

    private static func urlEncode(_ value: String) -> String {
        value.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? value
    }
}

enum AgentAPIError: LocalizedError {
    case requestFailed(String)

    var errorDescription: String? {
        switch self {
        case .requestFailed(let message): message
        }
    }
}

private struct ServerSentEventParser {
    private var eventName = "message"
    private var dataLines: [String] = []
    private let decoder = JSONDecoder()

    mutating func consume(_ line: String) throws -> AgentStreamEvent? {
        if line.hasPrefix("event: ") {
            eventName = String(line.dropFirst("event: ".count)).trimmingCharacters(in: .whitespaces)
            return nil
        }
        if line.hasPrefix("data: ") {
            dataLines.append(String(line.dropFirst("data: ".count)))
            return try finish()
        }
        if line.isEmpty {
            return try finish()
        }
        return nil
    }

    mutating func finish() throws -> AgentStreamEvent? {
        guard !dataLines.isEmpty else { return nil }
        let data = Data(dataLines.joined(separator: "\n").utf8)
        let value = try decoder.decode(JSONValue.self, from: data)
        let event = AgentStreamEvent(event: eventName, data: value)
        eventName = "message"
        dataLines = []
        return event
    }
}
