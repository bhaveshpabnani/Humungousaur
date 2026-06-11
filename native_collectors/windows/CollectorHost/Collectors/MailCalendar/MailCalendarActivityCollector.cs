using System.Collections.Concurrent;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using Humungousaur.Collectors.Windows.Collectors.Window;
using Humungousaur.Collectors.Windows.Contracts;
using Humungousaur.Collectors.Windows.Core;
using Humungousaur.Collectors.Windows.Win32;

namespace Humungousaur.Collectors.Windows.Collectors.MailCalendar;

internal sealed class MailCalendarActivityCollector : IDisposable
{
    private readonly List<FileSystemWatcher> _watchers = [];
    private readonly Action<NativeCollectorEvent> _emit;
    private readonly ConcurrentDictionary<string, DateTimeOffset> _lastEmitted = new();
    private Dictionary<int, ProcessSnapshot> _processes = SnapshotProcesses();
    private string _lastForegroundSignature = "";

    public MailCalendarActivityCollector(CollectorHostOptions options, Action<NativeCollectorEvent> emit)
    {
        _emit = emit;
        foreach (var root in ResolveWatchRoots(options.WatchPaths))
        {
            AddWatcher(root);
        }
    }

    public void Dispose()
    {
        foreach (var watcher in _watchers)
        {
            watcher.Dispose();
        }
        _watchers.Clear();
    }

    public IEnumerable<NativeCollectorEvent> Diff()
    {
        var current = SnapshotProcesses();
        foreach (var pair in current)
        {
            if (_processes.ContainsKey(pair.Key))
            {
                continue;
            }
            var profile = MailCalendarAppProfile.FromProcessName(pair.Value.Name);
            if (profile is null)
            {
                continue;
            }
            foreach (var collectorEvent in ProcessStarted(profile, pair.Value))
            {
                yield return collectorEvent;
            }
        }

        _processes = current;
    }

    public IEnumerable<NativeCollectorEvent> ObserveForeground(WindowSnapshot snapshot)
    {
        var profile = MailCalendarAppProfile.FromWindow(snapshot);
        if (profile is null)
        {
            yield break;
        }

        var signature = $"{profile.AppId}:{snapshot.ProcessId}:{snapshot.TitleHash}:{snapshot.TitleLength}";
        if (_lastForegroundSignature == signature)
        {
            yield break;
        }
        _lastForegroundSignature = signature;

        var metadata = WindowMetadata(snapshot, profile, "windows_winevent_mail_calendar_foreground");
        if (profile.SupportsMail && profile.PrimarySurface is "mail" or "suite" && Throttle($"foreground:mail:{signature}", TimeSpan.FromSeconds(8)))
        {
            yield return Sensitive(CollectorCatalog.MailActivity, "email_opened", "Mail-capable surface focused; subject, sender, recipients, and message body are omitted.", metadata);
        }
        if (profile.SupportsCalendar && profile.PrimarySurface == "calendar" && Throttle($"foreground:calendar:{signature}", TimeSpan.FromSeconds(8)))
        {
            yield return Metadata(CollectorCatalog.CalendarActivity, "followup_due", "Calendar surface focused; event title, attendees, location, and notes are omitted.", metadata);
            yield return Sensitive(CollectorCatalog.CalendarSchedulingActivity, "calendar_availability_checked", "Calendar availability surface observed; event details and attendee identities are omitted.", metadata);
        }
        if (profile.SupportsReminder && Throttle($"foreground:reminder:{signature}", TimeSpan.FromSeconds(8)))
        {
            yield return Metadata(CollectorCatalog.Wakeups, "followup_due", "Reminder/to-do surface focused; reminder title and notes are omitted.", metadata);
            yield return Sensitive(CollectorCatalog.ReminderTodoActivity, "todo_list_changed", "Reminder/to-do list surface observed; task titles and notes are omitted.", metadata);
        }
    }

    public IEnumerable<NativeCollectorEvent> ObserveKeyDown(uint virtualKey)
    {
        var snapshot = WindowSnapshot.FromForeground();
        if (snapshot is null)
        {
            yield break;
        }
        var profile = MailCalendarAppProfile.FromWindow(snapshot);
        if (profile is null)
        {
            yield break;
        }

        var ctrl = NativeMethods.IsKeyDown(NativeMethods.VkControl);
        var shift = NativeMethods.IsKeyDown(NativeMethods.VkShift);
        var alt = NativeMethods.IsKeyDown(NativeMethods.VkMenu);
        var metadata = SensitiveMetadata(WindowMetadata(snapshot, profile, "windows_keyboard_mail_calendar_shortcut"));
        metadata["shortcut_dialect"] = profile.ShortcutDialect;
        metadata["modifier_ctrl"] = ctrl.ToString().ToLowerInvariant();
        metadata["modifier_shift"] = shift.ToString().ToLowerInvariant();
        metadata["modifier_alt"] = alt.ToString().ToLowerInvariant();
        metadata["raw_key_omitted"] = "true";

        foreach (var collectorEvent in ObserveMailShortcut(profile, virtualKey, ctrl, shift, metadata))
        {
            yield return collectorEvent;
        }
        foreach (var collectorEvent in ObserveCalendarShortcut(profile, virtualKey, ctrl, shift, metadata))
        {
            yield return collectorEvent;
        }
        foreach (var collectorEvent in ObserveReminderShortcut(profile, virtualKey, ctrl, shift, metadata))
        {
            yield return collectorEvent;
        }
    }

    private IEnumerable<NativeCollectorEvent> ProcessStarted(MailCalendarAppProfile profile, ProcessSnapshot process)
    {
        var metadata = ProcessMetadata(process, profile, "windows_process_snapshot_mail_calendar");
        if (profile.SupportsMail && profile.PrimarySurface is "mail" or "suite" && Throttle($"process:mail:{process.ProcessId}", TimeSpan.FromSeconds(3)))
        {
            yield return Sensitive(CollectorCatalog.MailActivity, "email_opened", "Mail-capable process started; subjects, senders, recipients, and message bodies are omitted.", metadata);
        }
        if (profile.SupportsCalendar && profile.PrimarySurface == "calendar" && Throttle($"process:calendar:{process.ProcessId}", TimeSpan.FromSeconds(3)))
        {
            yield return Metadata(CollectorCatalog.CalendarActivity, "followup_due", "Calendar process started; event titles, attendees, locations, and notes are omitted.", metadata);
            yield return Sensitive(CollectorCatalog.CalendarSchedulingActivity, "calendar_availability_checked", "Calendar process started; availability details and event metadata are omitted.", metadata);
        }
        if (profile.SupportsReminder && Throttle($"process:reminder:{process.ProcessId}", TimeSpan.FromSeconds(3)))
        {
            yield return Metadata(CollectorCatalog.Wakeups, "followup_due", "Reminder/to-do process started; reminder title and notes are omitted.", metadata);
            yield return Sensitive(CollectorCatalog.ReminderTodoActivity, "todo_list_changed", "Reminder/to-do process started; task titles and notes are omitted.", metadata);
        }
    }

    private IEnumerable<NativeCollectorEvent> ObserveMailShortcut(
        MailCalendarAppProfile profile,
        uint virtualKey,
        bool ctrl,
        bool shift,
        Dictionary<string, string> metadata
    )
    {
        if (!profile.SupportsMail)
        {
            yield break;
        }

        if ((ctrl && !shift && virtualKey == (uint)NativeMethods.VkN || ctrl && shift && virtualKey == (uint)NativeMethods.VkM) && Throttle("shortcut:mail:draft", TimeSpan.FromSeconds(2)))
        {
            yield return Sensitive(CollectorCatalog.MailCompositionActivity, "email_draft_started", "Mail compose shortcut observed; subject, body, recipients, and attachments are omitted.", metadata);
            yield return Sensitive(CollectorCatalog.MailActivity, "draft_started", "Mail draft shortcut observed; subject, body, and recipients are omitted.", metadata);
        }
        if (ctrl && !shift && virtualKey == (uint)NativeMethods.VkR && Throttle("shortcut:mail:reply", TimeSpan.FromSeconds(2)))
        {
            yield return Sensitive(CollectorCatalog.MailCompositionActivity, "email_reply_started", "Mail reply shortcut observed; original message and recipients are omitted.", metadata);
        }
        if (ctrl && virtualKey == (uint)NativeMethods.VkF && Throttle("shortcut:mail:forward", TimeSpan.FromSeconds(2)))
        {
            yield return Sensitive(CollectorCatalog.MailCompositionActivity, "email_forward_started", "Mail forward shortcut observed; message body, subject, and recipients are omitted.", metadata);
        }
        if (ctrl && virtualKey == (uint)NativeMethods.VkEnter && Throttle("shortcut:mail:send", TimeSpan.FromSeconds(2)))
        {
            yield return Sensitive(CollectorCatalog.MailCompositionActivity, "email_sent", "Mail send shortcut observed; message contents, subject, and recipients are omitted.", metadata);
        }
        if (ctrl && virtualKey == (uint)NativeMethods.VkS && Throttle("shortcut:mail:save", TimeSpan.FromSeconds(2)))
        {
            yield return Sensitive(CollectorCatalog.MailCompositionActivity, "email_draft_updated", "Mail save-draft shortcut observed; draft contents are omitted.", metadata);
        }
        if (ctrl && virtualKey == (uint)NativeMethods.VkE && Throttle("shortcut:mail:search", TimeSpan.FromSeconds(2)))
        {
            yield return Sensitive(CollectorCatalog.MailOrganizationActivity, "email_search_performed", "Mail search shortcut observed; query, senders, subjects, and mailbox labels are omitted.", metadata);
        }
        if (virtualKey == (uint)NativeMethods.VkDelete && Throttle("shortcut:mail:delete", TimeSpan.FromSeconds(2)))
        {
            yield return Sensitive(CollectorCatalog.MailOrganizationActivity, "email_deleted", "Mail delete shortcut observed; message identifiers, senders, and subjects are omitted.", metadata);
        }
        if (ctrl && virtualKey == (uint)NativeMethods.VkU && Throttle("shortcut:mail:unread", TimeSpan.FromSeconds(2)))
        {
            yield return Sensitive(CollectorCatalog.MailOrganizationActivity, "email_unread_marked", "Mail unread shortcut observed; message identifiers and subjects are omitted.", metadata);
        }
        if (ctrl && shift && virtualKey == (uint)NativeMethods.VkG && Throttle("shortcut:mail:flag", TimeSpan.FromSeconds(2)))
        {
            yield return Sensitive(CollectorCatalog.MailOrganizationActivity, "email_flagged", "Mail flag shortcut observed; sender, subject, and flag label are omitted.", metadata);
        }
    }

    private IEnumerable<NativeCollectorEvent> ObserveCalendarShortcut(
        MailCalendarAppProfile profile,
        uint virtualKey,
        bool ctrl,
        bool shift,
        Dictionary<string, string> metadata
    )
    {
        if (!profile.SupportsCalendar)
        {
            yield break;
        }

        if ((profile.PrimarySurface == "calendar" && ctrl && virtualKey == (uint)NativeMethods.VkN || ctrl && shift && virtualKey == (uint)NativeMethods.VkA || ctrl && shift && virtualKey == (uint)NativeMethods.VkQ) && Throttle("shortcut:calendar:create", TimeSpan.FromSeconds(2)))
        {
            yield return Sensitive(CollectorCatalog.CalendarSchedulingActivity, "calendar_event_created", "Calendar create-event shortcut observed; title, attendees, location, and notes are omitted.", metadata);
        }
        if (ctrl && virtualKey == (uint)NativeMethods.VkS && profile.PrimarySurface == "calendar" && Throttle("shortcut:calendar:update", TimeSpan.FromSeconds(2)))
        {
            yield return Sensitive(CollectorCatalog.CalendarSchedulingActivity, "calendar_event_updated", "Calendar save/update shortcut observed; event details are omitted.", metadata);
        }
        if (virtualKey == (uint)NativeMethods.VkDelete && profile.PrimarySurface == "calendar" && Throttle("shortcut:calendar:delete", TimeSpan.FromSeconds(2)))
        {
            yield return Sensitive(CollectorCatalog.CalendarSchedulingActivity, "calendar_event_deleted", "Calendar delete shortcut observed; event title and attendee details are omitted.", metadata);
        }
        if (ctrl && (virtualKey == (uint)NativeMethods.VkE || virtualKey == (uint)NativeMethods.VkF) && Throttle("shortcut:calendar:availability", TimeSpan.FromSeconds(2)))
        {
            yield return Sensitive(CollectorCatalog.CalendarSchedulingActivity, "calendar_availability_checked", "Calendar search/availability shortcut observed; query and attendee identities are omitted.", metadata);
        }
    }

    private IEnumerable<NativeCollectorEvent> ObserveReminderShortcut(
        MailCalendarAppProfile profile,
        uint virtualKey,
        bool ctrl,
        bool shift,
        Dictionary<string, string> metadata
    )
    {
        if (!profile.SupportsReminder)
        {
            yield break;
        }

        if (ctrl && virtualKey == (uint)NativeMethods.VkN && Throttle("shortcut:reminder:create", TimeSpan.FromSeconds(2)))
        {
            yield return Sensitive(CollectorCatalog.ReminderTodoActivity, "todo_created", "To-do create shortcut observed; task title and notes are omitted.", metadata);
            yield return Metadata(CollectorCatalog.Wakeups, "scheduled_wakeup_due", "Reminder/to-do create shortcut observed; reminder title and notes are omitted.", metadata);
        }
        if (ctrl && virtualKey == (uint)NativeMethods.VkS && Throttle("shortcut:reminder:update", TimeSpan.FromSeconds(2)))
        {
            yield return Sensitive(CollectorCatalog.ReminderTodoActivity, shift ? "reminder_snoozed" : "reminder_updated", "Reminder update shortcut observed; title and notes are omitted.", metadata);
        }
        if (ctrl && virtualKey == (uint)NativeMethods.VkEnter && Throttle("shortcut:reminder:complete", TimeSpan.FromSeconds(2)))
        {
            yield return Sensitive(CollectorCatalog.ReminderTodoActivity, "todo_completed", "To-do completion shortcut observed; task title and notes are omitted.", metadata);
        }
        if (virtualKey == (uint)NativeMethods.VkDelete && Throttle("shortcut:reminder:delete", TimeSpan.FromSeconds(2)))
        {
            yield return Sensitive(CollectorCatalog.ReminderTodoActivity, "reminder_deleted", "Reminder delete shortcut observed; title and notes are omitted.", metadata);
        }
    }

    private void AddWatcher(string root)
    {
        if (!Directory.Exists(root))
        {
            return;
        }
        try
        {
            var watcher = new FileSystemWatcher(root)
            {
                IncludeSubdirectories = true,
                NotifyFilter = NotifyFilters.FileName | NotifyFilters.DirectoryName | NotifyFilters.LastWrite | NotifyFilters.Size | NotifyFilters.CreationTime,
            };
            watcher.Created += (_, args) => ObserveFileChange(root, args.FullPath, args.ChangeType);
            watcher.Changed += (_, args) => ObserveFileChange(root, args.FullPath, args.ChangeType);
            watcher.Deleted += (_, args) => ObserveFileChange(root, args.FullPath, args.ChangeType);
            watcher.Renamed += (_, args) => ObserveFileChange(root, args.FullPath, args.ChangeType);
            watcher.Error += (_, _) => { };
            watcher.EnableRaisingEvents = true;
            _watchers.Add(watcher);
        }
        catch
        {
            // Mail/calendar file watching is best-effort and never blocks the helper.
        }
    }

    private void ObserveFileChange(string root, string path, WatcherChangeTypes changeType)
    {
        foreach (var collectorEvent in ClassifyFileChange(root, path, changeType))
        {
            _emit(collectorEvent);
        }
    }

    private IEnumerable<NativeCollectorEvent> ClassifyFileChange(string root, string path, WatcherChangeTypes changeType)
    {
        var normalized = Normalize(path);
        var fileName = Path.GetFileName(normalized);
        var extension = Path.GetExtension(normalized).ToLowerInvariant();
        var metadata = PathMetadata(root, path, "windows_mail_calendar_filesystem");
        metadata["change_kind"] = changeType.ToString().ToLowerInvariant();

        if (extension == ".ics" && Throttle($"file:ics:{StableHash(normalized)}:{changeType}", TimeSpan.FromSeconds(3)))
        {
            foreach (var collectorEvent in CalendarFileEvents(changeType, metadata))
            {
                yield return collectorEvent;
            }
        }
        if ((extension is ".eml" or ".msg") && Throttle($"file:mail:{StableHash(normalized)}:{changeType}", TimeSpan.FromSeconds(3)))
        {
            yield return Sensitive(CollectorCatalog.MailActivity, changeType == WatcherChangeTypes.Created ? "email_received" : "email_opened", "Mail message file changed; sender, recipients, subject, and body are omitted.", metadata);
            yield return Sensitive(CollectorCatalog.MailOrganizationActivity, "email_moved", "Mail message file metadata changed; mailbox, sender, and subject are omitted.", metadata);
        }
        if (extension == ".oft" && Throttle($"file:template:{StableHash(normalized)}:{changeType}", TimeSpan.FromSeconds(3)))
        {
            yield return Sensitive(CollectorCatalog.MailCompositionActivity, changeType == WatcherChangeTypes.Created ? "email_draft_started" : "email_draft_updated", "Mail template/draft file changed; subject, body, recipients, and filenames are omitted.", metadata);
        }
        if (IsReminderLike(fileName, extension) && Throttle($"file:reminder:{StableHash(normalized)}:{changeType}", TimeSpan.FromSeconds(3)))
        {
            foreach (var collectorEvent in ReminderFileEvents(changeType, metadata))
            {
                yield return collectorEvent;
            }
        }
        if (IsMailAttachmentLike(normalized, extension) && Throttle($"file:attachment:{StableHash(normalized)}:{changeType}", TimeSpan.FromSeconds(5)))
        {
            yield return Sensitive(CollectorCatalog.MailActivity, "attachment_downloaded", "Mail attachment-like file changed; filename, path, sender, and message subject are omitted.", metadata);
            yield return Sensitive(CollectorCatalog.MailCompositionActivity, changeType == WatcherChangeTypes.Deleted ? "email_attachment_removed" : "email_attachment_added", "Mail attachment workflow observed; filename, path, and attachment contents are omitted.", metadata);
        }
    }

    private static IEnumerable<NativeCollectorEvent> CalendarFileEvents(WatcherChangeTypes changeType, Dictionary<string, string> metadata)
    {
        yield return changeType switch
        {
            WatcherChangeTypes.Created => Sensitive(CollectorCatalog.CalendarSchedulingActivity, "calendar_invite_received", "Calendar invite file appeared; event title, attendees, location, and notes are omitted.", metadata),
            WatcherChangeTypes.Deleted => Sensitive(CollectorCatalog.CalendarSchedulingActivity, "calendar_event_deleted", "Calendar file deleted; event title, attendees, location, and notes are omitted.", metadata),
            WatcherChangeTypes.Renamed => Sensitive(CollectorCatalog.CalendarSchedulingActivity, "calendar_event_rescheduled", "Calendar file renamed/moved; event title, attendees, location, and notes are omitted.", metadata),
            _ => Sensitive(CollectorCatalog.CalendarSchedulingActivity, "calendar_event_updated", "Calendar file changed; event title, attendees, location, and notes are omitted.", metadata),
        };
    }

    private static IEnumerable<NativeCollectorEvent> ReminderFileEvents(WatcherChangeTypes changeType, Dictionary<string, string> metadata)
    {
        yield return changeType switch
        {
            WatcherChangeTypes.Created => Sensitive(CollectorCatalog.ReminderTodoActivity, "todo_created", "Reminder/to-do file appeared; task title and notes are omitted.", metadata),
            WatcherChangeTypes.Deleted => Sensitive(CollectorCatalog.ReminderTodoActivity, "reminder_deleted", "Reminder/to-do file deleted; title and notes are omitted.", metadata),
            WatcherChangeTypes.Renamed => Sensitive(CollectorCatalog.ReminderTodoActivity, "todo_due_date_changed", "Reminder/to-do file moved or renamed; title, notes, and date text are omitted.", metadata),
            _ => Sensitive(CollectorCatalog.ReminderTodoActivity, "reminder_updated", "Reminder/to-do file changed; title and notes are omitted.", metadata),
        };
        yield return Metadata(CollectorCatalog.Wakeups, changeType == WatcherChangeTypes.Created ? "scheduled_wakeup_due" : "followup_due", "Reminder/to-do metadata changed; title and notes are omitted.", metadata);
    }

    private bool Throttle(string key, TimeSpan interval)
    {
        var now = DateTimeOffset.UtcNow;
        var previous = _lastEmitted.GetOrAdd(key, DateTimeOffset.MinValue);
        if (now - previous < interval)
        {
            return false;
        }
        _lastEmitted[key] = now;
        return true;
    }

    private static NativeCollectorEvent Metadata(string collector, string stimulusType, string text, Dictionary<string, string> metadata) =>
        Create(collector, SourceFor(collector), stimulusType, text, metadata, "metadata");

    private static NativeCollectorEvent Sensitive(string collector, string stimulusType, string text, Dictionary<string, string> metadata) =>
        Create(collector, SourceFor(collector), stimulusType, text, SensitiveMetadata(metadata), "sensitive_metadata");

    private static NativeCollectorEvent Create(string collector, string source, string stimulusType, string text, Dictionary<string, string> metadata, string privacyTier) =>
        new(collector, source, stimulusType, text, metadata, PrivacyTier: privacyTier);

    private static string SourceFor(string collector) => collector switch
    {
        CollectorCatalog.CalendarActivity => "system",
        CollectorCatalog.Wakeups => "system",
        CollectorCatalog.CalendarSchedulingActivity => "system",
        CollectorCatalog.ReminderTodoActivity => "system",
        _ => "activity",
    };

    private static Dictionary<string, string> ProcessMetadata(ProcessSnapshot process, MailCalendarAppProfile profile, string nativeSource)
    {
        var metadata = BaseMetadata(nativeSource, profile);
        metadata["process_id"] = process.ProcessId.ToStringInvariant();
        metadata["process_name"] = process.Name;
        metadata["command_line_omitted"] = "true";
        metadata["process_path_omitted"] = "true";
        return metadata;
    }

    private static Dictionary<string, string> WindowMetadata(WindowSnapshot snapshot, MailCalendarAppProfile profile, string nativeSource)
    {
        var metadata = BaseMetadata(nativeSource, profile);
        metadata["process_id"] = snapshot.ProcessId.ToStringInvariant();
        metadata["process_name"] = SafeProcessName(snapshot.ProcessNameOrUnknown);
        metadata["window_class"] = snapshot.ClassName;
        metadata["window_title_omitted"] = "true";
        metadata["window_title_hash"] = snapshot.TitleHash;
        metadata["window_title_length"] = snapshot.TitleLength.ToStringInvariant();
        metadata["screen_content_omitted"] = "true";
        return metadata;
    }

    private static Dictionary<string, string> PathMetadata(string root, string path, string nativeSource)
    {
        var extension = Path.GetExtension(path);
        return new Dictionary<string, string>
        {
            ["native_source"] = nativeSource,
            ["raw_content_included"] = "false",
            ["root_digest"] = StableHash(Normalize(root)),
            ["path_digest"] = StableHash(Normalize(path)),
            ["parent_digest"] = StableHash(Normalize(Path.GetDirectoryName(path) ?? "")),
            ["extension"] = SafeExtension(extension),
            ["filename_omitted"] = "true",
            ["path_redacted"] = "true",
            ["contents_omitted"] = "true",
            ["message_subject_omitted"] = "true",
            ["message_body_omitted"] = "true",
            ["participants_omitted"] = "true",
            ["attendees_omitted"] = "true",
            ["calendar_title_omitted"] = "true",
        };
    }

    private static Dictionary<string, string> BaseMetadata(string nativeSource, MailCalendarAppProfile profile) => new()
    {
        ["native_source"] = nativeSource,
        ["app_id"] = profile.AppId,
        ["surface_kind"] = profile.PrimarySurface,
        ["raw_content_included"] = "false",
        ["subject_omitted"] = "true",
        ["sender_omitted"] = "true",
        ["recipients_omitted"] = "true",
        ["message_body_omitted"] = "true",
        ["mailbox_label_omitted"] = "true",
        ["calendar_title_omitted"] = "true",
        ["calendar_location_omitted"] = "true",
        ["attendees_omitted"] = "true",
        ["task_title_omitted"] = "true",
        ["notes_omitted"] = "true",
        ["url_omitted"] = "true",
    };

    private static Dictionary<string, string> SensitiveMetadata(Dictionary<string, string> metadata)
    {
        var copy = new Dictionary<string, string>(metadata);
        copy["sensitive_values_omitted"] = "true";
        copy["raw_text_omitted"] = "true";
        return copy;
    }

    private static Dictionary<int, ProcessSnapshot> SnapshotProcesses()
    {
        try
        {
            return Process.GetProcesses().ToDictionary(
                process => process.Id,
                process => new ProcessSnapshot(process.Id, SafeProcessName(process))
            );
        }
        catch
        {
            return new Dictionary<int, ProcessSnapshot>();
        }
    }

    private static List<string> ResolveWatchRoots(IReadOnlyList<string> configured)
    {
        var roots = configured.Count > 0 ? configured : [Environment.CurrentDirectory];
        return roots.Select(ExpandPath).Where(Directory.Exists).Distinct(StringComparer.OrdinalIgnoreCase).Take(10).ToList();
    }

    private static string ExpandPath(string path)
    {
        if (path.StartsWith("~", StringComparison.Ordinal))
        {
            var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            return Path.GetFullPath(Path.Combine(home, path.TrimStart('~', '/', '\\')));
        }
        return Path.GetFullPath(path);
    }

    private static bool IsReminderLike(string fileName, string extension) =>
        extension is ".todo" or ".task" or ".tasks"
        || fileName.Contains("todo", StringComparison.OrdinalIgnoreCase)
        || fileName.Contains("reminder", StringComparison.OrdinalIgnoreCase)
        || fileName.Contains("task", StringComparison.OrdinalIgnoreCase);

    private static bool IsMailAttachmentLike(string normalized, string extension) =>
        extension is not "" and not ".eml" and not ".msg" and not ".oft" and not ".ics"
        && (normalized.Contains("attachment", StringComparison.OrdinalIgnoreCase)
            || normalized.Contains("outlook", StringComparison.OrdinalIgnoreCase)
            || normalized.Contains($"{Path.DirectorySeparatorChar}mail{Path.DirectorySeparatorChar}", StringComparison.OrdinalIgnoreCase));

    private static string SafeProcessName(Process process)
    {
        try
        {
            return SafeProcessName(process.ProcessName);
        }
        catch
        {
            return "unknown";
        }
    }

    private static string SafeProcessName(string processName)
    {
        var name = (processName ?? "").Trim();
        return name.EndsWith(".exe", StringComparison.OrdinalIgnoreCase) ? Path.GetFileNameWithoutExtension(name).ToLowerInvariant() : name.ToLowerInvariant();
    }

    private static string SafeExtension(string extension)
    {
        if (string.IsNullOrWhiteSpace(extension))
        {
            return "";
        }
        return SecretExtensions.Contains(extension) ? "" : extension.Trim().ToLowerInvariant();
    }

    private static string Normalize(string path)
    {
        try
        {
            return Path.GetFullPath(path).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar).ToLowerInvariant();
        }
        catch
        {
            return (path ?? "").Trim().ToLowerInvariant();
        }
    }

    private static string StableHash(string value)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(bytes).ToLowerInvariant()[..16];
    }

    private sealed record ProcessSnapshot(int ProcessId, string Name);

    private sealed record MailCalendarAppProfile(
        string AppId,
        string PrimarySurface,
        bool SupportsMail,
        bool SupportsCalendar,
        bool SupportsReminder,
        string ShortcutDialect
    )
    {
        public static MailCalendarAppProfile? FromWindow(WindowSnapshot snapshot) =>
            FromProcessName(snapshot.ProcessNameOrUnknown);

        public static MailCalendarAppProfile? FromProcessName(string processName)
        {
            var process = SafeProcessName(processName);
            if (MailSuites.Contains(process))
            {
                return new MailCalendarAppProfile(process, "suite", true, true, false, "outlook");
            }
            if (MailClients.Contains(process))
            {
                return new MailCalendarAppProfile(process, "mail", true, false, false, "mail");
            }
            if (CalendarClients.Contains(process))
            {
                return new MailCalendarAppProfile(process, "calendar", false, true, false, "calendar");
            }
            if (ReminderClients.Contains(process))
            {
                return new MailCalendarAppProfile(process, "reminder", false, false, true, "todo");
            }
            return null;
        }
    }

    private static readonly HashSet<string> MailSuites = new(StringComparer.OrdinalIgnoreCase)
    {
        "outlook", "olk", "newoutlook", "emclient", "thunderbird",
    };

    private static readonly HashSet<string> MailClients = new(StringComparer.OrdinalIgnoreCase)
    {
        "hxoutlook", "mail", "mailspring", "mailbird", "bluemail", "postbox", "hiri",
    };

    private static readonly HashSet<string> CalendarClients = new(StringComparer.OrdinalIgnoreCase)
    {
        "hxcalendarappimm", "calendar", "calendarapp",
    };

    private static readonly HashSet<string> ReminderClients = new(StringComparer.OrdinalIgnoreCase)
    {
        "todo", "todos", "microsofttodo", "microsoft.todos", "todoist", "ticktick", "onenote", "onenotem", "stickynotes",
    };

    private static readonly HashSet<string> SecretExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".key", ".pem", ".p12", ".pfx", ".crt",
    };
}
