using System.Diagnostics;
using Humungousaur.App.Models;

namespace Humungousaur.App.Services;

public sealed class LocalAgentProcess
{
    private Process? _process;
    private string _stdoutLogPath = "";
    private string _stderrLogPath = "";

    public event Action<string>? OutputReceived;

    public bool IsRunning => _process is { HasExited: false };

    public void Start(AppSettings settings)
    {
        if (IsRunning)
        {
            return;
        }

        var workspace = string.IsNullOrWhiteSpace(settings.WorkspacePath)
            ? Environment.CurrentDirectory
            : settings.WorkspacePath;
        var logRoot = Path.Combine(workspace, "artifacts", "windows-app");
        Directory.CreateDirectory(logRoot);
        _stdoutLogPath = Path.Combine(logRoot, "api.stdout.log");
        _stderrLogPath = Path.Combine(logRoot, "api.stderr.log");

        var info = new ProcessStartInfo
        {
            FileName = ResolvePythonPath(settings, workspace),
            WorkingDirectory = workspace,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        info.ArgumentList.Add("-m");
        info.ArgumentList.Add("humungousaur");
        info.ArgumentList.Add("serve");
        info.ArgumentList.Add("--workspace");
        info.ArgumentList.Add(workspace);
        info.ArgumentList.Add("--port");
        info.ArgumentList.Add(settings.Port.ToString());
        info.ArgumentList.Add("--planner");
        info.ArgumentList.Add(AppRuntimeDefaults.EffectivePlanner(settings.Planner));
        info.ArgumentList.Add("--model-provider");
        info.ArgumentList.Add(AppRuntimeDefaults.CliModelProvider(settings.ModelProvider));
        info.ArgumentList.Add("--model");
        info.ArgumentList.Add(AppRuntimeDefaults.EffectiveModelName(settings.ModelName));
        info.ArgumentList.Add("--model-api-key-env");
        info.ArgumentList.Add(AppRuntimeDefaults.ModelApiKeyName(settings.ModelProvider));
        if (!string.IsNullOrWhiteSpace(settings.ModelBaseUrl))
        {
            info.ArgumentList.Add("--model-base-url");
            info.ArgumentList.Add(settings.ModelBaseUrl);
        }
        var activeProvider = AppRuntimeDefaults.EffectiveActiveModelProvider(settings.ActiveModelProvider);
        if (!activeProvider.Equals("same-as-main", StringComparison.OrdinalIgnoreCase))
        {
            info.ArgumentList.Add("--active-model-provider");
            info.ArgumentList.Add(AppRuntimeDefaults.CliActiveModelProvider(activeProvider));
            info.ArgumentList.Add("--active-model-api-key-env");
            info.ArgumentList.Add(AppRuntimeDefaults.ModelApiKeyName(activeProvider));
            if (!string.IsNullOrWhiteSpace(settings.ActiveModelName))
            {
                info.ArgumentList.Add("--active-model");
                info.ArgumentList.Add(settings.ActiveModelName);
            }
            if (!string.IsNullOrWhiteSpace(settings.ActiveModelBaseUrl))
            {
                info.ArgumentList.Add("--active-model-base-url");
                info.ArgumentList.Add(settings.ActiveModelBaseUrl);
            }
        }
        ApplyRuntimeEnvironment(info, settings);

        _process = new Process { StartInfo = info, EnableRaisingEvents = true };
        _process.OutputDataReceived += (_, args) => Emit(args.Data, _stdoutLogPath);
        _process.ErrorDataReceived += (_, args) => Emit(args.Data, _stderrLogPath);
        _process.Exited += (_, _) => Emit("Agent process exited.");
        _process.Start();
        _process.BeginOutputReadLine();
        _process.BeginErrorReadLine();
    }

    public void Stop()
    {
        if (!IsRunning)
        {
            return;
        }

        _process!.Kill(entireProcessTree: true);
        _process.Dispose();
        _process = null;
    }

    private void Emit(string? line, string logPath = "")
    {
        if (!string.IsNullOrWhiteSpace(line))
        {
            if (!string.IsNullOrWhiteSpace(logPath))
            {
                try
                {
                    File.AppendAllText(logPath, $"{DateTimeOffset.Now:O}  {line}{Environment.NewLine}");
                }
                catch
                {
                    // UI logging should not keep the local API from running.
                }
            }
            OutputReceived?.Invoke(line);
        }
    }

    private static string ResolvePythonPath(AppSettings settings, string workspace)
    {
        if (!string.IsNullOrWhiteSpace(settings.PythonPath))
        {
            return settings.PythonPath;
        }

        var venvPython = Path.Combine(workspace, ".venv", "Scripts", "python.exe");
        if (File.Exists(venvPython))
        {
            return venvPython;
        }

        return "python";
    }

    private static void ApplyRuntimeEnvironment(ProcessStartInfo info, AppSettings settings)
    {
        AddEnvironmentSecret(info, AppRuntimeDefaults.ModelApiKeyName(settings.ModelProvider), settings.ModelApiKey);
        var activeProvider = AppRuntimeDefaults.EffectiveActiveModelProvider(settings.ActiveModelProvider);
        if (!activeProvider.Equals("same-as-main", StringComparison.OrdinalIgnoreCase))
        {
            AddEnvironmentSecret(info, AppRuntimeDefaults.ModelApiKeyName(activeProvider), settings.ActiveModelApiKey);
        }
        AddEnvironmentSecret(info, "DEEPGRAM_API_KEY", settings.DeepgramApiKey);
        AddEnvironmentSecret(info, "ELEVENLABS_API_KEY", settings.ElevenLabsApiKey);
        AddEnvironmentSecret(info, "ELEVENLABS_VOICE_ID", settings.VoiceId);
        AddEnvironmentSecret(info, "ELEVENLABS_MODEL_ID", settings.ElevenLabsModel);

        foreach (var channel in settings.Channels)
        {
            AddEnvironmentSecret(info, channel.SecretName, channel.SecretValue);
            foreach (var item in channel.SecretValues ?? [])
            {
                AddEnvironmentSecret(info, item.Key, item.Value);
            }
        }

    }

    private static void AddEnvironmentSecret(ProcessStartInfo info, string name, string value)
    {
        if (!string.IsNullOrWhiteSpace(name) && !string.IsNullOrWhiteSpace(value))
        {
            info.Environment[name.Trim()] = value;
        }
    }

}
