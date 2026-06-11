import SwiftUI

struct ActiveAgentView: View {
    @EnvironmentObject private var model: AppViewModel
    @State private var correctionNote = "Feedback from macOS Active Agent panel."
    @State private var wrongTaskNote = "This active-agent context matched the wrong task."
    @State private var taskDraft = ActiveAgentTaskContextDraft()
    @State private var mutedScopeDraft = ActiveAgentMutedScopeDraft()

    private var status: ActiveAgentStatusResponse {
        model.activeAgentStatus
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                SectionHeader(
                    eyebrow: "Control",
                    title: "Active Agent",
                    subtitle: "Inspect why Humungousaur reacted, tune the task context, and keep collector access scoped."
                )

                LazyVGrid(columns: metricColumns, spacing: 12) {
                    MetricTile(title: "Posture", value: status.latestPosture, symbol: "antenna.radiowaves.left.and.right")
                    MetricTile(title: "Decisions", value: "\(status.decisions.count)", symbol: "bolt.horizontal")
                    MetricTile(title: "Contexts", value: "\(status.taskContexts.count)", symbol: "rectangle.stack")
                    MetricTile(title: "Collector Health", value: model.collectorStatus.statusText, symbol: "waveform.path.ecg")
                }

                plannerPreviewPanel

                HStack(alignment: .top, spacing: 14) {
                    ActiveAgentRecordPanel(title: "Latest Reflex", records: status.decisions, emptyMessage: "No reflex decisions recorded yet.")
                    ActiveAgentRecordPanel(title: "Agent Bridge", records: status.activations, emptyMessage: "No prepared or submitted activations yet.")
                }

                HStack(alignment: .top, spacing: 14) {
                    ActiveAgentRecordPanel(title: "Task Context", records: status.taskContexts, emptyMessage: "No active task context yet.")
                    ActiveAgentRecordPanel(title: "Memory Candidates", records: status.memoryCandidates, emptyMessage: "No Reflex memory candidates yet.")
                }

                HStack(alignment: .top, spacing: 14) {
                    deepDivePanel
                    ActiveAgentRecordPanel(title: "Why", records: status.explanations, emptyMessage: "No explanations recorded yet.")
                }

                HStack(alignment: .top, spacing: 14) {
                    feedbackPanel
                    taskCorrectionPanel
                }

                HStack(alignment: .top, spacing: 14) {
                    mutedScopePanel
                    collectorHealthPanel
                }

                UserTechnicalDetails(title: "Technical active-agent status") {
                    JSONTextView(value: technicalStatus)
                        .frame(minHeight: 300)
                }
            }
            .padding(28)
        }
        .task {
            await model.refreshActiveAgent()
        }
    }

    private var metricColumns: [GridItem] {
        [
            GridItem(.flexible()),
            GridItem(.flexible()),
            GridItem(.flexible()),
            GridItem(.flexible())
        ]
    }

    private var feedbackPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            panelTitle("Feedback", symbol: "hand.thumbsup")
            Text(model.activeAgentStatusText)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            TextField("Feedback note", text: $correctionNote, axis: .vertical)
                .lineLimit(2...4)

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                correctionButton("Helpful", symbol: "hand.thumbsup", type: "helpful")
                correctionButton("Not Relevant", symbol: "xmark.circle", type: "not_relevant")
                correctionButton("Private", symbol: "lock", type: "private", includeScope: true)
                correctionButton("Not Now", symbol: "bell.slash", type: "not_now", includeScope: true)
            }

            Button {
                Task { await model.refreshActiveAgent() }
            } label: {
                Label("Refresh", systemImage: "arrow.clockwise")
            }
            .buttonStyle(.borderedProminent)
            .tint(DS.accent)
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .glassPanel()
    }

    private var plannerPreviewPanel: some View {
        let preview = model.activeAgentPlannerContext
        return VStack(alignment: .leading, spacing: 12) {
            panelTitle("Planner Preview", symbol: "eye")
            Text(preview.privacy)
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                miniMetric("Memory", "\(preview.memoryItems.count)")
                miniMetric("Tasks", "\(preview.taskContexts.count)")
                miniMetric("Episodes", "\(preview.episodes.count)")
                miniMetric("Activations", "\(preview.activations.count)")
                miniMetric("Resume", "\(preview.resumeCapsules.count)")
                miniMetric("Deep Dives", "\(preview.deepDiveRequests.count)")
                miniMetric("Muted", "\(preview.mutedScopes.count)")
            }
            HStack(alignment: .top, spacing: 12) {
                ActiveAgentRecordPanel(title: "Current Activity", records: preview.episodes + preview.taskContexts, emptyMessage: "No planner-visible activity context yet.")
                ActiveAgentRecordPanel(title: "Planner Memory", records: preview.memoryItems, emptyMessage: "No promoted active-agent memory yet.")
            }
            HStack(alignment: .top, spacing: 12) {
                ActiveAgentRecordPanel(title: "Prepared Help", records: preview.activations + preview.resumeCapsules, emptyMessage: "No planner-visible prepared help yet.")
                ActiveAgentRecordPanel(title: "Approvals And Mutes", records: preview.deepDiveRequests + preview.mutedScopes, emptyMessage: "No pending deep dives or muted scopes.")
            }
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .glassPanel()
    }

    private var taskCorrectionPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            panelTitle("Wrong Task", symbol: "scope")
            TextField("User-declared goal", text: $taskDraft.goal, axis: .vertical)
                .lineLimit(1...3)
            TextField("Short summary", text: $taskDraft.summary, axis: .vertical)
                .lineLimit(2...4)
            Picker("Privacy", selection: $taskDraft.privacyMode) {
                Text("Metadata First").tag("metadata_first")
                Text("Private").tag("private")
                Text("Do Not Track").tag("do_not_track")
            }
            TextField("Allowed help, comma separated", text: $taskDraft.allowedHelp)
            TextField("Correction note", text: $wrongTaskNote, axis: .vertical)
                .lineLimit(2...4)
            HStack(spacing: 8) {
                Button {
                    Task {
                        await model.recordActiveAgentCorrection(
                            "wrong_task",
                            note: wrongTaskNote,
                            taskContext: taskDraft
                        )
                    }
                } label: {
                    Label("Record Wrong Task", systemImage: "arrow.triangle.2.circlepath")
                }
                .buttonStyle(.borderedProminent)
                .tint(DS.accent)
                .disabled(!taskDraft.hasContext)

                Button {
                    Task { await model.declareActiveAgentTaskContext(taskDraft) }
                } label: {
                    Label("Save Context", systemImage: "pin")
                }
                .buttonStyle(.bordered)
                .disabled(!taskDraft.hasContext)
            }
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .glassPanel()
    }

    private var deepDivePanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            panelTitle("Deep Dive Requests", symbol: "magnifyingglass")
            if status.deepDiveRequests.isEmpty {
                Text("No deep-dive requests waiting.")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(status.deepDiveRequests.prefix(5)) { request in
                    VStack(alignment: .leading, spacing: 8) {
                        HStack(alignment: .firstTextBaseline, spacing: 8) {
                            Text(request.statusText)
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(DS.accent)
                            Spacer()
                            Text(request.id)
                                .font(.caption2.monospaced())
                                .foregroundStyle(.secondary)
                                .lineLimit(1)
                        }
                        Text(request.primaryText)
                            .font(.callout)
                            .fixedSize(horizontal: false, vertical: true)
                        if !request.secondaryText.isEmpty {
                            Text(request.secondaryText)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .lineLimit(2)
                        }
                        HStack(spacing: 8) {
                            Button {
                                Task { await model.approveActiveAgentDeepDive(request) }
                            } label: {
                                Label("Approve", systemImage: "checkmark.seal")
                            }
                            .buttonStyle(.borderedProminent)
                            .tint(DS.accent)
                            .disabled(!request.canDecideDeepDive)

                            Button {
                                Task { await model.rejectActiveAgentDeepDive(request) }
                            } label: {
                                Label("Reject", systemImage: "xmark.seal")
                            }
                            .buttonStyle(.bordered)
                            .disabled(!request.canDecideDeepDive)
                        }
                    }
                    Divider()
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .glassPanel()
    }

    private var mutedScopePanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            panelTitle("Scoped Mutes", symbol: "speaker.slash")
            Picker("Mode", selection: $mutedScopeDraft.mode) {
                Text("No Assistance").tag("no_assistance")
                Text("Not Now").tag("not_now")
                Text("Do Not Track").tag("do_not_track")
                Text("Private").tag("private")
            }
            TextField("Collector", text: $mutedScopeDraft.collector)
            TextField("Source", text: $mutedScopeDraft.source)
            TextField("Stimulus type", text: $mutedScopeDraft.stimulusType)
            TextField("Entity refs, comma separated", text: $mutedScopeDraft.entityRefs)
            TextField("Reason", text: $mutedScopeDraft.reason, axis: .vertical)
                .lineLimit(2...3)
            Button {
                Task { await model.createActiveAgentMutedScope(mutedScopeDraft) }
            } label: {
                Label("Create Scoped Mute", systemImage: "plus.circle")
            }
            .buttonStyle(.borderedProminent)
            .tint(DS.accent)
            .disabled(!mutedScopeDraft.hasScope)

            Divider()

            if status.mutedScopes.isEmpty {
                Text("No active muted scopes.")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(status.mutedScopes.prefix(4)) { scope in
                    HStack(alignment: .top, spacing: 10) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(scope.statusText)
                                .font(.callout.weight(.semibold))
                            Text(scope.primaryText)
                                .font(.callout)
                                .foregroundStyle(.secondary)
                                .lineLimit(3)
                            if !scope.secondaryText.isEmpty {
                                Text(scope.secondaryText)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                    .lineLimit(2)
                            }
                        }
                        Spacer()
                        Button {
                            Task { await model.cancelActiveMutedScope(scope) }
                        } label: {
                            Image(systemName: "speaker.wave.2")
                        }
                        .buttonStyle(.borderless)
                        .help("Cancel muted scope")
                    }
                    Divider()
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .glassPanel()
    }

    private var collectorHealthPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            panelTitle("Collector Health", symbol: "waveform.path.ecg")
            Text(model.collectorStatusText)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            HStack(spacing: 8) {
                miniMetric("Events", "\(model.collectorStatus.eventCount)")
                miniMetric("Sequence", "\(model.collectorStatus.latestSequence)")
                miniMetric("Dead Letters", "\(model.collectorStatus.deadLetterCount)")
            }

            if model.collectorStatus.helperHealth.isEmpty {
                Text("No helper heartbeat records yet.")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(model.collectorStatus.helperHealth.prefix(6)) { helper in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(spacing: 8) {
                            Circle()
                                .fill(helper.needsAttention ? Color.orange : Color.green)
                                .frame(width: 8, height: 8)
                            Text(helper.collector)
                                .font(.callout.weight(.semibold))
                            Spacer()
                            Text(helper.statusText)
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(helper.needsAttention ? Color.orange : DS.accent)
                        }
                        Text(helper.platformText)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        if !helper.detailText.isEmpty {
                            Text(helper.detailText)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .lineLimit(2)
                        }
                    }
                    Divider()
                }
            }

            if !model.collectorStatus.recentEvents.isEmpty {
                Text("Recent Collector Stimuli")
                    .font(.callout.weight(.semibold))
                ForEach(model.collectorStatus.recentEvents.prefix(3)) { event in
                    VStack(alignment: .leading, spacing: 3) {
                        Text(event.primaryText)
                            .font(.callout)
                            .lineLimit(2)
                        Text(event.secondaryText)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .glassPanel()
    }

    private func correctionButton(_ title: String, symbol: String, type: String, includeScope: Bool = false) -> some View {
        Button {
            Task {
                await model.recordActiveAgentCorrection(
                    type,
                    note: correctionNote,
                    mutedScope: includeScope ? mutedScopeDraft : nil
                )
            }
        } label: {
            Label(title, systemImage: symbol)
                .frame(maxWidth: .infinity)
        }
        .buttonStyle(.bordered)
    }

    private func panelTitle(_ title: String, symbol: String) -> some View {
        Label(title, systemImage: symbol)
            .font(.headline)
    }

    private func miniMetric(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(value)
                .font(.headline)
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(Color.primary.opacity(0.025), in: RoundedRectangle(cornerRadius: DS.radius, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: DS.radius, style: .continuous)
                .stroke(DS.line, lineWidth: 1)
        )
    }

    private var technicalStatus: JSONValue {
        .object([
            "routes": .array(status.routes.map(\.detailValue)),
            "decisions": .array(status.decisions.map(\.detailValue)),
            "activations": .array(status.activations.map(\.detailValue)),
            "memory_candidates": .array(status.memoryCandidates.map(\.detailValue)),
            "task_contexts": .array(status.taskContexts.map(\.detailValue)),
            "muted_scopes": .array(status.mutedScopes.map(\.detailValue)),
            "deep_dive_requests": .array(status.deepDiveRequests.map(\.detailValue)),
            "context_window": status.contextWindow,
            "context_windows": .array(status.contextWindows.map(\.detailValue)),
            "context_boundaries": .array(status.contextBoundaries.map(\.detailValue)),
            "resume_capsules": .array(status.resumeCapsules.map(\.detailValue)),
            "explanations": .array(status.explanations.map(\.detailValue)),
            "corrections": .array(status.corrections.map(\.detailValue)),
            "collector_status": model.collectorStatus.detailValue
        ])
    }
}

private struct ActiveAgentRecordPanel: View {
    let title: String
    let records: [ActiveAgentRecord]
    let emptyMessage: String

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(title)
                    .font(.headline)
                Spacer()
                Text("\(records.count)")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
            }
            if records.isEmpty {
                Text(emptyMessage)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                ForEach(records.prefix(4)) { record in
                    VStack(alignment: .leading, spacing: 5) {
                        HStack(spacing: 8) {
                            Text(record.statusText)
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(DS.accent)
                            Spacer()
                            Text(record.id)
                                .font(.caption2.monospaced())
                                .foregroundStyle(.secondary)
                                .lineLimit(1)
                        }
                        Text(record.primaryText)
                            .font(.callout)
                            .fixedSize(horizontal: false, vertical: true)
                        if !record.secondaryText.isEmpty {
                            Text(record.secondaryText)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .lineLimit(2)
                        }
                    }
                    Divider()
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .glassPanel()
    }
}

private extension ActiveAgentRecord {
    var canDecideDeepDive: Bool {
        let status = string("status")?.lowercased()
        return status == nil || status == "needs_approval" || status == "pending"
    }
}
