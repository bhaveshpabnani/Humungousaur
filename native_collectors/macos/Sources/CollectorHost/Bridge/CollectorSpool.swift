import EventWriter
import Foundation

final class CollectorSpool {
    private let root: URL
    private var writers: [String: JsonlEventWriter] = [:]

    init(dataDir: URL) {
        self.root = dataDir.appendingPathComponent("collector_spool", isDirectory: true)
    }

    func append(
        collector: String,
        source: String,
        stimulusType: String,
        text: String,
        metadata: [String: String] = [:],
        payload: [String: String] = [:],
        privacyTier: String = "metadata",
        pathsRedacted: Bool = true
    ) {
        let now = isoNow()
        let event = CollectorEventEnvelope(
            eventId: "\(collector)-\(UUID().uuidString)",
            collector: collector,
            source: source,
            stimulusType: stimulusType,
            privacyTier: privacyTier,
            occurredAt: now,
            signature: stableSignature(collector, stimulusType, metadata, payload),
            text: text,
            metadata: metadata.merging([
                "helper_id": helperID,
                "helper_version": helperVersion,
                "platform": "macos",
                "raw_content_included": "false",
            ], uniquingKeysWith: { current, _ in current }),
            payload: payload,
            redaction: .metadata(pathsRedacted: pathsRedacted, privacyTier: privacyTier)
        )

        do {
            let writer = writers[collector] ?? JsonlEventWriter(outputURL: root.appendingPathComponent("\(collector).jsonl"))
            writers[collector] = writer
            try writer.append(event)
        } catch {
            fputs("HumungousaurMacCollectorHost failed to append \(collector): \(error)\n", stderr)
        }
    }
}
