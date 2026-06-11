import Foundation

final class AppleAppsWorkflowRuntime {
    private let collector: AppleAppsWorkflowCollector
    private let pollSeconds: TimeInterval
    private var timer: Timer?

    init(spool: CollectorSpool, health: HelperHealthReporter, pollSeconds: TimeInterval) {
        self.collector = AppleAppsWorkflowCollector(spool: spool, health: health)
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
