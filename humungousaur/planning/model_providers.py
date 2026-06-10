from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True, slots=True)
class ModelProviderSpec:
    provider_id: str
    label: str
    transport: str
    default_model: str
    model_env: str
    api_key_envs: tuple[str, ...]
    default_base_url: str
    base_url_env: str = ""
    aliases: tuple[str, ...] = ()
    allow_openai_fallback: bool = True

    @property
    def primary_api_key_env(self) -> str:
        return self.api_key_envs[0] if self.api_key_envs else ""


OPENAI_RESPONSES = "openai_responses"
OPENAI_CHAT = "openai_chat"
ANTHROPIC_MESSAGES = "anthropic_messages"
EXTERNAL_RUNTIME = "external_runtime"


MODEL_PROVIDER_REGISTRY: tuple[ModelProviderSpec, ...] = (
    ModelProviderSpec(
        "openai-responses",
        "OpenAI Responses",
        OPENAI_RESPONSES,
        "gpt-5-mini",
        "OPENAI_MODEL",
        ("OPENAI_API_KEY",),
        "https://api.openai.com/v1",
        "OPENAI_BASE_URL",
        aliases=("openai", "openai-api"),
        allow_openai_fallback=False,
    ),
    ModelProviderSpec(
        "openai-chat",
        "OpenAI Chat",
        OPENAI_CHAT,
        "gpt-5-mini",
        "OPENAI_MODEL",
        ("OPENAI_API_KEY",),
        "https://api.openai.com/v1",
        "OPENAI_BASE_URL",
        allow_openai_fallback=False,
    ),
    ModelProviderSpec(
        "openrouter",
        "OpenRouter",
        OPENAI_CHAT,
        "anthropic/claude-sonnet-4.6",
        "OPENROUTER_MODEL",
        ("OPENROUTER_API_KEY",),
        "https://openrouter.ai/api/v1",
        "OPENROUTER_BASE_URL",
    ),
    ModelProviderSpec(
        "nous",
        "Nous Portal",
        OPENAI_CHAT,
        "moonshotai/kimi-k2.6",
        "NOUS_MODEL",
        ("NOUS_API_KEY", "NOUS_INFERENCE_API_KEY"),
        "https://inference-api.nousresearch.com/v1",
        "NOUS_INFERENCE_BASE_URL",
    ),
    ModelProviderSpec(
        "novita",
        "NovitaAI",
        OPENAI_CHAT,
        "deepseek/deepseek-r1",
        "NOVITA_MODEL",
        ("NOVITA_API_KEY",),
        "https://api.novita.ai/openai/v1",
        "NOVITA_BASE_URL",
    ),
    ModelProviderSpec(
        "lmstudio",
        "LM Studio",
        OPENAI_CHAT,
        "local-model",
        "LM_MODEL",
        ("LM_API_KEY",),
        "http://127.0.0.1:1234/v1",
        "LM_BASE_URL",
    ),
    ModelProviderSpec(
        "anthropic",
        "Anthropic",
        ANTHROPIC_MESSAGES,
        "claude-sonnet-4-6",
        "ANTHROPIC_MODEL",
        ("ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"),
        "https://api.anthropic.com",
        "ANTHROPIC_BASE_URL",
    ),
    ModelProviderSpec(
        "alibaba",
        "Qwen Cloud",
        OPENAI_CHAT,
        "qwen-max",
        "DASHSCOPE_MODEL",
        ("DASHSCOPE_API_KEY",),
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "DASHSCOPE_BASE_URL",
        aliases=("qwen", "dashscope"),
    ),
    ModelProviderSpec(
        "xai",
        "xAI Grok",
        OPENAI_CHAT,
        "grok-4.3",
        "XAI_MODEL",
        ("XAI_API_KEY",),
        "https://api.x.ai/v1",
        "XAI_BASE_URL",
        aliases=("grok", "x-ai"),
    ),
    ModelProviderSpec(
        "gemini",
        "Google Gemini",
        OPENAI_CHAT,
        "gemini-3-pro-preview",
        "GEMINI_MODEL",
        ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "GEMINI_BASE_URL",
        aliases=("google", "google-ai-studio"),
    ),
    ModelProviderSpec(
        "deepseek",
        "DeepSeek",
        OPENAI_CHAT,
        "deepseek-chat",
        "DEEPSEEK_MODEL",
        ("DEEPSEEK_API_KEY",),
        "https://api.deepseek.com/v1",
        "DEEPSEEK_BASE_URL",
    ),
    ModelProviderSpec(
        "mistral",
        "Mistral",
        OPENAI_CHAT,
        "mistral-large-latest",
        "MISTRAL_MODEL",
        ("MISTRAL_API_KEY",),
        "https://api.mistral.ai/v1",
        "MISTRAL_BASE_URL",
    ),
    ModelProviderSpec(
        "groq",
        "Groq",
        OPENAI_CHAT,
        "llama-3.3-70b-versatile",
        "GROQ_MODEL",
        ("GROQ_API_KEY",),
        "https://api.groq.com/openai/v1",
        "GROQ_BASE_URL",
    ),
    ModelProviderSpec(
        "cerebras",
        "Cerebras",
        OPENAI_CHAT,
        "llama3.3-70b",
        "CEREBRAS_MODEL",
        ("CEREBRAS_API_KEY",),
        "https://api.cerebras.ai/v1",
        "CEREBRAS_BASE_URL",
    ),
    ModelProviderSpec(
        "ollama",
        "Ollama",
        OPENAI_CHAT,
        "llama3.1",
        "OLLAMA_MODEL",
        ("OLLAMA_API_KEY",),
        "http://127.0.0.1:11434/v1",
        "OLLAMA_BASE_URL",
    ),
    ModelProviderSpec(
        "ollama-cloud",
        "Ollama Cloud",
        OPENAI_CHAT,
        "gpt-oss:20b",
        "OLLAMA_CLOUD_MODEL",
        ("OLLAMA_API_KEY",),
        "https://ollama.com/v1",
        "OLLAMA_CLOUD_BASE_URL",
    ),
    ModelProviderSpec(
        "local-openai",
        "Local OpenAI-compatible",
        OPENAI_CHAT,
        "llama3.1",
        "LOCAL_LLM_MODEL",
        ("LOCAL_LLM_API_KEY",),
        "http://127.0.0.1:11434/v1",
        "LOCAL_LLM_BASE_URL",
    ),
    ModelProviderSpec(
        "vercel",
        "Vercel AI Gateway",
        OPENAI_CHAT,
        "anthropic/claude-sonnet-4.6",
        "AI_GATEWAY_MODEL",
        ("AI_GATEWAY_API_KEY", "VERCEL_OIDC_TOKEN"),
        "https://ai-gateway.vercel.sh/v1",
        "AI_GATEWAY_BASE_URL",
        aliases=("ai-gateway", "vercel-ai-gateway"),
    ),
    ModelProviderSpec(
        "litellm",
        "LiteLLM",
        OPENAI_CHAT,
        "openai/gpt-5-mini",
        "LITELLM_MODEL",
        ("LITELLM_API_KEY",),
        "http://localhost:4000/v1",
        "LITELLM_BASE_URL",
    ),
    ModelProviderSpec(
        "nvidia",
        "NVIDIA NIM",
        OPENAI_CHAT,
        "nvidia/nemotron-3-super-120b-a12b",
        "NVIDIA_MODEL",
        ("NVIDIA_API_KEY",),
        "https://integrate.api.nvidia.com/v1",
        "NVIDIA_BASE_URL",
        aliases=("nim",),
    ),
    ModelProviderSpec(
        "huggingface",
        "Hugging Face",
        OPENAI_CHAT,
        "meta-llama/Llama-3.3-70B-Instruct",
        "HF_MODEL",
        ("HF_TOKEN", "HUGGINGFACE_API_KEY"),
        "https://router.huggingface.co/v1",
        "HF_BASE_URL",
        aliases=("hf",),
    ),
    ModelProviderSpec(
        "zai",
        "Z.AI / GLM",
        OPENAI_CHAT,
        "glm-5.1",
        "GLM_MODEL",
        ("GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY"),
        "https://api.z.ai/api/paas/v4",
        "GLM_BASE_URL",
        aliases=("z-ai", "glm", "zhipu"),
    ),
    ModelProviderSpec(
        "kimi-coding",
        "Kimi / Moonshot",
        OPENAI_CHAT,
        "kimi-k2.6",
        "KIMI_MODEL",
        ("KIMI_API_KEY", "KIMI_CODING_API_KEY"),
        "https://api.moonshot.ai/v1",
        "KIMI_BASE_URL",
        aliases=("moonshot", "kimi"),
    ),
    ModelProviderSpec(
        "kimi-coding-cn",
        "Kimi / Moonshot China",
        OPENAI_CHAT,
        "kimi-k2.6",
        "KIMI_CN_MODEL",
        ("KIMI_CN_API_KEY",),
        "https://api.moonshot.cn/v1",
        "KIMI_CN_BASE_URL",
    ),
    ModelProviderSpec(
        "stepfun",
        "StepFun Step Plan",
        OPENAI_CHAT,
        "step-3.7-flash",
        "STEPFUN_MODEL",
        ("STEPFUN_API_KEY",),
        "https://api.stepfun.ai/step_plan/v1",
        "STEPFUN_BASE_URL",
    ),
    ModelProviderSpec(
        "minimax",
        "MiniMax",
        ANTHROPIC_MESSAGES,
        "minimax-m3",
        "MINIMAX_MODEL",
        ("MINIMAX_API_KEY",),
        "https://api.minimax.io/anthropic",
        "MINIMAX_BASE_URL",
    ),
    ModelProviderSpec(
        "minimax-cn",
        "MiniMax China",
        ANTHROPIC_MESSAGES,
        "minimax-m3",
        "MINIMAX_CN_MODEL",
        ("MINIMAX_CN_API_KEY",),
        "https://api.minimaxi.com/anthropic",
        "MINIMAX_CN_BASE_URL",
    ),
    ModelProviderSpec(
        "arcee",
        "Arcee AI",
        OPENAI_CHAT,
        "auto",
        "ARCEE_MODEL",
        ("ARCEEAI_API_KEY", "ARCEE_API_KEY"),
        "https://api.arcee.ai/api/v1",
        "ARCEE_BASE_URL",
    ),
    ModelProviderSpec(
        "gmi",
        "GMI Cloud",
        OPENAI_CHAT,
        "auto",
        "GMI_MODEL",
        ("GMI_API_KEY",),
        "https://api.gmi-serving.com/v1",
        "GMI_BASE_URL",
    ),
    ModelProviderSpec(
        "xiaomi",
        "Xiaomi MiMo",
        OPENAI_CHAT,
        "mimo-v2.5-pro",
        "XIAOMI_MODEL",
        ("XIAOMI_API_KEY",),
        "https://api.xiaomimimo.com/v1",
        "XIAOMI_BASE_URL",
    ),
    ModelProviderSpec(
        "tencent-tokenhub",
        "Tencent TokenHub",
        OPENAI_CHAT,
        "tencent/hy3-preview",
        "TOKENHUB_MODEL",
        ("TOKENHUB_API_KEY",),
        "https://tokenhub.tencentmaas.com/v1",
        "TOKENHUB_BASE_URL",
        aliases=("tokenhub", "tencent"),
    ),
    ModelProviderSpec(
        "opencode-zen",
        "OpenCode Zen",
        OPENAI_CHAT,
        "anthropic/claude-sonnet-4.6",
        "OPENCODE_ZEN_MODEL",
        ("OPENCODE_ZEN_API_KEY",),
        "https://opencode.ai/zen/v1",
        "OPENCODE_ZEN_BASE_URL",
    ),
    ModelProviderSpec(
        "opencode-go",
        "OpenCode Go",
        OPENAI_CHAT,
        "z-ai/glm-5.1",
        "OPENCODE_GO_MODEL",
        ("OPENCODE_GO_API_KEY",),
        "https://opencode.ai/zen/go/v1",
        "OPENCODE_GO_BASE_URL",
    ),
    ModelProviderSpec(
        "kilocode",
        "Kilo Code",
        OPENAI_CHAT,
        "anthropic/claude-sonnet-4.6",
        "KILOCODE_MODEL",
        ("KILOCODE_API_KEY",),
        "https://api.kilo.ai/api/gateway",
        "KILOCODE_BASE_URL",
    ),
    ModelProviderSpec(
        "azure-openai",
        "Azure OpenAI",
        OPENAI_CHAT,
        "gpt-5",
        "AZURE_OPENAI_MODEL",
        ("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_KEY"),
        "",
        "AZURE_OPENAI_ENDPOINT",
        aliases=("azure",),
    ),
    ModelProviderSpec(
        "azure-foundry",
        "Azure Foundry",
        OPENAI_CHAT,
        "gpt-5",
        "AZURE_FOUNDRY_MODEL",
        ("AZURE_FOUNDRY_API_KEY",),
        "",
        "AZURE_FOUNDRY_BASE_URL",
    ),
    ModelProviderSpec(
        "copilot",
        "GitHub Copilot",
        OPENAI_CHAT,
        "gpt-5.4",
        "COPILOT_MODEL",
        ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"),
        "https://api.githubcopilot.com",
        "COPILOT_API_BASE_URL",
        aliases=("github-copilot",),
    ),
    ModelProviderSpec(
        "bedrock",
        "AWS Bedrock",
        EXTERNAL_RUNTIME,
        "us.anthropic.claude-sonnet-4-20250514-v1:0",
        "BEDROCK_MODEL",
        ("AWS_ACCESS_KEY_ID",),
        "https://bedrock-runtime.us-east-1.amazonaws.com",
        "BEDROCK_BASE_URL",
        allow_openai_fallback=False,
    ),
    ModelProviderSpec(
        "browser-use-cloud",
        "Browser Use Cloud",
        EXTERNAL_RUNTIME,
        "bu-2-0",
        "BROWSER_USE_MODEL",
        ("BROWSER_USE_API_KEY",),
        "https://api.browser-use.com",
        "BROWSER_USE_BASE_URL",
        aliases=("browser-use",),
        allow_openai_fallback=False,
    ),
    ModelProviderSpec(
        "oci",
        "Oracle OCI",
        EXTERNAL_RUNTIME,
        "meta.llama-3.1-70b-instruct",
        "OCI_MODEL",
        (),
        "",
        "OCI_GENAI_ENDPOINT",
        aliases=("oracle",),
        allow_openai_fallback=False,
    ),
    ModelProviderSpec(
        "openai-codex",
        "OpenAI Codex",
        EXTERNAL_RUNTIME,
        "gpt-5.5",
        "CODEX_MODEL",
        ("OPENAI_API_KEY",),
        "https://chatgpt.com/backend-api/codex",
        "HERMES_CODEX_BASE_URL",
        allow_openai_fallback=False,
    ),
    ModelProviderSpec(
        "xai-oauth",
        "xAI Grok OAuth",
        EXTERNAL_RUNTIME,
        "grok-4.3",
        "XAI_MODEL",
        ("XAI_OAUTH_TOKEN",),
        "https://api.x.ai/v1",
        "XAI_BASE_URL",
        allow_openai_fallback=False,
    ),
    ModelProviderSpec(
        "qwen-oauth",
        "Qwen OAuth",
        EXTERNAL_RUNTIME,
        "qwen3-coder-plus",
        "QWEN_MODEL",
        ("QWEN_OAUTH_TOKEN",),
        "https://portal.qwen.ai/v1",
        "HERMES_QWEN_BASE_URL",
        allow_openai_fallback=False,
    ),
    ModelProviderSpec(
        "google-gemini-cli",
        "Google Gemini OAuth",
        EXTERNAL_RUNTIME,
        "gemini-3-pro-preview",
        "GEMINI_MODEL",
        ("GEMINI_OAUTH_TOKEN",),
        "cloudcode-pa://google",
        "",
        allow_openai_fallback=False,
    ),
    ModelProviderSpec(
        "copilot-acp",
        "GitHub Copilot ACP",
        EXTERNAL_RUNTIME,
        "copilot-acp",
        "COPILOT_ACP_MODEL",
        ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"),
        "acp://copilot",
        "COPILOT_ACP_BASE_URL",
        allow_openai_fallback=False,
    ),
    ModelProviderSpec(
        "minimax-oauth",
        "MiniMax OAuth",
        EXTERNAL_RUNTIME,
        "minimax-m3",
        "MINIMAX_MODEL",
        ("MINIMAX_OAUTH_TOKEN",),
        "https://api.minimax.io/anthropic",
        "MINIMAX_BASE_URL",
        allow_openai_fallback=False,
    ),
)


_PROVIDER_BY_ID = {provider.provider_id: provider for provider in MODEL_PROVIDER_REGISTRY}
_ALIASES = {
    alias: provider.provider_id
    for provider in MODEL_PROVIDER_REGISTRY
    for alias in provider.aliases
}
_ALIASES.update({"grok": "xai", "openai-api": "openai-responses"})


MODEL_PROVIDER_CHOICES: tuple[str, ...] = (
    "auto",
    *tuple(provider.provider_id for provider in MODEL_PROVIDER_REGISTRY),
    *tuple(alias for alias in sorted(_ALIASES) if alias not in _PROVIDER_BY_ID),
)


def normalize_model_provider(provider: str) -> str:
    normalized = str(provider or "auto").strip().lower()
    if not normalized:
        return "auto"
    return _ALIASES.get(normalized, normalized)


def model_provider_spec(provider: str) -> ModelProviderSpec:
    normalized = normalize_model_provider(provider)
    try:
        return _PROVIDER_BY_ID[normalized]
    except KeyError as exc:
        raise ValueError(f"Unknown model provider: {provider}") from exc


def configured_api_key_env(spec: ModelProviderSpec, override: str | None = None) -> str:
    if override and str(override).strip():
        return str(override).strip()
    return spec.primary_api_key_env


def configured_base_url(spec: ModelProviderSpec, override: str | None = None) -> str:
    if override:
        return str(override).strip()
    if spec.base_url_env and os.environ.get(spec.base_url_env):
        return os.environ[spec.base_url_env].strip()
    if spec.provider_id == "ollama":
        return os.environ.get("LOCAL_LLM_BASE_URL", "").strip() or spec.default_base_url
    return spec.default_base_url


def provider_has_credentials(spec: ModelProviderSpec) -> bool:
    base_url = configured_base_url(spec)
    if spec.transport == OPENAI_CHAT and _is_loopback_url(base_url):
        return True
    if not base_url and not spec.default_base_url:
        return False
    return any(os.environ.get(env_name) for env_name in spec.api_key_envs)


def _is_loopback_url(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    return "localhost" in normalized or "127.0.0.1" in normalized or "[::1]" in normalized
