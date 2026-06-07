from __future__ import annotations

import os

from humungousaur.config import AgentConfig

from .local_models import ollama_available, recommended_ollama_model
from .model_clients import ModelClient, OpenAICompatibleChatClient, OpenAIResponsesClient


def build_model_client(config: AgentConfig) -> ModelClient:
    provider = config.model_provider
    if provider == "auto":
        provider = auto_model_provider()
    if provider == "openai":
        provider = "openai-responses"
    if provider == "openai-responses":
        api_key_env = config.model_api_key_env or "OPENAI_API_KEY"
        return OpenAIResponsesClient(
            model=model_name(config, "OPENAI_MODEL", "gpt-5-mini"),
            api_key=config.secret_value(api_key_env),
            api_key_env=api_key_env,
            base_url=config.model_base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            timeout_seconds=config.model_timeout_seconds,
        )
    if provider == "openai-chat":
        api_key_env = config.model_api_key_env or "OPENAI_API_KEY"
        return OpenAICompatibleChatClient(
            model=model_name(config, "OPENAI_MODEL", "gpt-5-mini"),
            api_key=config.secret_value(api_key_env),
            api_key_env=api_key_env,
            base_url=config.model_base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            timeout_seconds=config.model_timeout_seconds,
            name="openai-chat",
        )
    if provider == "groq":
        api_key_env = config.model_api_key_env or "GROQ_API_KEY"
        return OpenAICompatibleChatClient(
            model=model_name(config, "GROQ_MODEL", "llama-3.3-70b-versatile"),
            api_key=config.secret_value(api_key_env),
            api_key_env=api_key_env,
            base_url=config.model_base_url or os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            timeout_seconds=config.model_timeout_seconds,
            name="groq-chat",
        )
    if provider == "grok":
        api_key_env = config.model_api_key_env or "XAI_API_KEY"
        return OpenAICompatibleChatClient(
            model=model_name(config, "XAI_MODEL", "grok-4.3"),
            api_key=config.secret_value(api_key_env),
            api_key_env=api_key_env,
            base_url=config.model_base_url or os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1"),
            timeout_seconds=config.model_timeout_seconds,
            name="grok-chat",
        )
    if provider == "ollama":
        api_key_env = config.model_api_key_env or "OLLAMA_API_KEY"
        return OpenAICompatibleChatClient(
            model=model_name(config, "OLLAMA_MODEL", recommended_ollama_model()),
            api_key=config.secret_value(api_key_env),
            api_key_env=api_key_env,
            base_url=config.model_base_url or os.environ.get("OLLAMA_BASE_URL") or os.environ.get("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1"),
            timeout_seconds=config.model_timeout_seconds,
            name="ollama-chat",
        )
    if provider == "local-openai":
        api_key_env = config.model_api_key_env or "LOCAL_LLM_API_KEY"
        return OpenAICompatibleChatClient(
            model=model_name(config, "LOCAL_LLM_MODEL", "llama3.1"),
            api_key=config.secret_value(api_key_env),
            api_key_env=api_key_env,
            base_url=config.model_base_url or os.environ.get("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1"),
            timeout_seconds=config.model_timeout_seconds,
            name="local-openai-chat",
        )
    raise ValueError(f"Unknown model provider: {provider}")


def auto_model_provider() -> str:
    if os.environ.get("HUMUNGOUSAUR_CLOUD_FIRST", "").strip().lower() in {"1", "true", "yes"}:
        if os.environ.get("OPENAI_API_KEY"):
            return "openai-responses"
        if os.environ.get("GROQ_API_KEY"):
            return "groq"
    if ollama_available():
        return "ollama"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai-responses"
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    return "ollama"


def model_name(config: AgentConfig, env_name: str, default: str) -> str:
    if config.model_name and config.model_name != "gpt-5-mini":
        return config.model_name
    if os.environ.get(env_name):
        return os.environ[env_name]
    return default
