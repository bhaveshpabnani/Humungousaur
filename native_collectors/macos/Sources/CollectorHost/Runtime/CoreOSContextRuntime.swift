import AppKit
import Foundation

final class CoreOSContextRuntime {
    private let health: HelperHealthReporter
    private let pollSeconds: TimeInterval
    private let appLifecycle: AppLifecycleCollector
    private let windowContext: WindowContextCollector
    private let deviceState: DeviceStateCollector
    private let inputDevice: InputDeviceCollector
    private let keyboardIME: KeyboardIMECollector
    private let textInputSurface: TextInputSurfaceCollector
    private let pasteboardWorkflow: PasteboardWorkflowCollector
    private var timer: Timer?
    private var eventMonitors: [Any] = []

    init(spool: CollectorSpool, health: HelperHealthReporter, pollSeconds: TimeInterval) {
        self.health = health
        self.pollSeconds = pollSeconds
        let appLifecycle = AppLifecycleCollector(spool: spool, health: health)
        self.appLifecycle = appLifecycle
        self.windowContext = WindowContextCollector(spool: spool, health: health, appLifecycle: appLifecycle)
        self.deviceState = DeviceStateCollector(spool: spool, health: health)
        self.pasteboardWorkflow = PasteboardWorkflowCollector(spool: spool, health: health)
        self.inputDevice = InputDeviceCollector(spool: spool, health: health, pasteboardWorkflow: pasteboardWorkflow)
        self.keyboardIME = KeyboardIMECollector(spool: spool, health: health)
        self.textInputSurface = TextInputSurfaceCollector(spool: spool, health: health)
    }

    func start() {
        report(status: "starting", message: "Starting macOS core OS context helper.")
        installWorkspaceObservers()
        installEventMonitors()
        sampleAll(emitInitial: true)
        report(status: "running", message: "macOS core OS context helper is running.")
        timer = Timer.scheduledTimer(withTimeInterval: pollSeconds, repeats: true) { [weak self] _ in
            self?.sampleAll(emitInitial: false)
        }
    }

    func sampleOnce() {
        report(status: "running", message: "macOS core OS context helper one-shot sample.")
        sampleAll(emitInitial: true)
    }

    func stop() {
        timer?.invalidate()
        for monitor in eventMonitors {
            NSEvent.removeMonitor(monitor)
        }
        eventMonitors.removeAll()
        report(status: "stopped", message: "macOS core OS context helper stopped.")
    }

    private func installWorkspaceObservers() {
        appLifecycle.installObservers()
        deviceState.installObservers()
        windowContext.installObservers()
    }

    private func installEventMonitors() {
        eventMonitors.append(contentsOf: inputDevice.installEventMonitors())
    }

    private func sampleAll(emitInitial: Bool) {
        windowContext.sample(emitInitial: emitInitial)
        keyboardIME.sample(emitInitial: emitInitial)
        textInputSurface.sample(emitInitial: emitInitial)
        pasteboardWorkflow.sample(emitInitial: emitInitial)
        deviceState.sample(emitInitial: emitInitial)
    }

    private func report(status: String, message: String) {
        health.report(
            status: status,
            permissionState: accessibilityPermissionState(),
            message: message,
            metadata: [
                "accessibility_permission": accessibilityPermissionState(),
                "input_monitoring_note": "Global key monitors may require Input Monitoring permission.",
                "pasteboard_content_captured": "false",
                "window_title_raw_captured": "false",
            ]
        )
    }
}
