import AppKit
import Foundation

final class FileManagerUICollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var finderWindowSignature = ""
    private var quickLookSignature = ""

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func sample(emitInitial: Bool) {
        sampleFinderWindow(emitInitial: emitInitial)
        sampleQuickLook(emitInitial: emitInitial)
    }

    private func sampleFinderWindow(emitInitial: Bool) {
        guard let app = NSWorkspace.shared.frontmostApplication,
              app.bundleIdentifier == "com.apple.finder" else {
            return
        }
        let snapshot = frontmostWindowSnapshot(for: app)
        guard snapshot["window_visible"] == "true" else {
            return
        }
        let signature = [
            app.bundleIdentifier ?? "",
            snapshot["window_id"] ?? "",
            snapshot["window_title_hash"] ?? "",
        ].joined(separator: "|")
        guard emitInitial || signature != finderWindowSignature else {
            return
        }
        finderWindowSignature = signature
        spool.append(
            collector: "folder_navigation_activity",
            source: "activity",
            stimulusType: "folder_opened",
            text: "Finder folder window focused.",
            metadata: appMetadata(app).merging(snapshot, uniquingKeysWith: { current, _ in current }).merging([
                "native_source": "macos_finder_window_metadata",
                "privacy_level": "redacted",
            ], uniquingKeysWith: { current, _ in current }),
            payload: ["window_signature_hash": sha256(signature)],
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }

    private func sampleQuickLook(emitInitial: Bool) {
        guard let app = NSWorkspace.shared.frontmostApplication,
              (app.bundleIdentifier ?? "").localizedCaseInsensitiveContains("quicklook") else {
            return
        }
        let snapshot = frontmostWindowSnapshot(for: app)
        let signature = [
            app.bundleIdentifier ?? "",
            snapshot["window_id"] ?? "",
            snapshot["window_title_hash"] ?? "",
        ].joined(separator: "|")
        guard emitInitial || signature != quickLookSignature else {
            return
        }
        quickLookSignature = signature
        spool.append(
            collector: "file_preview_activity",
            source: "activity",
            stimulusType: "quick_look_opened",
            text: "Quick Look preview focused.",
            metadata: appMetadata(app).merging(snapshot, uniquingKeysWith: { current, _ in current }).merging([
                "native_source": "macos_quicklook_window_metadata",
                "privacy_level": "redacted",
            ], uniquingKeysWith: { current, _ in current }),
            payload: ["window_signature_hash": sha256(signature)],
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }
}
