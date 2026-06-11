import Foundation

struct CollectorHostOptions {
    let workspace: URL
    let dataDir: URL
    let watchRoots: [URL]
    let apiURL: URL?
    let pollSeconds: TimeInterval
    let fileEventLatency: TimeInterval
    let duration: TimeInterval?
    let once: Bool

    static func parse(_ args: [String]) -> CollectorHostOptions {
        var workspace = URL(fileURLWithPath: FileManager.default.currentDirectoryPath).standardizedFileURL
        var dataDir: URL?
        var watchRoots: [URL] = []
        var apiURL: URL?
        var pollSeconds: TimeInterval = 2
        var fileEventLatency: TimeInterval = 0.35
        var duration: TimeInterval?
        var once = false

        var index = 1
        while index < args.count {
            switch args[index] {
            case "--workspace" where index + 1 < args.count:
                workspace = URL(fileURLWithPath: args[index + 1]).standardizedFileURL
                index += 1
            case "--data-dir" where index + 1 < args.count:
                dataDir = URL(fileURLWithPath: args[index + 1]).standardizedFileURL
                index += 1
            case "--watch" where index + 1 < args.count:
                watchRoots.append(URL(fileURLWithPath: args[index + 1]).standardizedFileURL)
                index += 1
            case "--api-url" where index + 1 < args.count:
                apiURL = URL(string: args[index + 1].trimmingCharacters(in: .whitespacesAndNewlines))
                index += 1
            case "--poll-seconds" where index + 1 < args.count:
                pollSeconds = max(0.5, TimeInterval(args[index + 1]) ?? pollSeconds)
                index += 1
            case "--latency" where index + 1 < args.count,
                 "--file-event-latency" where index + 1 < args.count:
                fileEventLatency = max(0.1, TimeInterval(args[index + 1]) ?? fileEventLatency)
                index += 1
            case "--duration" where index + 1 < args.count:
                duration = TimeInterval(args[index + 1])
                index += 1
            case "--once":
                once = true
            default:
                break
            }
            index += 1
        }

        if watchRoots.isEmpty {
            watchRoots = [workspace]
        }
        return CollectorHostOptions(
            workspace: workspace,
            dataDir: dataDir ?? workspace.appendingPathComponent("artifacts", isDirectory: true),
            watchRoots: watchRoots,
            apiURL: apiURL,
            pollSeconds: pollSeconds,
            fileEventLatency: fileEventLatency,
            duration: duration,
            once: once
        )
    }
}
