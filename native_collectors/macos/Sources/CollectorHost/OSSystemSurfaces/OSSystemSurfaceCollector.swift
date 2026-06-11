import Foundation

final class OSSystemSurfaceCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var seenWindowSignatures: [String: String] = [:]
    private var recordingSurfaceSignature = ""

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func sample(emitInitial: Bool) {
        for snapshot in osSystemSurfaceSnapshots() {
            guard let surface = snapshot["os_surface"],
                  let signature = snapshot["surface_signature_hash"],
                  emitInitial || seenWindowSignatures[surface] != signature else {
                continue
            }
            seenWindowSignatures[surface] = signature
            emitSurface(surface: surface, snapshot: snapshot)
        }
        sampleRecordingSurface(emitInitial: emitInitial)
    }

    private func emitSurface(surface: String, snapshot: [String: String]) {
        let route = route(surface: surface)
        spool.append(
            collector: route.collector,
            source: route.source,
            stimulusType: route.stimulusType,
            text: route.text,
            metadata: snapshot,
            payload: [
                "surface_signature_hash": snapshot["surface_signature_hash"] ?? "",
                "os_surface": surface,
            ],
            privacyTier: route.privacyTier
        )
        health.noteEvent()
    }

    private func sampleRecordingSurface(emitInitial: Bool) {
        let signature = screenRecordingSurfaceSignature()
        if !recordingSurfaceSignature.isEmpty, recordingSurfaceSignature != signature {
            spool.append(
                collector: "media_activity",
                source: "activity",
                stimulusType: signature.isEmpty ? "screen_recording_stopped" : "screen_recording_started",
                text: "Screen recording surface metadata changed.",
                metadata: [
                    "native_source": "macos_visible_system_surface_metadata",
                    "source_api": "CGWindowListCopyWindowInfo",
                    "privacy_level": "redacted",
                    "screen_pixels_captured": "false",
                    "surface_signature_hash": signature,
                ],
                payload: ["surface_signature_hash": signature]
            )
            health.noteEvent()
        }
        if emitInitial, !signature.isEmpty {
            spool.append(
                collector: "media_activity",
                source: "activity",
                stimulusType: "screen_recording_started",
                text: "Screen recording surface metadata is visible.",
                metadata: [
                    "native_source": "macos_visible_system_surface_metadata",
                    "source_api": "CGWindowListCopyWindowInfo",
                    "privacy_level": "redacted",
                    "screen_pixels_captured": "false",
                    "surface_signature_hash": signature,
                ],
                payload: ["surface_signature_hash": signature]
            )
            health.noteEvent()
        }
        recordingSurfaceSignature = signature
    }

    private func route(surface: String) -> (collector: String, source: String, stimulusType: String, text: String, privacyTier: String) {
        switch surface {
        case "notification":
            return ("notification_activity", "activity", "notification_received", "Notification surface metadata appeared.", "metadata")
        case "spotlight":
            return ("search_activity", "activity", "spotlight_opened", "Spotlight surface metadata appeared.", "sensitive_metadata")
        case "screen_time":
            return ("wellbeing_activity", "system", "wellbeing_nudge_shown", "Screen Time or wellbeing surface metadata appeared.", "metadata")
        case "policy":
            return ("policy_activity", "system", "managed_profile_changed", "Device-management surface metadata appeared.", "metadata")
        default:
            return ("notification_activity", "activity", "notification_received", "System surface metadata appeared.", "metadata")
        }
    }
}
