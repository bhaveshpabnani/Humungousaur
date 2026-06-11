using System.Text.Json;
using System.Security.Cryptography;
using System.Text;
using Humungousaur.App.Models;

namespace Humungousaur.App.Services;

public sealed class AppSettingsStore
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };
    private readonly string _settingsPath;

    public AppSettingsStore()
    {
        var root = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Humungousaur",
            "AssistantShell");
        Directory.CreateDirectory(root);
        _settingsPath = Path.Combine(root, "settings.json");
    }

    public AppSettings Load()
    {
        if (!File.Exists(_settingsPath))
        {
            return WithDefaults(new AppSettings());
        }

        try
        {
            var settings = JsonSerializer.Deserialize<AppSettings>(File.ReadAllText(_settingsPath), JsonOptions) ?? new AppSettings();
            UnprotectSettings(settings);
            return WithDefaults(settings);
        }
        catch
        {
            return WithDefaults(new AppSettings());
        }
    }

    public void Save(AppSettings settings)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(_settingsPath)!);
        File.WriteAllText(_settingsPath, JsonSerializer.Serialize(ProtectedCopy(settings), JsonOptions));
    }

    private static AppSettings WithDefaults(AppSettings settings)
    {
        if (string.IsNullOrWhiteSpace(settings.WorkspacePath))
        {
            settings.WorkspacePath = FindWorkspaceRoot() ??
                Environment.GetFolderPath(Environment.SpecialFolder.UserProfile) ??
                Environment.CurrentDirectory;
        }

        if (string.IsNullOrWhiteSpace(settings.PythonPath))
        {
            var installedPython = InstalledRuntimePythonPath();
            if (!string.IsNullOrWhiteSpace(installedPython))
            {
                settings.PythonPath = installedPython;
            }
        }

        if (settings.Port <= 0)
        {
            settings.Port = 8765;
        }

        if (string.IsNullOrWhiteSpace(settings.ApiBaseUrl))
        {
            settings.ApiBaseUrl = $"http://127.0.0.1:{settings.Port}";
        }

        settings.Planner = AppRuntimeDefaults.EffectivePlanner(settings.Planner);
        if (string.IsNullOrWhiteSpace(settings.ModelProvider) ||
            (settings.ModelProvider.Equals("groq", StringComparison.OrdinalIgnoreCase) &&
             string.IsNullOrWhiteSpace(settings.ModelApiKey)))
        {
            settings.ModelProvider = AppRuntimeDefaults.ModelProvider;
        }
        else
        {
            settings.ModelProvider = AppRuntimeDefaults.EffectiveModelProvider(settings.ModelProvider);
        }
        settings.ModelName = AppRuntimeDefaults.EffectiveModelName(settings.ModelName);
        settings.JanusModelProvider = AppRuntimeDefaults.EffectiveJanusModelProvider(settings.JanusModelProvider);
        settings.TtsProvider = AppRuntimeDefaults.EffectiveTtsProvider(settings.TtsProvider);
        if (string.IsNullOrWhiteSpace(settings.VoiceWakePhrases) ||
            settings.VoiceWakePhrases.Contains("jarvis", StringComparison.OrdinalIgnoreCase))
        {
            settings.VoiceWakePhrases = "hey humungousaur";
        }
        if (string.IsNullOrWhiteSpace(settings.VoiceStopPhrases) ||
            settings.VoiceStopPhrases.Contains("jarvis", StringComparison.OrdinalIgnoreCase))
        {
            settings.VoiceStopPhrases = "stop humungousaur";
        }

        return settings;
    }

    private static AppSettings ProtectedCopy(AppSettings settings)
    {
        return new AppSettings
        {
            ApiBaseUrl = settings.ApiBaseUrl,
            WorkspacePath = settings.WorkspacePath,
            PythonPath = settings.PythonPath,
            Port = settings.Port,
            Planner = settings.Planner,
            ModelProvider = settings.ModelProvider,
            ModelName = settings.ModelName,
            ModelBaseUrl = settings.ModelBaseUrl,
            ModelApiKey = Protect(settings.ModelApiKey),
            JanusModelProvider = settings.JanusModelProvider,
            JanusModelName = settings.JanusModelName,
            JanusModelBaseUrl = settings.JanusModelBaseUrl,
            JanusModelApiKey = Protect(settings.JanusModelApiKey),
            TtsProvider = settings.TtsProvider,
            VoiceId = settings.VoiceId,
            DeepgramApiKey = Protect(settings.DeepgramApiKey),
            ElevenLabsApiKey = Protect(settings.ElevenLabsApiKey),
            ElevenLabsModel = settings.ElevenLabsModel,
            VoiceWakeEnabled = settings.VoiceWakeEnabled,
            VoiceWakePhrases = settings.VoiceWakePhrases,
            VoiceStopPhrases = settings.VoiceStopPhrases,
            VoiceContinuousAfterWake = settings.VoiceContinuousAfterWake,
            ApproveHighRisk = settings.ApproveHighRisk,
            Channels = settings.Channels.Select(channel => new ChannelSetup
            {
                ChannelId = channel.ChannelId,
                Enabled = channel.Enabled,
                ListenEnabled = channel.ListenEnabled,
                ConversationId = channel.ConversationId,
                ConversationType = channel.ConversationType,
                SecretName = channel.SecretName,
                SecretValue = Protect(channel.SecretValue),
                SecretValues = (channel.SecretValues ?? new Dictionary<string, string>()).ToDictionary(item => item.Key, item => Protect(item.Value)),
                SecretConfigured = channel.SecretConfigured,
                Allowlist = (channel.Allowlist ?? new List<string>()).ToList(),
                GroupAllowlist = (channel.GroupAllowlist ?? new List<string>()).ToList(),
                Notes = channel.Notes,
            }).ToList(),
        };
    }

    private static void UnprotectSettings(AppSettings settings)
    {
        settings.ModelApiKey = Unprotect(settings.ModelApiKey);
        settings.JanusModelApiKey = Unprotect(settings.JanusModelApiKey);
        settings.DeepgramApiKey = Unprotect(settings.DeepgramApiKey);
        settings.ElevenLabsApiKey = Unprotect(settings.ElevenLabsApiKey);
        foreach (var channel in settings.Channels)
        {
            channel.SecretValue = Unprotect(channel.SecretValue);
            channel.SecretValues = (channel.SecretValues ?? new Dictionary<string, string>()).ToDictionary(item => item.Key, item => Unprotect(item.Value));
            channel.Allowlist ??= new List<string>();
            channel.GroupAllowlist ??= new List<string>();
            channel.SecretConfigured = channel.SecretConfigured || !string.IsNullOrWhiteSpace(channel.SecretValue) || channel.SecretValues.Count > 0;
        }
    }

    private static string Protect(string value)
    {
        if (string.IsNullOrEmpty(value) || value.StartsWith("dpapi:", StringComparison.Ordinal))
        {
            return value;
        }

        var bytes = ProtectedData.Protect(Encoding.UTF8.GetBytes(value), null, DataProtectionScope.CurrentUser);
        return "dpapi:" + Convert.ToBase64String(bytes);
    }

    private static string Unprotect(string value)
    {
        if (string.IsNullOrEmpty(value) || !value.StartsWith("dpapi:", StringComparison.Ordinal))
        {
            return value;
        }

        try
        {
            var bytes = Convert.FromBase64String(value["dpapi:".Length..]);
            return Encoding.UTF8.GetString(ProtectedData.Unprotect(bytes, null, DataProtectionScope.CurrentUser));
        }
        catch
        {
            return "";
        }
    }

    private static string? FindWorkspaceRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null)
        {
            var marker = Path.Combine(directory.FullName, "pyproject.toml");
            if (File.Exists(marker) && File.ReadAllText(marker).Contains("humungousaur", StringComparison.OrdinalIgnoreCase))
            {
                return directory.FullName;
            }
            directory = directory.Parent;
        }
        return null;
    }

    private static string? InstalledRuntimePythonPath()
    {
        var localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        if (string.IsNullOrWhiteSpace(localAppData))
        {
            return null;
        }
        var candidate = Path.Combine(localAppData, "Humungousaur", "runtime", ".venv", "Scripts", "python.exe");
        return File.Exists(candidate) ? candidate : null;
    }
}
