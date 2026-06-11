import Foundation

struct DeveloperWorkflowOptions {
    let workspace: URL
    let dataDir: URL
    let pollSeconds: TimeInterval
}

final class DeveloperWorkflowRuntime {
    private let collector: DeveloperWorkflowCollector
    private let pollSeconds: TimeInterval
    private var timer: Timer?

    init(options: DeveloperWorkflowOptions, spool: CollectorSpool, health: HelperHealthReporter) {
        self.collector = DeveloperWorkflowCollector(options: options, spool: spool, health: health)
        self.pollSeconds = options.pollSeconds
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
