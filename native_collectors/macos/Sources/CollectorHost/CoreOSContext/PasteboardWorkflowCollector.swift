import AppKit
import Foundation

final class PasteboardWorkflowCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var pasteboardChangeCount = NSPasteboard.general.changeCount

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func sample(emitInitial: Bool) {
        let _ = emitInitial
        let pasteboard = NSPasteboard.general
        guard pasteboard.changeCount != pasteboardChangeCount else {
            return
        }
        pasteboardChangeCount = pasteboard.changeCount
        let categories = pasteboardTypeCategories(pasteboard.types ?? [])
        let stimulusType = categories["type_count"] == "0" ? "clipboard_cleared" : "copy_performed"
        spool.append(
            collector: "pasteboard_workflow_activity",
            source: "activity",
            stimulusType: stimulusType,
            text: stimulusType == "clipboard_cleared" ? "Clipboard cleared." : "Pasteboard changed without content capture.",
            metadata: categories.merging(["source_api": "NSPasteboard"], uniquingKeysWith: { current, _ in current }),
            payload: ["change_count": String(pasteboard.changeCount)],
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }

    func emitPasteCommand(matchStyle: Bool) {
        let stimulusType = matchStyle ? "paste_and_match_style_performed" : "paste_performed"
        spool.append(
            collector: "pasteboard_workflow_activity",
            source: "activity",
            stimulusType: stimulusType,
            text: matchStyle ? "Paste and match style command performed." : "Paste command performed.",
            metadata: ["source_api": "NSEventGlobalMonitor", "shortcut_family": "paste"],
            payload: [:],
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }
}
