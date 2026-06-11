import Darwin
import Foundation

struct FileSnapshot {
    let path: String
    let isDirectory: Bool
    let sizeBytes: Int64
    let modifiedNanoseconds: Int64
    let identity: String
    let pathDigest: String
    let parentDigest: String
    let extensionName: String
    let pathDepth: Int
    let isDownloadItem: Bool
    let isTrashItem: Bool

    var signature: String {
        "\(modifiedNanoseconds):\(sizeBytes)"
    }
}

private let ignoredPathParts: Set<String> = [".git", ".venv", "node_modules", ".build", "__pycache__", "artifacts", ".codex"]

func fileWatchRoots(_ options: FileSystemContextOptions) -> [URL] {
    var roots = options.watchRoots
    roots.append(contentsOf: downloadRoots())
    roots.append(contentsOf: trashRoots())
    var seen: Set<String> = []
    return roots.compactMap { root in
        let standardized = root.standardizedFileURL
        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: standardized.path, isDirectory: &isDirectory), isDirectory.boolValue else {
            return nil
        }
        guard !seen.contains(standardized.path) else {
            return nil
        }
        seen.insert(standardized.path)
        return standardized
    }
}

func buildFileSnapshot(roots: [URL], workspace: URL, ignoredRoots: [URL]) -> [String: FileSnapshot] {
    var result: [String: FileSnapshot] = [:]
    for root in roots {
        addFileSnapshot(root, workspace: workspace, ignoredRoots: ignoredRoots, into: &result)
        guard let enumerator = FileManager.default.enumerator(at: root, includingPropertiesForKeys: nil, options: [.skipsPackageDescendants]) else {
            continue
        }
        for case let url as URL in enumerator {
            if shouldIgnoreFileURL(url, ignoredRoots: ignoredRoots) {
                enumerator.skipDescendants()
                continue
            }
            addFileSnapshot(url, workspace: workspace, ignoredRoots: ignoredRoots, into: &result)
        }
    }
    return result
}

func addFileSnapshot(_ url: URL, workspace: URL, ignoredRoots: [URL], into result: inout [String: FileSnapshot]) {
    let standardized = url.standardizedFileURL
    guard !shouldIgnoreFileURL(standardized, ignoredRoots: ignoredRoots),
          let snapshot = fileSnapshot(path: standardized.path, workspace: workspace) else {
        return
    }
    result[standardized.path] = snapshot
}

func fileSnapshot(path: String, workspace: URL) -> FileSnapshot? {
    var statValue = stat()
    guard lstat(path, &statValue) == 0 else {
        return nil
    }
    let type = statValue.st_mode & S_IFMT
    let isDirectory = type == S_IFDIR
    let isFile = type == S_IFREG
    guard isDirectory || isFile else {
        return nil
    }
    let url = URL(fileURLWithPath: path)
    let modified = Int64(statValue.st_mtimespec.tv_sec) * 1_000_000_000 + Int64(statValue.st_mtimespec.tv_nsec)
    return FileSnapshot(
        path: path,
        isDirectory: isDirectory,
        sizeBytes: isDirectory ? 0 : Int64(statValue.st_size),
        modifiedNanoseconds: modified,
        identity: "\(statValue.st_dev):\(statValue.st_ino)",
        pathDigest: shortDigest(path),
        parentDigest: shortDigest(url.deletingLastPathComponent().path),
        extensionName: isDirectory ? "" : sanitizedExtension(url.pathExtension),
        pathDepth: max(0, url.standardizedFileURL.pathComponents.count - workspace.standardizedFileURL.pathComponents.count),
        isDownloadItem: isUnder(url, roots: downloadRoots()),
        isTrashItem: isUnder(url, roots: trashRoots())
    )
}

func shouldIgnoreFileURL(_ url: URL, ignoredRoots: [URL]) -> Bool {
    let standardized = url.standardizedFileURL
    if ignoredRoots.contains(where: { isUnder(standardized, root: $0) }) {
        return true
    }
    if standardized.pathComponents.contains(where: { ignoredPathParts.contains($0) }) {
        return true
    }
    let name = standardized.lastPathComponent.lowercased()
    if name == ".env" || name.hasPrefix(".env.") {
        return true
    }
    return [".pem", ".key", ".p12", ".pfx", ".crt"].contains { name.hasSuffix($0) }
}

func fileMetadata(_ info: FileSnapshot, nativeSource: String, reason: String) -> [String: String] {
    [
        "native_source": nativeSource,
        "reason": reason,
        "path_digest": info.pathDigest,
        "parent_digest": info.parentDigest,
        "file_extension": info.extensionName,
        "file_kind": info.isDirectory ? "directory" : "file",
        "path_depth_bucket": depthBucket(info.pathDepth),
        "size_bucket": sizeBucket(info.sizeBytes),
        "modified_at": isoString(nanoseconds: info.modifiedNanoseconds),
        "privacy_level": "redacted",
    ]
}

func filePayload(_ info: FileSnapshot) -> [String: String] {
    [
        "path_digest": info.pathDigest,
        "parent_digest": info.parentDigest,
        "file_extension": info.extensionName,
        "file_kind": info.isDirectory ? "directory" : "file",
        "path_depth_bucket": depthBucket(info.pathDepth),
        "size_bucket": sizeBucket(info.sizeBytes),
        "modified_at": isoString(nanoseconds: info.modifiedNanoseconds),
    ]
}

func downloadRoots() -> [URL] {
    FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask)
}

func trashRoots() -> [URL] {
    let homeTrash = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".Trash", isDirectory: true)
    return [homeTrash]
}

func isUnder(_ url: URL, roots: [URL]) -> Bool {
    roots.contains { isUnder(url, root: $0) }
}

func isUnder(_ url: URL, root: URL) -> Bool {
    let path = url.standardizedFileURL.path
    let rootPath = root.standardizedFileURL.path
    return path == rootPath || path.hasPrefix(rootPath.hasSuffix("/") ? rootPath : rootPath + "/")
}

func sanitizedExtension(_ value: String) -> String {
    let cleaned = value.lowercased().filter { $0.isLetter || $0.isNumber }
    return String(cleaned.prefix(12))
}

func depthBucket(_ depth: Int) -> String {
    switch depth {
    case ...0: return "0"
    case 1...2: return "1-2"
    case 3...5: return "3-5"
    default: return "6+"
    }
}

func sizeBucket(_ bytes: Int64) -> String {
    switch bytes {
    case ..<1_024: return "0-1kb"
    case ..<1_048_576: return "1kb-1mb"
    case ..<104_857_600: return "1mb-100mb"
    default: return "100mb+"
    }
}

func isoString(nanoseconds: Int64) -> String {
    ISO8601DateFormatter().string(from: Date(timeIntervalSince1970: TimeInterval(nanoseconds) / 1_000_000_000))
}
