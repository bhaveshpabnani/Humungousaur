import Foundation

final class ResourceStorageCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var thermalState = ""
    private var rootStorageSignature = ""
    private var lowVolumeSignatures: Set<String> = []

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func sample(emitInitial: Bool) {
        sampleResources(emitInitial: emitInitial)
        sampleStorage(emitInitial: emitInitial)
    }

    private func sampleResources(emitInitial: Bool) {
        let snapshot = resourcePressureSnapshot()
        let thermal = snapshot["thermal_state"] ?? ""
        if ["serious", "critical"].contains(thermal), emitInitial || thermalState != thermal {
            thermalState = thermal
            spool.append(
                collector: "resource_activity",
                source: "system",
                stimulusType: "thermal_pressure_high",
                text: "Thermal pressure metadata is high.",
                metadata: snapshot,
                payload: ["thermal_state": thermal]
            )
            health.noteEvent()
        } else if !thermal.isEmpty {
            thermalState = thermal
        }
    }

    private func sampleStorage(emitInitial: Bool) {
        if let root = rootStorageSnapshot() {
            let signature = root["storage_signature_hash"] ?? ""
            let low = root["storage_low"] == "true"
            if low, !signature.isEmpty, emitInitial || rootStorageSignature != signature {
                rootStorageSignature = signature
                spool.append(
                    collector: "storage_activity",
                    source: "system",
                    stimulusType: "disk_space_low",
                    text: "Root disk free-space metadata is low.",
                    metadata: root,
                    payload: ["storage_signature_hash": signature]
                )
                health.noteEvent()
            } else if !signature.isEmpty {
                rootStorageSignature = signature
            }
        }

        let lowVolumes = mountedVolumeStorageSnapshots().filter { $0["storage_low"] == "true" }
        let current = Set(lowVolumes.compactMap { $0["storage_signature_hash"] })
        for snapshot in lowVolumes {
            guard let signature = snapshot["storage_signature_hash"],
                  emitInitial || !lowVolumeSignatures.contains(signature) else {
                continue
            }
            spool.append(
                collector: "storage_activity",
                source: "system",
                stimulusType: "volume_space_low",
                text: "Mounted volume free-space metadata is low.",
                metadata: snapshot,
                payload: ["storage_signature_hash": signature]
            )
            health.noteEvent()
        }
        lowVolumeSignatures = current
    }
}
