import Foundation

let options = CollectorHostOptions.parse(CommandLine.arguments)
let spool = CollectorSpool(dataDir: options.dataDir)
let health = HelperHealthReporter(apiURL: options.apiURL, spool: spool)
let collector = CollectorHostRuntime(options: options, spool: spool, health: health)
let spoolPath = options.dataDir.appendingPathComponent("collector_spool", isDirectory: true).path

if options.once {
    collector.sampleOnce()
    print("HumungousaurMacCollectorHost wrote one-shot platform collector events under \(spoolPath)")
} else {
    collector.start()
    if let duration = options.duration {
        DispatchQueue.main.asyncAfter(deadline: .now() + duration) {
            collector.stop()
            Foundation.exit(0)
        }
    }
    print("HumungousaurMacCollectorHost watching platform collector events under \(spoolPath)")
    RunLoop.main.run()
}
