import SwiftUI

struct RootView: View {
    @EnvironmentObject private var model: AppViewModel

    var body: some View {
        ZStack {
            AppCanvasBackground()
                .ignoresSafeArea()

            NavigationSplitView {
                SidebarView()
                    .navigationSplitViewColumnWidth(min: 248, ideal: 284, max: 320)
            } detail: {
                MainContentView()
                    .navigationSplitViewColumnWidth(min: 660, ideal: 900)
            }
        }
        .background(WindowFullScreenConfigurator())
        .safeAreaInset(edge: .top) {
            if let notice = model.notice {
                HStack(spacing: 8) {
                    Image(systemName: "info.circle.fill")
                        .foregroundStyle(DS.accent)
                    Text(notice)
                        .font(.callout)
                    Spacer()
                    Button("Dismiss") {
                        model.notice = nil
                    }
                    .buttonStyle(.borderless)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(.thinMaterial)
                .overlay(Rectangle().fill(DS.line).frame(height: 1), alignment: .bottom)
            }
        }
    }
}

struct AppCanvasBackground: View {
    var body: some View {
        LinearGradient(
            colors: [
                Color(nsColor: .windowBackgroundColor),
                Color(nsColor: .controlBackgroundColor).opacity(0.72)
            ],
            startPoint: .top,
            endPoint: .bottom
        )
    }
}

struct StatusMenu: View {
    @EnvironmentObject private var model: AppViewModel

    var body: some View {
        Menu {
            Section("Connection") {
                Text("Status: \(model.status.rawValue.humanizedStatus)")
                Text("Server: \(model.settings.apiBaseURL)")
                Text("Project: \(model.health?.workspace ?? model.settings.workspacePath)")
            }
            Section("Runtime") {
                Text("Model: \(model.settings.modelName)")
                Text("Provider: \(model.settings.modelProvider)")
                Text("Capabilities: \(model.toolCatalog.toolCount)")
                Text("Activity: \(model.runs.count)")
                Text("Permissions: \(model.approvals.count)")
            }
            Divider()
            Button {
                Task { await model.refreshAll() }
            } label: {
                Label("Refresh Status", systemImage: "arrow.clockwise")
            }
            Button {
                model.selectedSection = .settings
            } label: {
                Label("Open Settings", systemImage: "gearshape")
            }
        } label: {
            HStack(spacing: 7) {
                Circle()
                    .fill(model.status.color)
                    .frame(width: 8, height: 8)
                Text(model.status.rawValue.capitalized)
                    .font(.callout.weight(.medium))
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 7)
            .background(.thinMaterial, in: Capsule())
            .overlay(Capsule().stroke(DS.line, lineWidth: 1))
        }
        .menuStyle(.borderlessButton)
        .help("Runtime status")
    }
}

struct WindowFullScreenConfigurator: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView {
        let view = NSView()
        DispatchQueue.main.async {
            configure(view.window)
        }
        return view
    }

    func updateNSView(_ nsView: NSView, context: Context) {
        DispatchQueue.main.async {
            configure(nsView.window)
        }
    }

    private func configure(_ window: NSWindow?) {
        guard let window else { return }
        window.collectionBehavior.insert(.fullScreenPrimary)
        window.styleMask.insert([.resizable, .fullSizeContentView])
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        window.toolbar = nil
        window.titlebarSeparatorStyle = .none
        window.backgroundColor = NSColor.windowBackgroundColor
        window.standardWindowButton(.zoomButton)?.isEnabled = true
    }
}

struct MainContentView: View {
    @EnvironmentObject private var model: AppViewModel

    var body: some View {
        Group {
            switch model.selectedSection {
            case .chat: ChatView()
            case .overview: OverviewView()
            case .workboard: WorkboardView()
            case .runs: RunsView()
            case .approvals: ApprovalsView()
            case .janus: JanusView()
            case .tools: ToolsView()
            case .connectors: ConnectorsView()
            case .channels: ChannelsView()
            case .voice: VoiceView()
            case .autonomy: AutonomyView()
            case .settings: SettingsView()
            }
        }
        .background(AppCanvasBackground())
    }
}
