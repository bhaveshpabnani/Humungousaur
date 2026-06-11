import AppKit
import Foundation

struct BrowserDefinition {
    let browserID: String
    let displayName: String
    let bundleIdentifiers: Set<String>
    let profileRoot: URL?
    let profileDirectoryNames: Set<String>
    let profileDirectoryPrefix: String?
    let isChromium: Bool
}

struct BrowserProfileSnapshot {
    let key: String
    let browserID: String
    let profileDigest: String
    let profileKind: String
    let extensionCount: Int
    let extensionSignature: String
    let webAppCount: Int
    let webAppSignature: String
    let bookmarkSignature: String
    let historySignature: String
    let tabGroupSignature: String

    var payload: [String: String] {
        [
            "browser_id": browserID,
            "profile_digest": profileDigest,
            "profile_kind": profileKind,
            "extension_signature": extensionSignature,
            "web_app_signature": webAppSignature,
            "bookmark_store_signature": bookmarkSignature,
            "history_store_signature": historySignature,
            "tab_group_store_signature": tabGroupSignature,
        ]
    }

    func metadata(reason: String) -> [String: String] {
        [
            "browser_id": browserID,
            "profile_digest": profileDigest,
            "profile_kind": profileKind,
            "native_source": "macos_browser_profile_store_metadata",
            "source_api": "FileManager",
            "reason": reason,
            "privacy_level": "redacted",
            "profile_name_omitted": "true",
            "account_details_omitted": "true",
            "raw_browser_store_content_included": "false",
        ]
    }
}

private let userApplicationSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
private let safariRoot = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Safari", isDirectory: true)

private let knownBrowserDefinitions: [BrowserDefinition] = [
    BrowserDefinition(
        browserID: "chrome",
        displayName: "Google Chrome",
        bundleIdentifiers: ["com.google.Chrome", "com.google.Chrome.canary"],
        profileRoot: userApplicationSupport?.appendingPathComponent("Google/Chrome", isDirectory: true),
        profileDirectoryNames: ["Default"],
        profileDirectoryPrefix: "Profile ",
        isChromium: true
    ),
    BrowserDefinition(
        browserID: "edge",
        displayName: "Microsoft Edge",
        bundleIdentifiers: ["com.microsoft.edgemac", "com.microsoft.edgemac.Canary"],
        profileRoot: userApplicationSupport?.appendingPathComponent("Microsoft Edge", isDirectory: true),
        profileDirectoryNames: ["Default"],
        profileDirectoryPrefix: "Profile ",
        isChromium: true
    ),
    BrowserDefinition(
        browserID: "brave",
        displayName: "Brave Browser",
        bundleIdentifiers: ["com.brave.Browser", "com.brave.Browser.nightly"],
        profileRoot: userApplicationSupport?.appendingPathComponent("BraveSoftware/Brave-Browser", isDirectory: true),
        profileDirectoryNames: ["Default"],
        profileDirectoryPrefix: "Profile ",
        isChromium: true
    ),
    BrowserDefinition(
        browserID: "arc",
        displayName: "Arc",
        bundleIdentifiers: ["company.thebrowser.Browser"],
        profileRoot: userApplicationSupport?.appendingPathComponent("Arc/User Data", isDirectory: true),
        profileDirectoryNames: ["Default"],
        profileDirectoryPrefix: "Profile ",
        isChromium: true
    ),
    BrowserDefinition(
        browserID: "safari",
        displayName: "Safari",
        bundleIdentifiers: ["com.apple.Safari", "com.apple.SafariTechnologyPreview"],
        profileRoot: safariRoot,
        profileDirectoryNames: [],
        profileDirectoryPrefix: nil,
        isChromium: false
    ),
]

func browserDefinition(for app: NSRunningApplication) -> BrowserDefinition? {
    guard let bundleID = app.bundleIdentifier else {
        return nil
    }
    if let direct = knownBrowserDefinitions.first(where: { $0.bundleIdentifiers.contains(bundleID) }) {
        return direct
    }
    if bundleID.hasPrefix("com.google.Chrome.app.") {
        return knownBrowserDefinitions.first(where: { $0.browserID == "chrome" })
    }
    if bundleID.hasPrefix("com.microsoft.edgemac.app.") {
        return knownBrowserDefinitions.first(where: { $0.browserID == "edge" })
    }
    if bundleID.hasPrefix("com.brave.Browser.app.") {
        return knownBrowserDefinitions.first(where: { $0.browserID == "brave" })
    }
    return nil
}

func browserWindowMetadata(app: NSRunningApplication, definition: BrowserDefinition, snapshot: [String: String]) -> [String: String] {
    [
        "browser_id": definition.browserID,
        "browser_bundle_id": app.bundleIdentifier ?? "",
        "process_identifier": String(app.processIdentifier),
        "window_visible": snapshot["window_visible"] ?? "false",
        "window_id": snapshot["window_id"] ?? "",
        "window_title_present": snapshot["window_title_present"] ?? "false",
        "window_title_hash": snapshot["window_title_hash"] ?? "",
        "window_title_length_bucket": snapshot["window_title_length_bucket"] ?? "",
        "window_bounds_bucket": snapshot["window_bounds_bucket"] ?? "",
        "native_source": "macos_nsworkspace_coregraphics_browser_metadata",
        "source_api": "NSWorkspace+CGWindowList",
        "privacy_level": "redacted",
        "url_omitted": "true",
        "title_omitted": "true",
        "page_content_omitted": "true",
    ]
}

func browserProfileSnapshots() -> [BrowserProfileSnapshot] {
    knownBrowserDefinitions.flatMap { definition -> [BrowserProfileSnapshot] in
        guard let root = definition.profileRoot,
              FileManager.default.fileExists(atPath: root.path) else {
            return []
        }
        return definition.isChromium
            ? chromiumProfileSnapshots(definition: definition, root: root)
            : safariProfileSnapshots(definition: definition, root: root)
    }
}

private func chromiumProfileSnapshots(definition: BrowserDefinition, root: URL) -> [BrowserProfileSnapshot] {
    guard let children = try? FileManager.default.contentsOfDirectory(
        at: root,
        includingPropertiesForKeys: [.isDirectoryKey, .contentModificationDateKey, .fileSizeKey],
        options: [.skipsHiddenFiles]
    ) else {
        return []
    }
    return children.compactMap { url in
        guard isDirectory(url),
              definition.profileDirectoryNames.contains(url.lastPathComponent)
                || definition.profileDirectoryPrefix.map({ url.lastPathComponent.hasPrefix($0) }) == true else {
            return nil
        }
        let profileDigest = shortDigest("\(definition.browserID)|\(url.standardizedFileURL.path)")
        let extensionStore = directorySignature(url.appendingPathComponent("Extensions", isDirectory: true))
        let webAppStore = directorySignature(url.appendingPathComponent("Web Applications", isDirectory: true))
        let bookmarkStore = fileSignature(url.appendingPathComponent("Bookmarks"))
        let historyStore = fileSignature(url.appendingPathComponent("History"))
        let tabGroupStore = aggregateSignature([
            directorySignature(url.appendingPathComponent("Sessions", isDirectory: true)).signature,
            fileSignature(root.appendingPathComponent("Current Tabs")).signature,
            fileSignature(root.appendingPathComponent("Current Session")).signature,
        ])
        return BrowserProfileSnapshot(
            key: "\(definition.browserID)|\(profileDigest)",
            browserID: definition.browserID,
            profileDigest: profileDigest,
            profileKind: url.lastPathComponent == "Default" ? "default" : "profile",
            extensionCount: extensionStore.count,
            extensionSignature: extensionStore.signature,
            webAppCount: webAppStore.count,
            webAppSignature: webAppStore.signature,
            bookmarkSignature: bookmarkStore.signature,
            historySignature: historyStore.signature,
            tabGroupSignature: tabGroupStore
        )
    }
}

private func safariProfileSnapshots(definition: BrowserDefinition, root: URL) -> [BrowserProfileSnapshot] {
    let profileDigest = shortDigest("\(definition.browserID)|\(root.standardizedFileURL.path)")
    let bookmarkStore = fileSignature(root.appendingPathComponent("Bookmarks.plist"))
    let historyStore = fileSignature(root.appendingPathComponent("History.db"))
    let tabGroupStore = aggregateSignature([
        fileSignature(root.appendingPathComponent("CloudTabs.db")).signature,
        directorySignature(root.appendingPathComponent("Profiles", isDirectory: true)).signature,
    ])
    return [
        BrowserProfileSnapshot(
            key: "\(definition.browserID)|\(profileDigest)",
            browserID: definition.browserID,
            profileDigest: profileDigest,
            profileKind: "safari",
            extensionCount: 0,
            extensionSignature: "missing",
            webAppCount: 0,
            webAppSignature: "missing",
            bookmarkSignature: bookmarkStore.signature,
            historySignature: historyStore.signature,
            tabGroupSignature: tabGroupStore
        )
    ]
}

private func directorySignature(_ url: URL) -> (count: Int, signature: String) {
    guard FileManager.default.fileExists(atPath: url.path),
          let children = try? FileManager.default.contentsOfDirectory(
            at: url,
            includingPropertiesForKeys: [.isDirectoryKey, .contentModificationDateKey, .fileSizeKey],
            options: [.skipsHiddenFiles]
          ) else {
        return (0, "missing")
    }
    let parts = children.sorted { $0.path < $1.path }.map { child in
        "\(shortDigest(child.standardizedFileURL.path)):\(fileSignature(child).signature)"
    }
    return (children.count, aggregateSignature(parts))
}

private func fileSignature(_ url: URL) -> (count: Int, signature: String) {
    guard let values = try? url.resourceValues(forKeys: [.contentModificationDateKey, .fileSizeKey]) else {
        return (0, "missing")
    }
    let modified = values.contentModificationDate?.timeIntervalSince1970 ?? 0
    let size = values.fileSize ?? 0
    return (1, shortDigest("\(url.standardizedFileURL.path)|\(Int(modified))|\(size)"))
}

private func aggregateSignature(_ parts: [String]) -> String {
    let cleaned = parts.filter { !$0.isEmpty }
    return cleaned.isEmpty ? "missing" : shortDigest(cleaned.sorted().joined(separator: "|"))
}

private func isDirectory(_ url: URL) -> Bool {
    (try? url.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) == true
}

func countBucket(_ count: Int) -> String {
    switch count {
    case 0: return "0"
    case 1: return "1"
    case 2...5: return "2-5"
    case 6...20: return "6-20"
    default: return "20+"
    }
}
