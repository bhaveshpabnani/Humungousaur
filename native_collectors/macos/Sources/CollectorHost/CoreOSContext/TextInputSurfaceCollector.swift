import ApplicationServices
import Foundation

final class TextInputSurfaceCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var focusedTextSurfaceSignature = ""

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func sample(emitInitial: Bool) {
        guard AXIsProcessTrusted() else {
            return
        }
        guard let surface = focusedTextSurface() else {
            return
        }
        let signature = [
            surface["app_bundle_id"] ?? "",
            surface["role"] ?? "",
            surface["subrole"] ?? "",
            surface["is_secure"] ?? "",
        ].joined(separator: "|")
        guard emitInitial || signature != focusedTextSurfaceSignature else {
            return
        }
        focusedTextSurfaceSignature = signature
        let stimulusType: String
        if surface["is_secure"] == "true" {
            stimulusType = "secure_text_field_focused"
        } else if surface["role"] == "AXTextArea" {
            stimulusType = "multiline_editor_focused"
        } else if surface["subrole"] == "AXSearchField" {
            stimulusType = "search_field_focused"
        } else {
            stimulusType = "text_field_focused"
        }
        spool.append(
            collector: "text_input_surface_activity",
            source: "accessibility",
            stimulusType: stimulusType,
            text: "Text input surface focused.",
            metadata: surface.merging(["source_api": "Accessibility"], uniquingKeysWith: { current, _ in current }),
            payload: [:],
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }
}
