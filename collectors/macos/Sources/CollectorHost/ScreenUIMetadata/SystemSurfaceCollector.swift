import Foundation

final class SystemSurfaceCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var surfaceSignatures: [String: String] = [:]

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func sample(emitInitial: Bool) {
        for snapshot in visibleSystemSurfaceSnapshots() {
            emit(snapshot, emitInitial: emitInitial)
        }
    }

    private func emit(_ snapshot: [String: String], emitInitial: Bool) {
        guard let surface = snapshot["system_surface"] else {
            return
        }
        let signature = [
            snapshot["bundle_id"] ?? "",
            snapshot["window_id"] ?? "",
            snapshot["window_title_hash"] ?? "",
            snapshot["window_bounds_bucket"] ?? "",
        ].joined(separator: "|")
        guard emitInitial || surfaceSignatures[surface] != signature else {
            return
        }
        surfaceSignatures[surface] = signature
        let route = route(surface: surface)
        spool.append(
            collector: route.collector,
            source: "system",
            stimulusType: route.stimulusType,
            text: route.text,
            metadata: snapshot.merging(["native_source": "macos_system_surface_window_metadata", "privacy_level": "redacted"], uniquingKeysWith: { current, _ in current }),
            payload: ["surface_signature_hash": sha256(signature), "system_surface": surface],
            privacyTier: route.privacyTier
        )
        health.noteEvent()
    }

    private func route(surface: String) -> (collector: String, stimulusType: String, text: String, privacyTier: String) {
        switch surface {
        case "dock":
            return ("dock_taskbar_activity", "dock_item_clicked", "Dock surface became active.", "sensitive_metadata")
        case "control_center":
            return ("quick_settings_activity", "control_center_opened", "Control Center opened.", "metadata")
        case "menu_bar":
            return ("menu_bar_tray_activity", "status_item_opened", "Menu bar status surface opened.", "sensitive_metadata")
        case "notification_center":
            return ("widget_activity", "widget_panel_opened", "Widget or notification panel opened.", "sensitive_metadata")
        default:
            return ("menu_bar_tray_activity", "background_app_menu_opened", "System surface opened.", "sensitive_metadata")
        }
    }
}
