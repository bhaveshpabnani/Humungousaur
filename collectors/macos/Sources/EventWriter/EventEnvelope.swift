import Foundation

public struct CollectorEventEnvelope: Codable {
    public let eventId: String
    public let schemaVersion: Int
    public let collector: String
    public let source: String
    public let platform: String
    public let stimulusType: String
    public let privacyTier: String
    public let occurredAt: String
    public let receivedAt: String?
    public let signature: String
    public let text: String
    public let metadata: [String: String]
    public let payload: [String: String]
    public let redaction: Redaction

    enum CodingKeys: String, CodingKey {
        case eventId = "event_id"
        case schemaVersion = "schema_version"
        case collector
        case source
        case platform
        case stimulusType = "stimulus_type"
        case privacyTier = "privacy_tier"
        case occurredAt = "occurred_at"
        case receivedAt = "received_at"
        case signature
        case text
        case metadata
        case payload
        case redaction
    }

    public init(
        eventId: String,
        collector: String,
        source: String,
        stimulusType: String,
        privacyTier: String,
        occurredAt: String,
        signature: String,
        text: String,
        metadata: [String: String] = [:],
        payload: [String: String] = [:],
        redaction: Redaction = .metadata()
    ) {
        self.eventId = eventId
        self.schemaVersion = 1
        self.collector = collector
        self.source = source
        self.platform = "macos"
        self.stimulusType = stimulusType
        self.privacyTier = privacyTier
        self.occurredAt = occurredAt
        self.receivedAt = ISO8601DateFormatter().string(from: Date())
        self.signature = signature
        self.text = text
        self.metadata = metadata
        self.payload = payload
        self.redaction = redaction
    }
}

public struct Redaction: Codable {
    public let rawContentIncluded: Bool
    public let attentionSafe: Bool
    public let pathsRedacted: Bool
    public let payloadCompactedBeforeLlm: Bool
    public let privacyTier: String

    enum CodingKeys: String, CodingKey {
        case rawContentIncluded = "raw_content_included"
        case attentionSafe = "attention_safe"
        case pathsRedacted = "paths_redacted"
        case payloadCompactedBeforeLlm = "payload_compacted_before_llm"
        case privacyTier = "privacy_tier"
    }

    public static func metadata(pathsRedacted: Bool = true, privacyTier: String = "metadata") -> Redaction {
        Redaction(
            rawContentIncluded: false,
            attentionSafe: true,
            pathsRedacted: pathsRedacted,
            payloadCompactedBeforeLlm: true,
            privacyTier: privacyTier
        )
    }
}
