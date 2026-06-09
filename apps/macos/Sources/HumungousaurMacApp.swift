import SwiftUI

@main
struct HumungousaurMacApp: App {
    @StateObject private var model = AppViewModel()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(model)
                .frame(minWidth: 1180, minHeight: 760)
                .task {
                    await model.bootstrap()
                }
        }
        .windowStyle(.hiddenTitleBar)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("New Session") {
                    model.startNewSession()
                }
                .keyboardShortcut("n", modifiers: [.command])
            }
            CommandMenu("Agent") {
                Button("Refresh Status") {
                    Task { await model.refreshAll() }
                }
                .keyboardShortcut("r", modifiers: [.command])

                Button(model.agentProcess.isRunning ? "Stop Local Agent" : "Start Local Agent") {
                    Task { await model.toggleAgentProcess() }
                }
                .keyboardShortcut("l", modifiers: [.command, .shift])
            }
        }
    }
}
