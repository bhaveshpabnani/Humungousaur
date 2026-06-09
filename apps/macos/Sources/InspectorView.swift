import SwiftUI

struct InspectorView: View {
    @EnvironmentObject private var model: AppViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("WORKSPACE")
                            .font(.caption.weight(.bold))
                            .foregroundStyle(.secondary)
                        Text("Project & Agent")
                            .font(.title3.weight(.semibold))
                    }
                    Spacer()
                    Button {
                        Task { await model.refreshAll() }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                }

                VStack(alignment: .leading, spacing: 9) {
                    Label(model.settings.workspacePath, systemImage: "folder")
                        .lineLimit(2)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Divider()
                    inspectorRow("Server", model.settings.apiBaseURL, "network")
                    inspectorRow("Model", model.settings.modelName, "cpu")
                    inspectorRow("Provider", model.settings.modelProvider, "server.rack")
                    inspectorRow("Reasoning", model.settings.planner.humanizedIdentifier, "point.3.connected.trianglepath.dotted")
                }
                .glassPanel(padding: 14)

                VStack(alignment: .leading, spacing: 10) {
                    Text("Capability Pulse")
                        .font(.headline)
                    inspectorMetric("Capabilities", "\(model.toolCatalog.toolCount)")
                    inspectorMetric("Channels", "\(model.channels.count)")
                    inspectorMetric("Runs", "\(model.runs.count)")
                    inspectorMetric("Permissions", "\(model.approvals.count)")
                }
                .glassPanel(padding: 14)

                VStack(alignment: .leading, spacing: 10) {
                    Text("Recent Runs")
                        .font(.headline)
                    ForEach(model.runs.prefix(6)) { run in
                        Button {
                            model.selectedRun = run
                            model.selectedSection = .runs
                        } label: {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(run.request.isEmpty ? run.runId : run.request)
                                    .lineLimit(1)
                                Text(run.status)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .glassPanel(padding: 14)
            }
            .padding(18)
        }
        .background(.bar)
    }

    private func inspectorRow(_ title: String, _ value: String, _ symbol: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: symbol)
                .foregroundStyle(DS.accent)
                .frame(width: 18)
            VStack(alignment: .leading, spacing: 1) {
                Text(title)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                Text(value.isEmpty ? "-" : value)
                    .font(.callout)
                    .lineLimit(2)
                    .truncationMode(.middle)
            }
        }
    }

    private func inspectorMetric(_ title: String, _ value: String) -> some View {
        HStack {
            Text(title)
                .foregroundStyle(.secondary)
            Spacer()
            Text(value)
                .fontWeight(.semibold)
        }
        .font(.callout)
    }
}
