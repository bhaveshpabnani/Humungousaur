import AppKit
import Foundation

struct AppleAppForegroundRoute {
    let key: String
    let collector: String
    let source: String
    let stimulusType: String
    let text: String
    let privacyTier: String
    let appFamily: String
    let metadata: [String: String]
}

struct AppleAppStateSnapshot {
    let key: String
    let collector: String
    let source: String
    let stimulusType: String
    let text: String
    let signature: String
    let metadata: [String: String]
    let payload: [String: String]
    let privacyTier: String
}

func appleAppForegroundRoutes(_ app: NSRunningApplication) -> [AppleAppForegroundRoute] {
    switch appleAppFamily(app) {
    case "finder":
        return [
            AppleAppForegroundRoute(key: "finder-folder", collector: "folder_navigation_activity", source: "activity", stimulusType: "folder_opened", text: "Finder navigation surface metadata observed.", privacyTier: "sensitive_metadata", appFamily: "finder", metadata: appleAppOmissionMetadata(appFamily: "finder")),
            AppleAppForegroundRoute(key: "finder-share", collector: "share_activity", source: "activity", stimulusType: "share_sheet_opened", text: "Finder sharing/navigation surface metadata observed.", privacyTier: "sensitive_metadata", appFamily: "finder", metadata: appleAppOmissionMetadata(appFamily: "finder")),
        ]
    case "messages":
        return [
            AppleAppForegroundRoute(key: "messages-communication", collector: "communication_activity", source: "channel_message", stimulusType: "channel_unread_changed", text: "Messages app foreground metadata observed.", privacyTier: "metadata", appFamily: "messages", metadata: appleAppOmissionMetadata(appFamily: "messages")),
            AppleAppForegroundRoute(key: "messages-composition", collector: "chat_composition_activity", source: "channel_message", stimulusType: "message_composed", text: "Messages composition surface metadata observed.", privacyTier: "sensitive_metadata", appFamily: "messages", metadata: appleAppOmissionMetadata(appFamily: "messages")),
            AppleAppForegroundRoute(key: "messages-thread", collector: "chat_thread_activity", source: "channel_message", stimulusType: "thread_opened", text: "Messages thread surface metadata observed.", privacyTier: "sensitive_metadata", appFamily: "messages", metadata: appleAppOmissionMetadata(appFamily: "messages")),
        ]
    case "notes":
        return [
            AppleAppForegroundRoute(key: "notes-edit", collector: "notes_activity", source: "activity", stimulusType: "note_edited", text: "Notes app foreground metadata observed.", privacyTier: "sensitive_metadata", appFamily: "notes", metadata: appleAppOmissionMetadata(appFamily: "notes")),
            AppleAppForegroundRoute(key: "notes-share", collector: "share_activity", source: "activity", stimulusType: "share_sheet_opened", text: "Notes sharing surface metadata observed.", privacyTier: "sensitive_metadata", appFamily: "notes", metadata: appleAppOmissionMetadata(appFamily: "notes")),
        ]
    case "pages":
        return [
            AppleAppForegroundRoute(key: "pages-compose", collector: "document_composition_activity", source: "activity", stimulusType: "document_edited", text: "Pages document composition metadata observed.", privacyTier: "sensitive_metadata", appFamily: "pages", metadata: appleAppOmissionMetadata(appFamily: "pages")),
            AppleAppForegroundRoute(key: "pages-review", collector: "document_review_activity", source: "activity", stimulusType: "document_review_requested", text: "Pages document review metadata observed.", privacyTier: "sensitive_metadata", appFamily: "pages", metadata: appleAppOmissionMetadata(appFamily: "pages")),
            AppleAppForegroundRoute(key: "pages-structure", collector: "document_structure_activity", source: "activity", stimulusType: "document_outline_opened", text: "Pages document structure metadata observed.", privacyTier: "sensitive_metadata", appFamily: "pages", metadata: appleAppOmissionMetadata(appFamily: "pages")),
            AppleAppForegroundRoute(key: "pages-export", collector: "document_export_publish_activity", source: "activity", stimulusType: "document_export_started", text: "Pages document export/share metadata observed.", privacyTier: "sensitive_metadata", appFamily: "pages", metadata: appleAppOmissionMetadata(appFamily: "pages")),
            AppleAppForegroundRoute(key: "pages-surface", collector: "document_activity", source: "activity", stimulusType: "doc_edited", text: "Pages document surface metadata observed.", privacyTier: "metadata", appFamily: "pages", metadata: appleAppOmissionMetadata(appFamily: "pages")),
        ]
    case "numbers":
        return [
            AppleAppForegroundRoute(key: "numbers-workbook", collector: "spreadsheet_activity", source: "activity", stimulusType: "workbook_opened", text: "Numbers workbook metadata observed.", privacyTier: "sensitive_metadata", appFamily: "numbers", metadata: appleAppOmissionMetadata(appFamily: "numbers")),
            AppleAppForegroundRoute(key: "numbers-edit", collector: "spreadsheet_editing_activity", source: "activity", stimulusType: "cell_range_selected", text: "Numbers spreadsheet editing metadata observed.", privacyTier: "sensitive_metadata", appFamily: "numbers", metadata: appleAppOmissionMetadata(appFamily: "numbers")),
            AppleAppForegroundRoute(key: "numbers-formula", collector: "spreadsheet_formula_activity", source: "activity", stimulusType: "calculation_started", text: "Numbers calculation/formula metadata observed.", privacyTier: "sensitive_metadata", appFamily: "numbers", metadata: appleAppOmissionMetadata(appFamily: "numbers")),
            AppleAppForegroundRoute(key: "numbers-analysis", collector: "spreadsheet_data_analysis_activity", source: "activity", stimulusType: "chart_updated", text: "Numbers data-analysis metadata observed.", privacyTier: "sensitive_metadata", appFamily: "numbers", metadata: appleAppOmissionMetadata(appFamily: "numbers")),
            AppleAppForegroundRoute(key: "numbers-export", collector: "spreadsheet_import_export_activity", source: "activity", stimulusType: "workbook_export_started", text: "Numbers import/export metadata observed.", privacyTier: "sensitive_metadata", appFamily: "numbers", metadata: appleAppOmissionMetadata(appFamily: "numbers")),
        ]
    case "keynote":
        return [
            AppleAppForegroundRoute(key: "keynote-surface", collector: "presentation_activity", source: "activity", stimulusType: "deck_opened", text: "Keynote deck metadata observed.", privacyTier: "sensitive_metadata", appFamily: "keynote", metadata: appleAppOmissionMetadata(appFamily: "keynote")),
            AppleAppForegroundRoute(key: "keynote-authoring", collector: "presentation_authoring_activity", source: "activity", stimulusType: "slide_edited", text: "Keynote authoring metadata observed.", privacyTier: "sensitive_metadata", appFamily: "keynote", metadata: appleAppOmissionMetadata(appFamily: "keynote")),
            AppleAppForegroundRoute(key: "keynote-design", collector: "presentation_design_activity", source: "activity", stimulusType: "layout_changed", text: "Keynote design metadata observed.", privacyTier: "sensitive_metadata", appFamily: "keynote", metadata: appleAppOmissionMetadata(appFamily: "keynote")),
            AppleAppForegroundRoute(key: "keynote-delivery", collector: "presentation_delivery_activity", source: "activity", stimulusType: "presenter_view_opened", text: "Keynote presentation delivery metadata observed.", privacyTier: "sensitive_metadata", appFamily: "keynote", metadata: appleAppOmissionMetadata(appFamily: "keynote")),
            AppleAppForegroundRoute(key: "keynote-export", collector: "presentation_export_activity", source: "activity", stimulusType: "deck_export_started", text: "Keynote export/share metadata observed.", privacyTier: "sensitive_metadata", appFamily: "keynote", metadata: appleAppOmissionMetadata(appFamily: "keynote")),
        ]
    case "preview":
        return [
            AppleAppForegroundRoute(key: "preview-pdf", collector: "pdf_activity", source: "activity", stimulusType: "pdf_opened", text: "Preview PDF/document metadata observed.", privacyTier: "sensitive_metadata", appFamily: "preview", metadata: appleAppOmissionMetadata(appFamily: "preview")),
            AppleAppForegroundRoute(key: "preview-review", collector: "document_review_activity", source: "activity", stimulusType: "document_comment_added", text: "Preview annotation/review metadata observed.", privacyTier: "sensitive_metadata", appFamily: "preview", metadata: appleAppOmissionMetadata(appFamily: "preview")),
            AppleAppForegroundRoute(key: "preview-export", collector: "document_export_publish_activity", source: "activity", stimulusType: "document_export_started", text: "Preview export/share metadata observed.", privacyTier: "sensitive_metadata", appFamily: "preview", metadata: appleAppOmissionMetadata(appFamily: "preview")),
        ]
    case "photos":
        return [
            AppleAppForegroundRoute(key: "photos-import", collector: "camera_capture_activity", source: "screen_ocr", stimulusType: "photo_imported", text: "Photos import/export surface metadata observed.", privacyTier: "sensitive_metadata", appFamily: "photos", metadata: appleAppOmissionMetadata(appFamily: "photos")),
            AppleAppForegroundRoute(key: "photos-media", collector: "media_activity", source: "activity", stimulusType: "media_track_changed", text: "Photos media-library surface metadata observed.", privacyTier: "metadata", appFamily: "photos", metadata: appleAppOmissionMetadata(appFamily: "photos")),
            AppleAppForegroundRoute(key: "photos-share", collector: "share_activity", source: "activity", stimulusType: "share_sheet_opened", text: "Photos share/export surface metadata observed.", privacyTier: "sensitive_metadata", appFamily: "photos", metadata: appleAppOmissionMetadata(appFamily: "photos")),
        ]
    default:
        return []
    }
}

func appleAppForegroundMetadata(app: NSRunningApplication) -> [String: String] {
    appMetadata(app)
        .merging(frontmostWindowSnapshot(for: app), uniquingKeysWith: { current, _ in current })
        .merging([
            "native_source": "macos_apple_app_foreground_metadata",
            "source_api": "NSWorkspace+CGWindowList",
            "privacy_level": "redacted",
            "apple_app_family": appleAppFamily(app),
            "window_title_omitted": "true",
            "raw_content_included": "false",
        ], uniquingKeysWith: { current, _ in current })
}

func appleAppStateSnapshots() -> [AppleAppStateSnapshot] {
    var snapshots: [AppleAppStateSnapshot] = []
    snapshots.append(contentsOf: appleNotesStateSnapshots())
    snapshots.append(contentsOf: appleDocumentStateSnapshots())
    snapshots.append(contentsOf: applePhotosStateSnapshots())
    return snapshots
}

private func appleAppFamily(_ app: NSRunningApplication) -> String {
    let bundle = (app.bundleIdentifier ?? "").lowercased()
    let name = safeAppName(app).lowercased()
    if bundle == "com.apple.finder" || name == "finder" { return "finder" }
    if bundle == "com.apple.mobilesms" || name == "messages" { return "messages" }
    if bundle == "com.apple.notes" || name == "notes" { return "notes" }
    if bundle == "com.apple.iwork.pages" || name == "pages" { return "pages" }
    if bundle == "com.apple.iwork.numbers" || name == "numbers" { return "numbers" }
    if bundle == "com.apple.iwork.keynote" || name == "keynote" { return "keynote" }
    if bundle == "com.apple.preview" || name == "preview" { return "preview" }
    if bundle == "com.apple.photos" || name == "photos" { return "photos" }
    return "other"
}

private func appleAppOmissionMetadata(appFamily: String) -> [String: String] {
    [
        "app_family": appFamily,
        "document_titles_omitted": "true",
        "document_text_omitted": "true",
        "selected_text_omitted": "true",
        "file_names_omitted": "true",
        "file_paths_omitted": "true",
        "message_bodies_omitted": "true",
        "participant_names_omitted": "true",
        "note_contents_omitted": "true",
        "photo_pixels_omitted": "true",
        "photo_metadata_values_omitted": "true",
    ]
}

private func appleNotesStateSnapshots() -> [AppleAppStateSnapshot] {
    let roots = [
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Group Containers/group.com.apple.notes", isDirectory: true),
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Containers/com.apple.Notes", isDirectory: true),
    ]
    let summary = appleDirectorySignature(roots: roots, allowedExtensions: ["sqlite", "storedata", "wal", "shm"], maxDepth: 5)
    guard summary.exists else {
        return []
    }
    let metadata = appleStateMetadata(
        nativeSource: "macos_apple_notes_store_metadata",
        appFamily: "notes",
        sourceAPI: "FileManager",
        summary: summary
    ).merging([
        "note_titles_omitted": "true",
        "note_bodies_omitted": "true",
        "attachment_names_omitted": "true",
    ], uniquingKeysWith: { current, _ in current })
    let payload = [
        "store_signature_hash": summary.signature,
        "item_count_bucket": countBucket(summary.itemCount),
        "extension_buckets": summary.extensionBuckets,
    ]
    return [
        AppleAppStateSnapshot(key: "apple-notes-store", collector: "notes_activity", source: "activity", stimulusType: "note_edited", text: "Apple Notes store metadata changed.", signature: summary.signature, metadata: metadata, payload: payload, privacyTier: "sensitive_metadata"),
    ]
}

private func appleDocumentStateSnapshots() -> [AppleAppStateSnapshot] {
    let roots = [
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Mobile Documents/com~apple~Pages/Documents", isDirectory: true),
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Mobile Documents/com~apple~Numbers/Documents", isDirectory: true),
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Mobile Documents/com~apple~Keynote/Documents", isDirectory: true),
        firstUserDirectory(.documentDirectory),
        firstUserDirectory(.desktopDirectory),
        firstUserDirectory(.downloadsDirectory),
    ].compactMap { $0 }
    let summary = appleDirectorySignature(roots: roots, allowedExtensions: ["pages", "numbers", "key", "pdf"], maxDepth: 3)
    guard summary.exists else {
        return []
    }
    let metadata = appleStateMetadata(
        nativeSource: "macos_apple_document_store_metadata",
        appFamily: "iwork_preview",
        sourceAPI: "FileManager",
        summary: summary
    )
    let payload = [
        "store_signature_hash": summary.signature,
        "item_count_bucket": countBucket(summary.itemCount),
        "extension_buckets": summary.extensionBuckets,
    ]
    return [
        AppleAppStateSnapshot(key: "apple-document-composition", collector: "document_composition_activity", source: "activity", stimulusType: "document_saved", text: "Apple document metadata changed.", signature: summary.signature, metadata: metadata, payload: payload, privacyTier: "sensitive_metadata"),
        AppleAppStateSnapshot(key: "apple-spreadsheet-import-export", collector: "spreadsheet_import_export_activity", source: "activity", stimulusType: "workbook_exported", text: "Apple spreadsheet document metadata changed.", signature: summary.signature, metadata: metadata, payload: payload, privacyTier: "sensitive_metadata"),
        AppleAppStateSnapshot(key: "apple-presentation-export", collector: "presentation_export_activity", source: "activity", stimulusType: "deck_exported", text: "Apple presentation document metadata changed.", signature: summary.signature, metadata: metadata, payload: payload, privacyTier: "sensitive_metadata"),
        AppleAppStateSnapshot(key: "apple-pdf-export", collector: "pdf_activity", source: "activity", stimulusType: "pdf_exported", text: "Apple PDF metadata changed.", signature: summary.signature, metadata: metadata, payload: payload, privacyTier: "sensitive_metadata"),
    ]
}

private func applePhotosStateSnapshots() -> [AppleAppStateSnapshot] {
    let pictures = firstUserDirectory(.picturesDirectory)
    let roots = [
        pictures?.appendingPathComponent("Photos Library.photoslibrary", isDirectory: true),
        pictures,
    ].compactMap { $0 }
    let summary = appleDirectorySignature(roots: roots, allowedExtensions: ["photoslibrary", "sqlite", "photosdb", "plist"], maxDepth: 4)
    guard summary.exists else {
        return []
    }
    let metadata = appleStateMetadata(
        nativeSource: "macos_apple_photos_library_metadata",
        appFamily: "photos",
        sourceAPI: "FileManager",
        summary: summary
    ).merging([
        "asset_filenames_omitted": "true",
        "exif_values_omitted": "true",
        "location_values_omitted": "true",
        "faces_people_omitted": "true",
        "pixels_captured": "false",
    ], uniquingKeysWith: { current, _ in current })
    let payload = [
        "library_signature_hash": summary.signature,
        "item_count_bucket": countBucket(summary.itemCount),
        "extension_buckets": summary.extensionBuckets,
    ]
    return [
        AppleAppStateSnapshot(key: "apple-photos-import", collector: "camera_capture_activity", source: "screen_ocr", stimulusType: "photo_imported", text: "Apple Photos library metadata changed.", signature: summary.signature, metadata: metadata, payload: payload, privacyTier: "sensitive_metadata"),
        AppleAppStateSnapshot(key: "apple-photos-media", collector: "media_activity", source: "activity", stimulusType: "media_track_changed", text: "Apple Photos media-library metadata changed.", signature: summary.signature, metadata: metadata, payload: payload, privacyTier: "metadata"),
    ]
}

private func firstUserDirectory(_ directory: FileManager.SearchPathDirectory) -> URL? {
    let urls: [URL] = FileManager.default.urls(for: directory, in: .userDomainMask)
    return urls.first
}

private struct AppleDirectorySummary {
    let exists: Bool
    let signature: String
    let itemCount: Int
    let totalSize: Int64
    let extensionBuckets: String
    let rootCount: Int
}

private func appleDirectorySignature(roots: [URL], allowedExtensions: Set<String>, maxDepth: Int) -> AppleDirectorySummary {
    var parts: [String] = []
    var itemCount = 0
    var totalSize: Int64 = 0
    var extensions: [String: Int] = [:]
    var existingRoots = 0

    for root in roots {
        let standardized = root.standardizedFileURL
        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: standardized.path, isDirectory: &isDirectory) else {
            continue
        }
        existingRoots += 1
        addAppleFileSignature(standardized, root: standardized, maxDepth: maxDepth, allowedExtensions: allowedExtensions, parts: &parts, itemCount: &itemCount, totalSize: &totalSize, extensions: &extensions)
        guard isDirectory.boolValue,
              let enumerator = FileManager.default.enumerator(
                at: standardized,
                includingPropertiesForKeys: [.isDirectoryKey, .fileSizeKey, .contentModificationDateKey, .isPackageKey],
                options: [.skipsHiddenFiles]
              ) else {
            continue
        }
        for case let url as URL in enumerator {
            let depth = max(0, url.standardizedFileURL.pathComponents.count - standardized.pathComponents.count)
            if depth > maxDepth {
                enumerator.skipDescendants()
                continue
            }
            addAppleFileSignature(url, root: standardized, maxDepth: maxDepth, allowedExtensions: allowedExtensions, parts: &parts, itemCount: &itemCount, totalSize: &totalSize, extensions: &extensions)
            if appleShouldSkipDescendants(url, allowedExtensions: allowedExtensions, depth: depth, maxDepth: maxDepth) {
                enumerator.skipDescendants()
            }
            if itemCount >= 512 {
                break
            }
        }
    }

    let normalizedParts = parts.sorted().prefix(512).joined(separator: "|")
    let extensionBuckets = extensions
        .sorted { $0.key < $1.key }
        .map { "\($0.key):\(countBucket($0.value))" }
        .joined(separator: ",")
    return AppleDirectorySummary(
        exists: existingRoots > 0,
        signature: shortDigest(normalizedParts),
        itemCount: itemCount,
        totalSize: totalSize,
        extensionBuckets: extensionBuckets,
        rootCount: existingRoots
    )
}

private func addAppleFileSignature(
    _ url: URL,
    root: URL,
    maxDepth: Int,
    allowedExtensions: Set<String>,
    parts: inout [String],
    itemCount: inout Int,
    totalSize: inout Int64,
    extensions: inout [String: Int]
) {
    let ext = sanitizedExtension(url.pathExtension)
    let isPackageMatch = allowedExtensions.contains(url.lastPathComponent.lowercased().split(separator: ".").last.map(String.init) ?? "")
    guard ext.isEmpty || allowedExtensions.contains(ext) || isPackageMatch else {
        return
    }
    let depth = max(0, url.standardizedFileURL.pathComponents.count - root.standardizedFileURL.pathComponents.count)
    guard depth <= maxDepth else {
        return
    }
    guard let values = try? url.resourceValues(forKeys: [.isDirectoryKey, .fileSizeKey, .contentModificationDateKey, .isPackageKey]) else {
        return
    }
    let modified = Int(values.contentModificationDate?.timeIntervalSince1970 ?? 0)
    let size = Int64(values.fileSize ?? 0)
    let kind = values.isDirectory == true ? "dir" : "file"
    let normalizedExtension = ext.isEmpty ? "package_or_directory" : ext
    itemCount += 1
    totalSize += max(0, size)
    extensions[normalizedExtension, default: 0] += 1
    parts.append("\(shortDigest(url.path)):\(normalizedExtension):\(kind):\(modified / 60):\(sizeBucket(size)):\(depthBucket(depth))")
}

private func appleShouldSkipDescendants(_ url: URL, allowedExtensions: Set<String>, depth: Int, maxDepth: Int) -> Bool {
    if depth >= maxDepth {
        return true
    }
    let ext = sanitizedExtension(url.pathExtension)
    if ["pages", "numbers", "key", "photoslibrary"].contains(ext), allowedExtensions.contains(ext) {
        return true
    }
    return false
}

private func appleStateMetadata(nativeSource: String, appFamily: String, sourceAPI: String, summary: AppleDirectorySummary) -> [String: String] {
    appleAppOmissionMetadata(appFamily: appFamily).merging([
        "native_source": nativeSource,
        "source_api": sourceAPI,
        "privacy_level": "redacted",
        "store_signature_hash": summary.signature,
        "item_count_bucket": countBucket(summary.itemCount),
        "root_count_bucket": countBucket(summary.rootCount),
        "total_size_bucket": sizeBucket(summary.totalSize),
        "extension_buckets": summary.extensionBuckets,
        "path_values_omitted": "true",
        "filename_values_omitted": "true",
        "raw_content_included": "false",
    ], uniquingKeysWith: { current, _ in current })
}
