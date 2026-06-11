import AppKit
import Foundation

final class CommunicationMeetingsRuntime {
    private let appActivity: CommunicationMeetingAppCollector
    private let shortcuts: CommunicationShortcutCollector
    private let pollSeconds: TimeInterval
    private var timer: Timer?
    private var observations: [NativeObservation] = []
    private var eventMonitors: [Any] = []

    init(spool: CollectorSpool, health: HelperHealthReporter, pollSeconds: TimeInterval) {
        self.appActivity = CommunicationMeetingAppCollector(spool: spool, health: health)
        self.shortcuts = CommunicationShortcutCollector(spool: spool, health: health)
        self.pollSeconds = pollSeconds
    }

    func start() {
        observations.append(contentsOf: appActivity.installObservers())
        eventMonitors.append(contentsOf: shortcuts.installEventMonitors())
        appActivity.sample(emitInitial: true)
        timer = Timer.scheduledTimer(withTimeInterval: pollSeconds, repeats: true) { [weak self] _ in
            self?.appActivity.sample(emitInitial: false)
        }
    }

    func sampleOnce() {
        appActivity.sample(emitInitial: true)
    }

    func stop() {
        timer?.invalidate()
        timer = nil
        for observation in observations {
            observation.center.removeObserver(observation.token)
        }
        observations.removeAll()
        for monitor in eventMonitors {
            NSEvent.removeMonitor(monitor)
        }
        eventMonitors.removeAll()
    }
}
