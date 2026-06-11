import CoreServices
import CryptoKit
import Foundation

struct Options {
    var workspace: URL
    var dataDir: URL
    var watchRoots: [URL]
    var latency: TimeInterval = 0.35
    var duration: TimeInterval?
    var verbose = false

    static func parse(_ args: [String]) throws -> Options {
        let current = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        var workspace = current
        var dataDir: URL?
        var watchRoots: [URL] = []
        var latency: TimeInterval = 0.35
        var duration: TimeInterval?
        var verbose = false
        var index = 1
        while index < args.count {
            let arg = args[index]
            switch arg {
            case "--workspace":
                index += 1
                workspace = URL(fileURLWithPath: try value(args, index, after: arg)).standardizedFileURL
            case "--data-dir":
                index += 1
                dataDir = URL(fileURLWithPath: try value(args, index, after: arg)).standardizedFileURL
            case "--watch":
                index += 1
                watchRoots.append(URL(fileURLWithPath: try value(args, index, after: arg)).standardizedFileURL)
            case "--latency":
                index += 1
                latency = TimeInterval(try value(args, index, after: arg)) ?? latency
            case "--duration":
                index += 1
                duration = TimeInterval(try value(args, index, after: arg))
            case "--verbose":
                verbose = true
            case "--help", "-h":
                throw HelperExit.help
            default:
                throw HelperExit.message("Unknown argument: \(arg)")
            }
            index += 1
        }
        let resolvedDataDir = dataDir ?? workspace.appendingPathComponent("artifacts", isDirectory: true)
        if watchRoots.isEmpty {
            watchRoots = [workspace]
        }
        return Options(workspace: workspace, dataDir: resolvedDataDir, watchRoots: watchRoots, latency: latency, duration: duration, verbose: verbose)
    }
}

enum HelperExit: Error, CustomStringConvertible {
    case help
    case message(String)

    var description: String {
        switch self {
        case .help:
            return """
            Usage: HumungousaurFileEvents --workspace <path> --data-dir <path> [--watch <path> ...] [--duration seconds] [--latency seconds] [--verbose]

            Watches macOS File System Events and appends redacted collector bridge JSONL records under data_dir/collector_spool/.
            """
        case .message(let message):
            return message
        }
    }
}

struct FileInfo: Equatable {
    let path: String
    let relativePath: String
    let isDirectory: Bool
    let sizeBytes: Int64
    let modifiedNanoseconds: Int64
    let identity: String

    var signature: String {
        "\(modifiedNanoseconds):\(sizeBytes)"
    }
}

struct BridgeRecord: Encodable {
    let eventId: String
    let stimulusType: String
    let text: String
    let occurredAt: String
    let metadata: [String: String]
    let payload: [String: String]

    enum CodingKeys: String, CodingKey {
        case eventId = "event_id"
        case stimulusType = "stimulus_type"
        case text
        case occurredAt = "occurred_at"
        case metadata
        case payload
    }
}

final class BridgeWriter {
    private let dataDir: URL
    private let encoder = JSONEncoder()

    init(dataDir: URL) {
        self.dataDir = dataDir
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
    }

    func append(collector: String, stimulusType: String, text: String, metadata: [String: String], payload: [String: String]) {
        let eventId = "\(collector)-\(stimulusType)-\(payload["path_digest"] ?? digest(text))-\(digest("\(Date().timeIntervalSince1970)-\(payload)") )"
        let record = BridgeRecord(
            eventId: eventId,
            stimulusType: stimulusType,
            text: text,
            occurredAt: ISO8601DateFormatter().string(from: Date()),
            metadata: metadata,
            payload: payload
        )
        do {
            let spoolDir = dataDir.appendingPathComponent("collector_spool", isDirectory: true)
            try FileManager.default.createDirectory(at: spoolDir, withIntermediateDirectories: true)
            let path = spoolDir.appendingPathComponent("\(collector).jsonl")
            let line = try encoder.encode(record) + Data([0x0A])
            if FileManager.default.fileExists(atPath: path.path) {
                let handle = try FileHandle(forWritingTo: path)
                defer { try? handle.close() }
                try handle.seekToEnd()
                try handle.write(contentsOf: line)
            } else {
                try line.write(to: path, options: .atomic)
            }
        } catch {
            fputs("HumungousaurFileEvents write failed: \(error)\n", stderr)
        }
    }
}

final class FileEventMonitor {
    private let options: Options
    private let writer: BridgeWriter
    private let eventQueue = DispatchQueue(label: "com.umang.humungousaur.file-events")
    private var snapshot: [String: FileInfo]
    private var stream: FSEventStreamRef?
    private let ignoredParts: Set<String> = [".git", ".venv", "node_modules", ".build", "__pycache__", "artifacts", ".codex"]

    init(options: Options) {
        self.options = options
        writer = BridgeWriter(dataDir: options.dataDir)
        snapshot = [:]
        snapshot = buildSnapshot()
    }

    func start() throws {
        var context = FSEventStreamContext(
            version: 0,
            info: Unmanaged.passUnretained(self).toOpaque(),
            retain: nil,
            release: nil,
            copyDescription: nil
        )
        let callback: FSEventStreamCallback = { _, info, eventCount, eventPaths, eventFlags, _ in
            guard let info else { return }
            let monitor = Unmanaged<FileEventMonitor>.fromOpaque(info).takeUnretainedValue()
            let paths = unsafeBitCast(eventPaths, to: NSArray.self) as? [String] ?? []
            var flags: [FSEventStreamEventFlags] = []
            for index in 0..<eventCount {
                flags.append(eventFlags[index])
            }
            monitor.handle(paths: paths, flags: flags)
        }
        let flags = FSEventStreamCreateFlags(kFSEventStreamCreateFlagFileEvents | kFSEventStreamCreateFlagUseCFTypes | kFSEventStreamCreateFlagNoDefer)
        guard let created = FSEventStreamCreate(
            kCFAllocatorDefault,
            callback,
            &context,
            options.watchRoots.map(\.path) as CFArray,
            FSEventStreamEventId(kFSEventStreamEventIdSinceNow),
            options.latency,
            flags
        ) else {
            throw HelperExit.message("Could not create FSEvent stream.")
        }
        stream = created
        FSEventStreamSetDispatchQueue(created, eventQueue)
        guard FSEventStreamStart(created) else {
            throw HelperExit.message("Could not start FSEvent stream.")
        }
        if let duration = options.duration {
            Timer.scheduledTimer(withTimeInterval: duration, repeats: false) { _ in
                CFRunLoopStop(CFRunLoopGetCurrent())
            }
        }
        if options.verbose {
            print("HumungousaurFileEvents watching \(options.watchRoots.map(\.path).joined(separator: ", "))")
        }
        CFRunLoopRun()
        stop()
    }

    private func stop() {
        guard let stream else { return }
        FSEventStreamStop(stream)
        FSEventStreamInvalidate(stream)
        FSEventStreamRelease(stream)
        self.stream = nil
    }

    private func handle(paths: [String], flags: [FSEventStreamEventFlags]) {
        if options.verbose {
            for (index, path) in paths.enumerated() {
                let flag = index < flags.count ? flags[index] : 0
                print("FSEvent \(flag): \(path)")
            }
        }
        diffAndEmit()
    }

    private func diffAndEmit() {
        let previous = snapshot
        let current = buildSnapshot()
        let previousByIdentity = Dictionary(uniqueKeysWithValues: previous.values.filter { !$0.identity.isEmpty }.map { ($0.identity, $0) })
        let previousPaths = Set(previous.keys)
        let currentPaths = Set(current.keys)
        var movedOrRenamedPaths: Set<String> = []

        for path in currentPaths.subtracting(previousPaths).sorted() {
            guard let info = current[path] else { continue }
            if let old = previousByIdentity[info.identity], !old.identity.isEmpty {
                let sameParent = URL(fileURLWithPath: old.path).deletingLastPathComponent().path == URL(fileURLWithPath: info.path).deletingLastPathComponent().path
                emitMoveOrRename(info: info, previous: old, sameParent: sameParent)
                movedOrRenamedPaths.insert(path)
            } else if info.isDirectory {
                emitFolder(info: info, stimulusType: "folder_created")
            } else {
                emitFile(info: info, stimulusType: "file_saved")
            }
        }

        for path in currentPaths.intersection(previousPaths).sorted() {
            guard !movedOrRenamedPaths.contains(path), let old = previous[path], let info = current[path] else { continue }
            if old.signature == info.signature {
                continue
            }
            if info.isDirectory {
                emitFolder(info: info, stimulusType: "folder_changed")
            } else {
                emitFile(info: info, stimulusType: "file_saved")
            }
        }

        snapshot = current
    }

    private func buildSnapshot() -> [String: FileInfo] {
        var result: [String: FileInfo] = [:]
        for root in options.watchRoots {
            addInfo(root, into: &result)
            guard let enumerator = FileManager.default.enumerator(at: root, includingPropertiesForKeys: nil, options: []) else {
                continue
            }
            for case let url as URL in enumerator {
                if shouldIgnore(url) {
                    enumerator.skipDescendants()
                    continue
                }
                addInfo(url, into: &result)
            }
        }
        return result
    }

    private func addInfo(_ url: URL, into result: inout [String: FileInfo]) {
        let path = url.standardizedFileURL.path
        guard !shouldIgnore(url), let info = fileInfo(path: path) else { return }
        result[path] = info
    }

    private func fileInfo(path: String) -> FileInfo? {
        var statValue = stat()
        guard lstat(path, &statValue) == 0 else { return nil }
        let type = statValue.st_mode & S_IFMT
        let isDirectory = type == S_IFDIR
        let isFile = type == S_IFREG
        guard isDirectory || isFile else { return nil }
        let modified = Int64(statValue.st_mtimespec.tv_sec) * 1_000_000_000 + Int64(statValue.st_mtimespec.tv_nsec)
        return FileInfo(
            path: path,
            relativePath: relativePath(path),
            isDirectory: isDirectory,
            sizeBytes: isDirectory ? 0 : Int64(statValue.st_size),
            modifiedNanoseconds: modified,
            identity: "\(statValue.st_dev):\(statValue.st_ino)"
        )
    }

    private func shouldIgnore(_ url: URL) -> Bool {
        let parts = url.standardizedFileURL.pathComponents
        if parts.contains(where: { ignoredParts.contains($0) }) {
            return true
        }
        let name = url.lastPathComponent.lowercased()
        if name == ".env" || name.hasPrefix(".env.") {
            return true
        }
        return [".pem", ".key", ".p12", ".pfx", ".crt"].contains { name.hasSuffix($0) }
    }

    private func emitMoveOrRename(info: FileInfo, previous: FileInfo, sameParent: Bool) {
        if info.isDirectory {
            emitFolder(info: info, stimulusType: sameParent ? "folder_renamed" : "folder_moved", previous: previous)
        } else {
            emitFile(info: info, stimulusType: sameParent ? "file_renamed" : "file_moved", previous: previous)
        }
    }

    private func emitFile(info: FileInfo, stimulusType: String, previous: FileInfo? = nil) {
        var metadata = baseMetadata(nativeSource: "macos_fsevents_helper")
        metadata["file_action"] = String(stimulusType.dropFirst("file_".count))
        var payload = basePayload(info: info)
        if let previous {
            payload["previous_relative_path"] = previous.relativePath
            payload["previous_path_digest"] = digest(previous.path)
        }
        writer.append(
            collector: "file_operation_activity",
            stimulusType: stimulusType,
            text: stimulusType.replacingOccurrences(of: "_", with: " ").capitalized,
            metadata: metadata,
            payload: payload
        )
    }

    private func emitFolder(info: FileInfo, stimulusType: String, previous: FileInfo? = nil) {
        var metadata = baseMetadata(nativeSource: "macos_fsevents_helper")
        metadata["folder_action"] = String(stimulusType.dropFirst("folder_".count))
        var payload = basePayload(info: info)
        if let previous {
            payload["previous_relative_path"] = previous.relativePath
            payload["previous_path_digest"] = digest(previous.path)
        }
        writer.append(
            collector: "folder_navigation_activity",
            stimulusType: stimulusType,
            text: stimulusType.replacingOccurrences(of: "_", with: " ").capitalized,
            metadata: metadata,
            payload: payload
        )
    }

    private func baseMetadata(nativeSource: String) -> [String: String] {
        [
            "native_source": nativeSource,
            "platform": "Darwin",
            "privacy_level": "redacted"
        ]
    }

    private func basePayload(info: FileInfo) -> [String: String] {
        [
            "relative_path": info.relativePath,
            "modified_at": ISO8601DateFormatter().string(from: Date(timeIntervalSince1970: TimeInterval(info.modifiedNanoseconds) / 1_000_000_000)),
            "size_bytes": "\(info.sizeBytes)",
            "path_digest": digest(info.path)
        ]
    }

    private func relativePath(_ path: String) -> String {
        let workspacePath = options.workspace.standardizedFileURL.path
        if path == workspacePath {
            return "."
        }
        let prefix = workspacePath.hasSuffix("/") ? workspacePath : workspacePath + "/"
        if path.hasPrefix(prefix) {
            return String(path.dropFirst(prefix.count))
        }
        return URL(fileURLWithPath: path).lastPathComponent
    }
}

private func value(_ args: [String], _ index: Int, after flag: String) throws -> String {
    guard index < args.count else {
        throw HelperExit.message("Missing value after \(flag)")
    }
    return args[index]
}

private func digest(_ value: String) -> String {
    let data = Data(value.utf8)
    return SHA256.hash(data: data).compactMap { String(format: "%02x", $0) }.joined().prefix(16).description
}

do {
    let options = try Options.parse(CommandLine.arguments)
    let monitor = FileEventMonitor(options: options)
    try monitor.start()
} catch let exit as HelperExit {
    print(exit.description)
    switch exit {
    case .help:
        Foundation.exit(0)
    case .message:
        Foundation.exit(2)
    }
} catch {
    fputs("HumungousaurFileEvents failed: \(error)\n", stderr)
    Foundation.exit(1)
}
