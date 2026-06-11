import AVFoundation
import CoreGraphics
import CoreLocation
import Foundation

final class PermissionLocationCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var permissionStates: [String: String] = [:]
    private var locationAuthorization = ""
    private var timezoneSignature = ""
    private var regionSignature = ""

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func installObservers() -> [NativeObservation] {
        let token = NotificationCenter.default.addObserver(
            forName: .NSSystemTimeZoneDidChange,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            self?.sampleLocation(emitInitial: false)
        }
        return [(NotificationCenter.default, token)]
    }

    func sample(emitInitial: Bool) {
        samplePermissions(emitInitial: emitInitial)
        sampleLocation(emitInitial: emitInitial)
    }

    private func samplePermissions(emitInitial: Bool) {
        for snapshot in permissionSnapshots() {
            let service = snapshot["permission_service"] ?? ""
            let status = snapshot["permission_status"] ?? ""
            guard !service.isEmpty, !status.isEmpty else {
                continue
            }
            let previous = permissionStates[service]
            guard emitInitial || previous != status else {
                continue
            }
            permissionStates[service] = status
            let stimulusType = permissionStimulus(previous: previous, current: status)
            spool.append(
                collector: "permission_activity",
                source: "system",
                stimulusType: stimulusType,
                text: "Permission state metadata changed.",
                metadata: snapshot.merging([
                    "native_source": "macos_permission_state",
                    "privacy_level": "redacted",
                    "protected_content_omitted": "true",
                ], uniquingKeysWith: { current, _ in current }),
                payload: [
                    "permission_service": service,
                    "permission_status": status,
                ],
                privacyTier: "sensitive_metadata"
            )
            health.noteEvent()
        }
    }

    private func sampleLocation(emitInitial: Bool) {
        let snapshot = locationContextSnapshot()
        let authorization = snapshot["location_authorization_status"] ?? ""
        if !authorization.isEmpty, emitInitial || locationAuthorization != authorization {
            let previous = locationAuthorization
            locationAuthorization = authorization
            let stimulus = locationStimulus(previous: previous, current: authorization)
            spool.append(
                collector: "location_activity",
                source: "system",
                stimulusType: stimulus,
                text: "Location authorization metadata changed.",
                metadata: snapshot,
                payload: ["location_authorization_status": authorization],
                privacyTier: "sensitive_metadata"
            )
            health.noteEvent()
        }

        let timezone = snapshot["timezone_identifier_hash"] ?? ""
        if !timezone.isEmpty, emitInitial || timezoneSignature != timezone {
            timezoneSignature = timezone
            spool.append(
                collector: "location_activity",
                source: "system",
                stimulusType: "timezone_changed",
                text: "Time zone metadata changed.",
                metadata: snapshot,
                payload: ["timezone_identifier_hash": timezone],
                privacyTier: "sensitive_metadata"
            )
            health.noteEvent()
        }

        let region = snapshot["region_identifier_hash"] ?? ""
        if !region.isEmpty, emitInitial || regionSignature != region {
            regionSignature = region
            spool.append(
                collector: "location_activity",
                source: "system",
                stimulusType: "region_changed",
                text: "Region metadata changed.",
                metadata: snapshot,
                payload: ["region_identifier_hash": region],
                privacyTier: "sensitive_metadata"
            )
            health.noteEvent()
        }
    }

    private func permissionStimulus(previous: String?, current: String) -> String {
        if previous == "granted", current != "granted" {
            return "permission_revoked"
        }
        if current == "granted" {
            return "permission_granted"
        }
        if current == "not_determined" {
            return "permission_requested"
        }
        return "permission_denied"
    }

    private func locationStimulus(previous: String, current: String) -> String {
        if current == "authorized" {
            return "location_access_started"
        }
        if previous == "authorized", current != "authorized" {
            return "location_access_stopped"
        }
        return "location_requested"
    }
}
