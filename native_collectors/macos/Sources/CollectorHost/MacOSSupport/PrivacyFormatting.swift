import AppKit
import CryptoKit
import Foundation

func normalizedModifiers(_ flags: NSEvent.ModifierFlags) -> [String] {
    var values: [String] = []
    if flags.contains(.command) { values.append("command") }
    if flags.contains(.control) { values.append("control") }
    if flags.contains(.option) { values.append("option") }
    if flags.contains(.shift) { values.append("shift") }
    return values
}

func titleLengthBucket(_ title: String) -> String {
    switch title.count {
    case 0: return "0"
    case 1...20: return "1-20"
    case 21...60: return "21-60"
    case 61...120: return "61-120"
    default: return "120+"
    }
}

func boundsBucket(_ bounds: [String: Any]) -> String {
    let width = intValue(bounds["Width"])
    let height = intValue(bounds["Height"])
    return "\(width / 100 * 100)x\(height / 100 * 100)"
}

func intValue(_ value: Any?) -> Int {
    if let value = value as? Int {
        return value
    }
    if let value = value as? Double {
        return Int(value)
    }
    if let value = value as? CGFloat {
        return Int(value)
    }
    if let value = value as? NSNumber {
        return value.intValue
    }
    return 0
}

func batteryBucket(_ percent: Int) -> String {
    switch percent {
    case ...20: return "0-20"
    case 21...50: return "21-50"
    case 51...80: return "51-80"
    default: return "81-100"
    }
}

func idleSecondsBucket(_ seconds: Double) -> String {
    switch seconds {
    case ..<60: return "0-60"
    case ..<300: return "60-300"
    case ..<900: return "300-900"
    default: return "900+"
    }
}

func stableSignature(_ collector: String, _ stimulusType: String, _ metadata: [String: String], _ payload: [String: String]) -> String {
    let metadataParts = metadata.sorted { $0.key < $1.key }.map { "\($0.key)=\($0.value)" }
    let payloadParts = payload.sorted { $0.key < $1.key }.map { "\($0.key)=\($0.value)" }
    let body = ([collector, stimulusType] + metadataParts + payloadParts).joined(separator: "|")
    return "\(collector):\(stimulusType):\(sha256(body))"
}

func sha256(_ value: String) -> String {
    let digest = SHA256.hash(data: Data(value.utf8))
    return digest.map { String(format: "%02x", $0) }.joined()
}

func shortDigest(_ value: String) -> String {
    String(sha256(value).prefix(16))
}

func isoNow() -> String {
    ISO8601DateFormatter().string(from: Date())
}
