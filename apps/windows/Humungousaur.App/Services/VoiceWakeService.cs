using System.Diagnostics;
using Windows.Media.SpeechRecognition;

namespace Humungousaur.App.Services;

public sealed class VoiceRecognitionUpdate
{
    public string Transcript { get; init; } = "";
    public bool IsFinal { get; init; }
}

public sealed class VoiceActivityOptions
{
    public TimeSpan InitialSilenceTimeout { get; init; } = TimeSpan.FromSeconds(12);
    public TimeSpan EndSilenceTimeout { get; init; } = TimeSpan.FromSeconds(1.4);
    public TimeSpan BabbleTimeout { get; init; } = TimeSpan.FromSeconds(45);
}

public sealed class VoiceWakeService : IDisposable
{
    private SpeechRecognizer? _commandRecognizer;
    private SpeechRecognizer? _dictationRecognizer;
    private Process? _acknowledgementProcess;
    private bool _disposed;

    public event EventHandler<VoiceRecognitionUpdate>? RecognitionUpdated;
    public event EventHandler<Exception>? RecognitionFailed;

    public async Task StartCommandsAsync(IEnumerable<string> commands)
    {
        ThrowIfDisposed();
        await StopCommandsAsync();

        var cleanCommands = commands
            .Select(command => command.Trim())
            .Where(command => !string.IsNullOrWhiteSpace(command))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();
        if (cleanCommands.Count == 0)
        {
            throw new InvalidOperationException("At least one voice command phrase is required.");
        }

        var recognizer = new SpeechRecognizer();
        recognizer.Constraints.Add(new SpeechRecognitionListConstraint(cleanCommands, "Humungousaur commands"));
        var compile = await recognizer.CompileConstraintsAsync();
        if (compile.Status != SpeechRecognitionResultStatus.Success)
        {
            recognizer.Dispose();
            throw new InvalidOperationException($"Windows speech command recognition failed to compile: {compile.Status}.");
        }

        recognizer.ContinuousRecognitionSession.ResultGenerated += CommandResultGenerated;
        recognizer.ContinuousRecognitionSession.Completed += CommandRecognitionCompleted;
        _commandRecognizer = recognizer;
        await recognizer.ContinuousRecognitionSession.StartAsync();
    }

    public async Task StopCommandsAsync()
    {
        var recognizer = _commandRecognizer;
        _commandRecognizer = null;
        if (recognizer is null)
        {
            return;
        }

        recognizer.ContinuousRecognitionSession.ResultGenerated -= CommandResultGenerated;
        recognizer.ContinuousRecognitionSession.Completed -= CommandRecognitionCompleted;
        try
        {
            await recognizer.ContinuousRecognitionSession.StopAsync();
        }
        catch
        {
            // Stop can throw when the recognizer is already completing; disposal below is enough.
        }
        recognizer.Dispose();
    }

    public async Task StopAllAsync()
    {
        await StopCommandsAsync();
        StopDictation();
        StopAcknowledgement();
    }

    public async Task<string> TranscribeTaskAsync(
        VoiceActivityOptions? options,
        Action<string> onPartial,
        CancellationToken cancellationToken = default)
    {
        ThrowIfDisposed();
        StopDictation();

        var activity = options ?? new VoiceActivityOptions();
        var recognizer = new SpeechRecognizer();
        recognizer.Timeouts.InitialSilenceTimeout = activity.InitialSilenceTimeout;
        recognizer.Timeouts.EndSilenceTimeout = activity.EndSilenceTimeout;
        recognizer.Timeouts.BabbleTimeout = activity.BabbleTimeout;
        recognizer.Constraints.Add(new SpeechRecognitionTopicConstraint(SpeechRecognitionScenario.Dictation, "Humungousaur task dictation"));
        recognizer.HypothesisGenerated += (_, args) =>
        {
            var partial = args.Hypothesis.Text.Trim();
            if (!string.IsNullOrWhiteSpace(partial))
            {
                onPartial(partial);
            }
        };

        var compile = await recognizer.CompileConstraintsAsync();
        if (compile.Status != SpeechRecognitionResultStatus.Success)
        {
            recognizer.Dispose();
            throw new InvalidOperationException($"Windows speech dictation failed to compile: {compile.Status}.");
        }

        _dictationRecognizer = recognizer;
        using var registration = cancellationToken.Register(() => StopDictation());
        try
        {
            var result = await recognizer.RecognizeAsync();
            cancellationToken.ThrowIfCancellationRequested();
            if (result.Status != SpeechRecognitionResultStatus.Success)
            {
                throw new InvalidOperationException($"Windows speech dictation failed: {result.Status}.");
            }
            var transcript = result.Text.Trim();
            if (string.IsNullOrWhiteSpace(transcript))
            {
                throw new InvalidOperationException("No speech was recognized.");
            }
            return transcript;
        }
        finally
        {
            if (ReferenceEquals(_dictationRecognizer, recognizer))
            {
                _dictationRecognizer = null;
            }
            recognizer.Dispose();
        }
    }

    public void SpeakAcknowledgement(string text)
    {
        StopAcknowledgement();
        if (string.IsNullOrWhiteSpace(text))
        {
            return;
        }

        var escaped = text.Replace("'", "''", StringComparison.Ordinal);
        var script = $"Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Speak('{escaped}')";
        try
        {
            _acknowledgementProcess = Process.Start(new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments = $"-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command \"{script}\"",
                UseShellExecute = false,
                CreateNoWindow = true,
            });
        }
        catch (Exception exc)
        {
            RecognitionFailed?.Invoke(this, exc);
        }
    }

    public void StopAcknowledgement()
    {
        try
        {
            if (_acknowledgementProcess is { HasExited: false })
            {
                _acknowledgementProcess.Kill(entireProcessTree: true);
            }
        }
        catch
        {
            // Best effort only; acknowledgement is short-lived.
        }
        finally
        {
            _acknowledgementProcess?.Dispose();
            _acknowledgementProcess = null;
        }
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }
        _disposed = true;
        _ = StopAllAsync();
    }

    private void CommandResultGenerated(SpeechContinuousRecognitionSession sender, SpeechContinuousRecognitionResultGeneratedEventArgs args)
    {
        var transcript = args.Result.Text.Trim();
        if (string.IsNullOrWhiteSpace(transcript))
        {
            return;
        }
        RecognitionUpdated?.Invoke(this, new VoiceRecognitionUpdate { Transcript = transcript, IsFinal = true });
    }

    private void CommandRecognitionCompleted(SpeechContinuousRecognitionSession sender, SpeechContinuousRecognitionCompletedEventArgs args)
    {
        if (args.Status != SpeechRecognitionResultStatus.Success)
        {
            RecognitionFailed?.Invoke(this, new InvalidOperationException($"Windows speech command recognition stopped: {args.Status}."));
        }
    }

    private void StopDictation()
    {
        var recognizer = _dictationRecognizer;
        _dictationRecognizer = null;
        recognizer?.Dispose();
    }

    private void ThrowIfDisposed()
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
    }
}
