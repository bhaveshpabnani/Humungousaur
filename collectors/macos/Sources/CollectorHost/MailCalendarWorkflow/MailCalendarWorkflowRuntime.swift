import Foundation

final class MailCalendarWorkflowRuntime {
    private let collector: MailCalendarWorkflowCollector
    private let pollSeconds: TimeInterval
    private var timer: Timer?

    init(spool: CollectorSpool, health: HelperHealthReporter, pollSeconds: TimeInterval) {
        self.collector = MailCalendarWorkflowCollector(spool: spool, health: health)
        self.pollSeconds = pollSeconds
    }

    func start() {
        collector.sample(emitInitial: true)
        timer = Timer.scheduledTimer(withTimeInterval: pollSeconds, repeats: true) { [weak self] _ in
            self?.collector.sample(emitInitial: false)
        }
    }

    func sampleOnce() {
        collector.sample(emitInitial: true)
    }

    func stop() {
        timer?.invalidate()
        timer = nil
    }
}
