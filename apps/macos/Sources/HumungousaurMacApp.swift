import AppKit
import SwiftUI

@main
struct HumungousaurMacApp: App {
    @Environment(\.openWindow) private var openWindow
    @StateObject private var model = AppViewModel()

    var body: some Scene {
        WindowGroup("Humungousaur", id: "main") {
            RootView()
                .environmentObject(model)
                .frame(minWidth: 1180, minHeight: 760)
                .background(WindowIdentityView(identifier: "humungousaur-main"))
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

        MenuBarExtra {
            Button("Open Humungousaur") {
                openMainWindow()
            }
            .keyboardShortcut("o")

            Divider()

            Button("Refresh Status") {
                Task { await model.refreshAll() }
            }
            .keyboardShortcut("r")

            Button(model.agentProcess.isRunning ? "Stop Local Agent" : "Start Local Agent") {
                Task { await model.toggleAgentProcess() }
            }

            Divider()

            Button("Quit Humungousaur") {
                NSApp.terminate(nil)
            }
            .keyboardShortcut("q")
        } label: {
            Image("humungousaur-logo-mark-32", bundle: .module)
                .renderingMode(.template)
        }
        .menuBarExtraStyle(.menu)
    }

    private func openMainWindow() {
        if !Self.focusMainWindow() {
            openWindow(id: "main")
            DispatchQueue.main.async {
                _ = Self.focusMainWindow()
            }
        }
        NSApp.activate(ignoringOtherApps: true)
    }

    @discardableResult
    private static func focusMainWindow() -> Bool {
        guard let window = NSApp.windows.first(where: { window in
            window.identifier?.rawValue == "humungousaur-main"
        }) else {
            return false
        }

        if window.isMiniaturized {
            window.deminiaturize(nil)
        }

        window.makeKeyAndOrderFront(nil)
        return true
    }
}

private struct WindowIdentityView: NSViewRepresentable {
    let identifier: String

    func makeNSView(context: Context) -> NSView {
        let view = NSView(frame: .zero)
        applyIdentity(to: view)
        return view
    }

    func updateNSView(_ nsView: NSView, context: Context) {
        applyIdentity(to: nsView)
    }

    private func applyIdentity(to view: NSView) {
        DispatchQueue.main.async {
            view.window?.identifier = NSUserInterfaceItemIdentifier(identifier)
            view.window?.title = "Humungousaur"
        }
    }
}
