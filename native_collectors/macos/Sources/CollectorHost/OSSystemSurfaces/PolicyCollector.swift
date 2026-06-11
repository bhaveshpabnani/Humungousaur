import Foundation

final class PolicyCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var enrollmentSignature = ""

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func sample(emitInitial: Bool) {
        guard let snapshot = managedProfileSnapshot(),
              let signature = snapshot["managed_profile_signature_hash"],
              emitInitial || enrollmentSignature != signature else {
            return
        }
        enrollmentSignature = signature
        spool.append(
            collector: "policy_activity",
            source: "system",
            stimulusType: "managed_profile_changed",
            text: "Managed-device profile metadata changed.",
            metadata: snapshot,
            payload: ["managed_profile_signature_hash": signature]
        )
        health.noteEvent()
    }
}
