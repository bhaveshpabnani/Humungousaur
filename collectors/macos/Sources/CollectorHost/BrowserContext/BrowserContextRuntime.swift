import Foundation

final class BrowserContextRuntime {
    private let browserActivity: BrowserActivityCollector
    private var timer: Timer?
    private let pollSeconds: TimeInterval

    init(spool: CollectorSpool, health: HelperHealthReporter, pollSeconds: TimeInterval) {
        self.browserActivity = BrowserActivityCollector(spool: spool, health: health)
        self.pollSeconds = pollSeconds
    }

    func start() {
        browserActivity.sample(emitInitial: true)
        timer = Timer.scheduledTimer(withTimeInterval: pollSeconds, repeats: true) { [weak self] _ in
            self?.browserActivity.sample(emitInitial: false)
        }
    }

    func sampleOnce() {
        browserActivity.sample(emitInitial: true)
    }

    func stop() {
        timer?.invalidate()
        timer = nil
    }
}
