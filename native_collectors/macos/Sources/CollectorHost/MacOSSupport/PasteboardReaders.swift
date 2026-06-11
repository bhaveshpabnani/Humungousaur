import AppKit
import Foundation

func pasteboardTypeCategories(_ types: [NSPasteboard.PasteboardType]) -> [String: String] {
    let rawTypes = Set(types.map(\.rawValue))
    let hasString = rawTypes.contains(NSPasteboard.PasteboardType.string.rawValue)
    let hasFile = rawTypes.contains(NSPasteboard.PasteboardType.fileURL.rawValue)
    let hasURL = rawTypes.contains(NSPasteboard.PasteboardType.URL.rawValue)
    let hasImage = rawTypes.contains(NSPasteboard.PasteboardType.tiff.rawValue) || rawTypes.contains(NSPasteboard.PasteboardType.png.rawValue)
    return [
        "type_count": String(rawTypes.count),
        "has_string_type": String(hasString),
        "has_file_url_type": String(hasFile),
        "has_url_type": String(hasURL),
        "has_image_type": String(hasImage),
        "type_fingerprint": rawTypes.isEmpty ? "" : sha256(rawTypes.sorted().joined(separator: "|")),
    ]
}
