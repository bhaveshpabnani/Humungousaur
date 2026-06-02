import unittest
from unittest.mock import patch

from humungousaur.planning.model_clients import OpenAICompatibleChatClient, redact_secrets


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


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self.body


if __name__ == "__main__":
    unittest.main()
