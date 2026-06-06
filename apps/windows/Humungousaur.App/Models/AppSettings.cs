namespace Humungousaur.App.Models;

public sealed class AppSettings
{
    public string ApiBaseUrl { get; set; } = "http://127.0.0.1:8765";
    public string WorkspacePath { get; set; } = "";
    public string PythonPath { get; set; } = "";
    public int Port { get; set; } = 8765;
    public string Planner { get; set; } = "model";
    public string ModelProvider { get; set; } = "groq";
    public string ModelName { get; set; } = "";
    public string TtsProvider { get; set; } = "system";
    public string VoiceId { get; set; } = "";
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
    public bool SecretConfigured { get; set; }
    public string Notes { get; set; } = "";
}
