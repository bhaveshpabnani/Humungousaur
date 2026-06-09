import AppKit
import SwiftUI

@main
struct HumungousaurMacApp: App {
    @Environment(\.openWindow) private var openWindow
    @StateObject private var model = AppViewModel()

    init() {
        HumungousaurStatusBarController.shared.install()
    }

    var body: some Scene {
        WindowGroup("Humungousaur", id: "main") {
            RootView()
                .environmentObject(model)
                .frame(minWidth: 1180, minHeight: 760)
                .background(WindowIdentityView(identifier: "humungousaur-main"))
                .onAppear {
                    configureStatusBarActions()
                }
                .onChange(of: model.agentProcess.isRunning) { _, isRunning in
                    HumungousaurStatusBarController.shared.setAgentRunning(isRunning)
                }
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

    private func configureStatusBarActions() {
        let controller = HumungousaurStatusBarController.shared
        controller.openAction = {
            openMainWindow()
        }
        controller.refreshAction = {
            Task { await model.refreshAll() }
        }
        controller.toggleAgentAction = {
            Task { await model.toggleAgentProcess() }
        }
        controller.setAgentRunning(model.agentProcess.isRunning)
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

@MainActor
private final class HumungousaurStatusBarController: NSObject {
    static let shared = HumungousaurStatusBarController()

    var openAction: (() -> Void)?
    var refreshAction: (() -> Void)?
    var toggleAgentAction: (() -> Void)?

    private var statusItem: NSStatusItem?
    private let toggleAgentItem = NSMenuItem(title: "Start Local Agent", action: #selector(toggleAgent), keyEquivalent: "")

    func install() {
        guard statusItem == nil else { return }

        let item = NSStatusBar.system.statusItem(withLength: 28)
        statusItem = item

        if let button = item.button {
            button.toolTip = "Humungousaur"
            button.image = Self.statusImage()
            button.imagePosition = .imageOnly
            if button.image == nil {
                button.title = "H"
            }
        }

        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Open Humungousaur", action: #selector(openHumungousaur), keyEquivalent: "o"))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "Refresh Status", action: #selector(refreshStatus), keyEquivalent: "r"))
        menu.addItem(toggleAgentItem)
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "Quit Humungousaur", action: #selector(quitHumungousaur), keyEquivalent: "q"))

        for item in menu.items {
            item.target = self
        }
        item.menu = menu
    }

    func setAgentRunning(_ isRunning: Bool) {
        toggleAgentItem.title = isRunning ? "Stop Local Agent" : "Start Local Agent"
    }

    @objc private func openHumungousaur() {
        openAction?()
    }

    @objc private func refreshStatus() {
        refreshAction?()
    }

    @objc private func toggleAgent() {
        toggleAgentAction?()
    }

    @objc private func quitHumungousaur() {
        NSApp.terminate(nil)
    }

    private static func statusImage() -> NSImage? {
        guard let url = Bundle.module.url(forResource: "humungousaur-logo-mark-32", withExtension: "png"),
              let image = NSImage(contentsOf: url) else {
            return nil
        }

        image.size = NSSize(width: 18, height: 18)
        image.isTemplate = true
        return image
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
