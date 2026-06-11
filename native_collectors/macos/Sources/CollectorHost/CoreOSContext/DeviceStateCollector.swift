import AppKit
import Foundation

final class DeviceStateCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var powerSignature = ""
    private var networkSignature = ""
    private var idleBucket = ""

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func installObservers() {
        let center = NSWorkspace.shared.notificationCenter
        center.addObserver(forName: NSWorkspace.screensDidSleepNotification, object: nil, queue: .main) { [weak self] _ in
            self?.emit(stimulusType: "screen_locked", text: "Screen locked or slept.", metadata: ["signal": "screens_did_sleep"])
        }
        center.addObserver(forName: NSWorkspace.screensDidWakeNotification, object: nil, queue: .main) { [weak self] _ in
            self?.emit(stimulusType: "screen_unlocked", text: "Screen unlocked or woke.", metadata: ["signal": "screens_did_wake"])
        }
        center.addObserver(forName: NSWorkspace.willSleepNotification, object: nil, queue: .main) { [weak self] _ in
            self?.emit(stimulusType: "sleep_started", text: "System sleep started.", metadata: ["signal": "will_sleep"])
        }
        center.addObserver(forName: NSWorkspace.didWakeNotification, object: nil, queue: .main) { [weak self] _ in
            self?.emit(stimulusType: "wake_started", text: "System wake started.", metadata: ["signal": "did_wake"])
        }
    }

    func sample(emitInitial: Bool) {
        samplePower(emitInitial: emitInitial)
        sampleNetwork(emitInitial: emitInitial)
        sampleIdle(emitInitial: emitInitial)
    }

    private func samplePower(emitInitial: Bool) {
        let power = powerSnapshot()
        let signature = "\(power["power_source_state"] ?? "")|\(power["battery_percent_bucket"] ?? "")|\(power["low_power_mode"] ?? "")"
        guard emitInitial || signature != powerSignature else {
            return
        }
        let previous = powerSignature
        powerSignature = signature
        if power["battery_low"] == "true" {
            emit(stimulusType: "battery_low", text: "Battery is low.", metadata: power)
        }
        if !previous.isEmpty, power["power_source_state"] == "AC Power" {
            emit(stimulusType: "charger_connected", text: "Charger connected.", metadata: power)
        }
    }

    private func sampleNetwork(emitInitial: Bool) {
        let network = networkSnapshot()
        let signature = "\(network["reachable"] ?? "")|\(network["connection_required"] ?? "")|\(network["transient_connection"] ?? "")"
        guard emitInitial || signature != networkSignature else {
            return
        }
        let previous = networkSignature
        networkSignature = signature
        if !previous.isEmpty {
            emit(stimulusType: "network_changed", text: "Network reachability changed.", metadata: network)
        }
    }

    private func sampleIdle(emitInitial: Bool) {
        guard let idleSeconds = idleSeconds() else {
            return
        }
        let bucket = idleSeconds >= 300 ? "idle" : "active"
        guard emitInitial || bucket != idleBucket else {
            return
        }
        let previous = idleBucket
        idleBucket = bucket
        spool.append(
            collector: "device_state",
            source: "system",
            stimulusType: "user_idle_state_changed",
            text: "User idle state changed to \(bucket).",
            metadata: [
                "idle_bucket": bucket,
                "idle_seconds_bucket": idleSecondsBucket(idleSeconds),
                "source_api": "IOHIDSystem",
            ],
            payload: ["previous_idle_bucket": previous]
        )
        health.noteEvent()
    }

    private func emit(stimulusType: String, text: String, metadata: [String: String]) {
        spool.append(
            collector: "device_state",
            source: "system",
            stimulusType: stimulusType,
            text: text,
            metadata: metadata,
            payload: [:]
        )
        health.noteEvent()
    }
}
