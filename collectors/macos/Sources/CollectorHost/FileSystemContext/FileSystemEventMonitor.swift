import CoreServices
import Foundation

final class FileSystemEventMonitor {
    let pollSeconds: TimeInterval
    private let options: FileSystemContextOptions
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private let eventQueue = DispatchQueue(label: "dev.humungousaur.native-collectors.filesystem")
    private var stream: FSEventStreamRef?
    private var snapshot: [String: FileSnapshot]

    init(options: FileSystemContextOptions, spool: CollectorSpool, health: HelperHealthReporter) {
        self.options = options
        self.spool = spool
        self.health = health
        self.pollSeconds = options.pollSeconds
        self.snapshot = buildFileSnapshot(roots: fileWatchRoots(options), workspace: options.workspace, ignoredRoots: [options.dataDir])
    }

    func start() {
        var context = FSEventStreamContext(
            version: 0,
            info: Unmanaged.passUnretained(self).toOpaque(),
            retain: nil,
            release: nil,
            copyDescription: nil
        )
        let callback: FSEventStreamCallback = { _, info, _, _, _, _ in
            guard let info else {
                return
            }
            let monitor = Unmanaged<FileSystemEventMonitor>.fromOpaque(info).takeUnretainedValue()
            monitor.diffAndEmit(reason: "fsevents")
        }
        let flags = FSEventStreamCreateFlags(kFSEventStreamCreateFlagFileEvents | kFSEventStreamCreateFlagUseCFTypes | kFSEventStreamCreateFlagNoDefer)
        guard let created = FSEventStreamCreate(
            kCFAllocatorDefault,
            callback,
            &context,
            fileWatchRoots(options).map(\.path) as CFArray,
            FSEventStreamEventId(kFSEventStreamEventIdSinceNow),
            options.latency,
            flags
        ) else {
            return
        }
        stream = created
        FSEventStreamSetDispatchQueue(created, eventQueue)
        if !FSEventStreamStart(created) {
            stop()
        }
    }

    func stop() {
        guard let stream else {
            return
        }
        FSEventStreamStop(stream)
        FSEventStreamInvalidate(stream)
        FSEventStreamRelease(stream)
        self.stream = nil
    }

    func diffAndEmit(reason: String) {
        eventQueue.async { [weak self] in
            self?.diffAndEmitOnQueue(reason: reason)
        }
    }

    private func diffAndEmitOnQueue(reason: String) {
        let previous = snapshot
        let current = buildFileSnapshot(roots: fileWatchRoots(options), workspace: options.workspace, ignoredRoots: [options.dataDir])
        let previousPaths = Set(previous.keys)
        let currentPaths = Set(current.keys)
        let previousByIdentity = Dictionary(uniqueKeysWithValues: previous.values.filter { !$0.identity.isEmpty }.map { ($0.identity, $0) })
        var movedCurrentPaths: Set<String> = []
        var movedPreviousPaths: Set<String> = []

        for path in currentPaths.subtracting(previousPaths).sorted() {
            guard let info = current[path] else {
                continue
            }
            if let old = previousByIdentity[info.identity], !old.identity.isEmpty {
                emitMoveOrRename(info: info, previous: old, reason: reason)
                movedCurrentPaths.insert(path)
                movedPreviousPaths.insert(old.path)
            } else {
                emitCreated(info: info, reason: reason)
            }
        }

        for path in currentPaths.intersection(previousPaths).sorted() {
            guard !movedCurrentPaths.contains(path), let old = previous[path], let info = current[path] else {
                continue
            }
            if old.signature != info.signature {
                emitModified(info: info, reason: reason)
            }
        }

        let currentTrashCount = current.values.filter(\.isTrashItem).count
        let previousTrashCount = previous.values.filter(\.isTrashItem).count
        for path in previousPaths.subtracting(currentPaths).sorted() {
            if movedPreviousPaths.contains(path) {
                continue
            }
            guard let old = previous[path] else {
                continue
            }
            emitDeleted(info: old, reason: reason)
        }
        if previousTrashCount > 0 && currentTrashCount == 0 {
            emitTrashEmptied(reason: reason)
        }

        snapshot = current
    }

    private func emitCreated(info: FileSnapshot, reason: String) {
        if info.isDirectory {
            emitFolder(info: info, stimulusType: "folder_created", reason: reason)
        } else {
            emitFilesystem(info: info, stimulusType: "file_created", reason: reason)
            emitFileOperation(info: info, stimulusType: "file_saved", reason: reason)
            if info.isDownloadItem {
                emitDownload(info: info, reason: reason)
            }
        }
        if info.isTrashItem {
            emitTrash(info: info, stimulusType: info.isDirectory ? "folder_moved_to_trash" : "file_moved_to_trash", reason: reason)
        }
    }

    private func emitModified(info: FileSnapshot, reason: String) {
        if info.isDirectory {
            emitFolder(info: info, stimulusType: "folder_changed", reason: reason)
        } else {
            emitFilesystem(info: info, stimulusType: "file_modified", reason: reason)
            emitFileOperation(info: info, stimulusType: "file_saved", reason: reason)
            if info.isDownloadItem {
                emitDownload(info: info, reason: reason)
            }
        }
    }

    private func emitDeleted(info: FileSnapshot, reason: String) {
        if !info.isDirectory {
            emitFilesystem(info: info, stimulusType: "file_deleted", reason: reason)
        }
        if info.isTrashItem {
            emitTrash(info: info, stimulusType: "trash_item_deleted", reason: reason)
        }
    }

    private func emitMoveOrRename(info: FileSnapshot, previous: FileSnapshot, reason: String) {
        let sameParent = info.parentDigest == previous.parentDigest
        if info.isDirectory {
            emitFolder(info: info, stimulusType: sameParent ? "folder_renamed" : "folder_moved", previous: previous, reason: reason)
        } else {
            emitFileOperation(info: info, stimulusType: sameParent ? "file_renamed" : "file_moved", previous: previous, reason: reason)
        }
    }

    private func emitFilesystem(info: FileSnapshot, stimulusType: String, reason: String) {
        spool.append(
            collector: "filesystem",
            source: "activity",
            stimulusType: stimulusType,
            text: stimulusType.replacingOccurrences(of: "_", with: " ").capitalized,
            metadata: fileMetadata(info, nativeSource: "macos_fsevents", reason: reason),
            payload: filePayload(info)
        )
        health.noteEvent()
    }

    private func emitDownload(info: FileSnapshot, reason: String) {
        spool.append(
            collector: "downloads",
            source: "activity",
            stimulusType: "downloaded_file",
            text: "Downloaded or exported file changed.",
            metadata: fileMetadata(info, nativeSource: "macos_fsevents_downloads", reason: reason),
            payload: filePayload(info)
        )
        health.noteEvent()
    }

    private func emitFileOperation(info: FileSnapshot, stimulusType: String, previous: FileSnapshot? = nil, reason: String) {
        var metadata = fileMetadata(info, nativeSource: "macos_fsevents", reason: reason)
        metadata["file_action"] = stimulusType.replacingOccurrences(of: "file_", with: "")
        var payload = filePayload(info)
        if let previous {
            payload["previous_path_digest"] = previous.pathDigest
            metadata["previous_path_digest"] = previous.pathDigest
        }
        spool.append(
            collector: "file_operation_activity",
            source: "activity",
            stimulusType: stimulusType,
            text: stimulusType.replacingOccurrences(of: "_", with: " ").capitalized,
            metadata: metadata,
            payload: payload,
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }

    private func emitFolder(info: FileSnapshot, stimulusType: String, previous: FileSnapshot? = nil, reason: String) {
        var metadata = fileMetadata(info, nativeSource: "macos_fsevents", reason: reason)
        metadata["folder_action"] = stimulusType.replacingOccurrences(of: "folder_", with: "")
        var payload = filePayload(info)
        if let previous {
            payload["previous_path_digest"] = previous.pathDigest
            metadata["previous_path_digest"] = previous.pathDigest
        }
        spool.append(
            collector: "folder_navigation_activity",
            source: "activity",
            stimulusType: stimulusType,
            text: stimulusType.replacingOccurrences(of: "_", with: " ").capitalized,
            metadata: metadata,
            payload: payload,
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }

    private func emitTrash(info: FileSnapshot, stimulusType: String, reason: String) {
        var metadata = fileMetadata(info, nativeSource: "macos_trash_metadata", reason: reason)
        metadata["trash_action"] = stimulusType
        spool.append(
            collector: "trash_activity",
            source: "activity",
            stimulusType: stimulusType,
            text: stimulusType.replacingOccurrences(of: "_", with: " ").capitalized,
            metadata: metadata,
            payload: filePayload(info),
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }

    private func emitTrashEmptied(reason: String) {
        spool.append(
            collector: "trash_activity",
            source: "activity",
            stimulusType: "trash_emptied",
            text: "Trash emptied.",
            metadata: ["native_source": "macos_trash_metadata", "privacy_level": "redacted", "reason": reason],
            payload: [:],
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }
}
