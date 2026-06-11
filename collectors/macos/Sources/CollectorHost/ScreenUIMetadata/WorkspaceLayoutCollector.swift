import Foundation

final class WorkspaceLayoutCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var displayArrangementSignature = ""
    private var displayResolutionSignature = ""
    private var displayScalingSignature = ""
    private var displayRotationSignature = ""
    private var primaryDisplayID = ""
    private var desktopSpaceID = ""
    private var stageManagerState = ""
    private var windowDisplaySignature = ""
    private var windowSpaceSignature = ""
    private var windowFullscreenState = ""
    private var appWorkspaceSignature = ""

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func sample(emitInitial: Bool) {
        sampleDisplayArrangement(emitInitial: emitInitial)
        sampleWorkspaceLayout(emitInitial: emitInitial)
        sampleWindowArrangement(emitInitial: emitInitial)
        sampleAppWorkspace(emitInitial: emitInitial)
    }

    private func sampleDisplayArrangement(emitInitial: Bool) {
        let snapshot = displayLayoutSnapshot()
        guard !snapshot.isEmpty else {
            return
        }
        emitDisplayIfChanged(
            snapshot,
            keyPath: \.displayArrangementSignature,
            newValue: snapshot["display_arrangement_signature"] ?? "",
            stimulusType: "display_arrangement_changed",
            text: "Display arrangement metadata changed.",
            emitInitial: emitInitial
        )
        emitDisplayIfChanged(
            snapshot,
            keyPath: \.displayResolutionSignature,
            newValue: snapshot["display_resolution_signature"] ?? "",
            stimulusType: "display_resolution_changed",
            text: "Display resolution metadata changed.",
            emitInitial: false
        )
        emitDisplayIfChanged(
            snapshot,
            keyPath: \.displayScalingSignature,
            newValue: snapshot["display_scaling_signature"] ?? "",
            stimulusType: "display_scaling_changed",
            text: "Display scaling metadata changed.",
            emitInitial: false
        )
        emitDisplayIfChanged(
            snapshot,
            keyPath: \.displayRotationSignature,
            newValue: snapshot["display_rotation_signature"] ?? "",
            stimulusType: "display_rotation_changed",
            text: "Display rotation metadata changed.",
            emitInitial: false
        )
        emitDisplayIfChanged(
            snapshot,
            keyPath: \.primaryDisplayID,
            newValue: snapshot["primary_display_id_hash"] ?? "",
            stimulusType: "primary_display_changed",
            text: "Primary display metadata changed.",
            emitInitial: false
        )
    }

    private func emitDisplayIfChanged(
        _ snapshot: [String: String],
        keyPath: ReferenceWritableKeyPath<WorkspaceLayoutCollector, String>,
        newValue: String,
        stimulusType: String,
        text: String,
        emitInitial: Bool
    ) {
        let previous = self[keyPath: keyPath]
        guard !newValue.isEmpty, emitInitial || previous != newValue else {
            return
        }
        self[keyPath: keyPath] = newValue
        spool.append(
            collector: "display_arrangement_activity",
            source: "system",
            stimulusType: stimulusType,
            text: text,
            metadata: snapshot.merging([
                "native_source": "macos_nsscreen_display_metadata",
                "source_api": "NSScreen+CoreGraphics",
                "privacy_level": "redacted",
                "display_names_omitted": "true",
            ], uniquingKeysWith: { current, _ in current }),
            payload: [
                "display_arrangement_signature": snapshot["display_arrangement_signature"] ?? "",
                "display_resolution_signature": snapshot["display_resolution_signature"] ?? "",
                "display_scaling_signature": snapshot["display_scaling_signature"] ?? "",
                "display_rotation_signature": snapshot["display_rotation_signature"] ?? "",
                "primary_display_id_hash": snapshot["primary_display_id_hash"] ?? "",
            ]
        )
        health.noteEvent()
    }

    private func sampleWorkspaceLayout(emitInitial: Bool) {
        let snapshot = workspaceLayoutSnapshot()
        let currentSpace = snapshot["desktop_space_id_hash"] ?? ""
        if !currentSpace.isEmpty, emitInitial || desktopSpaceID != currentSpace {
            desktopSpaceID = currentSpace
            spool.append(
                collector: "workspace_layout_activity",
                source: "system",
                stimulusType: "desktop_space_switched",
                text: "Desktop Space metadata changed.",
                metadata: snapshot,
                payload: ["desktop_space_id_hash": currentSpace],
                privacyTier: "sensitive_metadata"
            )
            health.noteEvent()
        }

        let currentStageManager = snapshot["stage_manager_enabled"] ?? ""
        if !currentStageManager.isEmpty, emitInitial || stageManagerState != currentStageManager {
            let hadPrevious = !stageManagerState.isEmpty
            stageManagerState = currentStageManager
            guard emitInitial || hadPrevious else {
                return
            }
            spool.append(
                collector: "workspace_layout_activity",
                source: "system",
                stimulusType: currentStageManager == "true" ? "stage_manager_enabled" : "stage_manager_disabled",
                text: "Stage Manager metadata changed.",
                metadata: snapshot,
                payload: ["stage_manager_enabled": currentStageManager],
                privacyTier: "sensitive_metadata"
            )
            health.noteEvent()
        }
    }

    private func sampleWindowArrangement(emitInitial: Bool) {
        guard let snapshot = frontmostWindowLayoutSnapshot() else {
            return
        }
        let windowID = snapshot["window_id"] ?? ""
        let desktopSpaceHash = snapshot["desktop_space_id_hash"] ?? ""
        let fullscreenBucket = snapshot["fullscreen_bucket"] ?? ""
        let displaySignature = [windowID, snapshot["display_id_hash"] ?? ""].joined(separator: "|")
        let spaceSignature = [windowID, desktopSpaceHash].joined(separator: "|")
        let fullscreenState = [windowID, fullscreenBucket].joined(separator: "|")

        if !displaySignature.isEmpty, emitInitial || (!windowDisplaySignature.isEmpty && windowDisplaySignature != displaySignature) {
            windowDisplaySignature = displaySignature
            emitWindow(snapshot, stimulusType: "window_moved_to_display", text: "Window display placement metadata changed.")
        } else if windowDisplaySignature.isEmpty {
            windowDisplaySignature = displaySignature
        }

        if !desktopSpaceHash.isEmpty, emitInitial || (!windowSpaceSignature.isEmpty && windowSpaceSignature != spaceSignature) {
            windowSpaceSignature = spaceSignature
            emitWindow(snapshot, stimulusType: "window_moved_to_space", text: "Window Space placement metadata changed.")
        } else if windowSpaceSignature.isEmpty, !desktopSpaceHash.isEmpty {
            windowSpaceSignature = spaceSignature
        }

        let fullscreenChanged = !windowFullscreenState.isEmpty && windowFullscreenState != fullscreenState
        let emitInitialFullscreen = emitInitial && fullscreenBucket == "fullscreen_like"
        if !fullscreenState.isEmpty, emitInitialFullscreen || fullscreenChanged {
            let isFullscreen = fullscreenBucket == "fullscreen_like"
            windowFullscreenState = fullscreenState
            emitWindow(
                snapshot,
                stimulusType: isFullscreen ? "window_fullscreen_entered" : "window_fullscreen_exited",
                text: "Window fullscreen metadata changed."
            )
        } else if windowFullscreenState.isEmpty {
            windowFullscreenState = fullscreenState
        }
    }

    private func emitWindow(_ snapshot: [String: String], stimulusType: String, text: String) {
        spool.append(
            collector: "window_arrangement_activity",
            source: "system",
            stimulusType: stimulusType,
            text: text,
            metadata: snapshot,
            payload: [
                "window_signature_hash": snapshot["window_signature_hash"] ?? "",
                "display_id_hash": snapshot["display_id_hash"] ?? "",
                "desktop_space_id_hash": snapshot["desktop_space_id_hash"] ?? "",
                "fullscreen_bucket": snapshot["fullscreen_bucket"] ?? "",
            ],
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }

    private func sampleAppWorkspace(emitInitial: Bool) {
        guard let snapshot = appWorkspaceSnapshot() else {
            return
        }
        let signature = snapshot["app_workspace_signature"] ?? ""
        guard !signature.isEmpty, emitInitial || appWorkspaceSignature != signature else {
            return
        }
        let hadPrevious = !appWorkspaceSignature.isEmpty
        appWorkspaceSignature = signature
        spool.append(
            collector: "app_workspace_activity",
            source: "activity",
            stimulusType: hadPrevious ? "app_workspace_switched" : "app_workspace_opened",
            text: "App workspace metadata changed.",
            metadata: snapshot,
            payload: ["app_workspace_signature": signature],
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }
}
