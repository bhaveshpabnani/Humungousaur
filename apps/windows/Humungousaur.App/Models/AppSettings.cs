namespace Humungousaur.App.Models;

public sealed class AppSettings
{
    public string ApiBaseUrl { get; set; } = "http://127.0.0.1:8765";
    public string WorkspacePath { get; set; } = "";
    public string PythonPath { get; set; } = "";
    public int Port { get; set; } = 8765;
    public string Planner { get; set; } = AppRuntimeDefaults.Planner;
    public string ModelProvider { get; set; } = AppRuntimeDefaults.ModelProvider;
    public string ModelName { get; set; } = AppRuntimeDefaults.ModelName;
    public string ModelBaseUrl { get; set; } = "";
    public string ModelApiKey { get; set; } = "";
    public string TtsProvider { get; set; } = AppRuntimeDefaults.TtsProvider;
    public string VoiceId { get; set; } = "";
    public string DeepgramApiKey { get; set; } = "";
    public string ElevenLabsApiKey { get; set; } = "";
    public string ElevenLabsModel { get; set; } = "";
    public bool VoiceWakeEnabled { get; set; }
    public string VoiceWakePhrases { get; set; } = "hey humungousaur";
    public string VoiceStopPhrases { get; set; } = "stop humungousaur";
    public bool VoiceContinuousAfterWake { get; set; } = true;
    public bool ApproveHighRisk { get; set; }
    public List<ChannelSetup> Channels { get; set; } = [];
}

public sealed class ChannelSetup
{
    public string ChannelId { get; set; } = "";
    public bool Enabled { get; set; }
    public bool ListenEnabled { get; set; } = true;
    public string ConversationId { get; set; } = "";
    public string ConversationType { get; set; } = "dm";
    public string SecretName { get; set; } = "";
    public string SecretValue { get; set; } = "";
    public Dictionary<string, string> SecretValues { get; set; } = [];
    public bool SecretConfigured { get; set; }
    public List<string> Allowlist { get; set; } = [];
    public List<string> GroupAllowlist { get; set; } = [];
    public string Notes { get; set; } = "";
}
