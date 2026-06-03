import unittest

from humungousaur.planning.model_clients import ModelClientError, StaticModelClient
from humungousaur.planning.providers import ExplicitFallbackPlanProvider, ModelPlanProvider
from humungousaur.planning.structured import PlanValidationError, StructuredPlanParser
from humungousaur.planner import Planner


class StructuredPlanParserTests(unittest.TestCase):
    def test_parses_allowed_tool_plan(self) -> None:
        parser = StructuredPlanParser({"list_files"})

        steps = parser.parse('{"steps":[{"tool_name":"list_files","tool_input":{"path":"."},"reason":"scan"}]}')

        self.assertEqual(steps[0].tool_name, "list_files")
        self.assertEqual(steps[0].source, "structured-json")

    def test_rejects_unknown_tool(self) -> None:
        parser = StructuredPlanParser({"list_files"})

        with self.assertRaises(PlanValidationError):
            parser.parse('{"steps":[{"tool_name":"delete_everything","tool_input":{},"reason":"bad"}]}')

    def test_rejects_non_json_plan(self) -> None:
        parser = StructuredPlanParser({"list_files"})

        with self.assertRaises(PlanValidationError):
            parser.parse("click the button then delete files")

    def test_accepts_single_tool_alias_shape(self) -> None:
        parser = StructuredPlanParser({"search_workspace"})

        steps = parser.parse('{"tool":"search_workspace","input":{"query":"README"}}')

        self.assertEqual(steps[0].tool_name, "search_workspace")
        self.assertEqual(steps[0].tool_input, {"query": "README"})

    def test_accepts_function_call_alias_shape(self) -> None:
        parser = StructuredPlanParser({"search_workspace"})

        steps = parser.parse('{"function_name":"search_workspace","args":{"query":"voice response"}}')

        self.assertEqual(steps[0].tool_name, "search_workspace")
        self.assertEqual(steps[0].tool_input, {"query": "voice response"})

    def test_json_schema_limits_tool_names_to_allowlist(self) -> None:
        parser = StructuredPlanParser({"list_files", "read_file"})

        schema = parser.json_schema()

        tool_enum = schema["properties"]["steps"]["items"]["properties"]["tool_name"]["enum"]
        self.assertEqual(tool_enum, ["list_files", "read_file"])


class ModelPlanProviderTests(unittest.TestCase):
    def test_model_plan_provider_uses_valid_structured_plan(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"search_workspace","tool_input":{"query":"audit"},"reason":"find audit refs"}]}'
        )
        provider = ModelPlanProvider(client, {"search_workspace"}, fallback=ExplicitFallbackPlanProvider())

        plan = provider.plan("look around")

        self.assertEqual(plan.steps[0].tool_name, "search_workspace")
        self.assertEqual(plan.steps[0].source, "model:static")
        self.assertEqual(plan.used_provider, "model:static")
        self.assertFalse(plan.fallback_used)

    def test_model_plan_provider_falls_back_on_disallowed_tool(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"delete_everything","tool_input":{},"reason":"bad"}]}'
        )
        provider = ModelPlanProvider(client, {"list_files", "search_workspace"}, fallback=ExplicitFallbackPlanProvider())

        plan = provider.plan('search_workspace {"query":"audit"}')

        self.assertEqual(plan.steps[0].tool_name, "search_workspace")
        self.assertEqual(plan.steps[0].source, "explicit")
        self.assertEqual(plan.requested_provider, "model")
        self.assertEqual(plan.used_provider, "explicit")
        self.assertTrue(plan.fallback_used)
        self.assertIsNotNone(plan.error)

    def test_model_plan_provider_falls_back_when_client_fails(self) -> None:
        class FailingClient(StaticModelClient):
            def complete_json(self, prompt, schema):
                raise ModelClientError("offline")

        provider = ModelPlanProvider(FailingClient("{}"), {"list_files"}, fallback=ExplicitFallbackPlanProvider())

        plan = provider.plan('list_files {"path":"."}')

        self.assertEqual(plan.steps[0].tool_name, "list_files")
        self.assertEqual(plan.steps[0].source, "explicit")
        self.assertTrue(plan.fallback_used)

    def test_model_plan_provider_does_not_guess_natural_language_when_model_fails(self) -> None:
        class FailingClient(StaticModelClient):
            def complete_json(self, prompt, schema):
                raise ModelClientError("offline")

        provider = ModelPlanProvider(FailingClient("{}"), {"list_files"}, fallback=ExplicitFallbackPlanProvider({"list_files"}))

        plan = provider.plan("summarize this project")

        self.assertEqual(plan.steps, [])
        self.assertEqual(plan.used_provider, "explicit")
        self.assertTrue(plan.fallback_used)
        self.assertIn("Explicit fallback accepts only JSON plans", plan.error or "")

    def test_model_prompt_includes_tool_catalog_and_non_keyword_guidance(self) -> None:
        provider = ModelPlanProvider(
            StaticModelClient("{}"),
            {"browser_open"},
            tool_catalog={
                "browser_open": {
                    "description": "Open a safe HTTP(S) page in a local browser session.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"url": {"type": "string"}},
                        "required": ["url"],
                    },
                }
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        prompt = provider._build_prompt("open example.com", {"memory": "none"})

        self.assertIn("Choose tools by their descriptions", prompt)
        self.assertIn("Global intelligence rule", prompt)
        self.assertIn("OpenAI, Groq, Ollama", prompt)
        self.assertIn("do not use pattern-based", prompt)
        self.assertIn("hand off through the most relevant capability tool", prompt)
        self.assertIn("browser_open", prompt)
        self.assertIn("Open a safe HTTP(S) page", prompt)
        self.assertIn('"url"', prompt)
        self.assertIn("retrieved data", prompt)

    def test_explicit_provider_can_list_plugin_manifests(self) -> None:
        plan = ExplicitFallbackPlanProvider({"plugin_manifests"}).plan('plugin_manifests {"include_errors":true}')

        self.assertEqual(plan.steps[0].tool_name, "plugin_manifests")
        self.assertTrue(plan.steps[0].tool_input["include_errors"])

    def test_explicit_provider_prepares_voice_response(self) -> None:
        plan = ExplicitFallbackPlanProvider({"voice_response_prepare"}).plan('voice_response_prepare {"text":"hello there","reason":"test"}')

        self.assertEqual(plan.steps[0].tool_name, "voice_response_prepare")
        self.assertEqual(plan.steps[0].tool_input["text"], "hello there")

    def test_explicit_provider_accepts_unescaped_windows_path_argument(self) -> None:
        plan = ExplicitFallbackPlanProvider({"summarize_pdfs"}).plan('summarize_pdfs {"path":"C:\\Users\\bhave\\Downloads"}')

        self.assertEqual(plan.steps[0].tool_name, "summarize_pdfs")
        self.assertEqual(plan.steps[0].tool_input["path"], "C:\\Users\\bhave\\Downloads")

    def test_model_provider_can_handoff_to_shell_command_profiles(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"run_shell_command","tool_input":{"argv":["python","-c","print(42)"],"command_profile":"trusted_dev"},"reason":"run approved inline Python dev command"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"run_shell_command"},
            tool_catalog={
                "run_shell_command": {
                    "description": "Run a constrained local command in the workspace after explicit approval.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "argv": {"type": "array", "items": {"type": "string"}},
                            "command_profile": {"type": "string"},
                        },
                        "required": ["argv"],
                    },
                    "capability_group": "shell",
                }
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("run approved inline python for a dev task")

        self.assertEqual(plan.steps[0].tool_name, "run_shell_command")
        self.assertEqual(plan.steps[0].tool_input["command_profile"], "trusted_dev")
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_memory_summary_tool(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"memory_summary","tool_input":{"period":"today","query":"","limit":100},"reason":"recap local activity"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"memory_summary"},
            tool_catalog={
                "memory_summary": {
                    "description": "Summarize local assistant memory for today, yesterday, the last week, or recent activity.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"period": {"type": "string"}},
                        "required": ["period"],
                    },
                    "capability_group": "memory",
                }
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("what was I working on today?")

        self.assertEqual(plan.steps[0].tool_name, "memory_summary")
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_cognitive_focus_and_knowledge_tools(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"cognitive_focus_update","tool_input":{"mode":"monitoring","summary":"Track the active review.","pinned_context":["review"]},"reason":"set durable focus"},{"tool_name":"cognitive_knowledge_record","tool_input":{"kind":"procedure","text":"Use blockers-first updates for status.","source":"user","confidence":0.8},"reason":"store reusable procedure"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"cognitive_focus_update", "cognitive_knowledge_record"},
            tool_catalog={
                "cognitive_focus_update": {
                    "description": "Update the assistant's durable current focus with explicit goal/task IDs, mode, summary, and pinned context.",
                    "risk_level": "medium",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"mode": {"type": "string"}, "summary": {"type": "string"}},
                    },
                    "capability_group": "cognition",
                },
                "cognitive_knowledge_record": {
                    "description": "Record a durable fact, preference, procedure, project context, or lesson with evidence references.",
                    "risk_level": "medium",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"kind": {"type": "string"}, "text": {"type": "string"}},
                        "required": ["kind", "text"],
                    },
                    "capability_group": "cognition",
                },
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("remember how I like status updates and keep watching the review")

        self.assertEqual([step.tool_name for step in plan.steps], ["cognitive_focus_update", "cognitive_knowledge_record"])
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_cognitive_briefing_tool(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"cognitive_briefing_prepare","tool_input":{"purpose":"current","horizon_hours":24,"include_state":false},"reason":"prepare current-work briefing from cognitive state"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"cognitive_briefing_prepare"},
            tool_catalog={
                "cognitive_briefing_prepare": {
                    "description": "Prepare and store a model-led operational briefing from current focus, goals, tasks, memory, wakeups, recovery, skills, and persona.",
                    "risk_level": "medium",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "purpose": {"type": "string"},
                            "horizon_hours": {"type": "integer"},
                            "include_state": {"type": "boolean"},
                        },
                    },
                    "capability_group": "cognition",
                }
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("give me my current work briefing")

        self.assertEqual(plan.steps[0].tool_name, "cognitive_briefing_prepare")
        self.assertEqual(plan.steps[0].tool_input["horizon_hours"], 24)
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_cognitive_memory_curation_tool(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"cognitive_memory_curate","tool_input":{"purpose":"memory_hygiene","max_archive":5,"max_summaries":2,"include_state":false},"reason":"curate stale or duplicate cognitive knowledge"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"cognitive_memory_curate"},
            tool_catalog={
                "cognitive_memory_curate": {
                    "description": "Run a model-led memory hygiene pass over durable cognitive knowledge to retain, summarize, or archive exact records.",
                    "risk_level": "medium",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "purpose": {"type": "string"},
                            "max_archive": {"type": "integer"},
                            "max_summaries": {"type": "integer"},
                            "include_state": {"type": "boolean"},
                        },
                    },
                    "capability_group": "cognition",
                }
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("clean up stale memory but preserve useful project facts")

        self.assertEqual(plan.steps[0].tool_name, "cognitive_memory_curate")
        self.assertEqual(plan.steps[0].tool_input["max_archive"], 5)
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_cognitive_skill_evolution_tool(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"cognitive_skill_evolve","tool_input":{"purpose":"skill_review","max_updates":4,"max_new_skills":2,"include_state":false},"reason":"review reusable skills from cognitive evidence"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"cognitive_skill_evolve"},
            tool_catalog={
                "cognitive_skill_evolve": {
                    "description": "Run a model-led review of reusable cognitive skills to improve, retire, create, or retain exact skill records from evidence.",
                    "risk_level": "medium",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "purpose": {"type": "string"},
                            "max_updates": {"type": "integer"},
                            "max_new_skills": {"type": "integer"},
                            "include_state": {"type": "boolean"},
                        },
                    },
                    "capability_group": "cognition",
                }
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("review the assistant skills and improve outdated workflows")

        self.assertEqual(plan.steps[0].tool_name, "cognitive_skill_evolve")
        self.assertEqual(plan.steps[0].tool_input["max_new_skills"], 2)
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_cognitive_persona_evolution_tool(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"cognitive_persona_evolve","tool_input":{"purpose":"persona_review","include_state":false},"reason":"review assistant persona and user model from evidence"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"cognitive_persona_evolve"},
            tool_catalog={
                "cognitive_persona_evolve": {
                    "description": "Run a model-led review of assistant persona, user preferences, stable facts, boundaries, identity, and communication style from durable evidence.",
                    "risk_level": "medium",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "purpose": {"type": "string"},
                            "include_state": {"type": "boolean"},
                        },
                    },
                    "capability_group": "cognition",
                }
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("review how the assistant should communicate with me over time")

        self.assertEqual(plan.steps[0].tool_name, "cognitive_persona_evolve")
        self.assertEqual(plan.steps[0].tool_input["purpose"], "persona_review")
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_cognitive_self_review_tool(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"cognitive_self_review","tool_input":{"purpose":"autonomy_check","include_state":false},"reason":"review uncertainty, risks, and autonomy posture"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"cognitive_self_review"},
            tool_catalog={
                "cognitive_self_review": {
                    "description": "Run a model-led metacognitive self-review of uncertainty, risks, autonomy posture, open questions, and recommended next actions from current cognitive evidence.",
                    "risk_level": "medium",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "purpose": {"type": "string"},
                            "include_state": {"type": "boolean"},
                        },
                    },
                    "capability_group": "cognition",
                }
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("check your own uncertainty and decide whether to continue or ask me")

        self.assertEqual(plan.steps[0].tool_name, "cognitive_self_review")
        self.assertEqual(plan.steps[0].tool_input["purpose"], "autonomy_check")
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_cognitive_interaction_review_tool(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"cognitive_interaction_review","tool_input":{"purpose":"relationship_review","include_state":false},"reason":"review collaboration posture, commitments, and response recommendations"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"cognitive_interaction_review"},
            tool_catalog={
                "cognitive_interaction_review": {
                    "description": "Run a model-led review of conversation state, collaboration posture, user-state hypotheses, unresolved commitments, response recommendations, and caution flags from current cognitive evidence.",
                    "risk_level": "medium",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "purpose": {"type": "string"},
                            "include_state": {"type": "boolean"},
                        },
                    },
                    "capability_group": "cognition",
                }
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("review the conversation state and decide how you should respond to me")

        self.assertEqual(plan.steps[0].tool_name, "cognitive_interaction_review")
        self.assertEqual(plan.steps[0].tool_input["purpose"], "relationship_review")
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_cognitive_commitment_review_tool(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"cognitive_commitment_review","tool_input":{"purpose":"follow_up_review","max_new_commitments":3,"max_updates":5,"include_state":false},"reason":"review outstanding promises and follow-ups from evidence"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"cognitive_commitment_review"},
            tool_catalog={
                "cognitive_commitment_review": {
                    "description": "Run a model-led review of durable evidence to create, update, resolve, or retain exact user-visible commitments and follow-ups.",
                    "risk_level": "medium",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "purpose": {"type": "string"},
                            "max_new_commitments": {"type": "integer"},
                            "max_updates": {"type": "integer"},
                            "include_state": {"type": "boolean"},
                        },
                    },
                    "capability_group": "cognition",
                }
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("review what you still owe me and update your follow-up ledger")

        self.assertEqual(plan.steps[0].tool_name, "cognitive_commitment_review")
        self.assertEqual(plan.steps[0].tool_input["purpose"], "follow_up_review")
        self.assertEqual(plan.steps[0].tool_input["max_updates"], 5)
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_cognitive_environment_review_tool(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"cognitive_environment_review","tool_input":{"purpose":"workspace_review","max_new_records":3,"max_updates":5,"include_state":false},"reason":"review workspace constraints and useful environment facts"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"cognitive_environment_review"},
            tool_catalog={
                "cognitive_environment_review": {
                    "description": "Run a model-led review of durable evidence to create, update, archive, or retain exact operating-environment records.",
                    "risk_level": "medium",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "purpose": {"type": "string"},
                            "max_new_records": {"type": "integer"},
                            "max_updates": {"type": "integer"},
                            "include_state": {"type": "boolean"},
                        },
                    },
                    "capability_group": "cognition",
                }
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("review the current workspace environment and remember useful constraints")

        self.assertEqual(plan.steps[0].tool_name, "cognitive_environment_review")
        self.assertEqual(plan.steps[0].tool_input["purpose"], "workspace_review")
        self.assertEqual(plan.steps[0].tool_input["max_updates"], 5)
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_activity_tools(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"activity_search","tool_input":{"query":"meeting notes","limit":5},"reason":"search native activity memory"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"activity_search"},
            tool_catalog={
                "activity_search": {
                    "description": "Search native local activity-memory events recorded from screen, audio, browser, or app context.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                    "capability_group": "activity",
                }
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("what activity mentioned meeting notes?")

        self.assertEqual(plan.steps[0].tool_name, "activity_search")
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_activity_policy_tools(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"activity_policy","tool_input":{},"reason":"inspect current policy"},{"tool_name":"activity_policy_update","tool_input":{"retention_days":7,"excluded_apps":["Mail"],"reason":"privacy request"},"reason":"update privacy policy"},{"tool_name":"activity_prune","tool_input":{"older_than_days":7,"reason":"apply retention"},"reason":"prune old activity"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"activity_policy", "activity_policy_update", "activity_prune"},
            tool_catalog={
                "activity_policy": {
                    "description": "Show the local Screenpipe-inspired activity memory retention and privacy exclusion policy.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {"type": "object", "properties": {}},
                    "capability_group": "activity",
                },
                "activity_policy_update": {
                    "description": "Update local activity memory retention and privacy exclusions after explicit approval.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {"retention_days": {"type": "integer"}, "reason": {"type": "string"}},
                        "required": ["reason"],
                    },
                    "capability_group": "activity",
                },
                "activity_prune": {
                    "description": "Delete local activity-memory events older than the policy retention window after explicit approval.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {"older_than_days": {"type": "integer"}, "reason": {"type": "string"}},
                        "required": ["reason"],
                    },
                    "capability_group": "activity",
                },
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("show activity privacy settings, exclude Mail, and prune old activity")

        self.assertEqual([step.tool_name for step in plan.steps], ["activity_policy", "activity_policy_update", "activity_prune"])
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_python_interpreter_tool(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"python_interpreter","tool_input":{"code":"import pandas as pd\\nprint(pd.Series([1,2,3]).sum())","import_mode":"allowlist","allowed_imports":["pandas"],"sandbox_profile":"read_only","reason":"local calculation"},"reason":"run bounded local analysis"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"python_interpreter"},
            tool_catalog={
                "python_interpreter": {
                    "description": "Run bounded Python analysis code in a child process with audit-hook filesystem, subprocess, and network controls.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "import_mode": {"type": "string"},
                            "allowed_imports": {"type": "array", "items": {"type": "string"}},
                            "sandbox_profile": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["code", "reason"],
                    },
                    "capability_group": "code",
                }
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("run a local python analysis over this small dataset")

        self.assertEqual(plan.steps[0].tool_name, "python_interpreter")
        self.assertEqual(plan.steps[0].tool_input["import_mode"], "allowlist")
        self.assertEqual(plan.steps[0].tool_input["allowed_imports"], ["pandas"])
        self.assertEqual(plan.steps[0].tool_input["sandbox_profile"], "read_only")
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_python_interpreter_artifact_tools(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"python_interpreter_runs","tool_input":{"limit":5},"reason":"inspect recent runs"},{"tool_name":"python_interpreter_run","tool_input":{"run_id":"python-20260602-120000-abcdef12"},"reason":"inspect one run"},{"tool_name":"python_interpreter_artifact","tool_input":{"run_id":"python-20260602-120000-abcdef12","filename":"result.txt","max_chars":1000},"reason":"read text artifact"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"python_interpreter_runs", "python_interpreter_run", "python_interpreter_artifact"},
            tool_catalog={
                "python_interpreter_runs": {
                    "description": "List recent bounded Python interpreter run manifests.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer"}},
                    },
                    "capability_group": "code",
                },
                "python_interpreter_run": {
                    "description": "Read one bounded Python interpreter run manifest by run id.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"run_id": {"type": "string"}},
                        "required": ["run_id"],
                    },
                    "capability_group": "code",
                },
                "python_interpreter_artifact": {
                    "description": "Read a text artifact from a bounded Python interpreter run by manifest-listed filename.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"run_id": {"type": "string"}, "filename": {"type": "string"}},
                        "required": ["run_id", "filename"],
                    },
                    "capability_group": "code",
                },
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("show recent python runs then read result.txt from the selected run")

        self.assertEqual(
            [step.tool_name for step in plan.steps],
            ["python_interpreter_runs", "python_interpreter_run", "python_interpreter_artifact"],
        )
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_python_interpreter_session_tools(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"python_interpreter_sessions","tool_input":{"limit":5},"reason":"inspect sessions"},{"tool_name":"python_interpreter_session","tool_input":{"session_id":"py-session-20260602-120000-abcdef12"},"reason":"inspect session"},{"tool_name":"python_interpreter","tool_input":{"code":"print(total)","session_id":"py-session-20260602-120000-abcdef12","replay_session":true,"sandbox_profile":"read_only","reason":"resume previous analysis"},"reason":"resume session"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"python_interpreter_sessions", "python_interpreter_session", "python_interpreter"},
            tool_catalog={
                "python_interpreter_sessions": {
                    "description": "List Python interpreter sessions with run counts and latest status.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer"}},
                    },
                    "capability_group": "code",
                },
                "python_interpreter_session": {
                    "description": "Read one Python interpreter session manifest by session id.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"session_id": {"type": "string"}},
                        "required": ["session_id"],
                    },
                    "capability_group": "code",
                },
                "python_interpreter": {
                    "description": "Run bounded Python analysis code in a child process and optionally replay prior session cells.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "session_id": {"type": "string"},
                            "replay_session": {"type": "boolean"},
                            "sandbox_profile": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["code", "reason"],
                    },
                    "capability_group": "code",
                },
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("show my python sessions and resume the previous analysis")

        self.assertEqual(
            [step.tool_name for step in plan.steps],
            ["python_interpreter_sessions", "python_interpreter_session", "python_interpreter"],
        )
        self.assertTrue(plan.steps[2].tool_input["replay_session"])
        self.assertEqual(plan.steps[2].tool_input["sandbox_profile"], "read_only")
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_browser_forget_tool(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"browser_forget_session","tool_input":{"session_id":"abc-123","reason":"stale local state"},"reason":"forget stale local browser state"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"browser_forget_session"},
            tool_catalog={
                "browser_forget_session": {
                    "description": "Forget one stored local browser session and its local form drafts.",
                    "risk_level": "medium",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {"session_id": {"type": "string"}},
                        "required": ["session_id"],
                    },
                    "capability_group": "browser",
                }
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("please forget the stale browser tab")

        self.assertEqual(plan.steps[0].tool_name, "browser_forget_session")
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_browser_sessions_tool(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"browser_sessions","tool_input":{"limit":10},"reason":"inspect local browser sessions"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"browser_sessions"},
            tool_catalog={
                "browser_sessions": {
                    "description": "List local browser-session metadata without returning page text.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer"}},
                    },
                    "capability_group": "browser",
                }
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("show me my local browser sessions")

        self.assertEqual(plan.steps[0].tool_name, "browser_sessions")
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_browser_back_tool(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"browser_back","tool_input":{"session_id":"abc-123"},"reason":"go back in the browser session"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"browser_back"},
            tool_catalog={
                "browser_back": {
                    "description": "Navigate a local browser session back to the previous page in its local history.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"session_id": {"type": "string"}},
                        "required": ["session_id"],
                    },
                    "capability_group": "browser",
                }
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("go back in this browser session")

        self.assertEqual(plan.steps[0].tool_name, "browser_back")
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_browser_observe_and_extract_tools(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"browser_observe","tool_input":{"session_id":"abc-123","include_text":false},"reason":"observe page state"},{"tool_name":"browser_extract","tool_input":{"session_id":"abc-123","query":"pricing","include_links":true},"reason":"extract pricing details"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"browser_observe", "browser_extract"},
            tool_catalog={
                "browser_observe": {
                    "description": "Observe a local browser session in a Browser Use-style shape.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"session_id": {"type": "string"}},
                        "required": ["session_id"],
                    },
                    "capability_group": "browser",
                },
                "browser_extract": {
                    "description": "Extract query-relevant text, links, and images from a local browser session.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"session_id": {"type": "string"}, "query": {"type": "string"}},
                        "required": ["session_id", "query"],
                    },
                    "capability_group": "browser",
                },
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("look at this browser session and extract pricing")

        self.assertEqual([step.tool_name for step in plan.steps], ["browser_observe", "browser_extract"])
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_browser_element_actions(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"browser_click_element","tool_input":{"session_id":"abc-123","element_id":"link:0"},"reason":"click observed link"},{"tool_name":"browser_type","tool_input":{"session_id":"abc-123","element_id":"form:0:field:email","text":"dev@example.com"},"reason":"type into observed field"},{"tool_name":"browser_find_text","tool_input":{"session_id":"abc-123","text":"pricing","max_matches":5},"reason":"find text in stored page"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"browser_click_element", "browser_type", "browser_find_text"},
            tool_catalog={
                "browser_click_element": {
                    "description": "Navigate a local browser session by clicking an observed link element id.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"session_id": {"type": "string"}, "element_id": {"type": "string"}},
                        "required": ["session_id", "element_id"],
                    },
                    "capability_group": "browser",
                },
                "browser_type": {
                    "description": "Type text into an observed form-field element in a local browser session draft.",
                    "risk_level": "medium",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "element_id": {"type": "string"},
                            "text": {"type": "string"},
                        },
                        "required": ["session_id", "element_id", "text"],
                    },
                    "capability_group": "browser",
                },
                "browser_find_text": {
                    "description": "Find exact text or query terms in a local browser session's stored page text.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"session_id": {"type": "string"}, "text": {"type": "string"}},
                        "required": ["session_id", "text"],
                    },
                    "capability_group": "browser",
                },
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("click the first observed browser link and type into the email field")

        self.assertEqual(
            [step.tool_name for step in plan.steps],
            ["browser_click_element", "browser_type", "browser_find_text"],
        )
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_live_browser_tools(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"browser_live_open","tool_input":{"url":"https://example.com","headless":true},"reason":"open a live page"},{"tool_name":"browser_live_observe","tool_input":{"live_session_id":"live-123","include_text":false},"reason":"observe live elements"},{"tool_name":"browser_live_click","tool_input":{"live_session_id":"live-123","element_id":"live:0","reason":"activate selected page control"},"reason":"click live element"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"browser_live_open", "browser_live_observe", "browser_live_click"},
            tool_catalog={
                "browser_live_open": {
                    "description": "Open an HTTP(S) URL in a native Playwright-backed live browser session.",
                    "risk_level": "medium",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"url": {"type": "string"}, "headless": {"type": "boolean"}},
                        "required": ["url"],
                    },
                    "capability_group": "browser",
                },
                "browser_live_observe": {
                    "description": "Observe a Playwright-backed live browser session with live element ids.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"live_session_id": {"type": "string"}, "include_text": {"type": "boolean"}},
                        "required": ["live_session_id"],
                    },
                    "capability_group": "browser",
                },
                "browser_live_click": {
                    "description": "Click an observed live browser element id after explicit approval.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "live_session_id": {"type": "string"},
                            "element_id": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["live_session_id", "element_id", "reason"],
                    },
                    "capability_group": "browser",
                },
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("open example in a real browser, observe it, then click the selected control")

        self.assertEqual([step.tool_name for step in plan.steps], ["browser_live_open", "browser_live_observe", "browser_live_click"])
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_richer_live_browser_controls(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"browser_live_wait","tool_input":{"live_session_id":"live-123","mode":"selector","selector":"select[name=status]","state":"visible"},"reason":"wait for dropdown"},{"tool_name":"browser_live_query_selector","tool_input":{"live_session_id":"live-123","selector":"select[name=status]","max_elements":5},"reason":"inspect dropdown"},{"tool_name":"browser_live_select_option","tool_input":{"live_session_id":"live-123","element_id":"live:2","values":["approved"],"reason":"choose approved status"},"reason":"select dropdown option"},{"tool_name":"browser_live_press_key","tool_input":{"live_session_id":"live-123","shortcut":"Enter","reason":"submit selected control"},"reason":"press key"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"browser_live_wait", "browser_live_query_selector", "browser_live_select_option", "browser_live_press_key"},
            tool_catalog={
                "browser_live_wait": {
                    "description": "Wait in a Playwright-backed live browser session for load state, selector, text, or a bounded timeout.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"live_session_id": {"type": "string"}, "mode": {"type": "string"}},
                        "required": ["live_session_id", "mode"],
                    },
                    "capability_group": "browser",
                },
                "browser_live_query_selector": {
                    "description": "Query a live browser page with a CSS selector and return bounded element metadata.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"live_session_id": {"type": "string"}, "selector": {"type": "string"}},
                        "required": ["live_session_id", "selector"],
                    },
                    "capability_group": "browser",
                },
                "browser_live_select_option": {
                    "description": "Select option values in an observed live browser select element after explicit approval.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "live_session_id": {"type": "string"},
                            "element_id": {"type": "string"},
                            "values": {"type": "array", "items": {"type": "string"}},
                            "reason": {"type": "string"},
                        },
                        "required": ["live_session_id", "element_id", "values", "reason"],
                    },
                    "capability_group": "browser",
                },
                "browser_live_press_key": {
                    "description": "Press a keyboard shortcut in a live browser session after explicit approval.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "live_session_id": {"type": "string"},
                            "shortcut": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["live_session_id", "shortcut", "reason"],
                    },
                    "capability_group": "browser",
                },
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("wait for the status dropdown, inspect it, select approved, then press enter")

        self.assertEqual(
            [step.tool_name for step in plan.steps],
            ["browser_live_wait", "browser_live_query_selector", "browser_live_select_option", "browser_live_press_key"],
        )
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_advanced_live_browser_file_and_js_controls(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"browser_live_upload_file","tool_input":{"live_session_id":"live-123","element_id":"live:4","path":"report.pdf","reason":"attach requested report"},"reason":"upload file"},{"tool_name":"browser_live_download","tool_input":{"live_session_id":"live-123","element_id":"live:5","reason":"save exported report"},"reason":"download export"},{"tool_name":"browser_live_save_pdf","tool_input":{"live_session_id":"live-123","filename":"page.pdf","reason":"archive current page"},"reason":"save PDF"},{"tool_name":"browser_live_evaluate_js","tool_input":{"live_session_id":"live-123","code":"() => document.title","reason":"read computed page title"},"reason":"evaluate JS"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"browser_live_upload_file", "browser_live_download", "browser_live_save_pdf", "browser_live_evaluate_js"},
            tool_catalog={
                "browser_live_upload_file": {
                    "description": "Upload a local file from an allowed read root into an observed live browser file input after explicit approval.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "live_session_id": {"type": "string"},
                            "element_id": {"type": "string"},
                            "path": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["live_session_id", "element_id", "path", "reason"],
                    },
                    "capability_group": "browser",
                },
                "browser_live_download": {
                    "description": "Click an observed live browser element and save the resulting download under the local data directory after explicit approval.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "live_session_id": {"type": "string"},
                            "element_id": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["live_session_id", "element_id", "reason"],
                    },
                    "capability_group": "browser",
                },
                "browser_live_save_pdf": {
                    "description": "Save the current live browser page as a PDF under the local data directory after explicit approval.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {"live_session_id": {"type": "string"}, "reason": {"type": "string"}},
                        "required": ["live_session_id", "reason"],
                    },
                    "capability_group": "browser",
                },
                "browser_live_evaluate_js": {
                    "description": "Evaluate bounded JavaScript in a live browser page context after explicit approval.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "live_session_id": {"type": "string"},
                            "code": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["live_session_id", "code", "reason"],
                    },
                    "capability_group": "browser",
                },
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("upload report, download the export, save the page as pdf, and inspect title with javascript")

        self.assertEqual(
            [step.tool_name for step in plan.steps],
            ["browser_live_upload_file", "browser_live_download", "browser_live_save_pdf", "browser_live_evaluate_js"],
        )
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_os_observation_tools(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"os_windows","tool_input":{"limit":10},"reason":"inspect visible windows"},{"tool_name":"os_observe_ui","tool_input":{"max_elements":20,"reason":"inspect foreground UI"},"reason":"observe actionable UI elements"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"os_windows", "os_observe_ui"},
            tool_catalog={
                "os_windows": {
                    "description": "List visible top-level Windows desktop windows as metadata.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer"}},
                    },
                    "capability_group": "os",
                },
                "os_observe_ui": {
                    "description": "Observe the foreground Windows UI Automation element tree as indexed UI metadata after approval.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {"max_elements": {"type": "integer"}, "reason": {"type": "string"}},
                    },
                    "capability_group": "os",
                },
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("show my visible windows then inspect the current app UI")

        self.assertEqual([step.tool_name for step in plan.steps], ["os_windows", "os_observe_ui"])
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_os_ui_action_tools(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"os_click_element","tool_input":{"observation_id":"abc","element_id":"uia:2","reason":"click save"},"reason":"click observed element"},{"tool_name":"os_type_text","tool_input":{"observation_id":"abc","element_id":"uia:3","text":"Hello","reason":"type draft"},"reason":"type into observed element"},{"tool_name":"os_send_keys","tool_input":{"shortcut":"Ctrl+S","reason":"save changes"},"reason":"send shortcut"},{"tool_name":"os_scroll_element","tool_input":{"observation_id":"abc","element_id":"uia:4","direction":"down","reason":"scroll document"},"reason":"scroll observed pane"},{"tool_name":"os_switch_window","tool_input":{"window_id":"window:1234","reason":"focus app"},"reason":"switch visible window"},{"tool_name":"os_resize_window","tool_input":{"window_id":"window:1234","x":0,"y":0,"width":800,"height":600,"reason":"arrange window"},"reason":"resize visible window"}]}'
        )
        provider = ModelPlanProvider(
            client,
            {"os_click_element", "os_type_text", "os_send_keys", "os_scroll_element", "os_switch_window", "os_resize_window"},
            tool_catalog={
                "os_click_element": {
                    "description": "Click an element from a previously approved foreground UI observation.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "observation_id": {"type": "string"},
                            "element_id": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["observation_id", "element_id", "reason"],
                    },
                    "capability_group": "os",
                },
                "os_type_text": {
                    "description": "Type text into an element from a previously approved foreground UI observation.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "observation_id": {"type": "string"},
                            "element_id": {"type": "string"},
                            "text": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["observation_id", "element_id", "text", "reason"],
                    },
                    "capability_group": "os",
                },
                "os_send_keys": {
                    "description": "Send a structured keyboard shortcut such as Ctrl+S after explicit approval.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {"shortcut": {"type": "string"}, "reason": {"type": "string"}},
                        "required": ["shortcut", "reason"],
                    },
                    "capability_group": "os",
                },
                "os_scroll_element": {
                    "description": "Scroll over an element from a previously approved foreground UI observation.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "observation_id": {"type": "string"},
                            "element_id": {"type": "string"},
                            "direction": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["observation_id", "element_id", "direction", "reason"],
                    },
                    "capability_group": "os",
                },
                "os_switch_window": {
                    "description": "Switch focus to a visible top-level window returned by os_windows after explicit approval.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {"window_id": {"type": "string"}, "reason": {"type": "string"}},
                        "required": ["window_id", "reason"],
                    },
                    "capability_group": "os",
                },
                "os_resize_window": {
                    "description": "Move or resize a visible top-level window returned by os_windows after explicit approval.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "window_id": {"type": "string"},
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                            "width": {"type": "integer"},
                            "height": {"type": "integer"},
                            "reason": {"type": "string"},
                        },
                        "required": ["window_id", "x", "y", "width", "height", "reason"],
                    },
                    "capability_group": "os",
                },
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("click save, type hello, press ctrl s, scroll down, then arrange the window")

        self.assertEqual(
            [step.tool_name for step in plan.steps],
            ["os_click_element", "os_type_text", "os_send_keys", "os_scroll_element", "os_switch_window", "os_resize_window"],
        )
        self.assertEqual(plan.steps[0].source, "model:static")

    def test_model_provider_can_handoff_to_windows_use_expanded_tools(self) -> None:
        client = StaticModelClient(
            '{"steps":[{"tool_name":"os_cursor","tool_input":{},"reason":"inspect cursor"},{"tool_name":"os_click_coordinates","tool_input":{"x":50,"y":60,"reason":"click explicit point"},"reason":"click point"},{"tool_name":"os_uia_pattern_action","tool_input":{"observation_id":"abc","element_id":"uia:7","action":"invoke","reason":"invoke observed button"},"reason":"invoke UIA pattern"},{"tool_name":"os_window_state","tool_input":{"window_id":"window:1234","action":"maximize","reason":"maximize app"},"reason":"change window state"},{"tool_name":"os_virtual_desktops","tool_input":{"limit":10},"reason":"inspect virtual desktops"},{"tool_name":"os_move_window_to_desktop","tool_input":{"window_id":"window:1234","desktop_id":"11111111-1111-1111-1111-111111111111","reason":"move app"},"reason":"move desktop"},{"tool_name":"os_virtual_desktop_action","tool_input":{"action":"next","reason":"switch workspace"},"reason":"switch virtual desktop"}]}'
        )
        allowed = {
            "os_cursor",
            "os_click_coordinates",
            "os_uia_pattern_action",
            "os_window_state",
            "os_virtual_desktops",
            "os_move_window_to_desktop",
            "os_virtual_desktop_action",
        }
        provider = ModelPlanProvider(
            client,
            allowed,
            tool_catalog={
                "os_cursor": {
                    "description": "Inspect the current mouse cursor location without reading screen or UI contents.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {"type": "object", "properties": {}},
                    "capability_group": "os",
                },
                "os_click_coordinates": {
                    "description": "Click explicit screen coordinates after approval.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "reason": {"type": "string"}},
                        "required": ["x", "y", "reason"],
                    },
                    "capability_group": "os",
                },
                "os_uia_pattern_action": {
                    "description": "Invoke a Windows UI Automation pattern on an element from a previously approved UI observation.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "observation_id": {"type": "string"},
                            "element_id": {"type": "string"},
                            "action": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["observation_id", "element_id", "action", "reason"],
                    },
                    "capability_group": "os",
                },
                "os_window_state": {
                    "description": "Minimize, maximize, restore, or close a visible top-level window returned by os_windows after approval.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {"window_id": {"type": "string"}, "action": {"type": "string"}, "reason": {"type": "string"}},
                        "required": ["window_id", "action", "reason"],
                    },
                    "capability_group": "os",
                },
                "os_virtual_desktops": {
                    "description": "Inspect Windows virtual-desktop metadata for the active and visible windows.",
                    "risk_level": "low",
                    "requires_approval": False,
                    "input_schema": {"type": "object", "properties": {"limit": {"type": "integer"}}},
                    "capability_group": "os",
                },
                "os_move_window_to_desktop": {
                    "description": "Move a visible top-level window to a known Windows virtual desktop id after approval.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {"window_id": {"type": "string"}, "desktop_id": {"type": "string"}, "reason": {"type": "string"}},
                        "required": ["window_id", "desktop_id", "reason"],
                    },
                    "capability_group": "os",
                },
                "os_virtual_desktop_action": {
                    "description": "Send a Windows virtual-desktop keyboard action after approval.",
                    "risk_level": "high",
                    "requires_approval": True,
                    "input_schema": {
                        "type": "object",
                        "properties": {"action": {"type": "string"}, "reason": {"type": "string"}},
                        "required": ["action", "reason"],
                    },
                    "capability_group": "os",
                },
            },
            fallback=ExplicitFallbackPlanProvider(),
        )

        plan = provider.plan("inspect cursor, click coordinates, invoke the button, maximize the window, and move it to another desktop")

        self.assertEqual(
            [step.tool_name for step in plan.steps],
            [
                "os_cursor",
                "os_click_coordinates",
                "os_uia_pattern_action",
                "os_window_state",
                "os_virtual_desktops",
                "os_move_window_to_desktop",
                "os_virtual_desktop_action",
            ],
        )
        self.assertEqual(plan.steps[0].source, "model:static")


class PlannerFacadeTests(unittest.TestCase):
    def test_planner_passes_context_to_provider(self) -> None:
        class ContextProvider(ExplicitFallbackPlanProvider):
            def plan(self, request, context=None):
                self.context = context
                return super().plan(request, context=context)

        provider = ContextProvider()
        Planner(provider).plan("system status", context={"active_window": {"title": "Demo"}})

        self.assertEqual(provider.context, {"active_window": {"title": "Demo"}})


if __name__ == "__main__":
    unittest.main()

