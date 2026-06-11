import AppKit
import Foundation

final class FocusTaskCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var desktopSpaceHash = ""
    private var lowPowerMode = ""

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func installObservers() -> [NativeObservation] {
        let center = NSWorkspace.shared.notificationCenter
        let space = center.addObserver(forName: NSWorkspace.activeSpaceDidChangeNotification, object: nil, queue: .main) { [weak self] _ in
            self?.sample(emitInitial: false)
        }
        let lowPower = NotificationCenter.default.addObserver(forName: .NSProcessInfoPowerStateDidChange, object: nil, queue: .main) { [weak self] _ in
            self?.sample(emitInitial: false)
        }
        return [(center, space), (NotificationCenter.default, lowPower)]
    }

    func sample(emitInitial: Bool) {
        let workspace = workspaceLayoutSnapshot()
        let currentSpace = workspace["desktop_space_id_hash"] ?? ""
        if !currentSpace.isEmpty, emitInitial || (!desktopSpaceHash.isEmpty && desktopSpaceHash != currentSpace) {
            desktopSpaceHash = currentSpace
            spool.append(
                collector: "focus_task_activity",
                source: "activity",
                stimulusType: "desktop_space_changed",
                text: "Desktop Space metadata changed.",
                metadata: workspace,
                payload: ["desktop_space_id_hash": currentSpace],
                privacyTier: "sensitive_metadata"
            )
            health.noteEvent()
        } else if desktopSpaceHash.isEmpty {
            desktopSpaceHash = currentSpace
        }

        let currentLowPower = String(ProcessInfo.processInfo.isLowPowerModeEnabled)
        if emitInitial || (!lowPowerMode.isEmpty && lowPowerMode != currentLowPower) {
            lowPowerMode = currentLowPower
            spool.append(
                collector: "focus_task_activity",
                source: "activity",
                stimulusType: "mode_changed",
                text: "System task mode metadata changed.",
                metadata: [
                    "native_source": "macos_processinfo_power_mode",
                    "source_api": "ProcessInfo",
                    "privacy_level": "redacted",
                    "low_power_mode": currentLowPower,
                ],
                payload: ["low_power_mode": currentLowPower]
            )
            health.noteEvent()
        } else if lowPowerMode.isEmpty {
            lowPowerMode = currentLowPower
        }
    }
}
