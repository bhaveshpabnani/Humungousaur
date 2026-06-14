import AppKit
import SwiftUI
import UniformTypeIdentifiers

struct ChatView: View {
    @EnvironmentObject private var model: AppViewModel
    @State private var prompt = ""
    @State private var voiceInputMode = false
    @State private var selectedFileURLs: [URL] = []

    var body: some View {
        HStack(spacing: 0) {
            chatHistory
                .frame(width: 236)
                .background(.bar)
                .overlay(Rectangle().fill(DS.line).frame(width: 1), alignment: .trailing)

            VStack(spacing: 0) {
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(spacing: 18) {
                            if model.messages.isEmpty {
                                welcome
                            }
                            ForEach(model.messages) { message in
                                MessageBubble(message: message)
                                    .id(message.id)
                            }
                        }
                        .padding(28)
                    }
                    .onChange(of: model.messages.count) {
                        if let id = model.messages.last?.id {
                            proxy.scrollTo(id, anchor: .bottom)
                        }
                    }
                }

                ComposerView(
                    prompt: $prompt,
                    modelName: $model.settings.modelName,
                    voiceInputMode: $voiceInputMode,
                    selectedFiles: $selectedFileURLs
                ) {
                    let files = selectedFileURLs
                    let text = prompt.trimmingCharacters(in: .whitespacesAndNewlines)
                    let requestText = composedRequestText(prompt: text, files: files)
                    let displayText = composedDisplayText(prompt: text, files: files)
                    let source = voiceInputMode ? "voice_transcript" : "user_text"
                    prompt = ""
                    selectedFileURLs = []
                    Task { await model.send(requestText, source: source, responseMode: "text", displayText: displayText) }
                }
                .padding(.horizontal, 28)
                .padding(.top, 6)
                .padding(.bottom, 20)
            }
        }
    }

    private var chatHistory: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Chats")
                    .font(.headline.weight(.semibold))
                Spacer()
                Button {
                    model.startNewSession()
                } label: {
                    Image(systemName: "plus")
                }
                .buttonStyle(.borderless)
                .help("New chat")
            }
            .padding(.horizontal, 14)
            .padding(.top, 14)

            List(selection: conversationSelection) {
                ForEach(model.conversations) { conversation in
                    VStack(alignment: .leading, spacing: 3) {
                        Text(conversation.displayTitle)
                            .font(.callout.weight(.medium))
                            .lineLimit(1)
                        Text(conversation.subtitle)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                    .padding(.vertical, 4)
                    .tag(Optional(conversation.conversationId))
                }
            }
            .listStyle(.sidebar)
        }
    }

    private var conversationSelection: Binding<String?> {
        Binding {
            model.selectedConversationID
        } set: { value in
            guard let value else { return }
            Task { await model.loadConversation(value) }
        }
    }

    private var welcome: some View {
        VStack(spacing: 12) {
            Text("\(greeting), \(model.displayName)")
                .font(.system(size: 38, weight: .semibold, design: .rounded))
                .multilineTextAlignment(.center)
            Text("What should we move forward?")
                .font(.system(size: 18, weight: .regular, design: .rounded))
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, minHeight: 360, alignment: .center)
        .padding(.top, 18)
        .padding(.bottom, 20)
    }

    private var greeting: String {
        let hour = Calendar.current.component(.hour, from: Date())
        switch hour {
        case 5..<12: return "Good morning"
        case 12..<17: return "Good afternoon"
        default: return "Good evening"
        }
    }

    private func composedRequestText(prompt: String, files: [URL]) -> String {
        guard !files.isEmpty else { return prompt }
        let fileLines = files.map { url in
            "- \(url.lastPathComponent)\n  path: \(url.path)"
        }.joined(separator: "\n")
        let base = prompt.isEmpty ? "Please review the attached file(s)." : prompt
        return """
        \(base)

        Attached files:
        \(fileLines)
        """
    }

    private func composedDisplayText(prompt: String, files: [URL]) -> String {
        guard !files.isEmpty else { return prompt }
        let names = files.map(\.lastPathComponent).joined(separator: ", ")
        if prompt.isEmpty {
            return "Attached: \(names)"
        }
        return "\(prompt)\n\nAttached: \(names)"
    }
}

struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        switch message.role {
        case .user:
            HStack {
                Spacer(minLength: 80)
                Text(message.text)
                    .font(.body)
                    .textSelection(.enabled)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .frame(maxWidth: 720, alignment: .leading)
                    .background(Color(nsColor: .controlBackgroundColor).opacity(0.72), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 8, style: .continuous).stroke(Color.primary.opacity(0.10)))
            }
        case .assistant, .system:
            let deliveredText = message.text.trimmingCharacters(in: .whitespacesAndNewlines)
            VStack(alignment: .leading, spacing: 14) {
                if deliveredText.isEmpty && !message.activities.isEmpty {
                    ActivityTrailView(activities: message.activities, isStreaming: message.isStreaming)
                }
                if !deliveredText.isEmpty {
                    HStack(alignment: .top, spacing: 12) {
                        AssistantGlyph()
                            .padding(.top, 2)
                        MarkdownText(message.text)
                            .font(.system(size: 15.5, weight: .regular, design: .default))
                            .lineSpacing(4)
                            .textSelection(.enabled)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
            .frame(maxWidth: 820, alignment: .leading)
            .frame(maxWidth: .infinity, alignment: .leading)
        case .error:
            VStack(alignment: .leading, spacing: 10) {
                if !message.activities.isEmpty {
                    ActivityTrailView(activities: message.activities, isStreaming: false)
                }
                Text(message.text)
                    .font(.body)
                    .foregroundStyle(.red)
                    .textSelection(.enabled)
            }
            .frame(maxWidth: 820, alignment: .leading)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

struct AssistantGlyph: View {
    var body: some View {
        if let url = Bundle.module.url(forResource: "humungousaur-logo-mark-32", withExtension: "png"),
           let image = NSImage(contentsOf: url) {
            Image(nsImage: image)
                .resizable()
                .scaledToFit()
                .frame(width: 22, height: 22)
        } else {
            Image(systemName: "sparkle")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(DS.accent)
                .frame(width: 22, height: 22)
        }
    }
}

struct ActivityGlyph: View {
    let kind: String

    var body: some View {
        if kind == "thinking",
           let url = Bundle.module.url(forResource: "humungousaur-logo-mark-32", withExtension: "png"),
           let image = NSImage(contentsOf: url) {
            Image(nsImage: image)
                .resizable()
                .scaledToFit()
                .frame(width: 16, height: 16)
        } else {
            Image(systemName: symbol(for: kind))
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(tint(for: kind))
                .frame(width: 16, height: 16)
        }
    }

    private func symbol(for kind: String) -> String {
        switch kind {
        case "tool": "hammer.fill"
        case "skill": "sparkles"
        case "approval": "hand.raised.fill"
        case "response": "checkmark.circle.fill"
        case "error": "exclamationmark.triangle.fill"
        default: "sparkle"
        }
    }

    private func tint(for kind: String) -> Color {
        switch kind {
        case "tool": .blue
        case "skill": .purple
        case "approval": .orange
        case "response": .green
        case "error": .red
        default: DS.accent
        }
    }
}

struct ActivityTrailView: View {
    let activities: [StreamActivityItem]
    let isStreaming: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(activities.suffix(10)) { activity in
                HStack(alignment: .top, spacing: 8) {
                    ActivityGlyph(kind: activity.kind)
                    VStack(alignment: .leading, spacing: 2) {
                        HStack(spacing: 6) {
                            Text(activity.title)
                                .font(.caption.weight(.semibold))
                            if !activity.status.isEmpty {
                                Text(activity.status.humanizedStatus)
                                    .font(.caption2.weight(.medium))
                                    .foregroundStyle(.secondary)
                            }
                        }
                        if !activity.detail.isEmpty {
                            Text(activity.detail)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .lineLimit(3)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                .padding(.vertical, 2)
            }
        }
    }
}

struct MarkdownText: View {
    let markdown: String

    init(_ markdown: String) {
        self.markdown = markdown
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            ForEach(MarkdownBlock.parse(markdown)) { block in
                switch block.kind {
                case .heading(let level, let text):
                    InlineMarkdownText(text)
                        .font(.system(size: level == 1 ? 20 : 17, weight: .semibold))
                        .padding(.top, level == 1 ? 0 : 3)
                case .paragraph(let text):
                    InlineMarkdownText(text)
                case .bullet(let text):
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text("•")
                            .foregroundStyle(.secondary)
                        InlineMarkdownText(text)
                    }
                case .numbered(let number, let text):
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text("\(number).")
                            .foregroundStyle(.secondary)
                            .monospacedDigit()
                        InlineMarkdownText(text)
                    }
                case .code(let text):
                    Text(text)
                        .font(.system(.callout, design: .monospaced))
                        .textSelection(.enabled)
                        .padding(10)
                        .background(Color(nsColor: .controlBackgroundColor).opacity(0.74), in: RoundedRectangle(cornerRadius: 6, style: .continuous))
                case .table(let headers, let rows):
                    MarkdownTable(headers: headers, rows: rows)
                }
            }
        }
    }
}

struct InlineMarkdownText: View {
    let text: String

    init(_ text: String) {
        self.text = text
    }

    var body: some View {
        if let attributed = try? AttributedString(markdown: text) {
            Text(attributed)
        } else {
            Text(text)
        }
    }
}

struct MarkdownTable: View {
    let headers: [String]
    let rows: [[String]]

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            Grid(alignment: .leading, horizontalSpacing: 14, verticalSpacing: 7) {
                GridRow {
                    ForEach(Array(headers.enumerated()), id: \.offset) { _, header in
                        InlineMarkdownText(header)
                            .font(.callout.weight(.semibold))
                            .foregroundStyle(.primary)
                    }
                }
                Divider()
                    .gridCellColumns(max(headers.count, 1))
                ForEach(Array(rows.enumerated()), id: \.offset) { _, row in
                    GridRow {
                        ForEach(0..<headers.count, id: \.self) { index in
                            InlineMarkdownText(index < row.count ? row[index] : "")
                                .font(.callout)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
            .padding(.vertical, 4)
        }
    }
}

struct MarkdownBlock: Identifiable {
    enum Kind {
        case heading(level: Int, text: String)
        case paragraph(String)
        case bullet(String)
        case numbered(Int, String)
        case code(String)
        case table(headers: [String], rows: [[String]])
    }

    let id = UUID()
    let kind: Kind

    static func parse(_ markdown: String) -> [MarkdownBlock] {
        let lines = markdown.replacingOccurrences(of: "\r\n", with: "\n").components(separatedBy: "\n")
        var blocks: [MarkdownBlock] = []
        var index = 0
        while index < lines.count {
            let line = lines[index]
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.isEmpty {
                index += 1
                continue
            }
            if trimmed.hasPrefix("```") {
                var codeLines: [String] = []
                index += 1
                while index < lines.count && !lines[index].trimmingCharacters(in: .whitespaces).hasPrefix("```") {
                    codeLines.append(lines[index])
                    index += 1
                }
                blocks.append(MarkdownBlock(kind: .code(codeLines.joined(separator: "\n"))))
                index += index < lines.count ? 1 : 0
                continue
            }
            if let table = parseTable(lines: lines, start: index) {
                blocks.append(MarkdownBlock(kind: .table(headers: table.headers, rows: table.rows)))
                index = table.nextIndex
                continue
            }
            if let heading = parseHeading(trimmed) {
                blocks.append(MarkdownBlock(kind: .heading(level: heading.level, text: heading.text)))
                index += 1
                continue
            }
            if trimmed.hasPrefix("- ") || trimmed.hasPrefix("* ") {
                blocks.append(MarkdownBlock(kind: .bullet(String(trimmed.dropFirst(2)))))
                index += 1
                continue
            }
            if let numbered = parseNumbered(trimmed) {
                blocks.append(MarkdownBlock(kind: .numbered(numbered.number, numbered.text)))
                index += 1
                continue
            }
            var paragraphLines = [trimmed]
            index += 1
            while index < lines.count {
                let next = lines[index].trimmingCharacters(in: .whitespaces)
                if next.isEmpty || next.hasPrefix("#") || next.hasPrefix("- ") || next.hasPrefix("* ") || next.hasPrefix("```") || parseNumbered(next) != nil || parseTable(lines: lines, start: index) != nil {
                    break
                }
                paragraphLines.append(next)
                index += 1
            }
            blocks.append(MarkdownBlock(kind: .paragraph(paragraphLines.joined(separator: " "))))
        }
        return blocks.isEmpty ? [MarkdownBlock(kind: .paragraph(markdown))] : blocks
    }

    private static func parseHeading(_ line: String) -> (level: Int, text: String)? {
        let hashes = line.prefix { $0 == "#" }.count
        guard (1...3).contains(hashes), line.dropFirst(hashes).first == " " else { return nil }
        return (hashes, String(line.dropFirst(hashes + 1)).trimmingCharacters(in: .whitespaces))
    }

    private static func parseNumbered(_ line: String) -> (number: Int, text: String)? {
        guard let dotIndex = line.firstIndex(of: ".") else { return nil }
        let numberText = String(line[..<dotIndex])
        guard let number = Int(numberText) else { return nil }
        let textStart = line.index(after: dotIndex)
        guard textStart < line.endIndex, line[textStart] == " " else { return nil }
        return (number, String(line[line.index(after: textStart)...]))
    }

    private static func parseTable(lines: [String], start: Int) -> (headers: [String], rows: [[String]], nextIndex: Int)? {
        guard start + 1 < lines.count else { return nil }
        let header = lines[start].trimmingCharacters(in: .whitespaces)
        let separator = lines[start + 1].trimmingCharacters(in: .whitespaces)
        guard header.hasPrefix("|"), separator.hasPrefix("|"), isTableSeparator(separator) else { return nil }
        let headers = tableCells(header)
        var rows: [[String]] = []
        var index = start + 2
        while index < lines.count {
            let line = lines[index].trimmingCharacters(in: .whitespaces)
            guard line.hasPrefix("|") else { break }
            rows.append(tableCells(line))
            index += 1
        }
        return headers.isEmpty ? nil : (headers, rows, index)
    }

    private static func isTableSeparator(_ line: String) -> Bool {
        let cells = tableCells(line)
        return !cells.isEmpty && cells.allSatisfy { cell in
            let stripped = cell
                .replacingOccurrences(of: "-", with: "")
                .replacingOccurrences(of: ":", with: "")
                .trimmingCharacters(in: .whitespaces)
            return stripped.isEmpty
        }
    }

    private static func tableCells(_ line: String) -> [String] {
        var cleaned = line.trimmingCharacters(in: .whitespaces)
        if cleaned.hasPrefix("|") {
            cleaned.removeFirst()
        }
        if cleaned.hasSuffix("|") {
            cleaned.removeLast()
        }
        return cleaned.split(separator: "|", omittingEmptySubsequences: false).map {
            String($0).trimmingCharacters(in: .whitespaces)
        }
    }
}

struct ComposerView: View {
    @Binding var prompt: String
    @Binding var modelName: String
    @Binding var voiceInputMode: Bool
    @Binding var selectedFiles: [URL]
    @State private var showingFileImporter = false
    @State private var placeholderIndex = 0
    let onSend: () -> Void
    private let placeholderTimer = Timer.publish(every: 2.8, on: .main, in: .common).autoconnect()

    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            if !selectedFiles.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 7) {
                        ForEach(selectedFiles, id: \.self) { file in
                            AttachmentChip(file: file) {
                                removeFile(file)
                            }
                        }
                    }
                }
            }

            HStack(alignment: .center, spacing: 10) {
                Button {
                    showingFileImporter = true
                } label: {
                    Image(systemName: "paperclip")
                        .font(.system(size: 15, weight: .semibold))
                        .frame(width: 34, height: 34)
                }
                .buttonStyle(.plain)
                .focusable(false)
                .foregroundStyle(.secondary)
                .background(Color.primary.opacity(0.045), in: Circle())
                .help("Attach files")

                TextField(currentPlaceholder, text: $prompt, axis: .vertical)
                    .textFieldStyle(.plain)
                    .font(.system(.body, design: .rounded))
                    .lineLimit(1...5)
                    .frame(minHeight: 34)
                    .padding(.leading, 2)

                modelPicker
                Button {
                    voiceInputMode.toggle()
                } label: {
                    Image(systemName: voiceInputMode ? "mic.fill" : "mic")
                        .font(.system(size: 15, weight: .semibold))
                        .frame(width: 34, height: 34)
                }
                .buttonStyle(.plain)
                .focusable(false)
                .foregroundStyle(voiceInputMode ? DS.accent : .secondary)
                .background(Color.primary.opacity(voiceInputMode ? 0.08 : 0.045), in: Circle())
                .help(voiceInputMode ? "Voice source enabled" : "Use voice source")

                Button(action: onSend) {
                    Image(systemName: "arrow.up")
                        .font(.system(size: 16, weight: .bold))
                        .frame(width: 34, height: 34)
                }
                .buttonStyle(.plain)
                .focusable(false)
                .foregroundStyle(.white)
                .background(sendDisabled ? Color.secondary.opacity(0.35) : DS.accent, in: Circle())
                .disabled(sendDisabled)
                .help("Send")
            }
        }
        .padding(.leading, 18)
        .padding(.trailing, 12)
        .padding(.vertical, 12)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(DS.line, lineWidth: 1))
        .shadow(color: .black.opacity(0.04), radius: 18, y: 8)
        .accessibilityLabel("Message Assistant")
        .fileImporter(
            isPresented: $showingFileImporter,
            allowedContentTypes: [.item],
            allowsMultipleSelection: true
        ) { result in
            if case .success(let urls) = result {
                appendFiles(urls)
            }
        }
        .onReceive(placeholderTimer) { _ in
            placeholderIndex = (placeholderIndex + 1) % placeholderOptions.count
        }
    }

    private var sendDisabled: Bool {
        prompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && selectedFiles.isEmpty
    }

    private var currentPlaceholder: String {
        placeholderOptions[placeholderIndex % placeholderOptions.count]
    }

    private var placeholderOptions: [String] {
        [
            "Ask Humungousaur anything...",
            "Drop in a task or attach a file...",
            "Plan, research, compare, summarize...",
            "What should we work through next?",
            "Attach context and ask for the outcome..."
        ]
    }

    private func appendFiles(_ urls: [URL]) {
        let merged = selectedFiles + urls.map(\.standardizedFileURL)
        var seen = Set<String>()
        selectedFiles = merged.filter { url in
            let key = url.path
            guard !seen.contains(key) else { return false }
            seen.insert(key)
            return true
        }
    }

    private func removeFile(_ url: URL) {
        selectedFiles.removeAll { $0.standardizedFileURL.path == url.standardizedFileURL.path }
    }

    private var modelPicker: some View {
        Menu {
            ForEach(modelOptions, id: \.self) { option in
                Button {
                    modelName = option
                } label: {
                    if option == modelName {
                        Label(option, systemImage: "checkmark")
                    } else {
                        Text(option)
                    }
                }
            }
        } label: {
            HStack(spacing: 5) {
                Image(systemName: "cpu")
                Text(modelName.isEmpty ? "Model" : modelName)
                    .lineLimit(1)
                Image(systemName: "chevron.down")
                    .font(.caption2.weight(.bold))
            }
            .font(.caption.weight(.medium))
            .foregroundStyle(.secondary)
            .padding(.horizontal, 11)
            .frame(height: 34, alignment: .center)
            .background(Color.primary.opacity(0.04), in: Capsule())
        }
        .menuStyle(.borderlessButton)
        .focusable(false)
        .frame(width: 150, height: 34, alignment: .center)
    }

    private var modelOptions: [String] {
        var values = [modelName, "gpt-5-mini", "gpt-5", "gpt-4.1-mini", "o4-mini"]
        values = values.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty }
        return Array(NSOrderedSet(array: values)) as? [String] ?? values
    }
}

struct AttachmentChip: View {
    let file: URL
    let onRemove: () -> Void

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "doc")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(.secondary)
            Text(file.lastPathComponent)
                .font(.caption.weight(.medium))
                .lineLimit(1)
                .truncationMode(.middle)
                .frame(maxWidth: 220, alignment: .leading)
            Button(action: onRemove) {
                Image(systemName: "xmark.circle.fill")
                    .font(.system(size: 12, weight: .semibold))
            }
            .buttonStyle(.plain)
            .foregroundStyle(.secondary)
            .help("Remove")
        }
        .padding(.leading, 9)
        .padding(.trailing, 7)
        .frame(height: 28)
        .background(Color.primary.opacity(0.055), in: Capsule())
        .overlay(Capsule().stroke(Color.primary.opacity(0.08), lineWidth: 1))
    }
}
