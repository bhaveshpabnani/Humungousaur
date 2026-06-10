from __future__ import annotations

import os

from humungousaur.config import AgentConfig

from .local_models import ollama_available, recommended_ollama_model
from .model_clients import AnthropicMessagesClient, FallbackModelClient, ModelClient, ModelClientError, OpenAICompatibleChatClient, OpenAIResponsesClient
from .model_providers import (
    ANTHROPIC_MESSAGES,
    EXTERNAL_RUNTIME,
    MODEL_PROVIDER_REGISTRY,
    OPENAI_CHAT,
    OPENAI_RESPONSES,
    ModelProviderSpec,
    configured_api_key_env,
    configured_base_url,
    model_provider_spec,
    normalize_model_provider,
    provider_has_credentials,
)


def build_model_client(config: AgentConfig) -> ModelClient:
    provider = normalize_model_provider(config.model_provider)
    if provider == "auto":
        provider = auto_model_provider()
    spec = model_provider_spec(provider)
    if spec.provider_id == "ollama":
        spec = _ollama_spec_with_runtime_default(spec)
    return _client_for_spec(config, spec)


def _client_for_spec(config: AgentConfig, spec: ModelProviderSpec) -> ModelClient:
    api_key_env = configured_api_key_env(spec, config.model_api_key_env)
    base_url = configured_base_url(spec, config.model_base_url)
    model = model_name(config, spec.model_env, spec.default_model)
    if spec.transport == OPENAI_RESPONSES:
        return _openai_responses_client(config, spec=spec, api_key_env=api_key_env, base_url=base_url)
    if spec.transport == OPENAI_CHAT:
        return _with_openai_fallback(
            config,
            spec,
            OpenAICompatibleChatClient(
                model=model,
                api_key=config.secret_value(api_key_env),
                api_key_env=api_key_env,
                base_url=base_url,
                timeout_seconds=config.model_timeout_seconds,
                name=f"{spec.provider_id}-chat",
            ),
        )
    if spec.transport == ANTHROPIC_MESSAGES:
        return _with_openai_fallback(
            config,
            spec,
            AnthropicMessagesClient(
                model=model,
                api_key=config.secret_value(api_key_env),
                api_key_env=api_key_env,
                base_url=base_url,
                timeout_seconds=config.model_timeout_seconds,
                name=f"{spec.provider_id}-messages",
            ),
        )
    if spec.transport == EXTERNAL_RUNTIME and config.model_base_url:
        return _with_openai_fallback(
            config,
            spec,
            OpenAICompatibleChatClient(
                model=model,
                api_key=config.secret_value(api_key_env),
                api_key_env=api_key_env,
                base_url=base_url,
                timeout_seconds=config.model_timeout_seconds,
                name=f"{spec.provider_id}-external-compatible-chat",
            ),
        )
    return UnsupportedModelClient(spec)


class UnsupportedModelClient(ModelClient):
    def __init__(self, spec: ModelProviderSpec) -> None:
        self.spec = spec
        self.name = f"{spec.provider_id}-external-runtime"

    def complete_json(self, prompt: str, schema: dict) -> str:
        del prompt, schema
        raise ModelClientError(
            f"{self.spec.label} is registered but requires an external provider runtime bridge. "
            "Set --model-base-url to an OpenAI-compatible HTTP endpoint for embedded planner use."
        )


def _openai_responses_client(
    config: AgentConfig,
    *,
    spec: ModelProviderSpec | None = None,
    api_key_env: str = "OPENAI_API_KEY",
    base_url: str | None = None,
) -> OpenAIResponsesClient:
    active_spec = spec or model_provider_spec("openai-responses")
    return OpenAIResponsesClient(
            model=model_name(config, active_spec.model_env, active_spec.default_model),
            api_key=config.secret_value(api_key_env),
            api_key_env=api_key_env,
            base_url=base_url or configured_base_url(active_spec, config.model_base_url),
            timeout_seconds=config.model_timeout_seconds,
            name=active_spec.provider_id,
    )


def _with_openai_fallback(config: AgentConfig, spec: ModelProviderSpec, primary: ModelClient) -> ModelClient:
    if not spec.allow_openai_fallback or spec.provider_id.startswith("openai"):
        return primary
    api_key_env = "OPENAI_API_KEY"
    if not (config.secret_value(api_key_env) or os.environ.get(api_key_env)):
        return primary
    return FallbackModelClient(
        clients=[
            primary,
            _openai_responses_client(
                config,
                spec=model_provider_spec("openai-responses"),
                api_key_env=api_key_env,
                base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            ),
        ],
        name=f"{primary.name}->openai-responses",
    )


def auto_model_provider() -> str:
    if os.environ.get("HUMUNGOUSAUR_CLOUD_FIRST", "").strip().lower() in {"1", "true", "yes"}:
        provider = _first_configured_cloud_provider()
        if provider:
            return provider
    if ollama_available():
        return "ollama"
    provider = _first_configured_cloud_provider()
    if provider:
        return provider
    return "ollama"


def model_name(config: AgentConfig, env_name: str, default: str) -> str:
    if config.model_name and config.model_name != "gpt-5-mini":
        return config.model_name
    if os.environ.get(env_name):
        return os.environ[env_name]
    return default


def _first_configured_cloud_provider() -> str | None:
    for spec in MODEL_PROVIDER_REGISTRY:
        if spec.provider_id in {"ollama", "local-openai"}:
            continue
        if provider_has_credentials(spec):
            return spec.provider_id
    return None


def _ollama_spec_with_runtime_default(spec: ModelProviderSpec) -> ModelProviderSpec:
    if os.environ.get(spec.model_env):
        return spec
    return ModelProviderSpec(
        provider_id=spec.provider_id,
        label=spec.label,
        transport=spec.transport,
        default_model=recommended_ollama_model(),
        model_env=spec.model_env,
        api_key_envs=spec.api_key_envs,
        default_base_url=spec.default_base_url,
        base_url_env=spec.base_url_env,
        aliases=spec.aliases,
        allow_openai_fallback=spec.allow_openai_fallback,
    )
