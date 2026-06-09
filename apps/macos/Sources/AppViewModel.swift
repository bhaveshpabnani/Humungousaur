import Foundation
import SwiftUI

@MainActor
final class AppViewModel: ObservableObject {
    @Published var selectedSection: AppSection = .chat
    @Published var settings: AppSettings
    @Published var secrets: RuntimeSecrets
    @Published var status: AgentStatus = .offline
    @Published var health: HealthPayload?
    @Published var systemStatus: JSONValue = .object([:])
    @Published var toolCatalog = ToolCatalog(toolCount: 0, groups: [], tools: [])
    @Published var runs: [RunItem] = []
    @Published var approvals: [ApprovalItem] = []
    @Published var channels: [ChannelInfo] = []
    @Published var outbox = OutboxEnvelope(messages: [])
    @Published var autonomousStatus: JSONValue = .object([:])
    @Published var voiceStatus: JSONValue = .object([:])
    @Published var messages: [ChatMessage] = []
    @Published var selectedRun: RunItem?
    @Published var selectedApproval: ApprovalItem?
    @Published var selectedChannelID: String?
    @Published var channelStatusText = "Select a channel to view its connection status."
    @Published var channelListenerText = "Incoming message status appears after channel selection."
    @Published var channelRequirementText = ""
    @Published var channelSetupStepsText = ""
    @Published var channelPolicyText = ""
    @Published var channelDoctorText = "Run a connection check after saving setup or entering credentials."
    @Published var channelSmokeText = "Run a trial to validate drafting, sending, and incoming message readiness."
    @Published var channelListenLoopText = "Automatic checking is off."
    @Published var selectedToolGroup = "all"
    @Published var searchText = ""
    @Published var isRefreshing = false
    @Published var isSending = false
    @Published var channelListenerLoopEnabled = false
    @Published var channelListenerIntervalSeconds = 30
    @Published var notice: String?

    let agentProcess = LocalAgentProcess()

    var displayName: String {
        let fullName = NSFullUserName().trimmingCharacters(in: .whitespacesAndNewlines)
        if !fullName.isEmpty {
            let firstName = fullName.components(separatedBy: .whitespaces).first ?? fullName
            return firstName.localizedCapitalized
        }
        let userName = NSUserName().trimmingCharacters(in: .whitespacesAndNewlines)
        return userName.isEmpty ? "User" : userName.localizedCapitalized
    }

    private let settingsStore = SettingsStore()
    private let keychain = KeychainStore()
    private var api: AgentAPIClient
    private var channelListenerTask: Task<Void, Never>?
    private var channelListenerTickRunning = false

    init() {
        let loaded = settingsStore.load()
        settings = loaded
        secrets = RuntimeSecrets(
            modelAPIKey: keychain.read("model_api_key"),
            deepgramAPIKey: keychain.read("deepgram_api_key"),
            elevenLabsAPIKey: keychain.read("elevenlabs_api_key")
        )
        api = AgentAPIClient(baseURL: loaded.apiBaseURL)
    }

    func bootstrap() async {
        await refreshAll()
    }

    func refreshAll() async {
        isRefreshing = true
        api.setBaseURL(settings.apiBaseURL)
        defer { isRefreshing = false }
        await refreshHealth()
        await refreshTools()
        await refreshRuns()
        await refreshApprovals()
        await refreshChannels()
        await refreshAutonomy()
        await refreshVoice()
    }

    func refreshHealth() async {
        do {
            health = try await api.health()
            systemStatus = try await api.systemStatus()
            status = health?.status == "ok" ? .online : .degraded
        } catch {
            status = .offline
            systemStatus = .string(error.localizedDescription)
            notice = "API offline at \(settings.apiBaseURL)."
        }
    }

    func refreshTools() async {
        do {
            toolCatalog = try await api.tools()
        } catch {
            toolCatalog = ToolCatalog(toolCount: 0, groups: [], tools: [])
        }
    }

    func refreshRuns() async {
        do {
            runs = try await api.runs()
            if selectedRun == nil {
                selectedRun = runs.first
            }
        } catch {
            runs = []
        }
    }

    func refreshApprovals() async {
        do {
            approvals = try await api.approvals()
            if selectedApproval == nil {
                selectedApproval = approvals.first
            }
        } catch {
            approvals = []
        }
    }

    func refreshChannels() async {
        do {
            channels = try await api.channels()
            outbox = try await api.outbox()
            if selectedChannelID == nil {
                selectedChannelID = channels.first?.channelId
            }
            if let selectedChannel {
                await refreshChannelDetails(selectedChannel)
            }
        } catch {
            channels = []
            outbox = OutboxEnvelope(messages: [])
        }
    }

    func refreshAutonomy() async {
        do {
            autonomousStatus = try await api.autonomousStatus()
        } catch {
            autonomousStatus = .string(error.localizedDescription)
        }
    }

    func refreshVoice() async {
        do {
            voiceStatus = try await api.voiceStatus(settings: settings, secrets: secrets)
        } catch {
            voiceStatus = .string(error.localizedDescription)
        }
    }

    func send(_ prompt: String, source: String, responseMode: String, displayText: String? = nil) async {
        let trimmed = prompt.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        messages.append(ChatMessage(role: .user, text: displayText ?? trimmed))
        isSending = true
        defer { isSending = false }
        do {
            let response = try await api.sendStimulus(trimmed, source: source, responseMode: responseMode, settings: settingsWithChannelSecrets(), secrets: secrets)
            messages.append(ChatMessage(role: .assistant, text: response.displayText))
            await refreshRuns()
            await refreshApprovals()
            await refreshAutonomy()
        } catch {
            messages.append(ChatMessage(role: .error, text: error.localizedDescription))
        }
    }

    func runQuickCommand(_ command: String, display: String? = nil) {
        Task {
            await send(command, source: "user_text", responseMode: "text", displayText: display)
        }
    }

    func startNewSession() {
        messages = []
        selectedSection = .chat
    }

    func saveSettings() {
        settingsStore.save(settings)
        keychain.write(secrets.modelAPIKey, account: "model_api_key")
        keychain.write(secrets.deepgramAPIKey, account: "deepgram_api_key")
        keychain.write(secrets.elevenLabsAPIKey, account: "elevenlabs_api_key")
        api.setBaseURL(settings.apiBaseURL)
        notice = "Settings saved."
    }

    func settingsWithChannelSecrets() -> AppSettings {
        var copy = settings
        for index in copy.channels.indices {
            loadChannelSecrets(into: &copy.channels[index])
        }
        return copy
    }

    func toggleAgentProcess() async {
        if agentProcess.isRunning {
            agentProcess.stop()
            status = .offline
            return
        }
        do {
            status = .starting
            saveSettings()
            try agentProcess.start(settings: settingsWithChannelSecrets(), secrets: secrets)
            try? await Task.sleep(for: .seconds(1))
            await refreshAll()
        } catch {
            status = .offline
            notice = error.localizedDescription
        }
    }

    func approveSelected() async {
        guard let selectedApproval else { return }
        do {
            _ = try await api.approve(selectedApproval.approvalToken, note: "Approved from Humungousaur Mac.")
            notice = "Approved \(selectedApproval.toolName)."
            await refreshRuns()
            await refreshApprovals()
        } catch {
            notice = error.localizedDescription
        }
    }

    func rejectSelected() async {
        guard let selectedApproval else { return }
        do {
            _ = try await api.reject(selectedApproval.approvalToken, note: "Rejected from Humungousaur Mac.")
            notice = "Rejected \(selectedApproval.toolName)."
            await refreshRuns()
            await refreshApprovals()
        } catch {
            notice = error.localizedDescription
        }
    }

    func cancelSelectedRun() async {
        guard let selectedRun else { return }
        do {
            _ = try await api.cancelRun(selectedRun.runId, reason: "Cancelled from Humungousaur Mac.")
            notice = "Cancellation requested."
            await refreshRuns()
        } catch {
            notice = error.localizedDescription
        }
    }

    func runAutonomyCycle() async {
        do {
            autonomousStatus = try await api.runAutonomousCycle(settings: settingsWithChannelSecrets(), secrets: secrets)
            notice = "Autonomy cycle completed."
        } catch {
            notice = error.localizedDescription
        }
    }

    var selectedChannel: ChannelInfo? {
        channels.first { $0.channelId == selectedChannelID } ?? channels.first
    }

    func setup(for channel: ChannelInfo) -> ChannelSetup {
        var setup = settings.channels.first { $0.channelId == channel.channelId } ?? ChannelSetup(channelId: channel.channelId)
        applyDefaults(channel: channel, setup: &setup)
        loadChannelSecrets(into: &setup)
        return setup
    }

    func saveChannelSetup(_ channel: ChannelInfo, setup: ChannelSetup) async {
        var clean = setup
        clean.channelId = channel.channelId
        clean.secretConfigured = clean.secretConfigured
            || !clean.secretValue.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            || clean.secretValues.values.contains { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
        writeChannelSecrets(clean)
        var stored = clean
        stored.secretValue = ""
        stored.secretValues = [:]
        upsertChannelSetup(stored)
        settingsStore.save(settings)

        do {
            _ = try await api.saveChannelSetup(channel: channel, setup: clean)
            notice = "\(channel.displayName) setup saved."
            await refreshChannelDetails(channel)
        } catch {
            channelStatusText = error.localizedDescription
            notice = "Local setup saved, but backend setup sync failed."
        }
    }

    func refreshChannelDetails(_ channel: ChannelInfo) async {
        renderChannelRequirements(channel)
        await refreshChannelRequirements(channel)
        await refreshChannelStatus(channel)
    }

    func refreshChannelRequirements(_ channel: ChannelInfo) async {
        do {
            let requirements = try await api.channelRequirements(channelID: channel.channelId)
            channelRequirementText = formatRequirementSummary(requirements)
            channelSetupStepsText = formatSetupSteps(requirements["setup"])
            channelPolicyText = formatPolicySummary(
                policies: requirements["policies"],
                delivery: requirements["delivery"],
                runtime: requirements["runtime"]
            )
        } catch {
            notice = error.localizedDescription
        }
    }

    func refreshChannelStatus(_ channel: ChannelInfo) async {
        do {
            let runtimeSettings = settingsWithChannelSecrets()
            let status = try await api.channelStatus(channelID: channel.channelId, settings: runtimeSettings, secrets: secrets)
            channelStatusText = formatChannelStatus(status)
            let listeners = try await api.channelListeners(channelID: channel.channelId, settings: runtimeSettings, secrets: secrets)
            channelListenerText = formatChannelListenerStatus(listeners)
        } catch {
            channelStatusText = error.localizedDescription
        }
    }

    func runChannelDoctor(_ channel: ChannelInfo) async {
        do {
            let doctor = try await api.channelDoctor(channelID: channel.channelId, settings: settingsWithChannelSecrets(), secrets: secrets)
            channelDoctorText = formatDoctorFindings(doctor)
            let warnings = doctor["findings"]?.arrayValue?.filter { $0["severity"]?.stringValue == "warning" }.count ?? 0
            notice = warnings == 0 ? "\(channel.displayName) doctor is clean." : "\(channel.displayName) doctor found \(warnings) warning(s)."
        } catch {
            channelDoctorText = error.localizedDescription
            notice = "Channel doctor failed."
        }
    }

    func runChannelSmoke(_ channel: ChannelInfo) async {
        do {
            let smoke = try await api.runChannelSmoke(channelID: channel.channelId, settings: settingsWithChannelSecrets(), secrets: secrets)
            channelSmokeText = formatChannelSmoke(smoke)
            let readiness = smoke["channels"]?.arrayValue?.first?["readiness"]?.stringValue ?? smoke["overall_status"]?.stringValue ?? "unknown"
            notice = "\(channel.displayName) smoke: \(readiness)."
            outbox = try await api.outbox()
            await refreshChannelStatus(channel)
        } catch {
            channelSmokeText = error.localizedDescription
            notice = "Channel smoke failed."
        }
    }

    func prepareOutbound(channel: ChannelInfo, setup: ChannelSetup, text: String) async {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            notice = "Write an outbound message first."
            return
        }
        do {
            let result = try await api.prepareChannelMessage(
                channel: channel,
                setup: setup,
                text: trimmed,
                settings: settingsWithChannelSecrets(),
                secrets: secrets
            )
            let status = result["message"]?["status"]?.stringValue ?? "prepared"
            notice = "Outbound message \(status)."
            outbox = try await api.outbox()
        } catch {
            notice = error.localizedDescription
        }
    }

    func sendOutbound(channel: ChannelInfo, setup: ChannelSetup, text: String) async {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            notice = "Write an outbound message first."
            return
        }
        guard settings.approveHighRisk else {
            notice = "Enable high-risk approval in Settings before live channel sends."
            return
        }
        do {
            let result = try await api.sendChannelMessage(
                channel: channel,
                setup: setup,
                text: trimmed,
                settings: settingsWithChannelSecrets(),
                secrets: secrets
            )
            let status = result["message"]?["status"]?.stringValue ?? "unknown"
            notice = "Channel send result: \(status)."
            outbox = try await api.outbox()
            await refreshChannelStatus(channel)
        } catch {
            notice = error.localizedDescription
        }
    }

    func previewInbound(channel: ChannelInfo, setup: ChannelSetup, text: String) async {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            notice = "Write inbound preview text first."
            return
        }
        do {
            let result = try await api.sendChannelInbound(
                channel: channel,
                setup: setup,
                text: trimmed,
                settings: settingsWithChannelSecrets(),
                secrets: secrets
            )
            messages.append(ChatMessage(role: .system, text: result["prepared_reply"]?["text"]?.stringValue ?? result.description))
            notice = "Inbound preview prepared."
            outbox = try await api.outbox()
        } catch {
            notice = error.localizedDescription
        }
    }

    func tickChannel(_ channel: ChannelInfo) async {
        do {
            let result = try await api.tickChannelListener(channelID: channel.channelId, settings: settingsWithChannelSecrets(), secrets: secrets)
            let processed = result["processed_count"]?.numberText ?? "0"
            channelListenerText = "Listener tick processed \(processed) event(s)."
            notice = "Listener tick processed \(processed) event(s)."
            outbox = try await api.outbox()
            await refreshChannelStatus(channel)
        } catch {
            channelListenerText = error.localizedDescription
            notice = "Listener tick failed."
        }
    }

    func tickAllChannels(showNotice: Bool = true) async {
        guard !channelListenerTickRunning else { return }
        channelListenerTickRunning = true
        defer { channelListenerTickRunning = false }
        do {
            let result = try await api.tickAllChannelListeners(settings: settingsWithChannelSecrets(), secrets: secrets)
            let processed = result["processed_count"]?.numberText ?? "0"
            let notes = result["listener_notes"]?.arrayValue?.count ?? 0
            channelListenLoopText = "Last tick processed \(processed) event(s); \(notes) listener note(s)."
            if showNotice {
                notice = "Channel listener tick processed \(processed) event(s)."
            }
            outbox = try await api.outbox()
            if let selectedChannel {
                await refreshChannelStatus(selectedChannel)
            }
        } catch {
            channelListenLoopText = error.localizedDescription
            if showNotice {
                notice = "Channel listener tick failed."
            }
        }
    }

    func setChannelListenerLoop(_ enabled: Bool) {
        channelListenerLoopEnabled = enabled
        channelListenerTask?.cancel()
        channelListenerTask = nil
        guard enabled else {
            channelListenLoopText = "Listening loop stopped."
            return
        }
        let seconds = max(10, channelListenerIntervalSeconds)
        channelListenLoopText = "Listening loop running every \(seconds) seconds."
        channelListenerTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(seconds))
                if Task.isCancelled { break }
                await self?.tickAllChannels(showNotice: false)
            }
        }
    }

    var filteredTools: [ToolInfo] {
        toolCatalog.tools.filter { tool in
            let groupMatches = selectedToolGroup == "all" || tool.capabilityGroup == selectedToolGroup
            let query = searchText.trimmingCharacters(in: .whitespacesAndNewlines)
            let searchMatches = query.isEmpty
                || tool.name.localizedCaseInsensitiveContains(query)
                || tool.description.localizedCaseInsensitiveContains(query)
                || tool.capabilityGroup.localizedCaseInsensitiveContains(query)
            return groupMatches && searchMatches
        }
    }

    private func upsertChannelSetup(_ setup: ChannelSetup) {
        if let index = settings.channels.firstIndex(where: { $0.channelId == setup.channelId }) {
            settings.channels[index] = setup
        } else {
            settings.channels.append(setup)
        }
    }

    private func loadChannelSecrets(into setup: inout ChannelSetup) {
        if !setup.secretName.isEmpty {
            setup.secretValue = keychain.read(channelSecretAccount(channelID: setup.channelId, name: setup.secretName, primary: true))
        }
        var loaded: [String: String] = [:]
        for name in setup.secretNames {
            loaded[name] = keychain.read(channelSecretAccount(channelID: setup.channelId, name: name, primary: false))
        }
        setup.secretValues = loaded
    }

    private func writeChannelSecrets(_ setup: ChannelSetup) {
        if !setup.secretName.isEmpty {
            keychain.write(setup.secretValue, account: channelSecretAccount(channelID: setup.channelId, name: setup.secretName, primary: true))
        }
        for name in setup.secretNames {
            keychain.write(setup.secretValues[name, default: ""], account: channelSecretAccount(channelID: setup.channelId, name: name, primary: false))
        }
    }

    private func channelSecretAccount(channelID: String, name: String, primary: Bool) -> String {
        let cleanChannel = channelID.replacingOccurrences(of: " ", with: "_")
        let cleanName = name.replacingOccurrences(of: " ", with: "_")
        return primary ? "channel.\(cleanChannel).primary.\(cleanName)" : "channel.\(cleanChannel).secret.\(cleanName)"
    }

    private func applyDefaults(channel: ChannelInfo, setup: inout ChannelSetup) {
        let requiredSecrets = channel.setup?.stringArray("required_secrets") ?? []
        let optionalSecrets = channel.setup?.stringArray("optional_secrets") ?? []
        let allSecrets = Array(Set(requiredSecrets + optionalSecrets)).sorted()
        if setup.secretName.isEmpty, requiredSecrets.count == 1 {
            setup.secretName = requiredSecrets[0]
        }
        for secret in allSecrets where secret.localizedCaseInsensitiveCompare(setup.secretName) != .orderedSame {
            if !setup.secretNames.contains(where: { $0.localizedCaseInsensitiveCompare(secret) == .orderedSame }) {
                setup.secretNames.append(secret)
            }
        }
        if setup.conversationType.isEmpty {
            setup.conversationType = channel.conversationTypes.first ?? "dm"
        }
    }

    private func renderChannelRequirements(_ channel: ChannelInfo) {
        channelRequirementText = formatRequirementSummary(.object([
            "setup_kind": .string(channel.setupKind),
            "setup": channel.setup ?? .object([:]),
            "delivery": channel.delivery ?? .object([:]),
            "policies": channel.policies ?? .object([:]),
            "runtime": channel.runtime ?? .object([:])
        ]))
        channelSetupStepsText = formatSetupSteps(channel.setup)
        channelPolicyText = formatPolicySummary(policies: channel.policies, delivery: channel.delivery, runtime: channel.runtime)
    }
}

private extension AppViewModel {
    func formatRequirementSummary(_ requirements: JSONValue) -> String {
        let setup = requirements["setup"]
        let delivery = requirements["delivery"]
        let requiredSecrets = setup?.stringArray("required_secrets") ?? []
        let optionalSecrets = setup?.stringArray("optional_secrets") ?? []
        let requiredFields = setup?.stringArray("required_fields") ?? []
        let officialSend = delivery?["official_send"]
        let sendMode = officialSend?["mode"]?.stringValue ?? "prepared_outbox"
        let implemented = officialSend?["implemented"]?.boolValue == true ? "direct send available" : "prepared outbox only"
        return [
            "Setup: \(requirements["setup_kind"]?.stringValue ?? "channel")",
            "Required fields: \(formatInline(requiredFields))",
            "Required secrets: \(formatInline(requiredSecrets))",
            "Optional secrets: \(formatInline(optionalSecrets))",
            "Send mode: \(sendMode) (\(implemented))"
        ].joined(separator: "\n")
    }

    func formatSetupSteps(_ setup: JSONValue?) -> String {
        let steps = setup?.stringArray("steps") ?? []
        let notes = setup?.stringArray("notes") ?? []
        var lines = steps.enumerated().map { "\($0.offset + 1). \($0.element)" }
        if !notes.isEmpty {
            lines.append("")
            lines.append("Notes:")
            lines.append(contentsOf: notes.map { "- \($0)" })
        }
        return lines.isEmpty ? "No setup steps are published for this channel yet." : lines.joined(separator: "\n")
    }

    func formatPolicySummary(policies: JSONValue?, delivery: JSONValue?, runtime: JSONValue?) -> String {
        let officialSend = delivery?["official_send"]
        return [
            "DM policy: \(policies?["dm_policy"]?.stringValue ?? "not specified")",
            "Group policy: \(policies?["group_policy"]?.stringValue ?? "not specified")",
            "Mention required: \(yesNo(policies?["mention_required_by_default"]))",
            "Ambient room context: \(yesNo(policies?["ambient_room_events_supported"]))",
            "Bot-loop protection: \(yesNo(policies?["bot_loop_protection_supported"]))",
            "Native threads: \(yesNo(delivery?["native_threads"]))",
            "Approval reactions: \(yesNo(delivery?["approval_reactions"]))",
            "Listener required: \(yesNo(runtime?["listener_required_for_inbound"]))",
            "Runtime state: \(runtime?["state_dir_hint"]?.stringValue ?? "none")",
            "Official target: \(officialSend?["target"]?.stringValue ?? "conversation_id")"
        ].joined(separator: "\n")
    }

    func formatChannelStatus(_ status: JSONValue) -> String {
        guard let channel = status["channels"]?.arrayValue?.first else {
            return "Connection status unavailable."
        }
        let readyForSend = channel["ready_for_send"]?.boolValue == true
        let readyForInbound = channel["ready_for_inbound"]?.boolValue == true
        let listenEnabled = channel["listen_enabled"]?.boolValue == true
        let missing = channel["missing_send_env"]?.arrayValue?.compactMap(\.stringValue) ?? []
        if missing.isEmpty {
            return "Connection: replies \(readyForSend ? "ready" : "draft only"); incoming messages \(readyForInbound ? "ready" : listenEnabled ? "waiting" : "paused")."
        }
        return "Connection: missing \(missing.map(\.humanizedIdentifier).joined(separator: ", ")); incoming messages \(listenEnabled ? "waiting" : "paused"); drafts are available."
    }

    func formatChannelListenerStatus(_ status: JSONValue) -> String {
        guard let listener = status["listeners"]?.arrayValue?.first else {
            return "Incoming message status unavailable."
        }
        let ready = listener["ready"]?.boolValue == true
        let listenEnabled = listener["listen_enabled"]?.boolValue == true
        let mode = listener["listener_mode"]?.stringValue ?? "listener"
        let webhookPath = listener["webhook_path"]?.stringValue ?? ""
        let missing = listener["missing_env"]?.arrayValue?.compactMap(\.stringValue) ?? []
        if missing.isEmpty {
            return "Incoming messages: \(ready ? "ready" : listenEnabled ? "waiting" : "paused") via \(mode.humanizedIdentifier); webhook \(webhookPath)."
        }
        return "Incoming messages: missing \(missing.map(\.humanizedIdentifier).joined(separator: ", ")); \(listenEnabled ? "waiting" : "paused"); webhook \(webhookPath)."
    }

    func formatDoctorFindings(_ doctor: JSONValue) -> String {
        let findings = doctor["findings"]?.arrayValue ?? []
        guard !findings.isEmpty else {
            return "No doctor findings returned."
        }
        return findings.map { finding in
            "- \(finding["channel_id"]?.stringValue ?? "channel") [\(finding["severity"]?.stringValue ?? "info")]: \(finding["message"]?.stringValue ?? "")"
        }.joined(separator: "\n")
    }

    func formatChannelSmoke(_ smoke: JSONValue) -> String {
        guard let channel = smoke["channels"]?.arrayValue?.first else {
            return "No channel smoke result returned."
        }
        var lines = [
            "Trial: \((channel["readiness"]?.stringValue ?? "unknown").humanizedStatus)",
            "Prepared outbox: \(yesNo(channel["prepared_outbox_ready"])) (\(channel["prepared_message_id"]?.stringValue ?? "none"))",
            "Dry-run send: \(yesNo(channel["dry_run_send_ready"])) (\(channel["dry_run_message_id"]?.stringValue ?? "none"))",
            "Direct send: \(yesNo(channel["direct_send_ready"])) via \(channel["send_mode"]?.stringValue ?? "prepared")",
            "Incoming messages: \(yesNo(channel["listener_ready"])) via \((channel["listener_mode"]?.stringValue ?? "listener").humanizedIdentifier)"
        ]
        let blockers = channel["blockers"]?.arrayValue ?? []
        if !blockers.isEmpty {
            lines.append("Blockers:")
            lines.append(contentsOf: blockers.map { blocker in
                "- \(blocker["kind"]?.stringValue ?? "blocker"): \(blocker["detail"]?.compactDescription ?? "")"
            })
        }
        return lines.joined(separator: "\n")
    }

    func formatInline(_ values: [String]) -> String {
        values.isEmpty ? "none" : values.joined(separator: ", ")
    }

    func yesNo(_ value: JSONValue?) -> String {
        value?.boolValue == true ? "yes" : "no"
    }
}

private extension JSONValue {
    var numberText: String? {
        if case let .number(value) = self {
            return value == value.rounded() ? String(Int(value)) : value.formatted()
        }
        return nil
    }
}
