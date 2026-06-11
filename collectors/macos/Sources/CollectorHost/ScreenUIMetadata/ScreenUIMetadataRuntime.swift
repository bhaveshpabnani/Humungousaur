import AppKit
import Foundation

final class ScreenUIMetadataRuntime {
    private let accessibility: AccessibilityContextCollector
    private let shortcuts: UIShortcutCollector
    private let systemSurfaces: SystemSurfaceCollector
    private let workspaceLayout: WorkspaceLayoutCollector
    private let pollSeconds: TimeInterval
    private var timer: Timer?
    private var eventMonitors: [Any] = []

    init(spool: CollectorSpool, health: HelperHealthReporter, pollSeconds: TimeInterval) {
        self.accessibility = AccessibilityContextCollector(spool: spool, health: health)
        self.shortcuts = UIShortcutCollector(spool: spool, health: health)
        self.systemSurfaces = SystemSurfaceCollector(spool: spool, health: health)
        self.workspaceLayout = WorkspaceLayoutCollector(spool: spool, health: health)
        self.pollSeconds = pollSeconds
    }

    func start() {
        eventMonitors.append(contentsOf: shortcuts.installEventMonitors())
        sampleAll(emitInitial: true)
        timer = Timer.scheduledTimer(withTimeInterval: pollSeconds, repeats: true) { [weak self] _ in
            self?.sampleAll(emitInitial: false)
        }
    }

    func sampleOnce() {
        sampleAll(emitInitial: true)
    }

    func stop() {
        timer?.invalidate()
        for monitor in eventMonitors {
            NSEvent.removeMonitor(monitor)
        }
        eventMonitors.removeAll()
    }

    private func sampleAll(emitInitial: Bool) {
        accessibility.sample(emitInitial: emitInitial)
        systemSurfaces.sample(emitInitial: emitInitial)
        workspaceLayout.sample(emitInitial: emitInitial)
    }
}
