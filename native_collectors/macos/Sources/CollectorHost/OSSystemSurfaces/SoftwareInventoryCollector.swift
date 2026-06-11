import AppKit
import Foundation

final class SoftwareInventoryCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var appSignatures: [String: String] = [:]
    private var baselineReady = false

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func installObservers() -> [NativeObservation] {
        let center = NSWorkspace.shared.notificationCenter
        let launch = center.addObserver(forName: NSWorkspace.didLaunchApplicationNotification, object: nil, queue: .main) { [weak self] note in
            self?.handleApplicationLaunch(note)
        }
        return [(center, launch)]
    }

    func sample(emitInitial: Bool) {
        let current = applicationBundleSignatures()
        if !baselineReady {
            appSignatures = current
            baselineReady = true
            return
        }
        for (key, signature) in current where appSignatures[key] == nil {
            emit(stimulusType: "app_installed", key: key, signature: signature)
        }
        for (key, previous) in appSignatures where current[key] == nil {
            emit(stimulusType: "app_uninstalled", key: key, signature: previous)
        }
        for (key, signature) in current where appSignatures[key] != nil && appSignatures[key] != signature {
            emit(stimulusType: "app_updated", key: key, signature: signature)
        }
        appSignatures = current
    }

    private func handleApplicationLaunch(_ note: Notification) {
        guard let app = note.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication else {
            return
        }
        let metadata = appMetadata(app).merging([
            "native_source": "macos_nsworkspace_software_lifecycle",
            "source_api": "NSWorkspace.didLaunchApplicationNotification",
            "privacy_level": "redacted",
        ], uniquingKeysWith: { current, _ in current })
        let identity = "\(app.bundleIdentifier ?? "")|\(safeAppName(app))".lowercased()
        guard identity.contains("installer") || identity.contains("softwareupdate") || identity.contains("appstore") else {
            return
        }
        spool.append(
            collector: "software_activity",
            source: "system",
            stimulusType: "installer_started",
            text: "Installer or software-update app launched.",
            metadata: metadata,
            payload: ["app_signature_hash": shortDigest(identity)]
        )
        health.noteEvent()
    }

    private func emit(stimulusType: String, key: String, signature: String) {
        spool.append(
            collector: "software_activity",
            source: "system",
            stimulusType: stimulusType,
            text: "Application bundle inventory metadata changed.",
            metadata: [
                "native_source": "macos_application_bundle_inventory",
                "source_api": "FileManager+Bundle",
                "privacy_level": "redacted",
                "application_name_omitted": "true",
                "bundle_key_hash": shortDigest(key),
                "bundle_signature_hash": shortDigest(signature),
            ],
            payload: [
                "bundle_key_hash": shortDigest(key),
                "bundle_signature_hash": shortDigest(signature),
            ]
        )
        health.noteEvent()
    }
}
