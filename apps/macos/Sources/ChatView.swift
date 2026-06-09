import SwiftUI

struct ChatView: View {
    @EnvironmentObject private var model: AppViewModel
    @State private var prompt = ""
    @State private var voiceInputMode = false

    var body: some View {
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
                        if model.isSending {
                            HStack {
                                ProgressView()
                                    .controlSize(.small)
                                Text("Thinking")
                                    .foregroundStyle(.secondary)
                                Spacer()
                            }
                            .padding(.horizontal, 4)
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

            ComposerView(prompt: $prompt, modelName: $model.settings.modelName, voiceInputMode: $voiceInputMode) {
                let text = prompt
                let source = voiceInputMode ? "voice_transcript" : "user_text"
                prompt = ""
                Task { await model.send(text, source: source, responseMode: "text") }
            }
            .padding(.horizontal, 28)
            .padding(.top, 6)
            .padding(.bottom, 20)
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
}

struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            if message.role == .user { Spacer(minLength: 90) }
            Image(systemName: symbol)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(tint)
                .frame(width: 28, height: 28)
                .background(tint.opacity(0.12), in: Circle())
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text(title)
                        .font(.caption.weight(.bold))
                    Text(message.date, style: .time)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                Text(message.text)
                    .font(.body)
                    .textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(12)
            .background(background, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 14).stroke(DS.line))
            if message.role != .user { Spacer(minLength: 90) }
        }
    }

    private var title: String {
        switch message.role {
        case .user: "You"
        case .assistant: "Humungousaur"
        case .system: "System"
        case .error: "Error"
        }
    }

    private var symbol: String {
        switch message.role {
        case .user: "person.fill"
        case .assistant: "bolt.horizontal.circle.fill"
        case .system: "gearshape.fill"
        case .error: "exclamationmark.triangle.fill"
        }
    }

    private var tint: Color {
        switch message.role {
        case .user: .blue
        case .assistant: DS.accent
        case .system: .secondary
        case .error: .red
        }
    }

    private var background: some ShapeStyle {
        message.role == .user ? AnyShapeStyle(Color.accentColor.opacity(0.10)) : AnyShapeStyle(.regularMaterial)
    }
}

struct ComposerView: View {
    @Binding var prompt: String
    @Binding var modelName: String
    @Binding var voiceInputMode: Bool
    let onSend: () -> Void

    var body: some View {
        HStack(alignment: .center, spacing: 10) {
            TextField("Message Assistant (Enter to send)", text: $prompt, axis: .vertical)
                .textFieldStyle(.plain)
                .font(.system(.body, design: .rounded))
                .lineLimit(1...5)
                .onSubmit(onSend)
                .frame(minHeight: 34)
                .padding(.leading, 4)
            modelPicker
            Button {
                voiceInputMode.toggle()
            } label: {
                Image(systemName: voiceInputMode ? "mic.fill" : "mic")
                    .font(.system(size: 15, weight: .semibold))
                    .frame(width: 34, height: 34)
            }
            .buttonStyle(.plain)
            .foregroundStyle(voiceInputMode ? DS.accent : .secondary)
            .background(Color.primary.opacity(voiceInputMode ? 0.08 : 0.045), in: Circle())
            .help(voiceInputMode ? "Voice source enabled" : "Use voice source")

            Button(action: onSend) {
                Image(systemName: "arrow.up")
                    .font(.system(size: 16, weight: .bold))
                    .frame(width: 34, height: 34)
            }
            .buttonStyle(.plain)
            .foregroundStyle(.white)
            .background(sendDisabled ? Color.secondary.opacity(0.35) : DS.accent, in: Circle())
            .disabled(sendDisabled)
            .help("Send")
        }
        .padding(.leading, 18)
        .padding(.trailing, 12)
        .padding(.vertical, 12)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(DS.line, lineWidth: 1))
        .shadow(color: .black.opacity(0.04), radius: 18, y: 8)
    }

    private var sendDisabled: Bool {
        prompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
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
