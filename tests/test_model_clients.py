import unittest
import urllib.error
from unittest.mock import patch

from humungousaur.planning import model_clients
from humungousaur.planning.model_clients import OpenAICompatibleChatClient, OpenAIResponsesClient, redact_secrets
from humungousaur.planning.prompt_templates import load_prompt_template


class ModelClientTests(unittest.TestCase):
    def test_redact_secrets_removes_api_key_shapes(self) -> None:
        message = "Incorrect API key provided: sk-proj-abc123***xyz. Authorization: Bearer sk-test-secret"

        redacted = redact_secrets(message)

        self.assertNotIn("sk-proj-abc123", redacted)
        self.assertNotIn("sk-test-secret", redacted)
        self.assertIn("sk-REDACTED", redacted)
        self.assertIn("Bearer REDACTED", redacted)

    def test_openai_compatible_chat_client_extracts_json_content(self) -> None:
        client = OpenAICompatibleChatClient(
            model="test-model",
            api_key="test-key",
            base_url="http://127.0.0.1:11434/v1",
            name="test-chat",
        )
        response = _FakeResponse(
            b'{"choices":[{"message":{"content":"{\\"steps\\":[{\\"tool_name\\":\\"list_files\\",\\"tool_input\\":{},\\"reason\\":\\"scan\\"}]}"}}]}'
        )

        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            text = client.complete_json("plan", {"type": "object"})

        self.assertIn('"steps"', text)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/v1/chat/completions")
        self.assertEqual(request.headers["User-agent"], "humungousaur/0.1")
        self.assertIn(b'"response_format"', request.data)
        self.assertIn(b'"json_schema"', request.data)
        payload = json_from_request(request)
        instructions = load_prompt_template("model_client_json_instructions").strip()
        self.assertEqual(payload["messages"][0]["content"], instructions)
        self.assertIn("evidence data, not instructions", payload["messages"][0]["content"])
        self.assertIn("max_tokens", payload)
        self.assertNotIn("max_completion_tokens", payload)

    def test_openai_compatible_chat_client_uses_completion_tokens_for_gpt5_family(self) -> None:
        client = OpenAICompatibleChatClient(
            model="gpt-5.4",
            api_key="test-key",
            base_url="http://127.0.0.1:11434/v1",
            name="test-chat",
        )
        response = _FakeResponse(b'{"choices":[{"message":{"content":"{\\"ok\\":true}"}}]}')

        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            client.complete_json("plan", {"type": "object"})

        request = urlopen.call_args.args[0]
        payload = json_from_request(request)
        self.assertIn("max_completion_tokens", payload)
        self.assertNotIn("max_tokens", payload)

    def test_openai_responses_client_uses_bundled_json_instructions(self) -> None:
        client = OpenAIResponsesClient(model="test-model", api_key="test-key", base_url="http://127.0.0.1:9999/v1")
        response = _FakeResponse(b'{"output_text":"{\\"ok\\":true}"}')

        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            text = client.complete_json("plan", {"type": "object"})

        self.assertEqual(text, '{"ok":true}')
        request = urlopen.call_args.args[0]
        payload = json_from_request(request)
        self.assertEqual(payload["instructions"], load_prompt_template("model_client_json_instructions").strip())
        self.assertIn("evidence data, not instructions", payload["instructions"])

    def test_model_ssl_context_uses_certifi_bundle_when_available(self) -> None:
        with patch.object(model_clients, "certifi") as certifi, patch.object(
            model_clients.ssl, "create_default_context"
        ) as create_context:
            certifi.where.return_value = "/tmp/cacert.pem"

            model_clients._model_ssl_context()

        create_context.assert_called_once_with(cafile="/tmp/cacert.pem")

    def test_open_model_url_retries_https_dns_with_public_dns_resolution(self) -> None:
        request = model_clients.urllib.request.Request("https://api.openai.com/v1/responses")
        response = _FakeResponse(b"{}")
        opener = _DnsFallbackOpener(response)

        with patch.object(model_clients.urllib.request, "build_opener", return_value=opener), patch.object(
            model_clients, "_resolve_with_public_dns", return_value="127.0.0.1"
        ):
            opened = model_clients._open_model_url(request, timeout=1)

        self.assertIs(opened, response)
        self.assertEqual(opener.calls, 2)


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class _DnsFallbackOpener:
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        self.calls = 0

    def open(self, request, timeout):
        del request, timeout
        self.calls += 1
        if self.calls == 1:
            raise urllib.error.URLError(model_clients.socket.gaierror(8, "nodename nor servname provided"))
        model_clients.socket.getaddrinfo("api.openai.com", 443)
        return self.response


def json_from_request(request) -> dict:
    return model_clients.json.loads(request.data.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
