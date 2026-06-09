import SwiftUI

enum AppSection: String, CaseIterable, Identifiable {
    case chat
    case overview
    case workboard
    case runs
    case approvals
    case tools
    case channels
    case voice
    case autonomy
    case settings

    var id: String { rawValue }

    var title: String {
        switch self {
        case .chat: "Chat"
        case .overview: "Overview"
        case .workboard: "Workboard"
        case .runs: "Runs"
        case .approvals: "Permissions"
        case .tools: "Capabilities"
        case .channels: "Channels"
        case .voice: "Voice"
        case .autonomy: "Autonomy"
        case .settings: "Settings"
        }
    }

    var symbol: String {
        switch self {
        case .chat: "bubble.left.and.text.bubble.right"
        case .overview: "chart.bar.xaxis"
        case .workboard: "rectangle.3.group"
        case .runs: "clock.arrow.circlepath"
        case .approvals: "checkmark.seal"
        case .tools: "wrench.and.screwdriver"
        case .channels: "point.3.connected.trianglepath.dotted"
        case .voice: "waveform"
        case .autonomy: "sparkles"
        case .settings: "gearshape"
        }
    }
}

enum DS {
    static let accent = Color(red: 0.78, green: 0.18, blue: 0.16)
    static let accentSoft = Color(red: 1.0, green: 0.91, blue: 0.90)
    static let canvas = Color(nsColor: .windowBackgroundColor)
    static let sidebar = Color(nsColor: .underPageBackgroundColor)
    static let panel = Color(nsColor: .controlBackgroundColor)
    static let line = Color.primary.opacity(0.07)
    static let secondaryText = Color.secondary.opacity(0.86)
    static let radius: CGFloat = 8
}

struct GlassPanel: ViewModifier {
    var radius: CGFloat = DS.radius
    var padding: CGFloat = 16

    func body(content: Content) -> some View {
        content
            .padding(padding)
            .background(Color.primary.opacity(0.025), in: RoundedRectangle(cornerRadius: radius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .stroke(DS.line, lineWidth: 1)
            )
    }
}

extension View {
    func glassPanel(radius: CGFloat = DS.radius, padding: CGFloat = 16) -> some View {
        modifier(GlassPanel(radius: radius, padding: padding))
    }
}

struct StatusPill: View {
    let title: String
    let status: AgentStatus

    var body: some View {
        Label {
            Text(title)
                .font(.callout.weight(.medium))
        } icon: {
            Circle()
                .fill(status.color)
                .frame(width: 8, height: 8)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(.thinMaterial, in: Capsule())
        .overlay(Capsule().stroke(DS.line, lineWidth: 1))
    }
}

struct OnlineIndicator: View {
    let status: AgentStatus

    var body: some View {
        HStack(spacing: 7) {
            Circle()
                .fill(status.color)
                .frame(width: 8, height: 8)
            Text(status.rawValue.capitalized)
                .font(.callout.weight(.medium))
        }
        .foregroundStyle(.primary)
    }
}

enum AgentStatus: String {
    case online
    case offline
    case starting
    case degraded

    var color: Color {
        switch self {
        case .online: .green
        case .offline: .red
        case .starting: .orange
        case .degraded: .yellow
        }
    }
}
