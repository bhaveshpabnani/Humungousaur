import Foundation

final class KeyboardIMECollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var inputSourceSignature = ""

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func sample(emitInitial: Bool) {
        let source = currentInputSource()
        let signature = "\(source["input_source_id"] ?? "")|\(source["input_source_kind"] ?? "")"
        guard !signature.trimmingCharacters(in: CharacterSet(charactersIn: "|")).isEmpty else {
            return
        }
        guard emitInitial || signature != inputSourceSignature else {
            return
        }
        let previous = inputSourceSignature
        inputSourceSignature = signature
        spool.append(
            collector: "keyboard_input_activity",
            source: "system",
            stimulusType: "input_source_changed",
            text: "Keyboard input source changed.",
            metadata: source.merging(["source_api": "TextInputSources"], uniquingKeysWith: { current, _ in current }),
            payload: ["previous_input_source_hash": previous.isEmpty ? "" : sha256(previous)]
        )
        if source["input_source_kind"] == "ime" {
            spool.append(
                collector: "ime_activity",
                source: "accessibility",
                stimulusType: "language_input_switched",
                text: "Language input source switched.",
                metadata: source.merging(["source_api": "TextInputSources"], uniquingKeysWith: { current, _ in current }),
                payload: ["previous_input_source_hash": previous.isEmpty ? "" : sha256(previous)],
                privacyTier: "sensitive_metadata"
            )
        }
        health.noteEvent()
    }
}
