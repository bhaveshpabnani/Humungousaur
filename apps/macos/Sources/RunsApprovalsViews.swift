import SwiftUI

struct RunsView: View {
    @EnvironmentObject private var model: AppViewModel

    var body: some View {
        HStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 12) {
                SectionHeader(eyebrow: "Activity", title: "Recent Work", subtitle: "Tasks, progress, and responses without the internal trace noise.")
                List(model.runs, selection: $model.selectedRun) { run in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(run.displayStatus)
                                .font(.caption.weight(.bold))
                                .foregroundStyle(statusColor(run.status))
                            Spacer()
                            Text(run.startedAt)
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                        Text(run.displayRequest)
                            .lineLimit(2)
                    }
                    .padding(.vertical, 4)
                }
                .listStyle(.inset)
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            }
            .padding(24)
            .frame(minWidth: 360, maxWidth: 430)

            Divider()

            VStack(alignment: .leading, spacing: 16) {
                if let run = model.selectedRun {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(run.displayStatus)
                                .font(.caption.weight(.bold))
                                .foregroundStyle(statusColor(run.status))
                            Text(run.displayRequest)
                                .font(.title2.weight(.semibold))
                                .textSelection(.enabled)
                        }
                        Spacer()
                        Button("Cancel") {
                            Task { await model.cancelSelectedRun() }
                        }
                        .disabled(run.status == "succeeded" || run.status == "failed" || run.status == "blocked")
                    }
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Response")
                            .font(.headline)
                        ScrollView {
                            Text(run.finalResponse ?? "No final response yet.")
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .textSelection(.enabled)
                        }
                    }
                    .glassPanel()
                    Spacer()
                } else {
                    EmptyStateView(symbol: "clock.arrow.circlepath", title: "No activity yet", message: "Send a task from Chat or start the agent to see recent work here.")
                }
            }
            .padding(28)
        }
    }

    private func statusColor(_ status: String) -> Color {
        switch status {
        case "succeeded": .green
        case "needs_approval": .orange
        case "failed", "blocked", "cancelled": .red
        default: .secondary
        }
    }
}

struct ApprovalsView: View {
    @EnvironmentObject private var model: AppViewModel

    var body: some View {
        HStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 12) {
                SectionHeader(eyebrow: "Safety", title: "Permissions", subtitle: "Review protected actions before Humungousaur performs them.")
                if model.approvals.isEmpty {
                    EmptyStateView(symbol: "checkmark.seal", title: "Nothing needs permission", message: "Protected actions will pause here until you approve or reject them.")
                } else {
                    List(model.approvals, selection: $model.selectedApproval) { approval in
                        VStack(alignment: .leading, spacing: 5) {
                            HStack {
                                Text(approval.displayToolName)
                                    .font(.headline)
                                Spacer()
                                RiskBadge(risk: approval.displayRisk)
                            }
                            Text(approval.reason.isEmpty ? approval.request : approval.reason)
                                .lineLimit(2)
                                .foregroundStyle(.secondary)
                        }
                        .padding(.vertical, 5)
                    }
                    .listStyle(.inset)
                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                }
            }
            .padding(24)
            .frame(minWidth: 390, maxWidth: 460)

            Divider()

            VStack(alignment: .leading, spacing: 16) {
                if let approval = model.selectedApproval {
                    HStack(alignment: .top) {
                        VStack(alignment: .leading, spacing: 5) {
                            Text("Permission request")
                                .font(.caption.weight(.bold))
                                .foregroundStyle(DS.accent)
                            Text(approval.displayToolName)
                                .font(.largeTitle.weight(.semibold))
                            Text(approval.reason)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        RiskBadge(risk: approval.displayRisk)
                    }
                    UserTechnicalDetails(title: "Technical action details") {
                        JSONTextView(value: approval.toolInput ?? .object([:]))
                            .frame(minHeight: 220)
                    }
                    HStack {
                        Button(role: .destructive) {
                            Task { await model.rejectSelected() }
                        } label: {
                            Label("Reject", systemImage: "xmark.circle")
                        }
                        Spacer()
                        Button {
                            Task { await model.approveSelected() }
                        } label: {
                            Label("Approve", systemImage: "checkmark.circle.fill")
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.green)
                    }
                    Spacer()
                } else {
                    EmptyStateView(symbol: "shield.checkered", title: "Select a request", message: "You will see the reason, risk level, and technical details before deciding.")
                }
            }
            .padding(28)
        }
    }
}
