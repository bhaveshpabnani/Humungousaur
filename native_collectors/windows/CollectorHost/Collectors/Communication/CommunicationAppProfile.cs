using Humungousaur.Collectors.Windows.Collectors.Browser;
using Humungousaur.Collectors.Windows.Collectors.Window;

namespace Humungousaur.Collectors.Windows.Collectors.Communication;

internal sealed record CommunicationAppProfile(
    string AppId,
    string DisplayName,
    string Category,
    bool SupportsMeetings,
    bool SupportsChannels,
    bool SupportsVoiceWakeup,
    string ShortcutDialect
)
{
    public bool IsMeetingApp => SupportsMeetings;
    public bool IsChatApp => SupportsChannels;

    public static CommunicationAppProfile? FromWindow(WindowSnapshot snapshot)
    {
        var process = SafeProcessName(snapshot.ProcessName);
        if (ProfilesByProcess.TryGetValue(process, out var profile))
        {
            return profile;
        }
        if (BrowserMetadata.IsBrowserProcess(process))
        {
            return new CommunicationAppProfile(
                BrowserMetadata.BrowserKind(process),
                $"{BrowserMetadata.BrowserKind(process)} browser collaboration surface",
                "browser_collaboration",
                SupportsMeetings: true,
                SupportsChannels: true,
                SupportsVoiceWakeup: false,
                ShortcutDialect: "browser"
            );
        }
        return null;
    }

    public static CommunicationAppProfile? FromProcessName(string processName)
    {
        var process = SafeProcessName(processName);
        return ProfilesByProcess.TryGetValue(process, out var profile) ? profile : null;
    }

    public static bool IsKnownProcess(string processName) => FromProcessName(processName) is not null;

    private static string SafeProcessName(string processName)
    {
        var name = (processName ?? "").Trim();
        return name.EndsWith(".exe", StringComparison.OrdinalIgnoreCase) ? Path.GetFileNameWithoutExtension(name) : name;
    }

    private static readonly Dictionary<string, CommunicationAppProfile> ProfilesByProcess = new(StringComparer.OrdinalIgnoreCase)
    {
        ["Teams"] = new("teams", "Microsoft Teams", "team_chat_meeting", true, true, false, "teams"),
        ["ms-teams"] = new("teams", "Microsoft Teams", "team_chat_meeting", true, true, false, "teams"),
        ["msteams"] = new("teams", "Microsoft Teams", "team_chat_meeting", true, true, false, "teams"),
        ["Zoom"] = new("zoom", "Zoom", "meeting", true, false, false, "zoom"),
        ["ZoomMeetings"] = new("zoom", "Zoom", "meeting", true, false, false, "zoom"),
        ["CptHost"] = new("zoom_share", "Zoom sharing host", "meeting", true, false, false, "zoom"),
        ["slack"] = new("slack", "Slack", "team_chat", false, true, false, "slack"),
        ["Slack"] = new("slack", "Slack", "team_chat", false, true, false, "slack"),
        ["Discord"] = new("discord", "Discord", "voice_chat", true, true, false, "discord"),
        ["WhatsApp"] = new("whatsapp", "WhatsApp", "direct_chat_call", true, true, false, "whatsapp"),
        ["Telegram"] = new("telegram", "Telegram", "direct_chat_call", true, true, false, "telegram"),
        ["Signal"] = new("signal", "Signal", "direct_chat_call", true, true, false, "signal"),
        ["OUTLOOK"] = new("outlook", "Microsoft Outlook", "mail_calendar_chat", true, true, false, "outlook"),
        ["olk"] = new("outlook", "Microsoft Outlook", "mail_calendar_chat", true, true, false, "outlook"),
        ["Skype"] = new("skype", "Skype", "direct_chat_call", true, true, false, "skype"),
        ["Webex"] = new("webex", "Cisco Webex", "meeting", true, true, false, "webex"),
        ["ptoneclk"] = new("webex", "Cisco Webex", "meeting", true, true, false, "webex"),
        ["RingCentral"] = new("ringcentral", "RingCentral", "meeting_chat", true, true, false, "ringcentral"),
        ["Humungousaur.App"] = new("humungousaur", "Humungousaur", "voice_assistant", false, false, true, "humungousaur"),
        ["Humungousaur"] = new("humungousaur", "Humungousaur", "voice_assistant", false, false, true, "humungousaur"),
        ["VoiceAccess"] = new("windows_voice_access", "Windows Voice Access", "voice_assistant", false, false, true, "windows_voice"),
    };
}
