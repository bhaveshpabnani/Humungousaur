import Foundation

struct ChatMessage: Identifiable, Equatable {
    enum Role {
        case user
        case assistant
        case system
        case error
    }

    let id = UUID()
    var role: Role
    var text: String
    var date = Date()
    var activities: [StreamActivityItem] = []
    var isStreaming = false
}

struct StreamActivityItem: Identifiable, Equatable {
    let id = UUID()
    var kind: String
    var title: String
    var detail: String
    var status: String = ""
    var date = Date()
}

struct AgentStreamEvent: Identifiable, Equatable {
    let id = UUID()
    var event: String
    var data: JSONValue
}

struct HealthPayload: Decodable {
    var status: String
    var workspace: String
    var system: SystemPayload?
}

struct SystemPayload: Decodable {
    var overallStatus: String?
    var platform: [String: String]?
    var warnings: [String]?

    enum CodingKeys: String, CodingKey {
        case overallStatus = "overall_status"
        case platform
        case warnings
    }
}

struct ToolCatalog: Decodable {
    var toolCount: Int
    var groups: [ToolGroup]
    var tools: [ToolInfo]

    enum CodingKeys: String, CodingKey {
        case toolCount = "tool_count"
        case groups
        case tools
    }
}

struct ToolGroup: Decodable, Identifiable {
    var id: String { name }
    var name: String
    var toolCount: Int

    enum CodingKeys: String, CodingKey {
        case name
        case toolCount = "tool_count"
    }

    var displayName: String {
        name.humanizedIdentifier
    }
}

struct ToolInfo: Decodable, Identifiable {
    var id: String { name }
    var name: String
    var description: String
    var riskLevel: String
    var requiresApproval: Bool
    var capabilityGroup: String

    enum CodingKeys: String, CodingKey {
        case name
        case description
        case riskLevel = "risk_level"
        case requiresApproval = "requires_approval"
        case capabilityGroup = "capability_group"
    }

    var displayName: String {
        name.humanizedIdentifier
    }

    var displayGroup: String {
        capabilityGroup.humanizedIdentifier
    }

    var permissionSummary: String {
        requiresApproval ? "Needs permission" : "Ready to use"
    }
}

struct ModelProviderCatalog: Decodable {
    var providerCount: Int
    var providers: [ModelProviderInfo]
    var transports: [String]

    static let empty = ModelProviderCatalog(providerCount: 0, providers: [], transports: [])

    enum CodingKeys: String, CodingKey {
        case providerCount = "provider_count"
        case providers
        case transports
    }
}

struct ModelProviderInfo: Decodable, Identifiable, Equatable {
    var id: String { providerId }
    var providerId: String
    var label: String
    var transport: String
    var defaultModel: String
    var modelEnv: String
    var apiKeyEnvs: [String]
    var baseUrlEnv: String
    var defaultBaseUrl: String
    var aliases: [String]

    enum CodingKeys: String, CodingKey {
        case providerId = "provider_id"
        case label
        case transport
        case defaultModel = "default_model"
        case modelEnv = "model_env"
        case apiKeyEnvs = "api_key_envs"
        case baseUrlEnv = "base_url_env"
        case defaultBaseUrl = "default_base_url"
        case aliases
    }
}

struct RunItem: Decodable, Identifiable, Hashable {
    var id: String { runId }
    var runId: String
    var request: String
    var status: String
    var startedAt: String
    var finishedAt: String?
    var finalResponse: String?

    enum CodingKeys: String, CodingKey {
        case runId = "run_id"
        case request
        case status
        case startedAt = "started_at"
        case finishedAt = "finished_at"
        case finalResponse = "final_response"
    }

    var displayStatus: String {
        status.humanizedStatus
    }

    var displayRequest: String {
        request.isEmpty ? "Background task" : request
    }
}

struct ApprovalItem: Decodable, Identifiable, Hashable {
    var id: String { approvalToken }
    var approvalToken: String
    var runId: String
    var request: String
    var toolName: String
    var riskLevel: String
    var reason: String
    var status: String
    var createdAt: String
    var toolInput: JSONValue?

    enum CodingKeys: String, CodingKey {
        case approvalToken = "approval_token"
        case runId = "run_id"
        case request
        case toolName = "tool_name"
        case riskLevel = "risk_level"
        case reason
        case status
        case createdAt = "created_at"
        case toolInput = "tool_input"
    }

    var displayToolName: String {
        toolName.humanizedIdentifier
    }

    var displayRisk: String {
        riskLevel.humanizedStatus
    }
}

struct ChannelInfo: Decodable, Identifiable {
    var id: String { channelId }
    var channelId: String
    var displayName: String
    var transport: String
    var pluginKind: String?
    var setupKind: String
    var conversationTypes: [String]
    var supportsText: Bool
    var supportsMedia: Bool
    var supportsReactions: Bool
    var setup: JSONValue?
    var delivery: JSONValue?
    var policies: JSONValue?
    var runtime: JSONValue?

    enum CodingKeys: String, CodingKey {
        case channelId = "channel_id"
        case displayName = "display_name"
        case transport
        case pluginKind = "plugin_kind"
        case setupKind = "setup_kind"
        case conversationTypes = "conversation_types"
        case supportsText = "supports_text"
        case supportsMedia = "supports_media"
        case supportsReactions = "supports_reactions"
        case setup
        case delivery
        case policies
        case runtime
    }

    var displayTransport: String {
        transport.humanizedIdentifier
    }

    var setupSummary: String {
        setupKind.isEmpty ? "Ready to configure" : setupKind.humanizedIdentifier
    }
}

struct ChannelSetup: Codable, Equatable, Identifiable {
    var id: String { channelId }
    var channelId = ""
    var enabled = false
    var listenEnabled = true
    var conversationId = ""
    var conversationType = "dm"
    var secretName = ""
    var secretValue = ""
    var secretNames: [String] = []
    var secretValues: [String: String] = [:]
    var secretConfigured = false
    var allowlist: [String] = []
    var groupAllowlist: [String] = []
    var notes = ""

    enum CodingKeys: String, CodingKey {
        case channelId
        case enabled
        case listenEnabled
        case conversationId
        case conversationType
        case secretName
        case secretNames
        case secretConfigured
        case allowlist
        case groupAllowlist
        case notes
    }
}

struct OutboxEnvelope: Decodable {
    var messages: [JSONValue]
}

struct ConnectorCatalog: Decodable {
    var providerCount: Int
    var providers: [ConnectorProvider]
    var redirectUri: String

    enum CodingKeys: String, CodingKey {
        case providerCount = "provider_count"
        case providers
        case redirectUri = "redirect_uri"
    }
}

struct ConnectorProvider: Decodable, Identifiable {
    var id: String { providerId }
    var providerId: String
    var displayName: String
    var category: String
    var authUrl: String
    var tokenUrl: String
    var authType: String
    var credentialFields: [String]
    var oauthManagement: String
    var managedOAuthAvailable: Bool
    var advancedClientConfig: Bool
    var advancedClientConfigured: Bool
    var defaultScopes: [String]
    var workspaceApps: [String]
    var toolHints: [String]
    var supportsPkce: Bool
    var docsUrl: String
    var icon: String
    var brandColor: String
    var logoAsset: String
    var logoUrl: String
    var configured: Bool
    var clientId: String
    var connected: Bool
    var connectedAt: String
    var expiresAt: Double
    var hasRefreshToken: Bool
    var collectorSource: ConnectorCollectorSource?

    enum CodingKeys: String, CodingKey {
        case providerId = "provider_id"
        case displayName = "display_name"
        case category
        case authUrl = "auth_url"
        case tokenUrl = "token_url"
        case authType = "auth_type"
        case credentialFields = "credential_fields"
        case oauthManagement = "oauth_management"
        case managedOAuthAvailable = "managed_oauth_available"
        case advancedClientConfig = "advanced_client_config"
        case advancedClientConfigured = "advanced_client_configured"
        case defaultScopes = "default_scopes"
        case workspaceApps = "workspace_apps"
        case toolHints = "tool_hints"
        case supportsPkce = "supports_pkce"
        case docsUrl = "docs_url"
        case icon
        case brandColor = "brand_color"
        case logoAsset = "logo_asset"
        case logoUrl = "logo_url"
        case configured
        case clientId = "client_id"
        case connected
        case connectedAt = "connected_at"
        case expiresAt = "expires_at"
        case hasRefreshToken = "has_refresh_token"
        case collectorSource = "collector_source"
    }

    var statusText: String {
        if connected { return "Connected" }
        if usesOAuth {
            if managedOAuthAvailable || configured { return "Ready to connect" }
            return "Managed OAuth unavailable"
        }
        if configured { return "Credentials saved" }
        return "Needs credentials"
    }

    var usesOAuth: Bool {
        authType == "oauth2_authorization_code"
    }

    var setupTitle: String {
        if usesOAuth { return "Advanced OAuth Client" }
        if credentialFields.count <= 1 { return "Local Connection" }
        return credentialFields.contains("bot_token") ? "Bot Credentials" : "Connection Credentials"
    }

    var setupCaption: String {
        if usesOAuth {
            let scopeText = defaultScopes.isEmpty ? "OAuth scopes: none declared" : "OAuth scopes: \(defaultScopes.joined(separator: ", "))"
            return "Managed OAuth is the normal user path. Use these fields only for self-hosted or development builds. \(scopeText)"
        }
        if credentialFields.count <= 1 {
            return "No provider API secret is required here. Save a local connection name so tools and collectors can check readiness."
        }
        return "Credential fields: \(credentialFields.map(\.humanizedIdentifier).joined(separator: ", "))"
    }

    var primaryCredentialLabel: String {
        credentialFields.first?.humanizedIdentifier ?? (usesOAuth ? "Client ID" : "Connection ID")
    }

    var secondaryCredentialLabel: String {
        if usesOAuth && supportsPkce {
            return "Client Secret (optional)"
        }
        guard credentialFields.count > 1 else { return usesOAuth ? "Client secret" : "Secret or token" }
        return credentialFields[1].humanizedIdentifier
    }

    var saveButtonTitle: String {
        usesOAuth ? "Save Advanced OAuth Client" : "Save Credentials"
    }

    var connectionButtonTitle: String {
        if usesOAuth { return connected ? "Reconnect" : "Connect" }
        return configured ? "Check Readiness" : "Show Setup"
    }

    var connectionButtonSymbol: String {
        usesOAuth ? "safari" : "checkmark.seal"
    }

    var authModeText: String {
        authType.humanizedIdentifier
    }

    var collectorSourceText: String {
        guard let collectorSource else { return "-" }
        let modes = [
            collectorSource.pollerSupported ? "poller" : nil,
            collectorSource.webhookSupported ? "webhook" : nil
        ].compactMap { $0 }.joined(separator: ", ")
        let mappings = collectorSource.collectorMappings
            .prefix(8)
            .map { "\($0.sourceEvent.humanizedIdentifier) -> \($0.collector.humanizedIdentifier) / \($0.stimulusType.humanizedIdentifier)" }
            .joined(separator: "\n")
        return [
            collectorSource.sourceType.humanizedIdentifier,
            modes.isEmpty ? nil : "Modes: \(modes)",
            mappings.isEmpty ? nil : mappings
        ].compactMap { $0 }.joined(separator: "\n")
    }
}

struct ConnectorCollectorSource: Decodable {
    var sourceType: String
    var pollerSupported: Bool
    var webhookSupported: Bool
    var collectorMappings: [ConnectorCollectorMapping]

    enum CodingKeys: String, CodingKey {
        case sourceType = "source_type"
        case pollerSupported = "poller_supported"
        case webhookSupported = "webhook_supported"
        case collectorMappings = "collector_mappings"
    }
}

struct ConnectorCollectorMapping: Decodable {
    var sourceEvent: String
    var collector: String
    var stimulusType: String

    enum CodingKeys: String, CodingKey {
        case sourceEvent = "source_event"
        case collector
        case stimulusType = "stimulus_type"
    }
}

struct ConnectorAuthorization: Decodable {
    var providerId: String
    var displayName: String
    var authorizationURL: String
    var state: String
    var redirectUri: String
    var scopes: [String]
    var usesPkce: Bool

    enum CodingKeys: String, CodingKey {
        case providerId = "provider_id"
        case displayName = "display_name"
        case authorizationURL = "authorization_url"
        case state
        case redirectUri = "redirect_uri"
        case scopes
        case usesPkce = "uses_pkce"
    }
}

struct JanusStatusResponse: Decodable, Sendable {
    var routes: [JanusRecord]
    var decisions: [JanusRecord]
    var activations: [JanusRecord]
    var memoryCandidates: [JanusRecord]
    var taskContexts: [JanusRecord]
    var mutedScopes: [JanusRecord]
    var deepDiveRequests: [JanusRecord]
    var contextWindow: JSONValue
    var contextWindows: [JanusRecord]
    var contextBoundaries: [JanusRecord]
    var resumeCapsules: [JanusRecord]
    var explanations: [JanusRecord]
    var corrections: [JanusRecord]

    enum CodingKeys: String, CodingKey {
        case routes
        case decisions
        case activations
        case memoryCandidates = "memory_candidates"
        case taskContexts = "task_contexts"
        case mutedScopes = "muted_scopes"
        case deepDiveRequests = "deep_dive_requests"
        case contextWindow = "context_window"
        case contextWindows = "context_windows"
        case contextBoundaries = "context_boundaries"
        case resumeCapsules = "resume_capsules"
        case explanations
        case corrections
    }

    static let empty = JanusStatusResponse(
        routes: [],
        decisions: [],
        activations: [],
        memoryCandidates: [],
        taskContexts: [],
        mutedScopes: [],
        deepDiveRequests: [],
        contextWindow: .object([:]),
        contextWindows: [],
        contextBoundaries: [],
        resumeCapsules: [],
        explanations: [],
        corrections: []
    )

    var latestTarget: (type: String, id: String)? {
        if let activation = activations.first, !activation.id.isEmpty {
            return ("activation", activation.id)
        }
        if let memory = memoryCandidates.first, !memory.id.isEmpty {
            return ("memory_candidate", memory.id)
        }
        if let decision = decisions.first, !decision.id.isEmpty {
            return ("decision", decision.id)
        }
        if let explanation = explanations.first, !explanation.id.isEmpty {
            return ("explanation", explanation.id)
        }
        if let route = routes.first, !route.id.isEmpty {
            return ("route", route.id)
        }
        return nil
    }

    var latestPosture: String {
        activations.first?.activationDisplayStatus
            ?? decisions.first?.string("posture")?.humanizedStatus
            ?? routes.first?.string("route_class")?.humanizedStatus
            ?? "Listening"
    }
}

struct JanusPlannerContextPreview: Decodable, Sendable {
    var source: String
    var request: String
    var privacy: String
    var janusMemory: JSONValue
    var janusState: JSONValue
    var safety: JSONValue

    enum CodingKeys: String, CodingKey {
        case source
        case request
        case privacy
        case janusMemory = "janus_memory"
        case janusState = "janus_state"
        case safety
    }

    static let empty = JanusPlannerContextPreview(
        source: "",
        request: "",
        privacy: "Waiting for planner context.",
        janusMemory: .object([:]),
        janusState: .object([:]),
        safety: .object([:])
    )

    var memoryItems: [JanusRecord] {
        records(from: janusMemory["items"])
    }

    var taskContexts: [JanusRecord] {
        records(from: janusState["task_contexts"])
    }

    var episodes: [JanusRecord] {
        records(from: janusState["episodes"])
    }

    var activations: [JanusRecord] {
        records(from: janusState["activations"])
    }

    var resumeCapsules: [JanusRecord] {
        records(from: janusState["resume_capsules"])
    }

    var deepDiveRequests: [JanusRecord] {
        records(from: janusState["deep_dive_requests"])
    }

    var mutedScopes: [JanusRecord] {
        records(from: janusState["muted_scopes"])
    }

    private func records(from value: JSONValue?) -> [JanusRecord] {
        value?.arrayValue?.compactMap { item in
            guard let object = item.objectValue else { return nil }
            return JanusRecord(values: object)
        } ?? []
    }
}

struct JanusRecord: Decodable, Identifiable, Hashable, Sendable {
    var values: [String: JSONValue]

    var id: String {
        string("activation_id")
            ?? string("candidate_id")
            ?? string("decision_id")
            ?? string("route_id")
            ?? string("explanation_id")
            ?? string("correction_id")
            ?? string("task_context_id")
            ?? string("scope_id")
            ?? string("request_id")
            ?? string("boundary_id")
            ?? string("capsule_id")
            ?? string("id")
            ?? UUID().uuidString
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        values = (try? container.decode([String: JSONValue].self)) ?? [:]
    }

    init(values: [String: JSONValue]) {
        self.values = values
    }

    func string(_ key: String) -> String? {
        values[key]?.stringValue
    }

    func bool(_ key: String) -> Bool {
        values[key]?.boolValue ?? false
    }

    var primaryText: String {
        string("user_visible_text")
            ?? string("reason")
            ?? string("summary")
            ?? string("purpose")
            ?? string("note")
            ?? string("route_class")?.humanizedStatus
            ?? id
    }

    var activationDisplayStatus: String? {
        guard string("activation_id") != nil else { return nil }
        let posture = string("posture")?.humanizedStatus
        let status = string("status")?.humanizedStatus
        if let posture, let status {
            return "\(posture) / \(status)"
        }
        return status ?? posture
    }

    var secondaryText: String {
        [
            string("collector")?.humanizedIdentifier,
            string("source")?.humanizedIdentifier,
            string("stimulus_type")?.humanizedIdentifier,
            string("created_at")
        ]
        .compactMap { $0 }
        .filter { !$0.isEmpty }
        .joined(separator: " / ")
    }

    var statusText: String {
        string("status")?.humanizedStatus
            ?? string("posture")?.humanizedStatus
            ?? string("route_class")?.humanizedStatus
            ?? string("correction_type")?.humanizedStatus
            ?? "Recorded"
    }

    var detailValue: JSONValue {
        .object(values)
    }
}

struct JanusTaskContextDraft: Equatable {
    var goal = ""
    var summary = ""
    var privacyMode = "metadata_first"
    var allowedHelp = "resume_capsule"

    var allowedHelpList: [String] {
        allowedHelp
            .split(separator: ",")
            .map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    var hasContext: Bool {
        !goal.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            || !summary.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }
}

struct JanusMutedScopeDraft: Equatable {
    var mode = "no_assistance"
    var scopeType = "manual"
    var collector = ""
    var source = ""
    var stimulusType = ""
    var entityRefs = ""
    var expiresAt = ""
    var reason = "Muted from macOS Janus panel."

    var entityRefList: [String] {
        entityRefs
            .split(separator: ",")
            .map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    var hasScope: Bool {
        !collector.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            || !source.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            || !stimulusType.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            || !entityRefList.isEmpty
    }
}

struct CollectorStatusResponse: Decodable, Sendable {
    var values: [String: JSONValue]

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        values = (try? container.decode([String: JSONValue].self)) ?? [:]
    }

    init(values: [String: JSONValue]) {
        self.values = values
    }

    static let empty = CollectorStatusResponse(values: [:])

    var detailValue: JSONValue {
        .object(values)
    }

    var eventLog: JSONValue {
        values["event_log"] ?? .object([:])
    }

    var helperHealth: [CollectorHealthRecord] {
        eventLog["helper_health"]?.arrayValue?.compactMap { value in
            guard let object = value.objectValue else { return nil }
            return CollectorHealthRecord(values: object)
        } ?? []
    }

    var recentEvents: [JanusRecord] {
        let eventValues = values["recent_events"]?.arrayValue
            ?? eventLog["recent_events"]?.arrayValue
            ?? []
        return eventValues.compactMap { value in
            guard let object = value.objectValue else { return nil }
            return JanusRecord(values: object)
        }
    }

    var eventCount: Int {
        Int(eventLog["event_count"]?.numberValue ?? 0)
    }

    var latestSequence: Int {
        Int(eventLog["latest_sequence"]?.numberValue ?? 0)
    }

    var deadLetterCount: Int {
        Int(eventLog["dead_letter_count"]?.numberValue ?? 0)
    }

    var statusText: String {
        if helperHealth.contains(where: { $0.needsAttention }) || deadLetterCount > 0 {
            return "Needs attention"
        }
        if eventCount > 0 {
            return "Collecting"
        }
        return "Ready"
    }
}

struct CollectorHealthRecord: Identifiable, Hashable, Sendable {
    var values: [String: JSONValue]

    var id: String {
        string("helper_id")
            ?? string("collector")
            ?? UUID().uuidString
    }

    func string(_ key: String) -> String? {
        values[key]?.stringValue
    }

    var collector: String {
        string("collector")?.humanizedIdentifier ?? "Collector"
    }

    var statusText: String {
        string("status")?.humanizedStatus ?? "Unknown"
    }

    var platformText: String {
        string("platform")?.humanizedIdentifier ?? "Local"
    }

    var detailText: String {
        [
            string("permission_state")?.humanizedIdentifier,
            string("message"),
            string("last_event_at").map { "Last event: \($0)" }
        ]
        .compactMap { $0 }
        .filter { !$0.isEmpty }
        .joined(separator: " / ")
    }

    var needsAttention: Bool {
        switch string("status")?.lowercased() {
        case "degraded", "permission_denied", "stopped", "failed": true
        default: false
        }
    }
}

struct UpdateInfo: Decodable, Equatable {
    var currentVersion: String
    var latestVersion: String
    var latestTag: String
    var updateAvailable: Bool
    var releaseURL: String
    var platform: String
    var platformDownloadURL: String
    var checksumURL: String
    var source: String
    var error: String

    enum CodingKeys: String, CodingKey {
        case currentVersion = "current_version"
        case latestVersion = "latest_version"
        case latestTag = "latest_tag"
        case updateAvailable = "update_available"
        case releaseURL = "release_url"
        case platform
        case platformDownloadURL = "platform_download_url"
        case checksumURL = "checksum_url"
        case source
        case error
    }

    var statusText: String {
        if updateAvailable {
            return "Update \(latestTag) is available"
        }
        if !error.isEmpty {
            return "Using \(currentVersion); release check unavailable"
        }
        return "Current version \(currentVersion)"
    }

    var downloadURL: URL? {
        URL(string: platformDownloadURL.isEmpty ? releaseURL : platformDownloadURL)
    }
}

struct AgentRunResponse: Decodable {
    var runId: String?
    var finalResponse: String?
    var response: String?
    var decision: JSONValue?
    var run: JSONValue?

    enum CodingKeys: String, CodingKey {
        case runId = "run_id"
        case finalResponse = "final_response"
        case response
        case decision
        case run
    }

    var displayText: String {
        if let response, !response.isEmpty { return response }
        if let finalResponse, !finalResponse.isEmpty { return finalResponse }
        if case let .object(runObject)? = run {
            if case let .string(value)? = runObject["final_response"], !value.isEmpty {
                return value
            }
        }
        if case let .object(decisionObject)? = decision {
            if case let .string(value)? = decisionObject["reason"], !value.isEmpty {
                return value
            }
        }
        return "The agent returned a structured response."
    }
}

enum JSONValue: Decodable, Hashable, CustomStringConvertible, Sendable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([String: JSONValue].self) {
            self = .object(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else {
            self = .null
        }
    }

    var description: String {
        switch self {
        case .string(let value): value
        case .number(let value): value.formatted()
        case .bool(let value): value ? "true" : "false"
        case .object(let value): value.map { "\($0): \($1)" }.sorted().joined(separator: "\n")
        case .array(let value): value.map(\.description).joined(separator: "\n")
        case .null: "null"
        }
    }

    var objectValue: [String: JSONValue]? {
        if case let .object(value) = self { value } else { nil }
    }

    var arrayValue: [JSONValue]? {
        if case let .array(value) = self { value } else { nil }
    }

    var stringValue: String? {
        if case let .string(value) = self { value } else { nil }
    }

    var boolValue: Bool? {
        if case let .bool(value) = self { value } else { nil }
    }

    var numberValue: Double? {
        if case let .number(value) = self { value } else { nil }
    }

    subscript(_ key: String) -> JSONValue? {
        objectValue?[key]
    }

    func stringArray(_ key: String) -> [String] {
        self[key]?.arrayValue?.compactMap(\.stringValue) ?? []
    }

    var compactDescription: String {
        switch self {
        case .array(let values): values.map(\.compactDescription).filter { !$0.isEmpty }.joined(separator: ", ")
        case .object: description
        case .null: ""
        default: description
        }
    }
}

extension String {
    var humanizedIdentifier: String {
        let spaced = replacingOccurrences(of: "_", with: " ")
            .replacingOccurrences(of: "-", with: " ")
            .replacingOccurrences(of: ".", with: " ")
        return spaced
            .split(separator: " ")
            .map { word in
                let lower = word.lowercased()
                if ["api", "url", "id", "stt", "tts", "sms"].contains(lower) {
                    return lower.uppercased()
                }
                return lower.prefix(1).uppercased() + lower.dropFirst()
            }
            .joined(separator: " ")
    }

    var humanizedStatus: String {
        switch lowercased() {
        case "ok", "online", "succeeded": "Ready"
        case "offline": "Offline"
        case "starting": "Starting"
        case "degraded": "Needs attention"
        case "needs_approval": "Waiting for permission"
        case "failed": "Failed"
        case "blocked": "Blocked"
        case "cancelled": "Cancelled"
        case "high": "High attention"
        case "medium": "Medium attention"
        case "low": "Low attention"
        default: humanizedIdentifier
        }
    }
}
