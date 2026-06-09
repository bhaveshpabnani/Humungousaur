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

enum JSONValue: Decodable, Hashable, CustomStringConvertible {
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
