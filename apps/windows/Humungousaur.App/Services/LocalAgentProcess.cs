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
}
