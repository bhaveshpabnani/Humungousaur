import Foundation

struct FileSystemContextOptions {
    let workspace: URL
    let dataDir: URL
    let watchRoots: [URL]
    let latency: TimeInterval
    let pollSeconds: TimeInterval
}

final class FileSystemContextRuntime {
    private let monitor: FileSystemEventMonitor
    private let fileManagerUI: FileManagerUICollector
    private var timer: Timer?

    init(options: FileSystemContextOptions, spool: CollectorSpool, health: HelperHealthReporter) {
        self.monitor = FileSystemEventMonitor(options: options, spool: spool, health: health)
        self.fileManagerUI = FileManagerUICollector(spool: spool, health: health)
    }

    func start() {
        monitor.start()
        fileManagerUI.sample(emitInitial: true)
        timer = Timer.scheduledTimer(withTimeInterval: monitor.pollSeconds, repeats: true) { [weak self] _ in
            self?.monitor.diffAndEmit(reason: "timer")
            self?.fileManagerUI.sample(emitInitial: false)
        }
    }

    func sampleOnce() {
        monitor.diffAndEmit(reason: "one_shot")
        fileManagerUI.sample(emitInitial: true)
    }

    func stop() {
        timer?.invalidate()
        monitor.stop()
    }
}
