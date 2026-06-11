import Foundation
import AppKit
import SwiftUI

struct ConnectorsView: View {
    @EnvironmentObject private var model: AppViewModel

    var body: some View {
        HStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 12) {
                SectionHeader(eyebrow: "Workspace", title: "App Connectors", subtitle: "Connect workspace accounts once, then let native tools use the granted APIs.")
                if model.connectorCatalog.providers.isEmpty {
                    EmptyStateView(symbol: "link.badge.plus", title: "No connectors", message: "Start or refresh the local agent to load workspace connector providers.")
                } else {
                    List(model.connectorCatalog.providers, selection: $model.selectedConnectorID) { connector in
                        ConnectorListRow(connector: connector)
                            .tag(connector.providerId)
                    }
                    .listStyle(.inset)
                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                }
            }
            .padding(24)
            .frame(minWidth: 330, maxWidth: 410)

            Divider()

            if let connector = model.selectedConnector {
                ConnectorDetailView(connector: connector)
                    .id(connector.providerId)
            } else {
                EmptyStateView(symbol: "link.badge.plus", title: "Select a connector", message: "Setup, status, and launch controls appear here.")
                    .padding(28)
            }
        }
        .task(id: model.selectedConnectorID) {
            model.renderConnectorStatus()
        }
    }
}

struct ConnectorListRow: View {
    let connector: ConnectorProvider

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                ConnectorBrandBadge(connector: connector, size: 34)
                VStack(alignment: .leading) {
                    Text(connector.displayName)
                        .font(.headline)
                    Text(connector.category.humanizedIdentifier)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
            }
            Text(connector.statusText)
                .font(.caption.weight(.semibold))
                .foregroundStyle(connector.connected ? .green : connector.configured ? .orange : .secondary)
            Text(connector.authModeText)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(connector.workspaceApps.prefix(4).joined(separator: ", "))
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(2)
        }
        .padding(.vertical, 5)
    }
}

struct ConnectorDetailView: View {
    @EnvironmentObject private var model: AppViewModel
    let connector: ConnectorProvider
    @State private var clientID = ""
    @State private var clientSecret = ""

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                header
                statusGrid
                setupPanel
                actionsPanel
                toolPanel
                sourcePanel
            }
            .padding(28)
        }
        .onAppear {
            if clientID.isEmpty, connector.clientId != "" {
                clientID = connector.clientId
            }
        }
    }

    private var header: some View {
        HStack(alignment: .top, spacing: 12) {
            ConnectorBrandBadge(connector: connector, size: 42)
            VStack(alignment: .leading, spacing: 5) {
                Text(connector.displayName)
                    .font(.largeTitle.weight(.semibold))
                Text("\(connector.category.humanizedIdentifier) / \(connector.authModeText) / \(connector.statusText)")
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Button {
                Task { await model.refreshConnectors() }
            } label: {
                Label("Refresh", systemImage: "arrow.clockwise")
            }
        }
    }

    private var statusGrid: some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            ConnectorTextPanel(title: "Connection", text: model.connectorStatusText)
            ConnectorTextPanel(title: "Redirect URI", text: model.connectorCatalog.redirectUri)
        }
    }

    private var setupPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(connector.setupTitle)
                .font(.headline)
            Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 10) {
                GridRow {
                    TextField(connector.primaryCredentialLabel, text: $clientID)
                    SecureField(connector.secondaryCredentialLabel, text: $clientSecret)
                }
            }
            HStack {
                Button {
                    Task {
                        await model.configureConnector(connector, clientID: clientID, clientSecret: clientSecret)
                    }
                } label: {
                    Label(connector.saveButtonTitle, systemImage: "key")
                }
                if let docsURL = URL(string: connector.docsUrl), !connector.docsUrl.isEmpty {
                    Button {
                        NSWorkspace.shared.open(docsURL)
                    } label: {
                        Label("Docs", systemImage: "book")
                    }
                }
                Spacer()
            }
            Text(connector.setupCaption)
                .font(.caption)
                .foregroundStyle(.secondary)
                .textSelection(.enabled)
        }
        .glassPanel()
    }

    private var actionsPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Connection")
                .font(.headline)
            HStack {
                Button {
                    Task { await model.connectConnector(connector) }
                } label: {
                    Label(connector.connectionButtonTitle, systemImage: connector.connectionButtonSymbol)
                }

                Button {
                    Task { await model.refreshConnectorToken(connector) }
                } label: {
                    Label("Refresh Token", systemImage: "arrow.clockwise")
                }
                .disabled(!connector.hasRefreshToken || !connector.usesOAuth)

                Button(role: .destructive) {
                    Task { await model.disconnectConnector(connector) }
                } label: {
                    Label("Disconnect", systemImage: "xmark.circle")
                }
                .disabled(!connector.connected)

                Spacer()
            }
        }
        .glassPanel()
    }

    private var toolPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Native Tool Mapping")
                .font(.headline)
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                ForEach(connector.toolHints, id: \.self) { tool in
                    HStack {
                        Image(systemName: "wrench.and.screwdriver")
                            .foregroundStyle(DS.accent)
                        Text(tool.humanizedIdentifier)
                            .font(.callout)
                        Spacer()
                    }
                    .padding(10)
                    .background(Color.primary.opacity(0.035), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                }
            }
        }
        .glassPanel()
    }

    private var sourcePanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Collector Source Mapping")
                .font(.headline)
            Text(connector.collectorSourceText)
                .font(.callout)
                .foregroundStyle(.secondary)
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .glassPanel()
    }
}

struct ConnectorBrandBadge: View {
    let connector: ConnectorProvider
    let size: CGFloat

    var body: some View {
        let logo = connectorLogoImage(connector.logoAsset)
        ZStack(alignment: .bottomTrailing) {
            RoundedRectangle(cornerRadius: max(8, size * 0.24), style: .continuous)
                .fill(logo == nil ? Color(hex: connector.brandColor).opacity(0.94) : Color.white)
                .overlay {
                    if logo != nil {
                        RoundedRectangle(cornerRadius: max(8, size * 0.24), style: .continuous)
                            .stroke(Color.primary.opacity(0.12), lineWidth: 1)
                    }
                }
            if let logo {
                Image(nsImage: logo)
                    .resizable()
                    .scaledToFit()
                    .padding(size * 0.2)
                    .frame(width: size, height: size)
            } else {
                Image(systemName: connector.icon.isEmpty ? "link.badge.plus" : connector.icon)
                    .font(.system(size: max(14, size * 0.46), weight: .semibold))
                    .foregroundStyle(.white)
            }
            if connector.connected {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: max(10, size * 0.32), weight: .semibold))
                    .foregroundStyle(.white, .green)
                    .background(Circle().fill(Color.white.opacity(0.9)))
                    .offset(x: 3, y: 3)
            }
        }
        .frame(width: size, height: size)
    }
}

private func connectorLogoImage(_ asset: String) -> NSImage? {
    guard !asset.contains("/") else { return nil }
    let stem = URL(fileURLWithPath: asset).deletingPathExtension().lastPathComponent
    let ext = URL(fileURLWithPath: asset).pathExtension
    guard !stem.isEmpty, !ext.isEmpty else { return nil }
    guard let url = Bundle.module.url(forResource: stem, withExtension: ext) else {
        return nil
    }
    return NSImage(contentsOf: url)
}

struct ConnectorTextPanel: View {
    let title: String
    let text: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.headline)
            ScrollView {
                Text(text.isEmpty ? "-" : text)
                    .font(.system(.callout, design: .monospaced))
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
            }
            .frame(minHeight: 92)
        }
        .glassPanel()
    }
}

private extension Color {
    init(hex: String) {
        let clean = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var value: UInt64 = 0
        Scanner(string: clean).scanHexInt64(&value)
        let red: Double
        let green: Double
        let blue: Double
        switch clean.count {
        case 6:
            red = Double((value >> 16) & 0xFF) / 255
            green = Double((value >> 8) & 0xFF) / 255
            blue = Double(value & 0xFF) / 255
        default:
            red = 0.39
            green = 0.45
            blue = 0.55
        }
        self.init(red: red, green: green, blue: blue)
    }
}
