using System.Collections.ObjectModel;
using System.Text.Json.Nodes;
using Humungousaur.App.Models;
using Humungousaur.App.Services;
using Microsoft.UI;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Windows.System;

namespace Humungousaur.App;

public sealed partial class MainWindow : Window
{
    private readonly AppSettingsStore _settingsStore = new();
    private readonly AgentApiClient _api = new();
    private readonly LocalAgentProcess _agentProcess = new();
    private readonly VoiceWakeService _voiceWakeService = new();
    private readonly DispatcherTimer _autonomyTimer = new();
    private readonly DispatcherTimer _channelListenerTimer = new();
    private readonly ObservableCollection<ChatLogItem> _chat = [];
    private readonly ObservableCollection<string> _processLines = [];
    private AppSettings _settings = new();
    private List<ChannelInfo> _channels = [];
    private List<ToolInfo> _tools = [];
    private List<RuntimeRunItem> _runs = [];
    private List<ApprovalItem> _approvals = [];
    private string _latestDownloadUrl = "";
    private string _lastHandledVoiceTranscript = "";
    private string _activeVoiceRunId = "";
    private bool _autonomyCycleRunning;
    private bool _channelListenerTickRunning;
    private bool _voiceWakeIsAwake;
    private bool _voiceWakePausedForResponse;
    private bool _isCapturingVoiceTask;
    private bool _applyingSettingsToUi;
    private int _voiceAcknowledgementIndex;
    private CancellationTokenSource? _activeVoiceResponseCts;

    public MainWindow()
    {
        InitializeComponent();
        SystemBackdrop = new MicaBackdrop();
        ExtendsContentIntoTitleBar = true;
        AppWindow.SetIcon(Path.Combine(AppContext.BaseDirectory, "Assets", "Humungousaur.ico"));
        SetTitleBar(AppTitleBar);

        RootGrid.Loaded += RootGrid_Loaded;
        ChatLog.ItemsSource = _chat;
        ProcessLog.ItemsSource = _processLines;
        _agentProcess.OutputReceived += line => DispatcherQueue.TryEnqueue(() => AddProcessLine(line));
        _autonomyTimer.Tick += AutonomyTimer_Tick;
        _channelListenerTimer.Tick += ChannelListenerTimer_Tick;
        _voiceWakeService.RecognitionUpdated += VoiceWakeService_RecognitionUpdated;
        _voiceWakeService.RecognitionFailed += VoiceWakeService_RecognitionFailed;
    }

    private async void RootGrid_Loaded(object sender, RoutedEventArgs e)
    {
        _settings = _settingsStore.Load();
        ApplySettingsToUi();
        ShellNav.SelectedItem = FirstNavigationItem("assistant");
        ShowPage("assistant");
        AddChat("Humungousaur", "Native shell ready. Connect to the local agent or start it from Runtime.", "assistant");
        await RefreshAllAsync();
        if (_settings.VoiceWakeEnabled)
        {
            await SetVoiceWakeEnabledAsync(true, persist: false);
        }
    }

    private async void RefreshButton_Click(object sender, RoutedEventArgs e) => await RefreshAllAsync();

    private async Task RefreshAllAsync()
    {
        ReadSettingsFromUi();
        _api.SetBaseUrl(_settings.ApiBaseUrl);
        await RefreshHealthAsync();
        await RefreshChannelsAsync();
        await RefreshVoiceAsync();
        await RefreshToolsAsync();
        await RefreshAutonomyAsync();
        await RefreshOutboxAsync();
        await RefreshRuntimeAsync();
        await RefreshUpdateAsync();
    }

    private async Task RefreshHealthAsync()
    {
        try
        {
            var health = await _api.GetHealthAsync();
            var workspace = health["workspace"]?.GetValue<string>() ?? _settings.WorkspacePath;
            RuntimeSummaryText.Text = $"API online at {_settings.ApiBaseUrl}";
            WorkspaceCaption.Text = ShortenPath(workspace);
            SetStatus(true, "Online");
        }
        catch (Exception exc)
        {
            RuntimeSummaryText.Text = $"API offline at {_settings.ApiBaseUrl}";
            SetStatus(false, "Offline");
            AddProcessLine(exc.Message);
        }
    }

    private async Task RefreshChannelsAsync()
    {
        try
        {
            _channels = await _api.GetChannelsAsync();
            ChannelList.ItemsSource = _channels;
            ChannelCountText.Text = $"Channels {_channels.Count}";
            if (_channels.Count > 0 && ChannelList.SelectedIndex < 0)
            {
                ChannelList.SelectedIndex = 0;
            }
        }
        catch (Exception exc)
        {
            ChannelCountText.Text = "Channels offline";
            AddProcessLine(exc.Message);
        }
    }

    private async Task RefreshVoiceAsync()
    {
        try
        {
            var voice = await _api.GetVoiceStatusAsync(_settings);
            var deepgramConfigured = voice["stt"]?["deepgram"]?["configured"]?.GetValue<bool>() == true;
            var elevenConfigured = voice["tts"]?["elevenlabs"]?["configured"]?.GetValue<bool>() == true;
            var systemConfigured = voice["tts"]?["system"]?["configured"]?.GetValue<bool>() == true;
            DeepgramStatusText.Text = deepgramConfigured ? "Deepgram configured" : "Deepgram key missing";
            ElevenLabsStatusText.Text = elevenConfigured ? "ElevenLabs configured" : "ElevenLabs key missing";
            SystemVoiceStatusText.Text = systemConfigured ? "Windows SAPI available" : "System speech unavailable";
            VoiceReadyText.Text = $"Voice {(deepgramConfigured && (elevenConfigured || systemConfigured) ? "ready" : "partial")}";
        }
        catch (Exception exc)
        {
            VoiceReadyText.Text = "Voice offline";
            AddProcessLine(exc.Message);
        }
    }

    private async Task RefreshToolsAsync()
    {
        try
        {
            var catalog = await _api.GetToolsAsync();
            _tools = catalog.Tools;
            ToolCountText.Text = $"Tools {catalog.ToolCount}";
            ToolsSummaryText.Text = $"{catalog.ToolCount} tools across {catalog.Groups.Count} groups";
            ToolGroupList.ItemsSource = catalog.Groups.Select(group => $"{group.Name}  {group.ToolCount}").ToList();
            RenderTools();
        }
        catch (Exception exc)
        {
            ToolCountText.Text = "Tools offline";
            AddProcessLine(exc.Message);
        }
    }

    private async Task RefreshAutonomyAsync()
    {
        try
        {
            var status = await _api.GetAutonomousStatusAsync();
            AutonomyStatusText.Text = AgentApiClient.Pretty(status);
            AutonomyReadyText.Text = "Loop ready";
        }
        catch (Exception exc)
        {
            AutonomyReadyText.Text = "Loop offline";
            AutonomyStatusText.Text = exc.Message;
        }
    }

    private async Task RefreshOutboxAsync()
    {
        try
        {
            var outbox = await _api.GetOutboxAsync();
            OutboxList.ItemsSource = outbox.Messages
                .Select(message =>
                {
                    var channel = message["channel_id"]?.GetValue<string>() ?? "channel";
                    var text = message["text"]?.GetValue<string>() ?? message.ToJsonString();
                    return $"{channel}: {text}";
                })
                .ToList();
        }
        catch (Exception exc)
        {
            AddProcessLine(exc.Message);
        }
    }

    private async Task RefreshRuntimeAsync()
    {
        try
        {
            _runs = await _api.GetRunsAsync();
            _approvals = await _api.GetApprovalsAsync();
            RuntimeRunList.ItemsSource = _runs;
            ApprovalList.ItemsSource = _approvals;
            if (_approvals.Count > 0 && ApprovalList.SelectedIndex < 0)
            {
                ApprovalList.SelectedIndex = 0;
            }
            else if (_runs.Count > 0 && RuntimeRunList.SelectedIndex < 0)
            {
                RuntimeRunList.SelectedIndex = 0;
            }
            RuntimeDetailText.Text = $"Runs {_runs.Count}; pending approvals {_approvals.Count}.";
        }
        catch (Exception exc)
        {
            RuntimeDetailText.Text = exc.Message;
            AddProcessLine(exc.Message);
        }
    }

    private async Task RefreshUpdateAsync()
    {
        try
        {
            var update = await _api.GetLatestUpdateAsync();
            _latestDownloadUrl = update.DownloadUrl;
            UpdateStatusText.Text = update.StatusText;
            OpenDownloadButton.IsEnabled = !string.IsNullOrWhiteSpace(_latestDownloadUrl);
        }
        catch (Exception exc)
        {
            _latestDownloadUrl = "";
            UpdateStatusText.Text = exc.Message;
            OpenDownloadButton.IsEnabled = false;
        }
    }

    private async void SendButton_Click(object sender, RoutedEventArgs e)
    {
        var text = PromptBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(text))
        {
            ShowNotice("Nothing to send.", InfoBarSeverity.Warning);
            return;
        }

        ReadSettingsFromUi();
        var source = ComboTag(StimulusSourceBox, "user_text");
        var responseMode = ComboTag(ResponseModeBox, "text");
        AddChat("You", text, "user");
        PromptBox.Text = "";

        try
        {
            AddChat("Thinking", "Connected to the live agent stream.", "activity");
            await foreach (var streamEvent in _api.StreamStimulusAsync(text, source, responseMode, _settings))
            {
                ApplyStreamEvent(streamEvent);
            }
            await RefreshAutonomyAsync();
            await RefreshRuntimeAsync();
        }
        catch (Exception exc)
        {
            AddChat("Humungousaur", exc.Message, "error");
            ShowNotice("The agent request failed.", InfoBarSeverity.Error);
        }
    }

    private void QuickSystemButton_Click(object sender, RoutedEventArgs e)
    {
        PromptBox.Text = "Check local system status using the available system status tool.";
    }

    private void QuickAutonomyButton_Click(object sender, RoutedEventArgs e)
    {
        ShowPage("autonomy");
    }

    private void QuickChannelsButton_Click(object sender, RoutedEventArgs e)
    {
        ShowPage("channels");
    }

    private async void StartAgentButton_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            ReadSettingsFromUi();
            _settingsStore.Save(_settings);
            _agentProcess.Start(_settings);
            AddProcessLine("Starting local agent process.");
            await Task.Delay(900);
            await RefreshAllAsync();
        }
        catch (Exception exc)
        {
            ShowNotice(exc.Message, InfoBarSeverity.Error);
            AddProcessLine(exc.Message);
        }
    }

    private void StopAgentButton_Click(object sender, RoutedEventArgs e)
    {
        _agentProcess.Stop();
        SetStatus(false, "Stopped");
        AddProcessLine("Stop requested.");
    }

    private void ChannelList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (ChannelList.SelectedItem is not ChannelInfo channel)
        {
            return;
        }

        var setup = SetupFor(channel.ChannelId);
        ApplyChannelSetupDefaults(channel, setup);
        RenderChannelRequirements(channel);
        ChannelDoctorText.Text = "Run doctor after saving setup or entering runtime secrets.";
        ChannelSmokeText.Text = "Run smoke to prepare an envelope and validate dry-run send wiring.";
        ChannelTitleText.Text = channel.DisplayName;
        ChannelCapabilityText.Text = $"{channel.Transport}; text {(channel.SupportsText ? "yes" : "no")}; media {(channel.SupportsMedia ? "yes" : "no")}; reactions {(channel.SupportsReactions ? "yes" : "no")}";
        ChannelEnabledSwitch.IsOn = setup.Enabled;
        ChannelListenSwitch.IsOn = setup.ListenEnabled;
        ConversationIdBox.Text = setup.ConversationId;
        SecretNameBox.Text = setup.SecretName;
        ChannelSecretBox.Password = setup.SecretValue;
        ChannelSecretsBox.Text = SerializeSecretLines(setup.SecretValues);
        ChannelAllowlistBox.Text = SerializeListLines(setup.Allowlist);
        ChannelGroupAllowlistBox.Text = SerializeListLines(setup.GroupAllowlist);
        ChannelOutboundTextBox.Text = "";
        ChannelNotesBox.Text = setup.Notes;
        SetComboByTag(ConversationTypeBox, setup.ConversationType);
        _ = RefreshSelectedChannelRequirementsAsync(channel);
        _ = RefreshSelectedChannelStatusAsync(channel.ChannelId);
    }

    private async void SaveChannelButton_Click(object sender, RoutedEventArgs e)
    {
        if (ChannelList.SelectedItem is not ChannelInfo channel)
        {
            ShowNotice("Select a channel first.", InfoBarSeverity.Warning);
            return;
        }

        var setup = SetupFor(channel.ChannelId);
        setup.Enabled = ChannelEnabledSwitch.IsOn;
        setup.ListenEnabled = ChannelListenSwitch.IsOn;
        setup.ConversationId = ConversationIdBox.Text.Trim();
        setup.ConversationType = ComboTag(ConversationTypeBox, "dm");
        setup.SecretName = SecretNameBox.Text.Trim();
        setup.SecretValue = ChannelSecretBox.Password;
        setup.SecretValues = ParseSecretLines(ChannelSecretsBox.Text);
        setup.Allowlist = ParseListLines(ChannelAllowlistBox.Text);
        setup.GroupAllowlist = ParseListLines(ChannelGroupAllowlistBox.Text);
        setup.SecretConfigured = setup.SecretConfigured
            || !string.IsNullOrWhiteSpace(setup.SecretValue)
            || setup.SecretValues.Values.Any(value => !string.IsNullOrWhiteSpace(value));
        setup.Notes = ChannelNotesBox.Text.Trim();
        _settingsStore.Save(_settings);
        try
        {
            await _api.SaveChannelSetupAsync(channel, setup);
            await RefreshSelectedChannelStatusAsync(channel.ChannelId);
            ShowNotice($"{channel.DisplayName} setup saved.", InfoBarSeverity.Success);
        }
        catch (Exception exc)
        {
            ChannelStatusText.Text = exc.Message;
            ShowNotice("Local setup saved, but backend setup sync failed.", InfoBarSeverity.Warning);
        }
    }

    private async void TestChannelButton_Click(object sender, RoutedEventArgs e)
    {
        if (ChannelList.SelectedItem is not ChannelInfo channel)
        {
            ShowNotice("Select a channel first.", InfoBarSeverity.Warning);
            return;
        }

        try
        {
            ReadSettingsFromUi();
            var setup = SetupFor(channel.ChannelId);
            var result = await _api.SendChannelInboundAsync(channel, setup, "system_status {}", _settings);
            ShowNotice("Inbound preview prepared.", InfoBarSeverity.Success);
            AddChat(channel.DisplayName, result["prepared_reply"]?["text"]?.GetValue<string>() ?? AgentApiClient.Pretty(result), "channel");
            await RefreshOutboxAsync();
        }
        catch (Exception exc)
        {
            ShowNotice(exc.Message, InfoBarSeverity.Error);
        }
    }

    private async void RefreshOutboxButton_Click(object sender, RoutedEventArgs e) => await RefreshOutboxAsync();

    private async void RefreshListenersButton_Click(object sender, RoutedEventArgs e)
    {
        if (ChannelList.SelectedItem is ChannelInfo channel)
        {
            await RefreshSelectedChannelStatusAsync(channel.ChannelId);
        }
    }

    private async void RunChannelDoctorButton_Click(object sender, RoutedEventArgs e)
    {
        if (ChannelList.SelectedItem is not ChannelInfo channel)
        {
            ShowNotice("Select a channel first.", InfoBarSeverity.Warning);
            return;
        }

        try
        {
            ReadSettingsFromUi();
            var doctor = await _api.GetChannelDoctorAsync(channel.ChannelId, _settings);
            ChannelDoctorText.Text = FormatDoctorFindings(doctor);
            var warnings = doctor["findings"]?.AsArray().Count(item => item?["severity"]?.GetValue<string>() == "warning") ?? 0;
            ShowNotice(warnings == 0 ? $"{channel.DisplayName} doctor is clean." : $"{channel.DisplayName} doctor found {warnings} warning(s).", warnings == 0 ? InfoBarSeverity.Success : InfoBarSeverity.Warning);
        }
        catch (Exception exc)
        {
            ChannelDoctorText.Text = exc.Message;
            ShowNotice("Channel doctor failed.", InfoBarSeverity.Error);
        }
    }

    private async void RunChannelSmokeButton_Click(object sender, RoutedEventArgs e)
    {
        if (ChannelList.SelectedItem is not ChannelInfo channel)
        {
            ShowNotice("Select a channel first.", InfoBarSeverity.Warning);
            return;
        }

        try
        {
            ReadSettingsFromUi();
            var smoke = await _api.RunChannelSmokeAsync(channel.ChannelId, _settings);
            ChannelSmokeText.Text = FormatChannelSmoke(smoke);
            var readiness = smoke["channels"]?.AsArray().FirstOrDefault()?["readiness"]?.GetValue<string>() ?? smoke["overall_status"]?.GetValue<string>() ?? "unknown";
            ShowNotice($"{channel.DisplayName} smoke: {readiness}.", readiness == "ready" ? InfoBarSeverity.Success : InfoBarSeverity.Warning);
            await RefreshOutboxAsync();
            await RefreshSelectedChannelStatusAsync(channel.ChannelId);
        }
        catch (Exception exc)
        {
            ChannelSmokeText.Text = exc.Message;
            ShowNotice("Channel smoke failed.", InfoBarSeverity.Error);
        }
    }

    private async void TickChannelButton_Click(object sender, RoutedEventArgs e)
    {
        if (ChannelList.SelectedItem is not ChannelInfo channel)
        {
            ShowNotice("Select a channel first.", InfoBarSeverity.Warning);
            return;
        }

        try
        {
            ReadSettingsFromUi();
            var result = await _api.TickChannelListenerAsync(channel, _settings);
            var processed = result["processed_count"]?.GetValue<int>() ?? 0;
            ChannelListenerText.Text = $"Listener tick processed {processed} event(s).";
            ShowNotice($"Listener tick processed {processed} event(s).", InfoBarSeverity.Success);
            await RefreshOutboxAsync();
            await RefreshSelectedChannelStatusAsync(channel.ChannelId);
        }
        catch (Exception exc)
        {
            ChannelListenerText.Text = exc.Message;
            ShowNotice("Listener tick failed.", InfoBarSeverity.Error);
        }
    }

    private async void TickAllChannelsButton_Click(object sender, RoutedEventArgs e)
    {
        await RunChannelListenerTickAsync(showNotice: true);
    }

    private async Task RunChannelListenerTickAsync(bool showNotice)
    {
        if (_channelListenerTickRunning)
        {
            return;
        }

        try
        {
            _channelListenerTickRunning = true;
            ReadSettingsFromUi();
            var result = await _api.TickAllChannelListenersAsync(_settings);
            var processed = result["processed_count"]?.GetValue<int>() ?? 0;
            var notes = result["listener_notes"]?.AsArray().Count ?? 0;
            ChannelListenLoopText.Text = $"Last tick processed {processed} event(s); {notes} listener note(s).";
            if (showNotice)
            {
                ShowNotice($"Channel listener tick processed {processed} event(s).", InfoBarSeverity.Success);
            }
            await RefreshOutboxAsync();
            if (ChannelList.SelectedItem is ChannelInfo channel)
            {
                await RefreshSelectedChannelStatusAsync(channel.ChannelId);
            }
        }
        catch (Exception exc)
        {
            ChannelListenLoopText.Text = exc.Message;
            if (showNotice)
            {
                ShowNotice("Channel listener tick failed.", InfoBarSeverity.Error);
            }
        }
        finally
        {
            _channelListenerTickRunning = false;
        }
    }

    private async void ChannelListenerTimer_Tick(object? sender, object e)
    {
        await RunChannelListenerTickAsync(showNotice: false);
    }

    private void ContinuousChannelListenSwitch_Toggled(object sender, RoutedEventArgs e)
    {
        if (ContinuousChannelListenSwitch.IsOn)
        {
            var seconds = int.TryParse(ChannelListenIntervalBox.Text, out var parsed) ? Math.Max(10, parsed) : 30;
            _channelListenerTimer.Interval = TimeSpan.FromSeconds(seconds);
            _channelListenerTimer.Start();
            ChannelListenLoopText.Text = $"Listening loop running every {seconds} seconds.";
            ShowNotice($"Channel listening loop running every {seconds} seconds.", InfoBarSeverity.Success);
        }
        else
        {
            _channelListenerTimer.Stop();
            ChannelListenLoopText.Text = "Listening loop stopped.";
            ShowNotice("Channel listening loop stopped.", InfoBarSeverity.Informational);
        }
    }

    private async void PrepareOutboundButton_Click(object sender, RoutedEventArgs e)
    {
        if (ChannelList.SelectedItem is not ChannelInfo channel)
        {
            ShowNotice("Select a channel first.", InfoBarSeverity.Warning);
            return;
        }

        var text = ChannelOutboundTextBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(text))
        {
            ShowNotice("Write an outbound message first.", InfoBarSeverity.Warning);
            return;
        }

        try
        {
            ReadSettingsFromUi();
            var setup = SetupFor(channel.ChannelId);
            var result = await _api.PrepareChannelMessageAsync(channel, setup, text, _settings);
            var status = result["message"]?["status"]?.GetValue<string>() ?? "prepared";
            ShowNotice($"Outbound message {status}.", InfoBarSeverity.Success);
            await RefreshOutboxAsync();
        }
        catch (Exception exc)
        {
            ShowNotice(exc.Message, InfoBarSeverity.Error);
        }
    }

    private async void SendOutboundButton_Click(object sender, RoutedEventArgs e)
    {
        if (ChannelList.SelectedItem is not ChannelInfo channel)
        {
            ShowNotice("Select a channel first.", InfoBarSeverity.Warning);
            return;
        }

        var text = ChannelOutboundTextBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(text))
        {
            ShowNotice("Write an outbound message first.", InfoBarSeverity.Warning);
            return;
        }

        try
        {
            ReadSettingsFromUi();
            if (!_settings.ApproveHighRisk)
            {
                ShowNotice("Enable high-risk approval in Settings before live channel sends.", InfoBarSeverity.Warning);
                return;
            }
            var setup = SetupFor(channel.ChannelId);
            var result = await _api.SendChannelMessageAsync(channel, setup, text, _settings);
            var status = result["message"]?["status"]?.GetValue<string>() ?? "unknown";
            ShowNotice($"Channel send result: {status}.", status == "sent" ? InfoBarSeverity.Success : InfoBarSeverity.Warning);
            await RefreshOutboxAsync();
            await RefreshSelectedChannelStatusAsync(channel.ChannelId);
        }
        catch (Exception exc)
        {
            ShowNotice(exc.Message, InfoBarSeverity.Error);
        }
    }

    private async void SaveVoiceButton_Click(object sender, RoutedEventArgs e)
    {
        ReadSettingsFromUi();
        _settingsStore.Save(_settings);
        if (_settings.VoiceWakeEnabled)
        {
            await RestartVoiceWakeListenerAsync();
        }
        ShowNotice("Voice settings saved.", InfoBarSeverity.Success);
    }

    private async void RefreshVoiceButton_Click(object sender, RoutedEventArgs e) => await RefreshVoiceAsync();

    private async void SpeakTestButton_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            ReadSettingsFromUi();
            await _api.SendStimulusAsync(VoiceTestBox.Text, "voice_transcript", "voice_speak", _settings);
            ShowNotice("Voice test sent.", InfoBarSeverity.Success);
        }
        catch (Exception exc)
        {
            ShowNotice(exc.Message, InfoBarSeverity.Error);
        }
    }

    private async void StopVoiceButton_Click(object sender, RoutedEventArgs e)
    {
        await StopCurrentVoiceResponseAsync();
    }

    private async void VoiceWakeSwitch_Toggled(object sender, RoutedEventArgs e)
    {
        if (_settings is null)
        {
            return;
        }
        if (_applyingSettingsToUi)
        {
            return;
        }
        ReadSettingsFromUi();
        await SetVoiceWakeEnabledAsync(VoiceWakeSwitch.IsOn, persist: true);
    }

    private void VoiceWakeService_RecognitionUpdated(object? sender, VoiceRecognitionUpdate update)
    {
        DispatcherQueue.TryEnqueue(() => HandleVoiceRecognitionUpdate(update));
    }

    private void VoiceWakeService_RecognitionFailed(object? sender, Exception exc)
    {
        DispatcherQueue.TryEnqueue(() =>
        {
            VoiceWakeStatusText.Text = $"Voice listener issue: {exc.Message}";
            AddProcessLine(exc.Message);
        });
    }

    private async Task SetVoiceWakeEnabledAsync(bool enabled, bool persist)
    {
        _settings.VoiceWakeEnabled = enabled;
        VoiceWakeSwitch.IsOn = enabled;
        _lastHandledVoiceTranscript = "";
        _voiceWakeIsAwake = false;
        if (persist)
        {
            _settingsStore.Save(_settings);
        }

        if (!enabled)
        {
            await _voiceWakeService.StopAllAsync();
            VoiceWakeStatusText.Text = "Voice wake-up is off.";
            ShowNotice("Voice wake-up stopped.", InfoBarSeverity.Informational);
            return;
        }

        try
        {
            await _voiceWakeService.StartCommandsAsync(WakeCommandList());
            VoiceWakeStatusText.Text = $"Listening for {string.Join(", ", WakePhraseList())}.";
            ShowNotice("Voice wake-up is listening.", InfoBarSeverity.Success);
        }
        catch (Exception exc)
        {
            _settings.VoiceWakeEnabled = false;
            VoiceWakeSwitch.IsOn = false;
            VoiceWakeStatusText.Text = exc.Message;
            ShowNotice("Voice wake-up failed.", InfoBarSeverity.Error);
            if (persist)
            {
                _settingsStore.Save(_settings);
            }
        }
    }

    private async Task RestartVoiceWakeListenerAsync()
    {
        await _voiceWakeService.StopAllAsync();
        _lastHandledVoiceTranscript = "";
        _voiceWakeIsAwake = false;
        if (!_settings.VoiceWakeEnabled)
        {
            VoiceWakeStatusText.Text = "Voice wake-up is off.";
            return;
        }
        try
        {
            await _voiceWakeService.StartCommandsAsync(WakeCommandList());
            VoiceWakeStatusText.Text = $"Listening for {string.Join(", ", WakePhraseList())}.";
        }
        catch (Exception exc)
        {
            _settings.VoiceWakeEnabled = false;
            VoiceWakeSwitch.IsOn = false;
            VoiceWakeStatusText.Text = exc.Message;
            _settingsStore.Save(_settings);
        }
    }

    private void HandleVoiceRecognitionUpdate(VoiceRecognitionUpdate update)
    {
        var transcript = update.Transcript.Trim();
        if (string.IsNullOrWhiteSpace(transcript))
        {
            return;
        }
        VoiceWakeTranscriptText.Text = transcript;

        if (_voiceWakePausedForResponse)
        {
            if (IsStopPhrase(transcript))
            {
                _ = StopCurrentVoiceResponseAsync();
            }
            return;
        }

        var command = CommandAfterWakePhrase(transcript);
        if (command is not null)
        {
            _voiceWakeIsAwake = true;
            if (string.IsNullOrWhiteSpace(command))
            {
                StartVoiceTaskCapture(acknowledge: true);
                return;
            }
            _ = SubmitVoiceCommandAsync(command, keepListening: true);
            return;
        }

        if (!_voiceWakeIsAwake)
        {
            VoiceWakeStatusText.Text = "Heard background speech; waiting for wake phrase.";
            return;
        }

        _ = SubmitVoiceCommandAsync(transcript, keepListening: true);
    }

    private void StartVoiceTaskCapture(bool acknowledge)
    {
        if (_voiceWakePausedForResponse)
        {
            return;
        }
        if (_isCapturingVoiceTask)
        {
            VoiceWakeStatusText.Text = "Listening for your task...";
            return;
        }

        _isCapturingVoiceTask = true;
        _voiceWakeIsAwake = true;
        var acknowledgement = NextVoiceAcknowledgement();
        VoiceWakeStatusText.Text = $"{(acknowledge ? acknowledgement + ". " : "")}Listening for your task...";
        _ = Task.Run(async () =>
        {
            try
            {
                await _voiceWakeService.StopCommandsAsync();
                if (acknowledge)
                {
                    _voiceWakeService.SpeakAcknowledgement(acknowledgement);
                    await Task.Delay(900);
                }
                var transcript = await _voiceWakeService.TranscribeTaskAsync(
                    new VoiceActivityOptions(),
                    partial => DispatcherQueue.TryEnqueue(() =>
                    {
                        VoiceWakeTranscriptText.Text = partial;
                        VoiceWakeStatusText.Text = $"Hearing: {partial}";
                    }));
                DispatcherQueue.TryEnqueue(() =>
                {
                    VoiceWakeTranscriptText.Text = transcript;
                    VoiceWakeStatusText.Text = $"Heard: {transcript}";
                    _ = SubmitVoiceCommandAsync(transcript, keepListening: true);
                });
            }
            catch (Exception exc)
            {
                DispatcherQueue.TryEnqueue(async () =>
                {
                    VoiceWakeStatusText.Text = $"I did not catch that. {exc.Message}";
                    _voiceWakeIsAwake = false;
                    await ResumeWakeDetectionAsync();
                });
            }
            finally
            {
                DispatcherQueue.TryEnqueue(() => _isCapturingVoiceTask = false);
            }
        });
    }

    private async Task SubmitVoiceCommandAsync(string command, bool keepListening)
    {
        var trimmed = command.Trim();
        if (string.IsNullOrWhiteSpace(trimmed))
        {
            return;
        }
        var normalized = NormalizeSpeech(trimmed);
        if (normalized == _lastHandledVoiceTranscript)
        {
            return;
        }
        _lastHandledVoiceTranscript = normalized;
        ShowPage("assistant");
        AddChat("Voice", trimmed, "user");
        VoiceWakeStatusText.Text = "Voice task sent.";
        await PauseVoiceListeningForResponseAsync();

        _activeVoiceResponseCts?.Cancel();
        _activeVoiceResponseCts = new CancellationTokenSource();
        _activeVoiceRunId = "";
        try
        {
            await foreach (var streamEvent in _api.StreamStimulusAsync(trimmed, "voice_transcript", "voice_speak", _settings, _activeVoiceResponseCts.Token))
            {
                ApplyStreamEvent(streamEvent);
            }
            await RefreshAutonomyAsync();
            await RefreshRuntimeAsync();
        }
        catch (OperationCanceledException)
        {
            AddChat("Humungousaur", "Stopped.", "activity");
        }
        catch (Exception exc)
        {
            AddChat("Humungousaur", exc.Message, "error");
            ShowNotice("The voice request failed.", InfoBarSeverity.Error);
        }
        finally
        {
            _activeVoiceResponseCts?.Dispose();
            _activeVoiceResponseCts = null;
            _activeVoiceRunId = "";
            _voiceWakePausedForResponse = false;
            if (keepListening && _settings.VoiceContinuousAfterWake)
            {
                ScheduleNextVoiceCapture();
            }
            else
            {
                _voiceWakeIsAwake = false;
                await ResumeWakeDetectionAsync();
            }
        }
    }

    private async Task PauseVoiceListeningForResponseAsync()
    {
        _voiceWakePausedForResponse = true;
        _isCapturingVoiceTask = false;
        await _voiceWakeService.StopAllAsync();
        try
        {
            await _voiceWakeService.StartCommandsAsync(StopCommandList());
            VoiceWakeStatusText.Text = $"Responding. Say {StopPhraseList().FirstOrDefault() ?? "stop humungousaur"} to stop.";
        }
        catch (Exception exc)
        {
            VoiceWakeStatusText.Text = $"Responding. Stop phrase unavailable: {exc.Message}";
        }
    }

    private async Task StopCurrentVoiceResponseAsync()
    {
        _activeVoiceResponseCts?.Cancel();
        _voiceWakeService.StopAcknowledgement();
        if (!string.IsNullOrWhiteSpace(_activeVoiceRunId))
        {
            try
            {
                await _api.CancelRunAsync(_activeVoiceRunId, "Voice stop phrase.");
            }
            catch (Exception exc)
            {
                AddProcessLine(exc.Message);
            }
        }
        try
        {
            await _api.StopVoicePlaybackAsync(_settings);
        }
        catch (Exception exc)
        {
            AddProcessLine(exc.Message);
        }
        _voiceWakePausedForResponse = false;
        _voiceWakeIsAwake = false;
        VoiceWakeStatusText.Text = "Response stopped.";
        await ResumeWakeDetectionAsync();
    }

    private void ScheduleNextVoiceCapture()
    {
        if (!_settings.VoiceWakeEnabled || !_settings.VoiceContinuousAfterWake || !_voiceWakeIsAwake || _voiceWakePausedForResponse)
        {
            return;
        }
        _ = Task.Run(async () =>
        {
            await Task.Delay(1500);
            DispatcherQueue.TryEnqueue(() => StartVoiceTaskCapture(acknowledge: false));
        });
    }

    private async Task ResumeWakeDetectionAsync()
    {
        if (!_settings.VoiceWakeEnabled)
        {
            _voiceWakePausedForResponse = false;
            VoiceWakeStatusText.Text = "Voice wake-up is off.";
            return;
        }
        try
        {
            await _voiceWakeService.StartCommandsAsync(WakeCommandList());
            _voiceWakePausedForResponse = false;
            VoiceWakeStatusText.Text = $"Listening for {string.Join(", ", WakePhraseList())}.";
        }
        catch (Exception exc)
        {
            _settings.VoiceWakeEnabled = false;
            VoiceWakeSwitch.IsOn = false;
            _voiceWakePausedForResponse = false;
            VoiceWakeStatusText.Text = exc.Message;
            _settingsStore.Save(_settings);
        }
    }

    private string NextVoiceAcknowledgement()
    {
        var options = new[] { "Hey buddy", "Hey champ", "Hey there", "I'm listening" };
        var value = options[_voiceAcknowledgementIndex % options.Length];
        _voiceAcknowledgementIndex++;
        return value;
    }

    private string? CommandAfterWakePhrase(string transcript)
    {
        var normalized = NormalizeSpeech(transcript);
        foreach (var phrase in WakePhraseList())
        {
            var cleanPhrase = NormalizeSpeech(phrase);
            var index = normalized.IndexOf(cleanPhrase, StringComparison.OrdinalIgnoreCase);
            if (cleanPhrase.Length == 0 || index < 0)
            {
                continue;
            }
            return normalized[(index + cleanPhrase.Length)..].Trim();
        }
        return null;
    }

    private IReadOnlyList<string> WakePhraseList() => SplitPhrases(_settings.VoiceWakePhrases);

    private IReadOnlyList<string> StopPhraseList() => SplitPhrases(_settings.VoiceStopPhrases);

    private IReadOnlyList<string> WakeCommandList()
    {
        var phrases = WakePhraseList();
        var smokeCommands = new[] { "system status", "what is your system status", "are you online", "say you are online" };
        return phrases.Concat(phrases.SelectMany(phrase => smokeCommands.Select(command => $"{phrase} {command}")))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    private IReadOnlyList<string> StopCommandList()
    {
        var phrases = StopPhraseList();
        return phrases.Count == 0 ? ["stop humungousaur"] : phrases.Distinct(StringComparer.OrdinalIgnoreCase).ToList();
    }

    private bool IsStopPhrase(string transcript)
    {
        var normalized = NormalizeSpeech(transcript);
        return StopCommandList().Any(phrase => normalized.Contains(NormalizeSpeech(phrase), StringComparison.OrdinalIgnoreCase));
    }

    private static IReadOnlyList<string> SplitPhrases(string phrases)
    {
        return phrases
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .ToList();
    }

    private static string NormalizeSpeech(string value)
    {
        var normalized = new string(value.ToLowerInvariant().Select(ch => char.IsLetterOrDigit(ch) ? ch : ' ').ToArray());
        return string.Join(" ", normalized.Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries));
    }

    private async void RunCycleButton_Click(object sender, RoutedEventArgs e)
    {
        await RunAutonomyCycleAsync(showNotice: true);
    }

    private async Task RunAutonomyCycleAsync(bool showNotice)
    {
        if (_autonomyCycleRunning)
        {
            return;
        }

        try
        {
            _autonomyCycleRunning = true;
            ReadSettingsFromUi();
            var maxCycles = int.TryParse(MaxCyclesBox.Text, out var parsed) ? Math.Max(1, parsed) : 1;
            var result = await _api.RunAutonomousCycleAsync(_settings, AllowInitiativeSwitch.IsOn, maxCycles);
            AutonomyStatusText.Text = AgentApiClient.Pretty(result);
            if (showNotice)
            {
                ShowNotice("Autonomy cycle completed.", InfoBarSeverity.Success);
            }
        }
        catch (Exception exc)
        {
            ShowNotice(exc.Message, InfoBarSeverity.Error);
        }
        finally
        {
            _autonomyCycleRunning = false;
        }
    }

    private async void AutonomyTimer_Tick(object? sender, object e)
    {
        await RunAutonomyCycleAsync(showNotice: false);
    }

    private void ContinuousLoopSwitch_Toggled(object sender, RoutedEventArgs e)
    {
        if (ContinuousLoopSwitch.IsOn)
        {
            var seconds = int.TryParse(LoopIntervalBox.Text, out var parsed) ? Math.Max(15, parsed) : 60;
            _autonomyTimer.Interval = TimeSpan.FromSeconds(seconds);
            _autonomyTimer.Start();
            ShowNotice($"Continuous autonomy loop running every {seconds} seconds.", InfoBarSeverity.Success);
        }
        else
        {
            _autonomyTimer.Stop();
            ShowNotice("Continuous autonomy loop stopped.", InfoBarSeverity.Informational);
        }
    }

    private async void RefreshAutonomyButton_Click(object sender, RoutedEventArgs e) => await RefreshAutonomyAsync();

    private async void RefreshRuntimeButton_Click(object sender, RoutedEventArgs e) => await RefreshRuntimeAsync();

    private async void RuntimeRunList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (RuntimeRunList.SelectedItem is not RuntimeRunItem run)
        {
            return;
        }

        try
        {
            var timeline = await _api.GetRunTimelineAsync(run.RunId);
            RuntimeDetailText.Text = FormatRunDetail(run, timeline);
        }
        catch (Exception exc)
        {
            RuntimeDetailText.Text = exc.Message;
        }
    }

    private void ApprovalList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (ApprovalList.SelectedItem is ApprovalItem approval)
        {
            RuntimeDetailText.Text = FormatApprovalDetail(approval);
        }
    }

    private async void ApproveSelectedButton_Click(object sender, RoutedEventArgs e)
    {
        if (ApprovalList.SelectedItem is not ApprovalItem approval)
        {
            ShowNotice("Select an approval first.", InfoBarSeverity.Warning);
            return;
        }

        try
        {
            var note = string.IsNullOrWhiteSpace(ApprovalNoteBox.Text) ? "Approved from Windows app." : ApprovalNoteBox.Text.Trim();
            var result = await _api.ApproveAsync(approval.ApprovalToken, note);
            RuntimeDetailText.Text = AgentApiClient.Pretty(result);
            ShowNotice($"Approved {approval.ToolName}.", InfoBarSeverity.Success);
            await RefreshRuntimeAsync();
        }
        catch (Exception exc)
        {
            RuntimeDetailText.Text = exc.Message;
            ShowNotice("Approval failed.", InfoBarSeverity.Error);
        }
    }

    private async void RejectSelectedButton_Click(object sender, RoutedEventArgs e)
    {
        if (ApprovalList.SelectedItem is not ApprovalItem approval)
        {
            ShowNotice("Select an approval first.", InfoBarSeverity.Warning);
            return;
        }

        try
        {
            var note = string.IsNullOrWhiteSpace(ApprovalNoteBox.Text) ? "Rejected from Windows app." : ApprovalNoteBox.Text.Trim();
            var result = await _api.RejectAsync(approval.ApprovalToken, note);
            RuntimeDetailText.Text = AgentApiClient.Pretty(result);
            ShowNotice($"Rejected {approval.ToolName}.", InfoBarSeverity.Warning);
            await RefreshRuntimeAsync();
        }
        catch (Exception exc)
        {
            RuntimeDetailText.Text = exc.Message;
            ShowNotice("Rejection failed.", InfoBarSeverity.Error);
        }
    }

    private async void CancelRunButton_Click(object sender, RoutedEventArgs e)
    {
        if (RuntimeRunList.SelectedItem is not RuntimeRunItem run)
        {
            ShowNotice("Select a run first.", InfoBarSeverity.Warning);
            return;
        }

        try
        {
            var result = await _api.CancelRunAsync(run.RunId, "Cancelled from Windows app.");
            RuntimeDetailText.Text = AgentApiClient.Pretty(result);
            ShowNotice("Run cancellation requested.", InfoBarSeverity.Warning);
            await RefreshRuntimeAsync();
        }
        catch (Exception exc)
        {
            RuntimeDetailText.Text = exc.Message;
            ShowNotice("Run cancellation failed.", InfoBarSeverity.Error);
        }
    }

    private void ToolSearchBox_TextChanged(object sender, TextChangedEventArgs e) => RenderTools();

    private void SaveSettingsButton_Click(object sender, RoutedEventArgs e)
    {
        ReadSettingsFromUi();
        _settingsStore.Save(_settings);
        _api.SetBaseUrl(_settings.ApiBaseUrl);
        ShowNotice("Settings saved.", InfoBarSeverity.Success);
    }

    private async void CheckForUpdatesButton_Click(object sender, RoutedEventArgs e)
    {
        ReadSettingsFromUi();
        _api.SetBaseUrl(_settings.ApiBaseUrl);
        await RefreshUpdateAsync();
        ShowNotice(UpdateStatusText.Text, InfoBarSeverity.Informational);
    }

    private async void OpenDownloadButton_Click(object sender, RoutedEventArgs e)
    {
        if (Uri.TryCreate(_latestDownloadUrl, UriKind.Absolute, out var uri))
        {
            await Launcher.LaunchUriAsync(uri);
        }
    }

    private void ShellNav_SelectionChanged(NavigationView sender, NavigationViewSelectionChangedEventArgs args)
    {
        if (args.SelectedItem is NavigationViewItem item)
        {
            ShowPage(item.Tag?.ToString() ?? "assistant");
        }
    }

    private NavigationViewItem? FirstNavigationItem(string tag)
    {
        return ShellNav.MenuItems
            .OfType<NavigationViewItem>()
            .FirstOrDefault(item => string.Equals(item.Tag?.ToString(), tag, StringComparison.OrdinalIgnoreCase));
    }

    private void ShowPage(string tag)
    {
        AssistantPage.Visibility = tag == "assistant" ? Visibility.Visible : Visibility.Collapsed;
        ChannelsPage.Visibility = tag == "channels" ? Visibility.Visible : Visibility.Collapsed;
        VoicePage.Visibility = tag == "voice" ? Visibility.Visible : Visibility.Collapsed;
        AutonomyPage.Visibility = tag == "autonomy" ? Visibility.Visible : Visibility.Collapsed;
        RuntimePage.Visibility = tag == "runtime" ? Visibility.Visible : Visibility.Collapsed;
        ToolsPage.Visibility = tag == "tools" ? Visibility.Visible : Visibility.Collapsed;
        SettingsPage.Visibility = tag == "settings" ? Visibility.Visible : Visibility.Collapsed;
    }

    private void RenderTools()
    {
        var query = ToolSearchBox.Text.Trim();
        var tools = string.IsNullOrWhiteSpace(query)
            ? _tools
            : _tools.Where(tool =>
                tool.Name.Contains(query, StringComparison.OrdinalIgnoreCase)
                || tool.CapabilityGroup.Contains(query, StringComparison.OrdinalIgnoreCase)
                || tool.Description.Contains(query, StringComparison.OrdinalIgnoreCase)).ToList();
        ToolList.ItemsSource = tools;
    }

    private async Task RefreshSelectedChannelStatusAsync(string channelId)
    {
        try
        {
            var status = await _api.GetChannelStatusAsync(channelId, _settings);
            var channel = status["channels"]?.AsArray().FirstOrDefault()?.AsObject();
            if (channel is null)
            {
                ChannelStatusText.Text = "Backend setup status unavailable.";
                return;
            }

            var readyForSend = channel["ready_for_send"]?.GetValue<bool>() == true;
            var readyForInbound = channel["ready_for_inbound"]?.GetValue<bool>() == true;
            var listenEnabled = channel["listen_enabled"]?.GetValue<bool>() == true;
            var missing = channel["missing_send_env"]?.AsArray()
                .Select(item => item?.GetValue<string>())
                .Where(item => !string.IsNullOrWhiteSpace(item))
                .ToList() ?? [];
            ChannelStatusText.Text = missing.Count == 0
                ? $"Backend setup: send {(readyForSend ? "ready" : "prepared only")}; inbound {(readyForInbound ? "enabled" : listenEnabled ? "waiting" : "paused")}."
                : $"Backend setup: missing {string.Join(", ", missing)}; inbound {(listenEnabled ? "waiting" : "paused")}; prepared outbox is available.";
            await RefreshSelectedChannelListenerAsync(channelId);
        }
        catch (Exception exc)
        {
            ChannelStatusText.Text = exc.Message;
        }
    }

    private async Task RefreshSelectedChannelListenerAsync(string channelId)
    {
        try
        {
            var status = await _api.GetChannelListenersAsync(channelId, _settings);
            var listener = status["listeners"]?.AsArray().FirstOrDefault()?.AsObject();
            if (listener is null)
            {
                ChannelListenerText.Text = "Listener status unavailable.";
                return;
            }

            var ready = listener["ready"]?.GetValue<bool>() == true;
            var listenEnabled = listener["listen_enabled"]?.GetValue<bool>() == true;
            var mode = listener["listener_mode"]?.GetValue<string>() ?? "listener";
            var webhookPath = listener["webhook_path"]?.GetValue<string>() ?? "";
            var missingEnv = listener["missing_env"]?.AsArray()
                .Select(item => item?.GetValue<string>())
                .Where(item => !string.IsNullOrWhiteSpace(item))
                .ToList() ?? [];
            ChannelListenerText.Text = missingEnv.Count == 0
                ? $"Listener: {(ready ? "ready" : listenEnabled ? "waiting" : "paused")} via {mode}; webhook {webhookPath}."
                : $"Listener: missing {string.Join(", ", missingEnv)}; {(listenEnabled ? "waiting" : "paused")}; webhook {webhookPath}.";
        }
        catch (Exception exc)
        {
            ChannelListenerText.Text = exc.Message;
        }
    }

    private async Task RefreshSelectedChannelRequirementsAsync(ChannelInfo channel)
    {
        try
        {
            var requirements = await _api.GetChannelRequirementsAsync(channel.ChannelId);
            ChannelRequirementText.Text = FormatRequirementSummary(requirements);
            ChannelSetupStepsText.Text = FormatSetupSteps(requirements["setup"] as JsonObject);
            ChannelPolicyText.Text = FormatPolicySummary(requirements["policies"] as JsonObject, requirements["delivery"] as JsonObject, requirements["runtime"] as JsonObject);
        }
        catch (Exception exc)
        {
            AddProcessLine(exc.Message);
        }
    }

    private ChannelSetup SetupFor(string channelId)
    {
        var setup = _settings.Channels.FirstOrDefault(item => item.ChannelId == channelId);
        if (setup is not null)
        {
            return setup;
        }

        setup = new ChannelSetup { ChannelId = channelId };
        _settings.Channels.Add(setup);
        return setup;
    }

    private static void ApplyChannelSetupDefaults(ChannelInfo channel, ChannelSetup setup)
    {
        var requiredSecrets = JsonArrayStrings(channel.Setup, "required_secrets");
        var optionalSecrets = JsonArrayStrings(channel.Setup, "optional_secrets");
        var allSecrets = requiredSecrets.Concat(optionalSecrets).Distinct(StringComparer.OrdinalIgnoreCase).ToList();
        if (string.IsNullOrWhiteSpace(setup.SecretName) && requiredSecrets.Count == 1)
        {
            setup.SecretName = requiredSecrets[0];
        }
        foreach (var secret in allSecrets)
        {
            if (!setup.SecretValues.ContainsKey(secret) && !string.Equals(setup.SecretName, secret, StringComparison.OrdinalIgnoreCase))
            {
                setup.SecretValues[secret] = "";
            }
        }
        if (string.IsNullOrWhiteSpace(setup.ConversationType))
        {
            setup.ConversationType = channel.ConversationTypes.FirstOrDefault() ?? "dm";
        }
    }

    private void RenderChannelRequirements(ChannelInfo channel)
    {
        var requirements = new JsonObject
        {
            ["channel_id"] = channel.ChannelId,
            ["display_name"] = channel.DisplayName,
            ["setup_kind"] = channel.SetupKind,
            ["runtime_adapter"] = channel.Runtime?["owned_by"]?.GetValue<string>() ?? "",
            ["setup"] = channel.Setup?.DeepClone(),
            ["delivery"] = channel.Delivery?.DeepClone(),
            ["policies"] = channel.Policies?.DeepClone(),
            ["runtime"] = channel.Runtime?.DeepClone(),
        };
        ChannelRequirementText.Text = FormatRequirementSummary(requirements);
        ChannelSetupStepsText.Text = FormatSetupSteps(channel.Setup);
        ChannelPolicyText.Text = FormatPolicySummary(channel.Policies, channel.Delivery, channel.Runtime);
    }

    private static string FormatRequirementSummary(JsonObject requirements)
    {
        var setup = requirements["setup"] as JsonObject;
        var delivery = requirements["delivery"] as JsonObject;
        var requiredSecrets = JsonArrayStrings(setup, "required_secrets");
        var optionalSecrets = JsonArrayStrings(setup, "optional_secrets");
        var requiredFields = JsonArrayStrings(setup, "required_fields");
        var officialSend = delivery?["official_send"] as JsonObject;
        var sendMode = officialSend?["mode"]?.GetValue<string>() ?? "prepared_outbox";
        var implemented = officialSend?["implemented"]?.GetValue<bool>() == true ? "direct send available" : "prepared outbox only";
        return string.Join(Environment.NewLine, new[]
        {
            $"Setup: {requirements["setup_kind"]?.GetValue<string>() ?? "channel"}",
            $"Required fields: {FormatInline(requiredFields)}",
            $"Required secrets: {FormatInline(requiredSecrets)}",
            $"Optional secrets: {FormatInline(optionalSecrets)}",
            $"Send mode: {sendMode} ({implemented})",
        });
    }

    private static string FormatSetupSteps(JsonObject? setup)
    {
        var steps = JsonArrayStrings(setup, "steps");
        var notes = JsonArrayStrings(setup, "notes");
        var lines = new List<string>();
        lines.AddRange(steps.Select((step, index) => $"{index + 1}. {step}"));
        if (notes.Count > 0)
        {
            lines.Add("");
            lines.Add("Notes:");
            lines.AddRange(notes.Select(note => $"- {note}"));
        }
        return lines.Count == 0 ? "No setup steps are published for this channel yet." : string.Join(Environment.NewLine, lines);
    }

    private static string FormatPolicySummary(JsonObject? policies, JsonObject? delivery, JsonObject? runtime)
    {
        var officialSend = delivery?["official_send"] as JsonObject;
        var lines = new[]
        {
            $"DM policy: {JsonString(policies, "dm_policy", "not specified")}",
            $"Group policy: {JsonString(policies, "group_policy", "not specified")}",
            $"Mention required: {JsonBool(policies, "mention_required_by_default")}",
            $"Ambient room context: {JsonBool(policies, "ambient_room_events_supported")}",
            $"Bot-loop protection: {JsonBool(policies, "bot_loop_protection_supported")}",
            $"Native threads: {JsonBool(delivery, "native_threads")}",
            $"Approval reactions: {JsonBool(delivery, "approval_reactions")}",
            $"Listener required: {JsonBool(runtime, "listener_required_for_inbound")}",
            $"Runtime state: {JsonString(runtime, "state_dir_hint", "none")}",
            $"Official target: {JsonString(officialSend, "target", "conversation_id")}",
        };
        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatDoctorFindings(JsonObject doctor)
    {
        var findings = doctor["findings"]?.AsArray();
        if (findings is null || findings.Count == 0)
        {
            return "No doctor findings returned.";
        }
        return string.Join(
            Environment.NewLine,
            findings.Select(item =>
            {
                var finding = item?.AsObject();
                return finding is null
                    ? ""
                    : $"- {finding["channel_id"]?.GetValue<string>() ?? "channel"} [{finding["severity"]?.GetValue<string>() ?? "info"}]: {finding["message"]?.GetValue<string>() ?? ""}";
            }).Where(line => !string.IsNullOrWhiteSpace(line)));
    }

    private static string FormatChannelSmoke(JsonObject smoke)
    {
        var channel = smoke["channels"]?.AsArray().FirstOrDefault()?.AsObject();
        if (channel is null)
        {
            return "No channel smoke result returned.";
        }
        var blockers = channel["blockers"]?.AsArray()
            .Select(item =>
            {
                var blocker = item?.AsObject();
                return blocker is null ? "" : $"{blocker["kind"]?.GetValue<string>()}: {FormatJsonDetail(blocker["detail"])}";
            })
            .Where(item => !string.IsNullOrWhiteSpace(item))
            .ToList() ?? [];
        var lines = new List<string>
        {
            $"Smoke: {channel["readiness"]?.GetValue<string>() ?? "unknown"}",
            $"Prepared outbox: {JsonNodeBool(channel["prepared_outbox_ready"])} ({channel["prepared_message_id"]?.GetValue<string>() ?? "none"})",
            $"Dry-run send: {JsonNodeBool(channel["dry_run_send_ready"])} ({channel["dry_run_message_id"]?.GetValue<string>() ?? "none"})",
            $"Direct send: {JsonNodeBool(channel["direct_send_ready"])} via {channel["send_mode"]?.GetValue<string>() ?? "prepared"}",
            $"Listener: {JsonNodeBool(channel["listener_ready"])} via {channel["listener_mode"]?.GetValue<string>() ?? "listener"}",
        };
        if (blockers.Count > 0)
        {
            lines.Add("Blockers:");
            lines.AddRange(blockers.Select(item => $"- {item}"));
        }
        return string.Join(Environment.NewLine, lines);
    }

    private static List<string> JsonArrayStrings(JsonObject? node, string key)
    {
        if (node?[key] is not JsonArray array)
        {
            return [];
        }
        return array
            .Select(item => item?.GetValue<string>() ?? "")
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    private static string JsonString(JsonObject? node, string key, string fallback)
    {
        return node?[key]?.GetValue<string>() ?? fallback;
    }

    private static string JsonBool(JsonObject? node, string key)
    {
        return node?[key]?.GetValue<bool>() == true ? "yes" : "no";
    }

    private static string JsonNodeBool(JsonNode? node)
    {
        return node?.GetValue<bool>() == true ? "yes" : "no";
    }

    private static string FormatJsonDetail(JsonNode? node)
    {
        if (node is null)
        {
            return "";
        }
        if (node is JsonArray array)
        {
            return string.Join(", ", array.Select(item => item?.GetValue<string>() ?? "").Where(item => !string.IsNullOrWhiteSpace(item)));
        }
        try
        {
            return node.GetValue<string>();
        }
        catch
        {
            return node.ToJsonString();
        }
    }

    private static string FormatRunDetail(RuntimeRunItem run, IReadOnlyList<JsonObject> timeline)
    {
        var lines = new List<string>
        {
            $"Run: {run.RunId}",
            $"Status: {run.Status}",
            $"Started: {run.StartedAt}",
            $"Finished: {run.FinishedAt ?? ""}",
            $"Request: {run.Request}",
            "",
            "Final Response:",
            run.FinalResponse ?? "",
            "",
            "Timeline:",
        };
        lines.AddRange(timeline.Select(item =>
        {
            var eventType = item["event_type"]?.GetValue<string>() ?? "event";
            var summary = item["summary"]?.GetValue<string>() ?? "";
            return $"- {eventType}: {summary}";
        }));
        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatApprovalDetail(ApprovalItem approval)
    {
        return string.Join(
            Environment.NewLine,
            [
                $"Approval: {approval.ApprovalToken}",
                $"Status: {approval.Status}",
                $"Risk: {approval.RiskLevel}",
                $"Tool: {approval.ToolName}",
                $"Run: {approval.RunId}",
                $"Created: {approval.CreatedAt}",
                $"Reason: {approval.Reason}",
                $"Request: {approval.Request}",
                "",
                "Tool Input:",
                approval.ToolInput?.ToJsonString() ?? "{}",
            ]);
    }

    private static string FormatInline(IReadOnlyCollection<string> values)
    {
        return values.Count == 0 ? "none" : string.Join(", ", values);
    }

    private void ApplySettingsToUi()
    {
        _applyingSettingsToUi = true;
        try
        {
            ApiBaseUrlBox.Text = _settings.ApiBaseUrl;
            PortBox.Text = _settings.Port.ToString();
            WorkspacePathBox.Text = _settings.WorkspacePath;
            PythonPathBox.Text = _settings.PythonPath;
            ModelNameBox.Text = _settings.ModelName;
            ModelBaseUrlBox.Text = _settings.ModelBaseUrl;
            ModelApiKeyBox.Password = _settings.ModelApiKey;
            VoiceIdBox.Text = _settings.VoiceId;
            DeepgramApiKeyBox.Password = _settings.DeepgramApiKey;
            ElevenLabsApiKeyBox.Password = _settings.ElevenLabsApiKey;
            ElevenLabsModelBox.Text = _settings.ElevenLabsModel;
            VoiceWakeSwitch.IsOn = _settings.VoiceWakeEnabled;
            VoiceWakePhrasesBox.Text = _settings.VoiceWakePhrases;
            VoiceStopPhrasesBox.Text = _settings.VoiceStopPhrases;
            VoiceContinuousSwitch.IsOn = _settings.VoiceContinuousAfterWake;
            ApproveHighRiskSwitch.IsOn = _settings.ApproveHighRisk;
            SetComboByTag(PlannerBox, _settings.Planner);
            SetComboByTag(ModelProviderBox, _settings.ModelProvider);
            SetComboByTag(TtsProviderBox, _settings.TtsProvider);
            WorkspaceCaption.Text = ShortenPath(_settings.WorkspacePath);
            _api.SetBaseUrl(_settings.ApiBaseUrl);
        }
        finally
        {
            _applyingSettingsToUi = false;
        }
    }

    private void ReadSettingsFromUi()
    {
        _settings.Port = int.TryParse(PortBox.Text, out var port) ? Math.Max(1, port) : 8765;
        _settings.ApiBaseUrl = string.IsNullOrWhiteSpace(ApiBaseUrlBox.Text) ? $"http://127.0.0.1:{_settings.Port}" : ApiBaseUrlBox.Text.Trim();
        _settings.WorkspacePath = WorkspacePathBox.Text.Trim();
        _settings.PythonPath = PythonPathBox.Text.Trim();
        _settings.Planner = ComboTag(PlannerBox, "model");
        _settings.ModelProvider = ComboTag(ModelProviderBox, "openai");
        _settings.ModelName = ModelNameBox.Text.Trim();
        _settings.ModelBaseUrl = ModelBaseUrlBox.Text.Trim();
        _settings.ModelApiKey = ModelApiKeyBox.Password;
        _settings.TtsProvider = ComboTag(TtsProviderBox, "system");
        _settings.VoiceId = VoiceIdBox.Text.Trim();
        _settings.DeepgramApiKey = DeepgramApiKeyBox.Password;
        _settings.ElevenLabsApiKey = ElevenLabsApiKeyBox.Password;
        _settings.ElevenLabsModel = ElevenLabsModelBox.Text.Trim();
        _settings.VoiceWakeEnabled = VoiceWakeSwitch.IsOn;
        _settings.VoiceWakePhrases = string.IsNullOrWhiteSpace(VoiceWakePhrasesBox.Text) ? "hey humungousaur" : VoiceWakePhrasesBox.Text.Trim();
        _settings.VoiceStopPhrases = string.IsNullOrWhiteSpace(VoiceStopPhrasesBox.Text) ? "stop humungousaur" : VoiceStopPhrasesBox.Text.Trim();
        _settings.VoiceContinuousAfterWake = VoiceContinuousSwitch.IsOn;
        _settings.ApproveHighRisk = ApproveHighRiskSwitch.IsOn;
    }

    private void AddChat(string speaker, string text, string tone)
    {
        _chat.Add(new ChatLogItem { Speaker = speaker, Text = text, Tone = tone });
        ChatLog.ScrollIntoView(_chat.Last());
    }

    private void ApplyStreamEvent(AgentStreamEvent streamEvent)
    {
        if (streamEvent.Event == "final_response")
        {
            var response = streamEvent.Data["response"]?.GetValue<string>()
                ?? streamEvent.Data["result"]?["response"]?.GetValue<string>()
                ?? AgentApiClient.Pretty(streamEvent.Data);
            AddChat("Humungousaur", response, "assistant");
            return;
        }
        if (streamEvent.Event == "stream_error")
        {
            AddChat("Humungousaur", streamEvent.Data["error"]?.GetValue<string>() ?? "The stream failed.", "error");
            return;
        }
        if (streamEvent.Event != "run_event")
        {
            return;
        }

        var eventType = streamEvent.Data["event_type"]?.GetValue<string>() ?? "";
        var message = streamEvent.Data["message"]?.GetValue<string>() ?? Humanize(eventType);
        var payload = streamEvent.Data["payload"] as JsonObject;
        if (eventType == "run_started")
        {
            _activeVoiceRunId = payload?["run_id"]?.GetValue<string>() ?? streamEvent.Data["run_id"]?.GetValue<string>() ?? _activeVoiceRunId;
        }
        switch (eventType)
        {
            case "run_started":
            case "planning_context_collected":
                AddChat("Thinking", message, "activity");
                break;
            case "plan_created":
                AddChat("Plan", FormatPlannedSteps(payload), "activity");
                var skillText = FormatSelectedSkills(payload);
                if (!string.IsNullOrWhiteSpace(skillText))
                {
                    AddChat("Skills", skillText, "activity");
                }
                break;
            case "action_started":
                AddChat(
                    "Tool",
                    $"{Humanize(payload?["tool_name"]?.GetValue<string>() ?? "tool")}: {payload?["reason"]?.GetValue<string>() ?? message}",
                    "activity");
                break;
            case "action_finished":
                AddChat(
                    "Tool",
                    $"{Humanize(payload?["tool_name"]?.GetValue<string>() ?? "tool")} {Humanize(payload?["status"]?.GetValue<string>() ?? "")}: {payload?["summary"]?.GetValue<string>() ?? message}",
                    "activity");
                break;
            case "run_waiting_for_approval":
                AddChat("Approval", message, "activity");
                break;
            case "run_finished":
            case "run_cancelled":
                AddChat("Run", message, "activity");
                break;
        }
    }

    private static string FormatPlannedSteps(JsonObject? payload)
    {
        var planned = payload?["planned_steps"] as JsonArray;
        if (planned is not null && planned.Count > 0)
        {
            return string.Join(
                Environment.NewLine,
                planned.Select((step, index) =>
                {
                    var tool = Humanize(step?["tool_name"]?.GetValue<string>() ?? "tool");
                    var reason = step?["reason"]?.GetValue<string>() ?? "";
                    return string.IsNullOrWhiteSpace(reason) ? $"{index + 1}. {tool}" : $"{index + 1}. {tool}: {reason}";
                }));
        }

        var steps = payload?["steps"] as JsonArray;
        if (steps is null || steps.Count == 0)
        {
            return "No tool steps planned.";
        }
        return string.Join(", ", steps.Select(step => Humanize(step?.GetValue<string>() ?? "")));
    }

    private static string FormatSelectedSkills(JsonObject? payload)
    {
        var skills = payload?["active_workspace_skills"] as JsonArray;
        if (skills is null || skills.Count == 0)
        {
            return "";
        }
        return string.Join(
            ", ",
            skills.Select(skill => skill?["name"]?.GetValue<string>() ?? skill?["relative_path"]?.GetValue<string>() ?? "")
                .Where(value => !string.IsNullOrWhiteSpace(value)));
    }

    private static string Humanize(string value)
    {
        var clean = value.Replace("_", " ").Replace("-", " ").Replace(".", " ").Trim();
        if (string.IsNullOrWhiteSpace(clean))
        {
            return "";
        }
        return string.Join(
            " ",
            clean.Split(' ', StringSplitOptions.RemoveEmptyEntries)
                .Select(word => word.Length <= 1 ? word.ToUpperInvariant() : char.ToUpperInvariant(word[0]) + word[1..]));
    }

    private void AddProcessLine(string line)
    {
        _processLines.Add($"{DateTime.Now:h:mm:ss tt}  {line}");
        while (_processLines.Count > 80)
        {
            _processLines.RemoveAt(0);
        }
    }

    private void SetStatus(bool online, string text)
    {
        StatusDot.Fill = new SolidColorBrush(online ? Colors.SeaGreen : Colors.IndianRed);
        PaneStatusDot.Fill = StatusDot.Fill;
        StatusText.Text = text;
    }

    private void ShowNotice(string message, InfoBarSeverity severity)
    {
        NoticeBar.Message = message;
        NoticeBar.Severity = severity;
        NoticeBar.IsOpen = true;
    }

    private static string ComboTag(ComboBox box, string fallback)
    {
        return (box.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? fallback;
    }

    private static void SetComboByTag(ComboBox box, string tag)
    {
        foreach (var item in box.Items.OfType<ComboBoxItem>())
        {
            if (string.Equals(item.Tag?.ToString(), tag, StringComparison.OrdinalIgnoreCase))
            {
                box.SelectedItem = item;
                return;
            }
        }
    }

    private static Dictionary<string, string> ParseSecretLines(string text)
    {
        var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var rawLine in text.Split(["\r\n", "\n"], StringSplitOptions.None))
        {
            var line = rawLine.Trim();
            if (string.IsNullOrWhiteSpace(line) || line.StartsWith("#", StringComparison.Ordinal))
            {
                continue;
            }
            var separator = line.IndexOf('=');
            if (separator <= 0)
            {
                continue;
            }
            var key = line[..separator].Trim();
            var value = line[(separator + 1)..].Trim();
            if (!string.IsNullOrWhiteSpace(key) && !string.IsNullOrWhiteSpace(value))
            {
                values[key] = value;
            }
        }
        return values;
    }

    private static string SerializeSecretLines(Dictionary<string, string> values)
    {
        return string.Join(Environment.NewLine, values.Select(item => $"{item.Key}={item.Value}"));
    }

    private static List<string> ParseListLines(string text)
    {
        return text.Split(["\r\n", "\n", ","], StringSplitOptions.None)
            .Select(item => item.Trim())
            .Where(item => !string.IsNullOrWhiteSpace(item) && !item.StartsWith("#", StringComparison.Ordinal))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    private static string SerializeListLines(IEnumerable<string> values)
    {
        return string.Join(Environment.NewLine, values.Where(value => !string.IsNullOrWhiteSpace(value)));
    }

    private static string ShortenPath(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || path.Length <= 64)
        {
            return path;
        }
        return "..." + path[^61..];
    }
}
