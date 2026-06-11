import AppKit
import Foundation

final class PeripheralCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var displaySignature = ""
    private var displayCount = 0
    private var usbDevices: Set<String> = []
    private var mountedVolumes: Set<String> = []
    private var baselineReady = false

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func installObservers() -> [NativeObservation] {
        let workspace = NSWorkspace.shared.notificationCenter
        let mount = workspace.addObserver(forName: NSWorkspace.didMountNotification, object: nil, queue: .main) { [weak self] _ in
            self?.sample(emitInitial: false)
        }
        let unmount = workspace.addObserver(forName: NSWorkspace.didUnmountNotification, object: nil, queue: .main) { [weak self] _ in
            self?.sample(emitInitial: false)
        }
        let screen = NotificationCenter.default.addObserver(forName: NSApplication.didChangeScreenParametersNotification, object: nil, queue: .main) { [weak self] _ in
            self?.sample(emitInitial: false)
        }
        return [(workspace, mount), (workspace, unmount), (NotificationCenter.default, screen)]
    }

    func sample(emitInitial: Bool) {
        let displays = displayPeripheralSnapshot()
        let currentDisplaySignature = displays["display_signature_hash"] ?? ""
        let currentDisplayCount = Int(displays["display_count"] ?? "") ?? 0
        if !displaySignature.isEmpty, !currentDisplaySignature.isEmpty, displaySignature != currentDisplaySignature {
            let currentCount = Int(displays["display_count"] ?? "") ?? 0
            emit(stimulusType: currentCount >= displayCount ? "external_display_connected" : "external_display_disconnected", metadata: displays, payload: ["display_signature_hash": currentDisplaySignature])
        }
        displaySignature = currentDisplaySignature
        displayCount = currentDisplayCount

        let currentUSB = usbDeviceSignatureSet()
        let currentVolumes = mountedVolumeSignatureSet()
        if !baselineReady {
            usbDevices = currentUSB
            mountedVolumes = currentVolumes
            baselineReady = true
            return
        }
        for signature in currentUSB.subtracting(usbDevices) {
            emit(stimulusType: "usb_device_connected", metadata: peripheralMetadata(kind: "usb", signature: signature), payload: ["device_signature_hash": signature])
        }
        for signature in usbDevices.subtracting(currentUSB) {
            emit(stimulusType: "usb_device_disconnected", metadata: peripheralMetadata(kind: "usb", signature: signature), payload: ["device_signature_hash": signature])
        }
        for signature in currentVolumes.subtracting(mountedVolumes) {
            emit(stimulusType: "storage_device_mounted", metadata: peripheralMetadata(kind: "storage_volume", signature: signature), payload: ["volume_signature_hash": signature])
        }
        for signature in mountedVolumes.subtracting(currentVolumes) {
            emit(stimulusType: "storage_device_ejected", metadata: peripheralMetadata(kind: "storage_volume", signature: signature), payload: ["volume_signature_hash": signature])
        }
        usbDevices = currentUSB
        mountedVolumes = currentVolumes
    }

    private func emit(stimulusType: String, metadata: [String: String], payload: [String: String]) {
        spool.append(
            collector: "peripheral_activity",
            source: "system",
            stimulusType: stimulusType,
            text: "Peripheral metadata changed.",
            metadata: metadata,
            payload: payload
        )
        health.noteEvent()
    }
}
