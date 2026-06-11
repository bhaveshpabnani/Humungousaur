import AppKit
import Foundation

final class WindowContextCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private let appLifecycle: AppLifecycleCollector?
    private var activeWindowSignature = ""
    private var appFocusSignature = ""

    init(spool: CollectorSpool, health: HelperHealthReporter, appLifecycle: AppLifecycleCollector? = nil) {
        self.spool = spool
        self.health = health
        self.appLifecycle = appLifecycle
    }

    func installObservers() {
        NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.didActivateApplicationNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            self?.sample(emitInitial: true)
        }
    }

    func sample(emitInitial: Bool) {
        guard let app = NSWorkspace.shared.frontmostApplication else {
            return
        }
        let snapshot = frontmostWindowSnapshot(for: app)
        let signature = [
            app.bundleIdentifier ?? "",
            String(app.processIdentifier),
            snapshot["window_id"] ?? "",
            snapshot["window_title_hash"] ?? "",
        ].joined(separator: "|")
        guard emitInitial || signature != activeWindowSignature else {
            return
        }
        let previous = activeWindowSignature
        activeWindowSignature = signature

        let metadata = appMetadata(app).merging(snapshot, uniquingKeysWith: { current, _ in current })
        spool.append(
            collector: "active_window",
            source: "activity",
            stimulusType: "active_window_changed",
            text: "Active window changed: \(safeAppName(app)).",
            metadata: metadata.merging(["source_api": "NSWorkspace+CGWindowList"], uniquingKeysWith: { current, _ in current }),
            payload: ["previous_signature_hash": previous.isEmpty ? "" : sha256(previous)]
        )
        spool.append(
            collector: "window_lifecycle",
            source: "activity",
            stimulusType: "window_focused",
            text: "Window focus changed: \(safeAppName(app)).",
            metadata: metadata.merging(["source_api": "CGWindowList"], uniquingKeysWith: { current, _ in current }),
            payload: ["previous_signature_hash": previous.isEmpty ? "" : sha256(previous)]
        )

        let appSignature = "\(app.bundleIdentifier ?? "")|\(app.processIdentifier)"
        if emitInitial || appSignature != appFocusSignature {
            appFocusSignature = appSignature
            if let appLifecycle {
                appLifecycle.emitFocused(app: app)
            } else {
                spool.append(
                    collector: "app_lifecycle",
                    source: "activity",
                    stimulusType: "app_focused",
                    text: "App focused: \(safeAppName(app)).",
                    metadata: appMetadata(app).merging(["source_api": "NSWorkspace"], uniquingKeysWith: { current, _ in current }),
                    payload: ["process_identifier": String(app.processIdentifier)]
                )
            }
        }
        health.noteEvent()
    }
}
