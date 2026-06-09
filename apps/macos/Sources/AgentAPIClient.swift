import Foundation

struct RuntimeSecrets {
    var modelAPIKey = ""
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

    func tools() async throws -> ToolCatalog {
        try await get("tools")
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

    func autonomousStatus() async throws -> JSONValue {
        try await get("autonomous/status?limit=10")
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
        payload["text"] = formattedRequestText(text)
        payload["source"] = source
        payload["response_mode"] = responseMode
        payload["metadata"] = [
            "response_mode": responseMode,
            "tts_provider": settings.ttsProvider,
            "voice_id": settings.voiceId,
            "response_format": "markdown",
            "response_detail": "detailed"
        ]
        return try await post("stimuli", body: payload)
    }

    func streamStimulus(_ text: String, source: String, responseMode: String, settings: AppSettings, secrets: RuntimeSecrets) throws -> AsyncThrowingStream<AgentStreamEvent, Error> {
        var payload = runtimePayload(settings: settings, secrets: secrets)
        payload["text"] = formattedRequestText(text)
        payload["source"] = source
        payload["response_mode"] = responseMode
        payload["metadata"] = [
            "response_mode": responseMode,
            "tts_provider": settings.ttsProvider,
            "voice_id": settings.voiceId,
            "response_format": "markdown",
            "response_detail": "detailed"
        ]

        var request = URLRequest(url: try routeURL("stimuli/stream"))
        request.httpMethod = "POST"
        request.timeoutInterval = 300
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: payload, options: [])

        return AsyncThrowingStream { continuation in
            Task {
                do {
                    let (bytes, response) = try await URLSession.shared.bytes(for: request)
                    if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
                        throw AgentAPIError.requestFailed("stimuli/stream failed with HTTP \(http.statusCode).")
                    }
                    var parser = ServerSentEventParser()
                    for try await line in bytes.lines {
                        if let event = try parser.consume(line) {
                            continuation.yield(event)
                        }
                    }
                    if let event = try parser.finish() {
                        continuation.yield(event)
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
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

    private func formattedRequestText(_ text: String) -> String {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return text }
        return """
        \(trimmed)

        Response formatting requirements:
        \(responseFormattingInstruction)
        """
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

        var secretPayload: [String: String] = [:]
        addSecret(&secretPayload, name: modelKeyName(settings.modelProvider), value: secrets.modelAPIKey)
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
        case "groq": "GROQ_API_KEY"
        case "grok": "XAI_API_KEY"
        case "ollama": "OLLAMA_API_KEY"
        case "local-openai": "LOCAL_LLM_API_KEY"
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
