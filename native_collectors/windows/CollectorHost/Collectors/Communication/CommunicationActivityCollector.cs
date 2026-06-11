using System.Diagnostics;
using Humungousaur.Collectors.Windows.Collectors.Window;
using Humungousaur.Collectors.Windows.Contracts;
using Humungousaur.Collectors.Windows.Win32;

namespace Humungousaur.Collectors.Windows.Collectors.Communication;

internal sealed class CommunicationActivityCollector
{
    private readonly Dictionary<int, string> _knownProcesses = SnapshotCommunicationProcesses();
    private readonly Dictionary<string, bool> _toggleState = new(StringComparer.OrdinalIgnoreCase);
    private string _lastForegroundSignature = "";

    public IEnumerable<NativeCollectorEvent> Diff()
    {
        var current = SnapshotCommunicationProcesses();
        foreach (var pair in current)
        {
            if (_knownProcesses.ContainsKey(pair.Key))
            {
                continue;
            }
            var profile = CommunicationAppProfile.FromProcessName(pair.Value);
            if (profile is null)
            {
                continue;
            }
            foreach (var collectorEvent in ProcessOpened(profile, pair.Key, pair.Value))
            {
                yield return collectorEvent;
            }
        }
        foreach (var pair in _knownProcesses.ToArray())
        {
            if (current.ContainsKey(pair.Key))
            {
                continue;
            }
            var profile = CommunicationAppProfile.FromProcessName(pair.Value);
            if (profile is null)
            {
                continue;
            }
            foreach (var collectorEvent in ProcessClosed(profile, pair.Key, pair.Value))
            {
                yield return collectorEvent;
            }
        }
        _knownProcesses.Clear();
        foreach (var pair in current)
        {
            _knownProcesses[pair.Key] = pair.Value;
        }
    }

    public IEnumerable<NativeCollectorEvent> ObserveForeground(WindowSnapshot snapshot)
    {
        var profile = CommunicationAppProfile.FromWindow(snapshot);
        if (profile is null)
        {
            yield break;
        }

        var signature = $"{profile.AppId}:{snapshot.ProcessId}:{snapshot.TitleHash}:{snapshot.TitleLength}";
        if (signature == _lastForegroundSignature)
        {
            yield break;
        }
        var previous = _lastForegroundSignature;
        _lastForegroundSignature = signature;

        var metadata = WindowMetadata(snapshot, profile, "windows_winevent_communication_foreground");
        metadata["previous_foreground_digest"] = string.IsNullOrWhiteSpace(previous) ? "" : StableDigest(previous);
        if (profile.IsMeetingApp)
        {
            yield return Sensitive(
                CollectorCatalog.MeetingAppActivity,
                "meeting_joined",
                "Meeting-capable app foreground observed; meeting title and participants are omitted.",
                metadata
            );
            yield return Sensitive(
                CollectorCatalog.MeetingAudio,
                "call_started",
                "Call-capable app foreground observed; transcript and speaker names are omitted.",
                metadata
            );
        }
        if (profile.IsChatApp)
        {
            yield return Metadata(
                CollectorCatalog.ChannelActivity,
                "channel_unread_changed",
                "Communication app foreground state changed; message bodies, channel names, and unread labels are omitted.",
                metadata
            );
            yield return Metadata(
                CollectorCatalog.CommunicationActivity,
                "channel_unread_changed",
                "Communication app foreground state changed; message bodies, channel names, and unread labels are omitted.",
                metadata
            );
            yield return Sensitive(
                CollectorCatalog.ChatChannelNavigationActivity,
                string.IsNullOrWhiteSpace(previous) ? "chat_workspace_switched" : "chat_channel_opened",
                "Chat workspace or channel surface focused; names and visible contents are omitted.",
                metadata
            );
            yield return Sensitive(
                CollectorCatalog.ChatThreadActivity,
                "thread_opened",
                "Chat thread-like surface focused; thread title, participants, and replies are omitted.",
                metadata
            );
        }
        if (profile.SupportsVoiceWakeup)
        {
            yield return Sensitive(
                CollectorCatalog.VoiceWakeup,
                "wake_word_detected",
                "Voice assistant surface focused; wake text and transcript are omitted.",
                metadata
            );
        }
    }

    public IEnumerable<NativeCollectorEvent> ObserveKeyDown(uint virtualKey)
    {
        var snapshot = WindowSnapshot.FromForeground();
        if (snapshot is null)
        {
            yield break;
        }
        var profile = CommunicationAppProfile.FromWindow(snapshot);
        if (profile is null)
        {
            yield break;
        }

        var ctrl = NativeMethods.IsKeyDown(NativeMethods.VkControl);
        var alt = NativeMethods.IsKeyDown(NativeMethods.VkMenu);
        var shift = NativeMethods.IsKeyDown(NativeMethods.VkShift);
        var win = NativeMethods.IsKeyDown(NativeMethods.VkLwin) || NativeMethods.IsKeyDown(NativeMethods.VkRwin);
        var metadata = WindowMetadata(snapshot, profile, "windows_keyboard_communication_shortcut");
        metadata["shortcut_dialect"] = profile.ShortcutDialect;
        metadata["modifier_ctrl"] = ctrl.ToString().ToLowerInvariant();
        metadata["modifier_alt"] = alt.ToString().ToLowerInvariant();
        metadata["modifier_shift"] = shift.ToString().ToLowerInvariant();
        metadata["modifier_win"] = win.ToString().ToLowerInvariant();
        metadata["raw_key_omitted"] = "true";

        foreach (var collectorEvent in ObserveMeetingShortcut(profile, virtualKey, ctrl, alt, shift, metadata))
        {
            yield return collectorEvent;
        }
        foreach (var collectorEvent in ObserveChatShortcut(profile, virtualKey, ctrl, alt, shift, metadata))
        {
            yield return collectorEvent;
        }
        if (profile.SupportsVoiceWakeup && ((win && virtualKey == (uint)NativeMethods.VkH) || (ctrl && shift && virtualKey == (uint)NativeMethods.VkV)))
        {
            yield return Sensitive(
                CollectorCatalog.VoiceWakeup,
                "wake_word_detected",
                "Voice shortcut observed; transcript and dictated text are omitted.",
                metadata
            );
        }
    }

    private IEnumerable<NativeCollectorEvent> ProcessOpened(CommunicationAppProfile profile, int processId, string processName)
    {
        var metadata = ProcessMetadata(profile, processId, processName, "windows_process_snapshot_communication");
        if (profile.IsMeetingApp)
        {
            yield return Sensitive(CollectorCatalog.MeetingAppActivity, "meeting_joined", "Meeting-capable app process opened; meeting title and participants are omitted.", metadata);
            yield return Sensitive(CollectorCatalog.MeetingAudio, "call_started", "Call-capable app process opened; transcript and speaker names are omitted.", metadata);
        }
        if (profile.IsChatApp)
        {
            yield return Metadata(CollectorCatalog.ChannelActivity, "channel_unread_changed", "Communication app process opened; message bodies and channel names are omitted.", metadata);
            yield return Metadata(CollectorCatalog.CommunicationActivity, "channel_unread_changed", "Communication app process opened; message bodies and channel names are omitted.", metadata);
            yield return Sensitive(CollectorCatalog.ChatPresenceActivity, "presence_changed", "Chat app availability changed; custom status text is omitted.", metadata);
        }
        if (profile.SupportsVoiceWakeup)
        {
            yield return Sensitive(CollectorCatalog.VoiceWakeup, "wake_word_detected", "Voice assistant process opened; wake text and transcript are omitted.", metadata);
        }
    }

    private IEnumerable<NativeCollectorEvent> ProcessClosed(CommunicationAppProfile profile, int processId, string processName)
    {
        var metadata = ProcessMetadata(profile, processId, processName, "windows_process_snapshot_communication");
        if (profile.IsMeetingApp)
        {
            yield return Sensitive(CollectorCatalog.MeetingAppActivity, "meeting_left", "Meeting-capable app process closed; meeting title and participants are omitted.", metadata);
            yield return Sensitive(CollectorCatalog.MeetingAudio, "call_ended", "Call-capable app process closed; transcript and speaker names are omitted.", metadata);
        }
        if (profile.IsChatApp)
        {
            yield return Sensitive(CollectorCatalog.ChatPresenceActivity, "presence_changed", "Chat app availability changed; custom status text is omitted.", metadata);
        }
    }

    private IEnumerable<NativeCollectorEvent> ObserveMeetingShortcut(
        CommunicationAppProfile profile,
        uint virtualKey,
        bool ctrl,
        bool alt,
        bool shift,
        Dictionary<string, string> metadata
    )
    {
        if (!profile.IsMeetingApp)
        {
            yield break;
        }

        if (IsMicrophoneShortcut(profile, virtualKey, ctrl, alt, shift))
        {
            yield return Toggle(CollectorCatalog.CallControlActivity, profile, "microphone", "microphone_muted", "microphone_unmuted", "Microphone control shortcut observed; audio and transcript are omitted.", metadata);
        }
        if (IsCameraShortcut(profile, virtualKey, ctrl, alt, shift))
        {
            yield return Toggle(CollectorCatalog.CallControlActivity, profile, "camera", "camera_enabled", "camera_disabled", "Camera control shortcut observed; video contents are omitted.", metadata);
        }
        if (IsShareShortcut(profile, virtualKey, ctrl, alt, shift))
        {
            yield return Toggle(CollectorCatalog.MeetingPresentationActivity, profile, "share", "screen_share_started", "screen_share_stopped", "Screen-share shortcut observed; shared window names and contents are omitted.", metadata);
        }
        if (IsCaptionShortcut(profile, virtualKey, ctrl, alt, shift))
        {
            yield return Toggle(CollectorCatalog.CallControlActivity, profile, "captions", "captions_enabled", "captions_disabled", "Captions shortcut observed; caption text is omitted.", metadata);
        }
        if (IsRaiseHandShortcut(profile, virtualKey, ctrl, alt, shift))
        {
            yield return Toggle(CollectorCatalog.CallControlActivity, profile, "hand", "hand_raised", "hand_lowered", "Raise-hand shortcut observed; participant names are omitted.", metadata);
        }
        if (IsMeetingChatShortcut(profile, virtualKey, ctrl, alt, shift))
        {
            yield return Sensitive(CollectorCatalog.CallControlActivity, "meeting_chat_opened", "Meeting chat surface opened; chat contents and participants are omitted.", metadata);
        }
        if (IsReactionShortcut(profile, virtualKey, ctrl, alt, shift))
        {
            yield return Sensitive(CollectorCatalog.CallControlActivity, "reaction_sent", "Meeting reaction shortcut observed; reaction content and participants are omitted.", metadata);
        }
        if (IsRecordingShortcut(profile, virtualKey, ctrl, alt, shift))
        {
            var recordingEvent = Toggle(CollectorCatalog.MeetingAppActivity, profile, "recording", "meeting_recording_started", "meeting_recording_stopped", "Meeting recording shortcut observed; recording contents are omitted.", metadata);
            yield return recordingEvent;
            if (recordingEvent.StimulusType == "meeting_recording_stopped")
            {
                yield return Sensitive(CollectorCatalog.MeetingArtifactActivity, "meeting_recording_available", "Meeting recording may be available; recording contents are omitted.", metadata);
            }
        }
    }

    private IEnumerable<NativeCollectorEvent> ObserveChatShortcut(
        CommunicationAppProfile profile,
        uint virtualKey,
        bool ctrl,
        bool alt,
        bool shift,
        Dictionary<string, string> metadata
    )
    {
        if (!profile.IsChatApp)
        {
            yield break;
        }

        if (ctrl && (virtualKey == (uint)NativeMethods.VkK || virtualKey == (uint)NativeMethods.VkF))
        {
            yield return Sensitive(CollectorCatalog.ChatChannelNavigationActivity, "chat_channel_search_performed", "Chat search/navigation shortcut observed; query and channel names are omitted.", metadata);
        }
        if (ctrl && virtualKey == (uint)NativeMethods.VkN)
        {
            yield return Sensitive(CollectorCatalog.ChatCompositionActivity, "chat_draft_started", "Chat compose shortcut observed; message body and recipients are omitted.", metadata);
            yield return Metadata(CollectorCatalog.ChannelActivity, "draft_created", "Chat draft started; message body and recipients are omitted.", metadata);
            yield return Metadata(CollectorCatalog.CommunicationActivity, "draft_created", "Chat draft started; message body and recipients are omitted.", metadata);
        }
        if (ctrl && virtualKey == (uint)NativeMethods.VkEnter)
        {
            yield return Sensitive(CollectorCatalog.ChatCompositionActivity, "chat_message_sent", "Chat send shortcut observed; message body and recipients are omitted.", metadata);
            yield return Metadata(CollectorCatalog.ChannelActivity, "message_sent", "Chat message sent; body and recipients are omitted.", metadata);
            yield return Metadata(CollectorCatalog.CommunicationActivity, "message_sent", "Chat message sent; body and recipients are omitted.", metadata);
        }
        if (virtualKey == (uint)NativeMethods.VkOem2)
        {
            yield return Sensitive(CollectorCatalog.ChatCompositionActivity, "slash_command_used", "Slash command surface observed; command payload is omitted.", metadata);
        }
        if (ctrl && shift && virtualKey == (uint)NativeMethods.VkE)
        {
            yield return Sensitive(CollectorCatalog.ChatCompositionActivity, "emoji_picker_opened", "Emoji picker opened; selected emoji and message body are omitted.", metadata);
        }
        if (ctrl && shift && virtualKey == (uint)NativeMethods.VkT)
        {
            yield return Sensitive(CollectorCatalog.ChatThreadActivity, "thread_opened", "Thread navigation shortcut observed; thread title and replies are omitted.", metadata);
        }
        if (ctrl && shift && virtualKey == (uint)NativeMethods.VkD)
        {
            yield return Sensitive(CollectorCatalog.ChatPresenceActivity, "do_not_disturb_enabled", "Do-not-disturb shortcut observed; custom status text is omitted.", metadata);
        }
        if (alt && (virtualKey == (uint)NativeMethods.VkUp || virtualKey == (uint)NativeMethods.VkDown))
        {
            yield return Sensitive(CollectorCatalog.ChatChannelNavigationActivity, "chat_channel_opened", "Channel navigation shortcut observed; channel names and contents are omitted.", metadata);
        }
    }

    private NativeCollectorEvent Toggle(
        string collector,
        CommunicationAppProfile profile,
        string key,
        string enabledStimulus,
        string disabledStimulus,
        string text,
        Dictionary<string, string> metadata
    )
    {
        var toggleKey = $"{profile.AppId}:{key}";
        var enabled = !_toggleState.TryGetValue(toggleKey, out var previous) || !previous;
        _toggleState[toggleKey] = enabled;
        var payload = new Dictionary<string, string>(metadata)
        {
            ["control_toggle_state_inferred"] = enabled ? "enabled" : "disabled",
            ["control_state_source"] = "shortcut_toggle_inference",
        };
        return Sensitive(collector, enabled ? enabledStimulus : disabledStimulus, text, payload);
    }

    private static bool IsMicrophoneShortcut(CommunicationAppProfile profile, uint key, bool ctrl, bool alt, bool shift) =>
        profile.ShortcutDialect switch
        {
            "zoom" => alt && key == (uint)NativeMethods.VkA,
            "teams" => ctrl && shift && key == (uint)NativeMethods.VkM,
            "discord" => ctrl && shift && key == (uint)NativeMethods.VkM,
            _ => ctrl && shift && key == (uint)NativeMethods.VkM,
        };

    private static bool IsCameraShortcut(CommunicationAppProfile profile, uint key, bool ctrl, bool alt, bool shift) =>
        profile.ShortcutDialect switch
        {
            "zoom" => alt && key == (uint)NativeMethods.VkV,
            "teams" => ctrl && shift && key == (uint)NativeMethods.VkO,
            _ => ctrl && shift && key == (uint)NativeMethods.VkV,
        };

    private static bool IsShareShortcut(CommunicationAppProfile profile, uint key, bool ctrl, bool alt, bool shift) =>
        profile.ShortcutDialect switch
        {
            "zoom" => alt && shift && key == (uint)NativeMethods.VkS || alt && key == (uint)NativeMethods.VkS,
            "teams" => ctrl && shift && key == (uint)NativeMethods.VkE,
            _ => ctrl && shift && key == (uint)NativeMethods.VkS,
        };

    private static bool IsCaptionShortcut(CommunicationAppProfile profile, uint key, bool ctrl, bool alt, bool shift) =>
        profile.ShortcutDialect switch
        {
            "zoom" => alt && key == (uint)NativeMethods.VkC,
            "teams" => ctrl && shift && key == (uint)NativeMethods.VkL,
            _ => ctrl && shift && key == (uint)NativeMethods.VkC,
        };

    private static bool IsRaiseHandShortcut(CommunicationAppProfile profile, uint key, bool ctrl, bool alt, bool shift) =>
        profile.ShortcutDialect switch
        {
            "zoom" => alt && key == (uint)NativeMethods.VkY,
            "teams" => ctrl && shift && key == (uint)NativeMethods.VkK,
            _ => ctrl && shift && key == (uint)NativeMethods.VkH,
        };

    private static bool IsMeetingChatShortcut(CommunicationAppProfile profile, uint key, bool ctrl, bool alt, bool shift) =>
        profile.ShortcutDialect switch
        {
            "zoom" => alt && key == (uint)NativeMethods.VkH,
            "teams" => ctrl && shift && key == (uint)NativeMethods.VkH,
            _ => ctrl && shift && key == (uint)NativeMethods.VkH,
        };

    private static bool IsReactionShortcut(CommunicationAppProfile profile, uint key, bool ctrl, bool alt, bool shift) =>
        profile.ShortcutDialect switch
        {
            "zoom" => alt && shift && key == (uint)NativeMethods.VkR,
            "teams" => ctrl && shift && key == (uint)NativeMethods.VkR,
            _ => ctrl && shift && key == (uint)NativeMethods.VkR,
        };

    private static bool IsRecordingShortcut(CommunicationAppProfile profile, uint key, bool ctrl, bool alt, bool shift) =>
        profile.ShortcutDialect switch
        {
            "zoom" => alt && key == (uint)NativeMethods.VkR,
            "teams" => ctrl && shift && key == (uint)NativeMethods.VkR,
            _ => ctrl && shift && key == (uint)NativeMethods.VkR,
        };

    private static Dictionary<int, string> SnapshotCommunicationProcesses()
    {
        try
        {
            return Process.GetProcesses()
                .Select(process => (process.Id, Name: SafeProcessName(process)))
                .Where(pair => !string.IsNullOrWhiteSpace(pair.Name) && CommunicationAppProfile.IsKnownProcess(pair.Name))
                .ToDictionary(pair => pair.Id, pair => pair.Name);
        }
        catch
        {
            return new Dictionary<int, string>();
        }
    }

    private static string SafeProcessName(Process process)
    {
        try
        {
            return process.ProcessName;
        }
        catch
        {
            return "";
        }
    }

    private static Dictionary<string, string> WindowMetadata(WindowSnapshot snapshot, CommunicationAppProfile profile, string source)
    {
        var metadata = ProcessMetadata(profile, snapshot.ProcessId, snapshot.ProcessName, source);
        metadata["window_handle"] = WindowSnapshot.HandleString(snapshot.Handle);
        metadata["window_class"] = snapshot.ClassName;
        metadata["window_title_omitted"] = "true";
        metadata["window_title_length"] = snapshot.TitleLength.ToStringInvariant();
        metadata["window_title_hash"] = snapshot.TitleHash;
        metadata["message_body_omitted"] = "true";
        metadata["meeting_title_omitted"] = "true";
        metadata["participant_names_omitted"] = "true";
        metadata["channel_name_omitted"] = "true";
        metadata["thread_title_omitted"] = "true";
        metadata["transcript_omitted"] = "true";
        metadata["visible_contents_omitted"] = "true";
        return metadata;
    }

    private static Dictionary<string, string> ProcessMetadata(CommunicationAppProfile profile, int processId, string processName, string source) => new()
    {
        ["native_source"] = source,
        ["platform"] = "windows",
        ["app_name"] = profile.DisplayName,
        ["app_id"] = profile.AppId,
        ["app_category"] = profile.Category,
        ["process_name"] = processName,
        ["process_id"] = processId.ToStringInvariant(),
        ["message_body_omitted"] = "true",
        ["meeting_title_omitted"] = "true",
        ["participant_names_omitted"] = "true",
        ["channel_name_omitted"] = "true",
        ["transcript_omitted"] = "true",
        ["attachment_names_omitted"] = "true",
        ["custom_status_text_omitted"] = "true",
    };

    private static NativeCollectorEvent Metadata(string collector, string stimulusType, string text, Dictionary<string, string> metadata) =>
        new(collector, "channel_message", stimulusType, text, metadata);

    private static NativeCollectorEvent Sensitive(string collector, string stimulusType, string text, Dictionary<string, string> metadata)
    {
        var copy = new Dictionary<string, string>(metadata)
        {
            ["privacy_level"] = "redacted",
        };
        var source = collector == CollectorCatalog.MeetingAudio
            ? "audio_transcript"
            : collector == CollectorCatalog.VoiceWakeup
                ? "voice_transcript"
                : collector.StartsWith("chat_", StringComparison.Ordinal)
                    ? "channel_message"
                    : "activity";
        return new NativeCollectorEvent(collector, source, stimulusType, text, copy, PrivacyTier: "sensitive_metadata");
    }

    private static string StableDigest(string value)
    {
        var bytes = System.Security.Cryptography.SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(bytes).ToLowerInvariant()[..16];
    }
}
