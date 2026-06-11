import SwiftUI

struct SidebarView: View {
    @EnvironmentObject private var model: AppViewModel

    var body: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 11) {
                    HumungousaurLogoMark(size: 38)

                    VStack(alignment: .leading, spacing: 1) {
                        Text("CONTROL")
                            .font(.caption2.weight(.bold))
                            .foregroundStyle(.secondary)
                        Text("Humungousaur")
                            .font(.headline.weight(.semibold))
                    }
                    Spacer()
                    Button {
                        model.startNewSession()
                    } label: {
                        Image(systemName: "plus")
                    }
                    .buttonStyle(.borderless)
                    .help("New session")
                }

                HStack(spacing: 9) {
                    OnlineIndicator(status: model.status)
                    Spacer()
                    Text(model.agentProcess.isRunning ? "Local daemon" : "API link")
                        .font(.caption.weight(.medium))
                        .foregroundStyle(.secondary)
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 8)
                .background(Color.primary.opacity(0.035), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            }
            .padding(18)

            List(selection: $model.selectedSection) {
                Section("Chat") {
                    nav(.chat)
                }
                Section("Control") {
                    nav(.overview)
                    nav(.workboard)
                    nav(.runs)
                    nav(.approvals)
                    nav(.activeAgent)
                    nav(.autonomy)
                }
                Section("Agent") {
                    nav(.tools)
                    nav(.connectors)
                    nav(.channels)
                    nav(.voice)
                }
                Section("Settings") {
                    nav(.settings)
                }
            }
            .listStyle(.sidebar)

            VStack(spacing: 8) {
                HStack(spacing: 8) {
                    Image(systemName: "person.crop.circle")
                        .foregroundStyle(.secondary)
                    VStack(alignment: .leading, spacing: 1) {
                        Text(model.displayName)
                            .font(.callout.weight(.medium))
                            .lineLimit(1)
                        HStack(spacing: 5) {
                            Circle()
                                .fill(model.status.color)
                                .frame(width: 6, height: 6)
                            Text(model.status.rawValue.humanizedStatus)
                                .font(.caption2.weight(.medium))
                                .foregroundStyle(.secondary)
                        }
                    }
                    Spacer()
                    Menu {
                        Section("Connection") {
                            Text("Status: \(model.status.rawValue.humanizedStatus)")
                            Text("Server: \(model.settings.apiBaseURL)")
                            Text("Project: \(model.health?.workspace ?? model.settings.workspacePath)")
                        }
                        Divider()
                        Button {
                            Task { await model.refreshAll() }
                        } label: {
                            Label("Refresh", systemImage: "arrow.clockwise")
                        }
                        Button {
                            Task { await model.toggleAgentProcess() }
                        } label: {
                            Label(model.agentProcess.isRunning ? "Stop Agent" : "Start Agent", systemImage: model.agentProcess.isRunning ? "stop.fill" : "play.fill")
                        }
                    } label: {
                        Image(systemName: "ellipsis")
                            .font(.system(size: 14, weight: .bold))
                            .frame(width: 24, height: 24)
                    }
                    .menuStyle(.borderlessButton)
                    .help("Connection controls")
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 9)
                .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            }
            .padding(12)
        }
        .background(.bar)
    }

    private func nav(_ section: AppSection) -> some View {
        NavigationLink(value: section) {
            Label(section.title, systemImage: section.symbol)
        }
    }
}
