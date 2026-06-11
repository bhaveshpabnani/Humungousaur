import AppKit
import Foundation

final class BrowserActivityCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var foregroundSignature = ""
    private var foregroundWindowID = ""
    private var foregroundTitleHash = ""
    private var browserAppSignatures: Set<String> = []
    private var profileSnapshots: [String: BrowserProfileSnapshot] = [:]

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func sample(emitInitial: Bool) {
        sampleRunningBrowsers(emitInitial: emitInitial)
        sampleForegroundBrowser(emitInitial: emitInitial)
        sampleBrowserStores(emitInitial: emitInitial)
    }

    private func sampleRunningBrowsers(emitInitial: Bool) {
        let current = Set(NSWorkspace.shared.runningApplications.compactMap { app -> String? in
            guard let definition = browserDefinition(for: app) else {
                return nil
            }
            return "\(definition.browserID)|\(app.processIdentifier)"
        })
        if emitInitial {
            browserAppSignatures = current
            for signature in current.sorted().prefix(8) {
                guard let browserID = signature.split(separator: "|").first else {
                    continue
                }
                emitBrowserObserved(browserID: String(browserID), reason: "initial_running_app")
            }
            return
        }
        for signature in current.subtracting(browserAppSignatures).sorted().prefix(8) {
            guard let browserID = signature.split(separator: "|").first else {
                continue
            }
            emitBrowserObserved(browserID: String(browserID), reason: "running_app_opened")
        }
        browserAppSignatures = current
    }

    private func sampleForegroundBrowser(emitInitial: Bool) {
        guard let app = NSWorkspace.shared.frontmostApplication,
              let definition = browserDefinition(for: app) else {
            return
        }
        let snapshot = frontmostWindowSnapshot(for: app)
        let windowID = snapshot["window_id"] ?? ""
        let titleHash = snapshot["window_title_hash"] ?? ""
        let signature = [
            definition.browserID,
            String(app.processIdentifier),
            windowID,
            titleHash,
            snapshot["window_bounds_bucket"] ?? "",
        ].joined(separator: "|")
        guard emitInitial || signature != foregroundSignature else {
            return
        }

        let previousWindowID = foregroundWindowID
        let previousTitleHash = foregroundTitleHash
        foregroundSignature = signature
        foregroundWindowID = windowID
        foregroundTitleHash = titleHash

        let metadata = browserWindowMetadata(app: app, definition: definition, snapshot: snapshot)
        let payload = [
            "browser_signature_hash": sha256(signature),
            "window_signature_hash": sha256("\(definition.browserID)|\(windowID)|\(titleHash)"),
            "previous_window_signature_hash": previousWindowID.isEmpty ? "" : sha256("\(definition.browserID)|\(previousWindowID)"),
        ]
        spool.append(
            collector: "browser",
            source: "browser",
            stimulusType: "browser_tab_changed",
            text: "Foreground browser context changed.",
            metadata: metadata,
            payload: payload
        )
        spool.append(
            collector: "browser_window_activity",
            source: "browser",
            stimulusType: "browser_window_focused",
            text: "Browser window focused.",
            metadata: metadata,
            payload: payload
        )

        let lifecycleStimulus: String
        if previousTitleHash.isEmpty {
            lifecycleStimulus = "browser_tab_observed"
        } else if titleHash != previousTitleHash {
            lifecycleStimulus = "browser_title_changed"
        } else if windowID != previousWindowID {
            lifecycleStimulus = "browser_tab_switched"
        } else {
            lifecycleStimulus = "browser_tab_observed"
        }
        spool.append(
            collector: "browser_lifecycle",
            source: "browser",
            stimulusType: lifecycleStimulus,
            text: "Browser lifecycle metadata changed.",
            metadata: metadata,
            payload: payload
        )
        health.noteEvent()
    }

    private func sampleBrowserStores(emitInitial: Bool) {
        let current = Dictionary(uniqueKeysWithValues: browserProfileSnapshots().map { ($0.key, $0) })
        if emitInitial {
            profileSnapshots = current
            return
        }
        for key in Set(current.keys).subtracting(profileSnapshots.keys).sorted().prefix(12) {
            guard let snapshot = current[key] else {
                continue
            }
            emitProfile(snapshot, stimulusType: "browser_profile_created", reason: "profile_directory_added")
        }
        for key in Set(current.keys).intersection(profileSnapshots.keys).sorted().prefix(24) {
            guard let previous = profileSnapshots[key], let snapshot = current[key] else {
                continue
            }
            emitProfileDiff(previous: previous, current: snapshot)
        }
        profileSnapshots = current
    }

    private func emitBrowserObserved(browserID: String, reason: String) {
        let metadata = [
            "browser_id": browserID,
            "native_source": "macos_nsworkspace_browser_running_app",
            "source_api": "NSWorkspace.runningApplications",
            "reason": reason,
            "privacy_level": "redacted",
            "url_omitted": "true",
            "title_omitted": "true",
        ]
        spool.append(
            collector: "browser_lifecycle",
            source: "browser",
            stimulusType: "browser_tab_observed",
            text: "Browser process observed.",
            metadata: metadata,
            payload: ["browser_id": browserID]
        )
        health.noteEvent()
    }

    private func emitProfileDiff(previous: BrowserProfileSnapshot, current: BrowserProfileSnapshot) {
        if previous.extensionSignature != current.extensionSignature {
            let stimulus: String
            if current.extensionCount > previous.extensionCount {
                stimulus = "extension_installed"
            } else if current.extensionCount < previous.extensionCount {
                stimulus = "extension_removed"
            } else {
                stimulus = "extension_enabled"
            }
            emitExtension(current, stimulusType: stimulus, reason: "extension_store_changed")
        }
        if previous.webAppSignature != current.webAppSignature {
            emitWebApp(
                current,
                stimulusType: current.webAppCount < previous.webAppCount ? "web_app_uninstalled" : "web_app_installed",
                reason: "web_app_store_changed"
            )
        }
        if previous.bookmarkSignature != current.bookmarkSignature {
            emitBookmarkHistory(current, stimulusType: "bookmark_added", reason: "bookmark_store_changed")
        }
        if previous.historySignature != current.historySignature {
            emitBookmarkHistory(current, stimulusType: "history_item_opened", reason: "history_store_changed")
        }
        if previous.tabGroupSignature != current.tabGroupSignature {
            emitTabGroup(current, reason: "tab_group_store_changed")
            emitBookmarkHistory(current, stimulusType: "saved_tab_group_changed", reason: "tab_group_store_changed")
        }
    }

    private func emitProfile(_ snapshot: BrowserProfileSnapshot, stimulusType: String, reason: String) {
        spool.append(
            collector: "browser_profile_activity",
            source: "browser",
            stimulusType: stimulusType,
            text: "Browser profile metadata changed.",
            metadata: snapshot.metadata(reason: reason),
            payload: snapshot.payload,
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }

    private func emitExtension(_ snapshot: BrowserProfileSnapshot, stimulusType: String, reason: String) {
        spool.append(
            collector: "browser_extension_activity",
            source: "browser",
            stimulusType: stimulusType,
            text: "Browser extension metadata changed.",
            metadata: snapshot.metadata(reason: reason).merging([
                "extension_count_bucket": countBucket(snapshot.extensionCount),
                "extension_names_omitted": "true",
            ], uniquingKeysWith: { current, _ in current }),
            payload: snapshot.payload.merging(["extension_count": String(snapshot.extensionCount)], uniquingKeysWith: { current, _ in current }),
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }

    private func emitWebApp(_ snapshot: BrowserProfileSnapshot, stimulusType: String, reason: String) {
        spool.append(
            collector: "browser_web_app_activity",
            source: "browser",
            stimulusType: stimulusType,
            text: "Browser web app metadata changed.",
            metadata: snapshot.metadata(reason: reason).merging([
                "web_app_count_bucket": countBucket(snapshot.webAppCount),
                "web_app_names_omitted": "true",
            ], uniquingKeysWith: { current, _ in current }),
            payload: snapshot.payload.merging(["web_app_count": String(snapshot.webAppCount)], uniquingKeysWith: { current, _ in current }),
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }

    private func emitBookmarkHistory(_ snapshot: BrowserProfileSnapshot, stimulusType: String, reason: String) {
        spool.append(
            collector: "bookmark_history_activity",
            source: "browser",
            stimulusType: stimulusType,
            text: "Browser bookmark/history metadata changed.",
            metadata: snapshot.metadata(reason: reason).merging([
                "urls_omitted": "true",
                "titles_omitted": "true",
                "queries_omitted": "true",
            ], uniquingKeysWith: { current, _ in current }),
            payload: snapshot.payload,
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }

    private func emitTabGroup(_ snapshot: BrowserProfileSnapshot, reason: String) {
        spool.append(
            collector: "browser_tab_group_activity",
            source: "browser",
            stimulusType: "tab_group_saved",
            text: "Browser tab group metadata changed.",
            metadata: snapshot.metadata(reason: reason).merging([
                "tab_titles_omitted": "true",
                "tab_urls_omitted": "true",
            ], uniquingKeysWith: { current, _ in current }),
            payload: snapshot.payload,
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }
}
