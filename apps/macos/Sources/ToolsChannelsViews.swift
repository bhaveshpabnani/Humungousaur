import SwiftUI

struct ToolsView: View {
    @EnvironmentObject private var model: AppViewModel

    var body: some View {
        HStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 12) {
                SectionHeader(eyebrow: "Capabilities", title: "What Humungousaur Can Do", subtitle: "Browse available actions by area. Items that need your permission are clearly marked.")
                Picker("Group", selection: $model.selectedToolGroup) {
                    Text("All").tag("all")
                    ForEach(model.toolCatalog.groups) { group in
                        Text("\(group.displayName) (\(group.toolCount))").tag(group.name)
                    }
                }
                .labelsHidden()
                .pickerStyle(.menu)
                List(model.toolCatalog.groups) { group in
                    HStack {
                        Text(group.displayName)
                        Spacer()
                        Text("\(group.toolCount)")
                            .foregroundStyle(.secondary)
                    }
                }
                .listStyle(.inset)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }
            .padding(24)
            .frame(minWidth: 320, maxWidth: 390)

            Divider()

            VStack(spacing: 14) {
                TextField("Search capabilities", text: $model.searchText)
                    .textFieldStyle(.roundedBorder)
                    .padding(.horizontal, 28)
                    .padding(.top, 24)
                ScrollView {
                    LazyVStack(spacing: 10) {
                        ForEach(model.filteredTools) { tool in
                            ToolCard(tool: tool)
                        }
                    }
                    .padding(.horizontal, 28)
                    .padding(.bottom, 28)
                }
            }
        }
    }
}

struct ToolCard: View {
    let tool: ToolInfo

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: tool.requiresApproval ? "lock.shield" : "wrench.and.screwdriver")
                .foregroundStyle(tool.requiresApproval ? .orange : DS.accent)
                .frame(width: 30, height: 30)
                .background(Color.primary.opacity(0.045), in: RoundedRectangle(cornerRadius: 8))
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text(tool.displayName)
                        .font(.headline)
                    Text(tool.displayGroup)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    RiskBadge(risk: tool.riskLevel)
                }
                Text(tool.description)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                Text(tool.permissionSummary)
                    .font(.caption.weight(.medium))
                    .foregroundStyle(tool.requiresApproval ? .orange : .green)
            }
        }
        .glassPanel(padding: 14)
    }
}

struct ChannelsView: View {
    @EnvironmentObject private var model: AppViewModel

    var body: some View {
        HStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 12) {
                SectionHeader(eyebrow: "Connections", title: "Message Channels", subtitle: "Connect inboxes, preview messages, and keep replies approval-aware.")
                if model.channels.isEmpty {
                    EmptyStateView(symbol: "point.3.connected.trianglepath.dotted", title: "No channels", message: "Start or refresh the local agent to load the gateway catalog.")
                } else {
                    List(model.channels, selection: $model.selectedChannelID) { channel in
                        ChannelListRow(channel: channel)
                            .tag(channel.channelId)
                    }
                    .listStyle(.inset)
                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                }
            }
            .padding(24)
            .frame(minWidth: 330, maxWidth: 410)

            Divider()

            if let channel = model.selectedChannel {
                ChannelDetailView(channel: channel, setup: model.setup(for: channel))
                    .id(channel.channelId)
            } else {
                EmptyStateView(symbol: "message.badge", title: "Select a channel", message: "Setup, incoming message checks, and prepared replies appear here.")
                    .padding(28)
            }
        }
        .task(id: model.selectedChannelID) {
            if let channel = model.selectedChannel {
                await model.refreshChannelDetails(channel)
            }
        }
    }
}

struct ChannelListRow: View {
    let channel: ChannelInfo

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "message.badge.waveform")
                    .foregroundStyle(DS.accent)
                    .frame(width: 34, height: 34)
                    .background(DS.accent.opacity(0.12), in: RoundedRectangle(cornerRadius: 9))
                VStack(alignment: .leading) {
                    Text(channel.displayName)
                        .font(.headline)
                    Text(channel.displayTransport)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
            }
            HStack {
                channelFlag("Text", channel.supportsText)
                channelFlag("Media", channel.supportsMedia)
                channelFlag("Reactions", channel.supportsReactions)
            }
            Text(channel.setupSummary)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 5)
    }

    private func channelFlag(_ title: String, _ enabled: Bool) -> some View {
        Text(title)
            .font(.caption.weight(.semibold))
            .foregroundStyle(enabled ? .green : .secondary)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(Color.primary.opacity(0.045), in: Capsule())
    }
}

struct ChannelDetailView: View {
    @EnvironmentObject private var model: AppViewModel
    let channel: ChannelInfo
    @State private var setup: ChannelSetup
    @State private var inboundText = "Could you check whether everything is connected?"
    @State private var outboundText = ""

    init(channel: ChannelInfo, setup: ChannelSetup) {
        self.channel = channel
        _setup = State(initialValue: setup)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                channelHeader
                statusGrid
                setupForm
                diagnosticsGrid
                messagePanel
                listenerPanel
                outboxPanel
            }
            .padding(28)
        }
    }

    private var channelHeader: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: "message.badge.waveform")
                .font(.system(size: 20, weight: .semibold))
                .foregroundStyle(DS.accent)
                .frame(width: 42, height: 42)
                .background(DS.accent.opacity(0.12), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            VStack(alignment: .leading, spacing: 5) {
                Text(channel.displayName)
                    .font(.largeTitle.weight(.semibold))
                Text("\(channel.displayTransport) / \(channel.setupSummary)")
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Button {
                Task { await model.refreshChannelDetails(channel) }
            } label: {
                Label("Refresh", systemImage: "arrow.clockwise")
            }
        }
    }

    private var statusGrid: some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            ChannelTextPanel(title: "Connection", text: model.channelStatusText)
            ChannelTextPanel(title: "Incoming messages", text: model.channelListenerText)
            ChannelTextPanel(title: "Setup guide", text: model.channelRequirementText)
            ChannelTextPanel(title: "Permissions", text: model.channelPolicyText)
        }
    }

    private var setupForm: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Setup")
                .font(.headline)
            Toggle("Enabled", isOn: $setup.enabled)
                .toggleStyle(.switch)
            Toggle("Receive incoming messages", isOn: $setup.listenEnabled)
                .toggleStyle(.switch)
            Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 10) {
                GridRow {
                    Picker("Reply location", selection: $setup.conversationType) {
                        ForEach(conversationOptions, id: \.self) { option in
                            Text(option.humanizedIdentifier).tag(option)
                        }
                    }
                    TextField("Conversation or room", text: $setup.conversationId)
                }
                GridRow {
                    TextField("Credential label", text: $setup.secretName)
                    SecureField("Credential value", text: $setup.secretValue)
                }
            }
            VStack(alignment: .leading, spacing: 6) {
                Text("Additional credentials")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                TextEditor(text: secretLinesBinding)
                    .font(.system(.callout, design: .monospaced))
                    .frame(minHeight: 76)
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(DS.line, lineWidth: 1))
            }
            Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 10) {
                GridRow {
                    MultilineListEditor(title: "Allowed senders", values: $setup.allowlist)
                    MultilineListEditor(title: "Allowed rooms/groups", values: $setup.groupAllowlist)
                }
            }
            TextField("Setup notes", text: $setup.notes)
            HStack {
                Button {
                    Task { await model.saveChannelSetup(channel, setup: setup) }
                } label: {
                    Label("Save", systemImage: "square.and.arrow.down")
                }
                .buttonStyle(.borderedProminent)
                .tint(DS.accent)
                Button {
                    Task { await model.refreshChannelRequirements(channel) }
                } label: {
                    Label("Setup Guide", systemImage: "list.bullet.rectangle")
                }
                Spacer()
            }
        }
        .glassPanel()
    }

    private var diagnosticsGrid: some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("Connection check")
                        .font(.headline)
                    Spacer()
                    Button {
                        Task { await model.runChannelDoctor(channel) }
                    } label: {
                        Label("Check", systemImage: "stethoscope")
                    }
                }
                ScrollView {
                    Text(model.channelDoctorText)
                        .font(.system(.callout, design: .monospaced))
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .textSelection(.enabled)
                }
                .frame(minHeight: 132)
            }
            .glassPanel()

            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("Trial run")
                        .font(.headline)
                    Spacer()
                    Button {
                        Task { await model.runChannelSmoke(channel) }
                    } label: {
                        Label("Test", systemImage: "flame")
                    }
                }
                ScrollView {
                    Text(model.channelSmokeText)
                        .font(.system(.callout, design: .monospaced))
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .textSelection(.enabled)
                }
                .frame(minHeight: 132)
            }
            .glassPanel()
        }
    }

    private var messagePanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Message preview")
                .font(.headline)
            TextField("Test incoming message", text: $inboundText, axis: .vertical)
                .lineLimit(2...5)
            TextField("Draft reply", text: $outboundText, axis: .vertical)
                .lineLimit(3...7)
            HStack {
                Button {
                    Task { await model.previewInbound(channel: channel, setup: setup, text: inboundText) }
                } label: {
                    Label("Preview", systemImage: "tray.and.arrow.down")
                }
                Button {
                    Task { await model.prepareOutbound(channel: channel, setup: setup, text: outboundText) }
                } label: {
                    Label("Prepare Reply", systemImage: "envelope.badge")
                }
                Spacer()
                Button {
                    Task { await model.sendOutbound(channel: channel, setup: setup, text: outboundText) }
                } label: {
                    Label("Send", systemImage: "paperplane.fill")
                }
                .buttonStyle(.borderedProminent)
                .tint(model.settings.approveHighRisk ? .green : .orange)
            }
        }
        .glassPanel()
    }

    private var listenerPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Incoming messages")
                .font(.headline)
            HStack {
                Button {
                    Task { await model.tickChannel(channel) }
                } label: {
                    Label("Check Now", systemImage: "dot.radiowaves.left.and.right")
                }
                Button {
                    Task { await model.tickAllChannels() }
                } label: {
                    Label("Check All", systemImage: "antenna.radiowaves.left.and.right")
                }
                Stepper("Every \(model.channelListenerIntervalSeconds)s", value: $model.channelListenerIntervalSeconds, in: 10...600, step: 5)
                Toggle("Keep checking", isOn: Binding(
                    get: { model.channelListenerLoopEnabled },
                    set: { model.setChannelListenerLoop($0) }
                ))
                .toggleStyle(.switch)
                Spacer()
            }
            Text(model.channelListenLoopText)
                .foregroundStyle(.secondary)
        }
        .glassPanel()
    }

    private var outboxPanel: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Draft replies")
                    .font(.headline)
                Spacer()
                Button {
                    Task { await model.refreshChannels() }
                } label: {
                    Label("Refresh", systemImage: "arrow.clockwise")
                }
            }
            if model.outbox.messages.isEmpty {
                Text("No outbox messages yet.")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(Array(model.outbox.messages.enumerated()), id: \.offset) { _, item in
                    Text(item.compactDescription)
                        .font(.system(.caption, design: .monospaced))
                        .lineLimit(5)
                        .padding(10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.primary.opacity(0.035), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                        .textSelection(.enabled)
                }
            }
        }
        .glassPanel()
    }

    private var conversationOptions: [String] {
        let values = channel.conversationTypes.isEmpty ? ["dm", "room", "channel", "group"] : channel.conversationTypes
        return values.contains(setup.conversationType) ? values : [setup.conversationType] + values
    }

    private var secretLinesBinding: Binding<String> {
        Binding {
            serializeSecretLines(setup.secretNames, values: setup.secretValues)
        } set: { newValue in
            let parsed = parseSecretLines(newValue)
            setup.secretNames = Array(parsed.keys).sorted()
            setup.secretValues = parsed
        }
    }

    private func parseSecretLines(_ text: String) -> [String: String] {
        var values: [String: String] = [:]
        for rawLine in text.components(separatedBy: .newlines) {
            let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !line.isEmpty, !line.hasPrefix("#"), let separator = line.firstIndex(of: "=") else {
                continue
            }
            let key = line[..<separator].trimmingCharacters(in: .whitespacesAndNewlines)
            let value = line[line.index(after: separator)...].trimmingCharacters(in: .whitespacesAndNewlines)
            if !key.isEmpty {
                values[key] = value
            }
        }
        return values
    }

    private func serializeSecretLines(_ names: [String], values: [String: String]) -> String {
        let allNames = Array(Set(names + Array(values.keys))).sorted()
        return allNames.map { "\($0)=\(values[$0, default: ""])" }.joined(separator: "\n")
    }
}

struct ChannelTextPanel: View {
    let title: String
    let text: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.headline)
            ScrollView {
                Text(text.isEmpty ? "-" : text)
                    .font(.system(.callout, design: .monospaced))
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
            }
            .frame(minHeight: 92)
        }
        .glassPanel()
    }
}

struct MultilineListEditor: View {
    let title: String
    @Binding var values: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            TextEditor(text: Binding(
                get: { values.joined(separator: "\n") },
                set: { newValue in
                    values = newValue
                        .components(separatedBy: CharacterSet(charactersIn: "\n,"))
                        .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                        .filter { !$0.isEmpty && !$0.hasPrefix("#") }
                }
            ))
            .font(.system(.callout, design: .monospaced))
            .frame(minHeight: 62)
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(DS.line, lineWidth: 1))
        }
    }
}
