import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from humungousaur.config import AgentConfig
from humungousaur.orchestrator import AgentOrchestrator
from humungousaur.planning.model_factory import auto_model_provider
from humungousaur.planning.model_clients import OpenAICompatibleChatClient


class ModelOrchestratorTests(unittest.TestCase):
    def test_model_planner_without_api_key_does_not_guess_natural_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "README.md").write_text("# Demo\n\nLocal assistant.", encoding="utf-8")
            config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                planner_provider="model",
                model_provider="openai-responses",
                model_name="test-model",
            )

            with patch.dict("os.environ", {}, clear=True):
                result = AgentOrchestrator(config).run("summarize this project")

            self.assertIn("could not create a valid tool plan", result.final_response)
            self.assertEqual(result.results[0].tool_name, "write_note")

    def test_local_openai_provider_uses_env_base_url_without_live_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / ".env").write_text(
                "LOCAL_LLM_BASE_URL=http://127.0.0.1:9999/v1\nLOCAL_LLM_API_KEY=local-test\n",
                encoding="utf-8",
            )
            config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                planner_provider="model",
                model_provider="local-openai",
                model_name="llama-test",
            )

            with patch.dict("os.environ", {}, clear=True):
                client = AgentOrchestrator(config)._build_model_client()

            self.assertIsInstance(client, OpenAICompatibleChatClient)
            assert isinstance(client, OpenAICompatibleChatClient)
            self.assertEqual(client.base_url, "http://127.0.0.1:9999/v1")
            self.assertEqual(client.api_key_env, "LOCAL_LLM_API_KEY")

    def test_grok_provider_defaults_to_xai_openai_compatible_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                planner_provider="model",
                model_provider="grok",
                model_name="grok-4.3",
            )

            with patch.dict("os.environ", {}, clear=True):
                client = AgentOrchestrator(config)._build_model_client()

            self.assertIsInstance(client, OpenAICompatibleChatClient)
            assert isinstance(client, OpenAICompatibleChatClient)
            self.assertEqual(client.base_url, "https://api.x.ai/v1")
            self.assertEqual(client.api_key_env, "XAI_API_KEY")

    def test_groq_provider_defaults_to_openai_compatible_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                planner_provider="model",
                model_provider="groq",
            )

            with patch.dict("os.environ", {}, clear=True):
                client = AgentOrchestrator(config)._build_model_client()

            self.assertIsInstance(client, OpenAICompatibleChatClient)
            assert isinstance(client, OpenAICompatibleChatClient)
            self.assertEqual(client.base_url, "https://api.groq.com/openai/v1")
            self.assertEqual(client.api_key_env, "GROQ_API_KEY")
            self.assertEqual(client.model, "llama-3.3-70b-versatile")

    def test_ollama_provider_defaults_to_local_openai_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                planner_provider="model",
                model_provider="ollama",
            )

            with (
                patch.dict("os.environ", {}, clear=True),
                patch("humungousaur.planning.local_models.list_ollama_models", return_value=[]),
            ):
                client = AgentOrchestrator(config)._build_model_client()

            self.assertIsInstance(client, OpenAICompatibleChatClient)
            assert isinstance(client, OpenAICompatibleChatClient)
            self.assertEqual(client.base_url, "http://127.0.0.1:11434/v1")
            self.assertEqual(client.api_key_env, "OLLAMA_API_KEY")
            self.assertEqual(client.model, "llama3.2:3b")

    def test_auto_provider_prefers_available_ollama_for_local_first(self) -> None:
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test", "GROQ_API_KEY": "gsk-test"}, clear=True),
            patch("humungousaur.planning.model_factory.ollama_available", return_value=True),
        ):
            self.assertEqual(auto_model_provider(), "ollama")

    def test_auto_provider_can_be_forced_cloud_first(self) -> None:
        with (
            patch.dict("os.environ", {"HUMUNGOUSAUR_CLOUD_FIRST": "1", "OPENAI_API_KEY": "sk-test"}, clear=True),
            patch("humungousaur.planning.model_factory.ollama_available", return_value=True),
        ):
            self.assertEqual(auto_model_provider(), "openai-responses")


if __name__ == "__main__":
    unittest.main()
