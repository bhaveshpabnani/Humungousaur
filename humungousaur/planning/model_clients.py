from __future__ import annotations

import json
import http.client
import os
import re
import socket
import ssl
import subprocess
import time
import urllib.error
from urllib.parse import urlparse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from humungousaur.planning.prompt_templates import load_prompt_template

try:
    import certifi
except Exception:  # pragma: no cover - optional dependency fallback
    certifi = None


class ModelClientError(RuntimeError):
    pass


def redact_secrets(text: str) -> str:
    redacted = re.sub(r"sk-[A-Za-z0-9_*\-.]+", "sk-REDACTED", text)
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9_*\-.]+", "Bearer REDACTED", redacted, flags=re.IGNORECASE)
    return redacted


def _retry_after_seconds(exc: urllib.error.HTTPError) -> float:
    header = exc.headers.get("Retry-After") if exc.headers is not None else None
    if header:
        try:
            return max(0.5, min(float(header), 20.0))
        except ValueError:
            pass
    try:
        detail = exc.read().decode("utf-8", errors="replace")
    except Exception:
        return 2.0
    match = re.search(r"try again in ([0-9.]+)s", detail, flags=re.IGNORECASE)
    if match:
        return max(0.5, min(float(match.group(1)) + 0.25, 20.0))
    return 2.0


class ModelClient(ABC):
    name: str

    @abstractmethod
    def complete_json(self, prompt: str, schema: dict[str, Any]) -> str:
        raise NotImplementedError


MODEL_CLIENT_USER_AGENT = "humungousaur/0.1"
MODEL_CLIENT_INSTRUCTIONS_TEMPLATE = "model_client_json_instructions"


def _model_ssl_context() -> ssl.SSLContext:
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def _open_model_url(request: urllib.request.Request, *, timeout: float):
    parsed = urlparse(request.full_url)
    if parsed.scheme == "https":
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=_model_ssl_context()))
        try:
            return opener.open(request, timeout=timeout)
        except urllib.error.URLError as exc:
            if not _is_dns_resolution_error(exc):
                raise
            resolved_ip = _resolve_with_public_dns(parsed.hostname or "")
            if not resolved_ip:
                raise
            return _open_with_resolved_host(opener, request, timeout=timeout, hostname=parsed.hostname or "", resolved_ip=resolved_ip)
    return urllib.request.urlopen(request, timeout=timeout)


def _is_dns_resolution_error(exc: urllib.error.URLError) -> bool:
    reason = getattr(exc, "reason", None)
    if isinstance(reason, socket.gaierror):
        return True
    return "nodename nor servname provided" in str(exc).lower()


def _resolve_with_public_dns(hostname: str) -> str:
    if not hostname:
        return ""
    try:
        completed = subprocess.run(
            ["dig", "+short", hostname, "@1.1.1.1"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    for line in completed.stdout.splitlines():
        candidate = line.strip()
        if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", candidate):
            return candidate
    return ""


def _open_with_resolved_host(opener: urllib.request.OpenerDirector, request: urllib.request.Request, *, timeout: float, hostname: str, resolved_ip: str):
    original_getaddrinfo = socket.getaddrinfo

    def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        if str(host).lower() == hostname.lower():
            return original_getaddrinfo(resolved_ip, port, family, type, proto, flags)
        return original_getaddrinfo(host, port, family, type, proto, flags)

    socket.getaddrinfo = patched_getaddrinfo
    try:
        return opener.open(request, timeout=timeout)
    finally:
        socket.getaddrinfo = original_getaddrinfo


def _model_client_json_instructions() -> str:
    return load_prompt_template(MODEL_CLIENT_INSTRUCTIONS_TEMPLATE).strip()


@dataclass(slots=True)
class StaticModelClient(ModelClient):
    response: str
    name: str = "static"

    def complete_json(self, prompt: str, schema: dict[str, Any]) -> str:
        return self.response


@dataclass(slots=True)
class FallbackModelClient(ModelClient):
    clients: list[ModelClient]
    name: str = "fallback"

    def complete_json(self, prompt: str, schema: dict[str, Any]) -> str:
        errors: list[str] = []
        for client in self.clients:
            try:
                return client.complete_json(prompt, schema)
            except ModelClientError as exc:
                errors.append(f"{client.name}: {redact_secrets(str(exc))}")
        raise ModelClientError("All model providers failed: " + " | ".join(errors))


@dataclass(slots=True)
class OpenAIResponsesClient(ModelClient):
    model: str
    api_key: str | None = None
    api_key_env: str = "OPENAI_API_KEY"
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 45.0
    name: str = "openai-responses"

    def complete_json(self, prompt: str, schema: dict[str, Any]) -> str:
        api_key = self.api_key or os.environ.get(self.api_key_env)
        if not api_key:
            raise ModelClientError(f"{self.api_key_env} is required for the OpenAI Responses planner.")

        payload = {
            "model": self.model,
            "instructions": _model_client_json_instructions(),
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "humungousaur_plan",
                    "strict": False,
                    "schema": schema,
                }
            },
        }
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": MODEL_CLIENT_USER_AGENT,
            },
            method="POST",
        )
        try:
            body = self._urlopen_json(request)
        except urllib.error.HTTPError as exc:
            detail = redact_secrets(exc.read().decode("utf-8", errors="replace"))
            message = self._extract_error_message(detail)
            raise ModelClientError(f"OpenAI Responses API failed: HTTP {exc.code}: {message}") from exc
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError) as exc:
            raise ModelClientError(f"OpenAI Responses API request failed: {exc}") from exc

        text = self._extract_output_text(body)
        if not text:
            raise ModelClientError("OpenAI Responses API returned no output text.")
        return text

    def _urlopen_json(self, request: urllib.request.Request) -> dict[str, Any]:
        for _attempt in range(3):
            try:
                with _open_model_url(request, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and _attempt < 2:
                    time.sleep(_retry_after_seconds(exc))
                    continue
                raise
            except (urllib.error.URLError, http.client.HTTPException, TimeoutError) as exc:
                raise exc
        raise RuntimeError("OpenAI Responses request retry loop ended unexpectedly.")

    def _extract_error_message(self, detail: str) -> str:
        try:
            payload = json.loads(detail)
        except json.JSONDecodeError:
            return detail[:500]
        error = payload.get("error", {})
        if not isinstance(error, dict):
            return detail[:500]
        parts = []
        if error.get("type"):
            parts.append(f"type={error['type']}")
        if error.get("code"):
            parts.append(f"code={error['code']}")
        if error.get("message"):
            parts.append(f"message={redact_secrets(str(error['message']))}")
        return "; ".join(parts) or "unknown provider error"

    def _extract_output_text(self, body: dict[str, Any]) -> str:
        if isinstance(body.get("output_text"), str):
            return body["output_text"]
        chunks: list[str] = []
        for item in body.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if isinstance(text, str):
                    chunks.append(text)
        return "\n".join(chunks).strip()


@dataclass(slots=True)
class OpenAICompatibleChatClient(ModelClient):
    model: str
    api_key: str | None = None
    api_key_env: str = "OPENAI_API_KEY"
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 45.0
    name: str = "openai-compatible-chat"
    fallback_to_json_object: bool = True
    max_tokens: int = 400

    def complete_json(self, prompt: str, schema: dict[str, Any]) -> str:
        api_key = self._api_key()
        if not api_key:
            raise ModelClientError(f"{self.api_key_env} is required for the {self.name} planner.")

        try:
            body = self._post_chat(prompt, self._json_schema_format(schema), api_key)
        except urllib.error.HTTPError as exc:
            detail = redact_secrets(exc.read().decode("utf-8", errors="replace"))
            if not self.fallback_to_json_object or exc.code not in {400, 422}:
                message = self._extract_error_message(detail)
                raise ModelClientError(f"{self.name} API failed: HTTP {exc.code}: {message}") from exc
            try:
                body = self._post_chat(prompt, {"type": "json_object"}, api_key)
            except urllib.error.HTTPError as retry_exc:
                retry_detail = redact_secrets(retry_exc.read().decode("utf-8", errors="replace"))
                message = self._extract_error_message(retry_detail)
                raise ModelClientError(f"{self.name} API failed: HTTP {retry_exc.code}: {message}") from retry_exc
            except (urllib.error.URLError, http.client.HTTPException, TimeoutError) as retry_exc:
                raise ModelClientError(f"{self.name} API request failed: {retry_exc}") from retry_exc
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError) as exc:
            raise ModelClientError(f"{self.name} API request failed: {exc}") from exc

        text = self._extract_output_text(body)
        if not text:
            raise ModelClientError(f"{self.name} API returned no output text.")
        return text

    def _api_key(self) -> str | None:
        key = self.api_key or os.environ.get(self.api_key_env)
        if key:
            return key
        host = self.base_url.lower()
        if "localhost" in host or "127.0.0.1" in host:
            return "local"
        return None

    def _post_chat(self, prompt: str, response_format: dict[str, Any], api_key: str) -> dict[str, Any]:
        token_limit = max(128, min(int(self.max_tokens or 400), 1200))
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": _model_client_json_instructions(),
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": response_format,
            "stream": False,
        }
        payload["max_completion_tokens" if _chat_model_uses_completion_tokens(self.model) else "max_tokens"] = token_limit
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": MODEL_CLIENT_USER_AGENT,
            },
            method="POST",
        )
        for _attempt in range(3):
            try:
                with _open_model_url(request, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and _attempt < 2:
                    time.sleep(_retry_after_seconds(exc))
                    continue
                raise
            except (urllib.error.URLError, http.client.HTTPException, TimeoutError) as exc:
                raise exc
        raise RuntimeError(f"{self.name} request retry loop ended unexpectedly.")

    def _json_schema_format(self, schema: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "humungousaur_plan",
                "strict": False,
                "schema": schema,
            },
        }

    def _extract_error_message(self, detail: str) -> str:
        try:
            payload = json.loads(detail)
        except json.JSONDecodeError:
            return detail[:500]
        error = payload.get("error", {})
        if not isinstance(error, dict):
            return detail[:500]
        parts = []
        if error.get("type"):
            parts.append(f"type={error['type']}")
        if error.get("code"):
            parts.append(f"code={error['code']}")
        if error.get("message"):
            parts.append(f"message={redact_secrets(str(error['message']))}")
        return "; ".join(parts) or "unknown provider error"

    def _extract_output_text(self, body: dict[str, Any]) -> str:
        choices = body.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            chunks = [item.get("text", "") for item in content if isinstance(item, dict)]
            return "\n".join(chunk for chunk in chunks if chunk).strip()
        return ""


def _chat_model_uses_completion_tokens(model: str) -> bool:
    normalized = str(model or "").strip().lower()
    return normalized.startswith(("gpt-5", "o1", "o3", "o4"))


@dataclass(slots=True)
class AnthropicMessagesClient(ModelClient):
    model: str
    api_key: str | None = None
    api_key_env: str = "ANTHROPIC_API_KEY"
    base_url: str = "https://api.anthropic.com"
    timeout_seconds: float = 45.0
    name: str = "anthropic-messages"
    max_tokens: int = 400
    anthropic_version: str = "2023-06-01"

    def complete_json(self, prompt: str, schema: dict[str, Any]) -> str:
        del schema
        api_key = self.api_key or os.environ.get(self.api_key_env)
        if not api_key:
            raise ModelClientError(f"{self.api_key_env} is required for the {self.name} planner.")

        payload = {
            "model": self.model,
            "max_tokens": max(128, min(int(self.max_tokens or 400), 1200)),
            "system": _model_client_json_instructions(),
            "messages": [{"role": "user", "content": prompt}],
        }
        request = urllib.request.Request(
            self._messages_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": api_key,
                "anthropic-version": self.anthropic_version,
                "Content-Type": "application/json",
                "User-Agent": MODEL_CLIENT_USER_AGENT,
            },
            method="POST",
        )
        try:
            body = self._urlopen_json(request)
        except urllib.error.HTTPError as exc:
            detail = redact_secrets(exc.read().decode("utf-8", errors="replace"))
            message = self._extract_error_message(detail)
            raise ModelClientError(f"{self.name} API failed: HTTP {exc.code}: {message}") from exc
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError) as exc:
            raise ModelClientError(f"{self.name} API request failed: {exc}") from exc

        text = self._extract_output_text(body)
        if not text:
            raise ModelClientError(f"{self.name} API returned no output text.")
        return text

    def _messages_url(self) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/v1"):
            return f"{base}/messages"
        return f"{base}/v1/messages"

    def _urlopen_json(self, request: urllib.request.Request) -> dict[str, Any]:
        for _attempt in range(3):
            try:
                with _open_model_url(request, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and _attempt < 2:
                    time.sleep(_retry_after_seconds(exc))
                    continue
                raise
            except (urllib.error.URLError, http.client.HTTPException, TimeoutError) as exc:
                raise exc
        raise RuntimeError(f"{self.name} request retry loop ended unexpectedly.")

    def _extract_error_message(self, detail: str) -> str:
        try:
            payload = json.loads(detail)
        except json.JSONDecodeError:
            return detail[:500]
        error = payload.get("error", {})
        if not isinstance(error, dict):
            return detail[:500]
        parts = []
        if error.get("type"):
            parts.append(f"type={error['type']}")
        if error.get("message"):
            parts.append(f"message={redact_secrets(str(error['message']))}")
        return "; ".join(parts) or "unknown provider error"

    def _extract_output_text(self, body: dict[str, Any]) -> str:
        chunks: list[str] = []
        for item in body.get("content", []):
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str):
                chunks.append(text)
        return "\n".join(chunks).strip()
