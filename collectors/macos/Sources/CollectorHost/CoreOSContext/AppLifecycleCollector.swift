import AppKit
import Foundation

final class AppLifecycleCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func installObservers() {
        let center = NSWorkspace.shared.notificationCenter
        center.addObserver(forName: NSWorkspace.didLaunchApplicationNotification, object: nil, queue: .main) { [weak self] note in
            self?.emit(note: note, stimulusType: "app_opened")
        }
        center.addObserver(forName: NSWorkspace.didTerminateApplicationNotification, object: nil, queue: .main) { [weak self] note in
            self?.emit(note: note, stimulusType: "app_closed")
        }
        center.addObserver(forName: NSWorkspace.didActivateApplicationNotification, object: nil, queue: .main) { [weak self] note in
            self?.emit(note: note, stimulusType: "app_focused")
        }
        center.addObserver(forName: NSWorkspace.didHideApplicationNotification, object: nil, queue: .main) { [weak self] note in
            self?.emit(note: note, stimulusType: "app_hidden")
        }
    }

    func emitFocused(app: NSRunningApplication) {
        append(app: app, stimulusType: "app_focused", text: "App focused: \(safeAppName(app)).")
    }

    private func emit(note: Notification, stimulusType: String) {
        guard let app = note.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication else {
            return
        }
        append(
            app: app,
            stimulusType: stimulusType,
            text: "App lifecycle event: \(stimulusType.replacingOccurrences(of: "_", with: " "))."
        )
    }

    private func append(app: NSRunningApplication, stimulusType: String, text: String) {
        spool.append(
            collector: "app_lifecycle",
            source: "activity",
            stimulusType: stimulusType,
            text: text,
            metadata: appMetadata(app).merging(["source_api": "NSWorkspace"], uniquingKeysWith: { current, _ in current }),
            payload: ["process_identifier": String(app.processIdentifier)]
        )
        health.noteEvent()
    }
}
