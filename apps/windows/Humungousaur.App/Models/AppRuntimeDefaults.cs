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
            "openrouter" => "OPENROUTER_API_KEY",
            "nous" => "NOUS_API_KEY",
            "novita" => "NOVITA_API_KEY",
            "lmstudio" => "LM_API_KEY",
            "anthropic" => "ANTHROPIC_API_KEY",
            "alibaba" => "DASHSCOPE_API_KEY",
            "groq" => "GROQ_API_KEY",
            "grok" or "xai" => "XAI_API_KEY",
            "gemini" => "GOOGLE_API_KEY",
            "deepseek" => "DEEPSEEK_API_KEY",
            "mistral" => "MISTRAL_API_KEY",
            "cerebras" => "CEREBRAS_API_KEY",
            "ollama" => "OLLAMA_API_KEY",
            "ollama-cloud" => "OLLAMA_API_KEY",
            "local-openai" => "LOCAL_LLM_API_KEY",
            "vercel" => "AI_GATEWAY_API_KEY",
            "litellm" => "LITELLM_API_KEY",
            "nvidia" => "NVIDIA_API_KEY",
            "huggingface" => "HF_TOKEN",
            "zai" => "GLM_API_KEY",
            "kimi-coding" => "KIMI_API_KEY",
            "kimi-coding-cn" => "KIMI_CN_API_KEY",
            "stepfun" => "STEPFUN_API_KEY",
            "minimax" => "MINIMAX_API_KEY",
            "minimax-cn" => "MINIMAX_CN_API_KEY",
            "arcee" => "ARCEEAI_API_KEY",
            "gmi" => "GMI_API_KEY",
            "xiaomi" => "XIAOMI_API_KEY",
            "tencent-tokenhub" => "TOKENHUB_API_KEY",
            "opencode-zen" => "OPENCODE_ZEN_API_KEY",
            "opencode-go" => "OPENCODE_GO_API_KEY",
            "kilocode" => "KILOCODE_API_KEY",
            "azure-openai" => "AZURE_OPENAI_API_KEY",
            "azure-foundry" => "AZURE_FOUNDRY_API_KEY",
            "copilot" or "copilot-acp" => "GITHUB_TOKEN",
            "bedrock" => "AWS_ACCESS_KEY_ID",
            "browser-use-cloud" => "BROWSER_USE_API_KEY",
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
