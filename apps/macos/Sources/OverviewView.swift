import SwiftUI

struct OverviewView: View {
    @EnvironmentObject private var model: AppViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                SectionHeader(
                    eyebrow: "Runtime",
                    title: "Command Center",
                    subtitle: "A simple view of agent readiness, recent activity, permissions, and connection health."
                )
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                    MetricTile(title: "Agent", value: model.status.rawValue.humanizedStatus, symbol: "circle.hexagongrid.fill")
                    MetricTile(title: "Capabilities", value: "\(model.toolCatalog.toolCount)", symbol: "wrench.and.screwdriver")
                    MetricTile(title: "Need permission", value: "\(model.approvals.count)", symbol: "checkmark.seal")
                    MetricTile(title: "Recent activity", value: "\(model.runs.count)", symbol: "clock.arrow.circlepath")
                }

                HStack(alignment: .top, spacing: 12) {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Suggested Actions")
                            .font(.headline)
                        quick("Check readiness", command: "system_status {}", symbol: "gauge")
                        quick("Find voice features", command: "tool_search {\"query\":\"voice\",\"limit\":5}", symbol: "magnifyingglass")
                        quick("Review current focus", command: "cognitive_state {}", symbol: "brain")
                    }
                    .glassPanel()

                    VStack(alignment: .leading, spacing: 12) {
                        Text("Health")
                            .font(.headline)
                        HStack {
                            Text("Workspace")
                                .foregroundStyle(.secondary)
                            Spacer()
                            Text(model.health?.workspace ?? model.settings.workspacePath)
                                .lineLimit(1)
                                .truncationMode(.middle)
                        }
                        HStack {
                            Text("Platform")
                                .foregroundStyle(.secondary)
                            Spacer()
                            Text(model.health?.system?.platform?["system"] ?? "Unknown")
                        }
                        HStack {
                            Text("Warnings")
                                .foregroundStyle(.secondary)
                            Spacer()
                            Text("\(model.health?.system?.warnings?.count ?? 0)")
                        }
                        HStack {
                            Text("Overall")
                                .foregroundStyle(.secondary)
                            Spacer()
                            Text((model.systemStatus["overall_status"]?.stringValue ?? model.health?.system?.overallStatus ?? "Unknown").humanizedStatus)
                        }
                    }
                    .glassPanel()
                }

                RuntimeLogView()
            }
            .padding(28)
        }
    }

    private func quick(_ title: String, command: String, symbol: String) -> some View {
        Button {
            model.runQuickCommand(command, display: title)
            model.selectedSection = .chat
        } label: {
            HStack {
                Image(systemName: symbol)
                    .foregroundStyle(DS.accent)
                Text(title)
                Spacer()
                Image(systemName: "arrow.right")
                    .foregroundStyle(.secondary)
            }
        }
        .buttonStyle(.plain)
        .padding(11)
        .background(Color.primary.opacity(0.035), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
    }
}

struct RuntimeLogView: View {
    @EnvironmentObject private var model: AppViewModel

    var body: some View {
        UserTechnicalDetails(title: "Agent log") {
            if model.agentProcess.logLines.isEmpty {
                Text("No agent output yet.")
                    .foregroundStyle(.secondary)
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 5) {
                        ForEach(model.agentProcess.logLines, id: \.self) { line in
                            Text(line)
                                .font(.system(.caption, design: .monospaced))
                                .foregroundStyle(.secondary)
                                .textSelection(.enabled)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(minHeight: 160, maxHeight: 220)
            }
        }
    }
}

struct WorkboardView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                SectionHeader(eyebrow: "Workspace", title: "Workboard", subtitle: "Goals, follow-ups, focus, and blockers in one aligned workspace.")

                VStack(spacing: 0) {
                    WorkboardRow(title: "Current goal", symbol: "target", status: "Not set", text: "Start from Chat or Autonomy when you want the agent to keep track of a larger outcome.")
                    WorkboardRow(title: "Next follow-up", symbol: "alarm", status: "None", text: "Scheduled wakeups and reminders appear here when the agent reports them.")
                    WorkboardRow(title: "Focus", symbol: "scope", status: "Quiet", text: "Current focus will summarize what the agent is actively working on.")
                    WorkboardRow(title: "Needs attention", symbol: "exclamationmark.octagon", status: "Clear", text: "Blocked work and permission requests are summarized in Permissions and Activity.")
                }
                .background(Color.primary.opacity(0.022), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 10, style: .continuous).stroke(DS.line, lineWidth: 1))
            }
            .padding(28)
        }
    }
}

struct WorkboardRow: View {
    let title: String
    let symbol: String
    let status: String
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            Image(systemName: symbol)
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(DS.accent)
                .frame(width: 30, height: 30)
                .background(DS.accent.opacity(0.10), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.headline)
                Text(text)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 20)
            Text(status)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
                .padding(.horizontal, 9)
                .padding(.vertical, 5)
                .background(Color.primary.opacity(0.04), in: Capsule())
        }
        .frame(maxWidth: .infinity, minHeight: 78, alignment: .topLeading)
        .padding(.horizontal, 18)
        .padding(.vertical, 14)
        .overlay(alignment: .bottom) {
            Rectangle()
                .fill(DS.line)
                .frame(height: 1)
                .padding(.leading, 62)
        }
    }
}

struct UserTechnicalDetails<Content: View>: View {
    let title: String
    @ViewBuilder var content: Content

    var body: some View {
        DisclosureGroup(title) {
            content
                .padding(.top, 8)
        }
        .font(.callout)
        .foregroundStyle(.secondary)
        .glassPanel(padding: 14)
    }
}
