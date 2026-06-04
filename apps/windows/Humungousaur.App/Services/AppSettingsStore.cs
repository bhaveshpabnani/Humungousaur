using System.Text.Json;
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
        File.WriteAllText(_settingsPath, JsonSerializer.Serialize(settings, JsonOptions));
    }

    private static AppSettings WithDefaults(AppSettings settings)
    {
        if (string.IsNullOrWhiteSpace(settings.WorkspacePath))
        {
            settings.WorkspacePath = FindWorkspaceRoot() ?? Environment.CurrentDirectory;
        }

        if (settings.Port <= 0)
        {
            settings.Port = 8765;
        }

        if (string.IsNullOrWhiteSpace(settings.ApiBaseUrl))
        {
            settings.ApiBaseUrl = $"http://127.0.0.1:{settings.Port}";
        }

        return settings;
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
}
