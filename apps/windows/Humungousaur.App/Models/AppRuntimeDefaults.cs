namespace Humungousaur.App.Models;

public static class AppRuntimeDefaults
{
    public const string Planner = "model";
    public const string ModelProvider = "openai";
    public const string ModelName = "gpt-5-mini";
    public const string TtsProvider = "system";

    public static string EffectivePlanner(string planner)
    {
        return string.IsNullOrWhiteSpace(planner) ? Planner : planner.Trim();
    }

    public static string EffectiveModelProvider(string provider)
    {
        return string.IsNullOrWhiteSpace(provider) ? ModelProvider : provider.Trim();
    }

    public static string EffectiveModelName(string modelName)
    {
        return string.IsNullOrWhiteSpace(modelName) ? ModelName : modelName.Trim();
    }

    public static string EffectiveTtsProvider(string provider)
    {
        return string.IsNullOrWhiteSpace(provider) ? TtsProvider : provider.Trim();
    }

    public static string ModelApiKeyName(string provider)
    {
        return EffectiveModelProvider(provider) switch
        {
            "openai" or "openai-responses" or "openai-chat" => "OPENAI_API_KEY",
            "groq" => "GROQ_API_KEY",
            "grok" => "XAI_API_KEY",
            "ollama" => "OLLAMA_API_KEY",
            "local-openai" => "LOCAL_LLM_API_KEY",
            _ => "OPENAI_API_KEY",
        };
    }

    public static string CliModelProvider(string provider)
    {
        return EffectiveModelProvider(provider) switch
        {
            "openai" => "openai-responses",
            var value => value,
        };
    }
}
