import Foundation

public final class JsonlEventWriter {
    private let outputURL: URL
    private let encoder: JSONEncoder

    public init(outputURL: URL) {
        self.outputURL = outputURL
        self.encoder = JSONEncoder()
        self.encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
    }

    public func append(_ envelope: CollectorEventEnvelope) throws {
        try FileManager.default.createDirectory(
            at: outputURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let data = try encoder.encode(envelope) + Data([0x0A])
        if FileManager.default.fileExists(atPath: outputURL.path) {
            let handle = try FileHandle(forWritingTo: outputURL)
            defer { try? handle.close() }
            try handle.seekToEnd()
            try handle.write(contentsOf: data)
        } else {
            try data.write(to: outputURL, options: .atomic)
        }
    }
}
