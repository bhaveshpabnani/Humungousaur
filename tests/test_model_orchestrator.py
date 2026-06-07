import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from humungousaur.config import AgentConfig
from humungousaur.interaction import HarnessDecision, HarnessResult, Stimulus, harness_result_to_dict
from humungousaur.orchestrator import AgentOrchestrator
from humungousaur.planning.providers import ModelPlanProvider
from humungousaur.planning.model_factory import auto_model_provider
from humungousaur.planning.model_clients import FallbackModelClient, ModelClient, OpenAICompatibleChatClient
from humungousaur.tools.conversation.implementation import ConversationResponsePrepareTool


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

    def test_model_provider_uses_runtime_secret_and_desktop_model_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                planner_provider="model",
                model_provider="groq",
                model_name="desktop-model",
                runtime_secrets={"GROQ_API_KEY": "gsk-desktop"},
            )

            with patch.dict("os.environ", {"GROQ_MODEL": "env-model"}, clear=True):
                client = AgentOrchestrator(config)._build_model_client()

            self.assertIsInstance(client, OpenAICompatibleChatClient)
            assert isinstance(client, OpenAICompatibleChatClient)
            self.assertEqual(client.model, "desktop-model")
            self.assertEqual(client.api_key, "gsk-desktop")

    def test_groq_provider_uses_openai_fallback_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(
                workspace=workspace,
                data_dir=workspace / "artifacts",
                planner_provider="model",
                model_provider="groq",
            )

            with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
                client = AgentOrchestrator(config)._build_model_client()

            self.assertIsInstance(client, FallbackModelClient)
            assert isinstance(client, FallbackModelClient)
            self.assertEqual(client.name, "groq-chat->openai-responses")
            self.assertEqual(client.clients[0].name, "groq-chat")
            self.assertEqual(client.clients[1].name, "openai-responses")

    def test_conversation_response_tool_returns_direct_user_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts", planner_provider="explicit")

            result = AgentOrchestrator(config).run(
                'conversation_response_prepare {"text":"Hey, I am here.","reason":"Direct greeting response."}'
            )

            self.assertEqual(result.final_response, "Hey, I am here.")
            self.assertEqual(result.results[0].tool_name, "conversation_response_prepare")

    def test_harness_payload_includes_direct_response_without_run(self) -> None:
        payload = harness_result_to_dict(
            HarnessResult(
                stimulus=Stimulus(text="Hi"),
                decision=HarnessDecision(
                    decision="respond",
                    request="",
                    response_mode="text",
                    reason="No tool run needed.",
                    should_run_agent=False,
                    should_record_activity=False,
                    should_prepare_voice=False,
                    should_speak=False,
                    direct_response="Hello.",
                ),
            )
        )

        self.assertIsNone(payload["run"])
        self.assertEqual(payload["response"], "Hello.")

    def test_model_planner_repairs_tool_input_schema_before_execution(self) -> None:
        tool = ConversationResponsePrepareTool()
        provider = ModelPlanProvider(
            _SequenceModelClient(
                [
                    '{"steps":[{"tool_name":"conversation_response_prepare","tool_input":{},"reason":"reply"}]}',
                    '{"steps":[{"tool_name":"conversation_response_prepare","tool_input":{"text":"Hi there.","reason":"Direct greeting."},"reason":"reply"}]}',
                ]
            ),
            allowed_tools={tool.name},
            tool_catalog={
                tool.name: {
                    "description": tool.description,
                    "risk_level": tool.risk_level.value,
                    "requires_approval": tool.requires_approval,
                    "input_schema": tool.input_schema,
                    "capability_group": tool.capability_group,
                }
            },
        )

        plan = provider.plan("Hi")

        self.assertEqual(plan.used_provider, "model:sequence:repair")
        self.assertEqual(plan.steps[0].tool_input["text"], "Hi there.")

    def test_model_planner_repairs_tool_input_when_plan_repair_stays_invalid(self) -> None:
        tool = ConversationResponsePrepareTool()
        invalid_plan = '{"steps":[{"tool_name":"conversation_response_prepare","tool_input":{},"reason":"reply"}]}'
        provider = ModelPlanProvider(
            _SequenceModelClient(
                [
                    invalid_plan,
                    invalid_plan,
                    '{"tool_input":{"text":"Hello from repaired input.","reason":"Direct response."},"reason":"Filled required tool input."}',
                ]
            ),
            allowed_tools={tool.name},
            tool_catalog={
                tool.name: {
                    "description": tool.description,
                    "risk_level": tool.risk_level.value,
                    "requires_approval": tool.requires_approval,
                    "input_schema": tool.input_schema,
                    "capability_group": tool.capability_group,
                }
            },
        )

        plan = provider.plan("Hi")

        self.assertEqual(plan.used_provider, "model:sequence:repair")
        self.assertEqual(plan.steps[0].tool_input["text"], "Hello from repaired input.")

    def test_model_planner_repairs_numeric_schema_bounds(self) -> None:
        tool_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}},
            "required": ["limit"],
        }
        provider = ModelPlanProvider(
            _SequenceModelClient(
                [
                    '{"steps":[{"tool_name":"limited_tool","tool_input":{"limit":50},"reason":"inspect"}]}',
                    '{"steps":[{"tool_name":"limited_tool","tool_input":{"limit":10},"reason":"inspect"}]}',
                ]
            ),
            allowed_tools={"limited_tool"},
            tool_catalog={
                "limited_tool": {
                    "description": "Tool with bounded numeric limit.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": tool_schema,
                    "capability_group": "test",
                }
            },
        )

        plan = provider.plan("Inspect bounded state.")

        self.assertEqual(plan.used_provider, "model:sequence:repair")
        self.assertEqual(plan.steps[0].tool_input["limit"], 10)

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

class _SequenceModelClient(ModelClient):
    name = "sequence"

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses

    def complete_json(self, prompt: str, schema: dict) -> str:
        del prompt, schema
        if not self.responses:
            raise AssertionError("No model responses left.")
        return self.responses.pop(0)


if __name__ == "__main__":
    unittest.main()
