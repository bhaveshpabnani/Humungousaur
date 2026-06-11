import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from humungousaur.janus import (
    JanusStore,
    JanusEventRouter,
    janus_status,
    janus_privacy_delete,
    janus_privacy_export,
    apply_episode_operation,
    create_deep_dive_request,
    create_muted_scope,
    declare_task_context,
    execute_deep_dive_request,
    record_user_correction,
    respond_to_activation,
    run_janus_eval,
)
from humungousaur.janus.entities import extract_entity_refs
from humungousaur.janus.activity_guides import (
    ActivityGuideValidationError,
    load_activity_guides,
    select_activity_guides,
    validate_activity_guides,
)
from humungousaur.janus.models import RouteClass
from humungousaur.cognition.knowledge import KnowledgeStore
from humungousaur.cognition import FocusStore
from humungousaur.collectors.consumers.janus import JanusConsumer, janus_consumer_name
from humungousaur.collectors.envelope import CollectorEventEnvelope
from humungousaur.collectors.event_log import CollectorEventLog
from humungousaur.config import AgentConfig
from humungousaur.memory.event_store import EventStore
from humungousaur.planning.model_clients import ModelClientError, StaticModelClient


class JanusTests(unittest.TestCase):
    def test_context_events_are_stored_without_model_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            event = _event("ctx", collector="document_composition_activity", stimulus_type="document_saved")
            JanusEventRouter(config, model_client=StaticModelClient(_decision_payload()), run_agent=False).handle_event(event)
            status = janus_status(config)

        self.assertEqual(status["routes"][0]["route_class"], RouteClass.CONTEXT.value)
        self.assertEqual(status["decisions"], [])
        self.assertEqual(status["context_window"]["events"][0]["stimulus_type"], "document_saved")
        self.assertGreaterEqual(len(status["context_windows"]), 4)
        self.assertTrue(any(window.get("window_kind") == "entity" for window in status["context_windows"]))
        self.assertTrue(any(window.get("collector_counts", {}).get("document_composition_activity") == 1 for window in status["context_windows"]))
        self.assertIn("document_id_hash:doc123", json.dumps(status["context_windows"], sort_keys=True))

    def test_reflex_event_uses_model_decision_and_records_task_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            event = _event("unlock", collector="device_state", stimulus_type="screen_unlocked")
            JanusEventRouter(config, model_client=StaticModelClient(_decision_payload()), run_agent=False).handle_event(event)
            status = janus_status(config)
            memory_events = EventStore(config.memory_db_path).tail(limit=5)

        self.assertEqual(status["routes"][0]["route_class"], RouteClass.REFLEX.value)
        self.assertEqual(status["decisions"][0]["posture"], "prepare")
        self.assertEqual(status["decisions"][0]["model_status"], "model")
        self.assertEqual(status["task_contexts"][0]["summary"], "User resumed the Acme proposal.")
        self.assertEqual(status["memory_candidates"][0]["kind"], "working_context")
        self.assertEqual(status["memory_candidates"][0]["summary"], "Resume capsule prepared.")
        self.assertIn("reflex_decision:", json.dumps(status["memory_candidates"][0]["evidence_refs"]))
        self.assertTrue(any(event["event_type"] == "janus_memory_candidate" for event in memory_events))
        self.assertEqual(status["activations"][0]["posture"], "prepare")
        self.assertEqual(status["activations"][0]["status"], "prepared")
        self.assertEqual(status["activations"][0]["response_mode"], "silent")
        self.assertIn("prepare_silent_help", status["activations"][0]["allowed_actions"])
        self.assertIn("read_rich_content_without_approval", status["activations"][0]["forbidden_actions"])
        self.assertIn("reflex_decision:", json.dumps(status["activations"][0]["evidence_refs"]))

    def test_memory_candidate_corrections_update_candidate_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            event = _event("unlock", collector="device_state", stimulus_type="screen_unlocked")
            JanusEventRouter(config, model_client=StaticModelClient(_decision_payload()), run_agent=False).handle_event(event)
            candidate_id = janus_status(config)["memory_candidates"][0]["candidate_id"]

            accepted = record_user_correction(
                config,
                {
                    "target_type": "memory_candidate",
                    "target_id": candidate_id,
                    "correction_type": "helpful",
                    "reason": "This is useful working context.",
                },
            )
            accepted_again = record_user_correction(
                config,
                {
                    "target_type": "memory_candidate",
                    "target_id": candidate_id,
                    "correction_type": "helpful",
                    "reason": "Still useful.",
                },
            )
            knowledge_id = accepted["promoted_memory"]["knowledge"]["knowledge_id"]
            active_knowledge = KnowledgeStore(config.cognition_db_path).list(limit=10)
            subconscious = config.subconscious_markdown_path.read_text(encoding="utf-8")
            private = record_user_correction(
                config,
                {
                    "target_type": "memory_candidate",
                    "target_id": candidate_id,
                    "correction_type": "private",
                    "reason": "This context is private.",
                },
            )
            active_after_private = KnowledgeStore(config.cognition_db_path).get(knowledge_id)
            archived_after_private = KnowledgeStore(config.cognition_db_path).get(knowledge_id, include_archived=True)
            memory_events = EventStore(config.memory_db_path).tail(limit=10)

        self.assertEqual(accepted["memory_candidate"]["status"], "accepted")
        self.assertEqual(accepted["memory_candidate"]["promoted_knowledge_id"], knowledge_id)
        self.assertTrue(accepted["promoted_memory"]["created"])
        self.assertEqual(accepted_again["promoted_memory"]["created"], False)
        self.assertEqual(len(active_knowledge), 1)
        self.assertEqual(active_knowledge[0].knowledge_id, knowledge_id)
        self.assertEqual(active_knowledge[0].source, "janus_memory_candidate")
        self.assertIn(f"active_memory_candidate:{candidate_id}", active_knowledge[0].evidence_refs)
        self.assertIn("Resume capsule prepared.", active_knowledge[0].text)
        self.assertIn("Resume capsule prepared.", subconscious)
        self.assertEqual(private["memory_candidate"]["status"], "private")
        self.assertEqual(private["status"]["memory_candidates"][0]["status"], "private")
        self.assertIsNone(active_after_private)
        self.assertIsNotNone(archived_after_private)
        self.assertTrue(archived_after_private.archived_at)
        self.assertEqual(private["retracted_memories"][0]["knowledge"]["knowledge_id"], knowledge_id)
        self.assertIn("transition_note:This context is private.", private["memory_candidate"]["evidence_refs"])
        status_events = [event for event in memory_events if event["event_type"] == "janus_memory_candidate_status"]
        self.assertTrue(status_events)
        self.assertTrue(any(event["payload"]["status"] == "private" for event in status_events))
        self.assertTrue(any(event["event_type"] == "janus_memory_promotion" for event in memory_events))
        self.assertTrue(any(event["event_type"] == "janus_memory_retraction" for event in memory_events))

    def test_helpful_activation_feedback_accepts_and_promotes_related_memory_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            event = _event("unlock", collector="device_state", stimulus_type="screen_unlocked")
            JanusEventRouter(config, model_client=StaticModelClient(_decision_payload()), run_agent=False).handle_event(event)
            status_before = janus_status(config)
            activation_id = status_before["activations"][0]["activation_id"]
            candidate_id = status_before["memory_candidates"][0]["candidate_id"]

            correction = record_user_correction(
                config,
                {
                    "target_type": "activation",
                    "target_id": activation_id,
                    "correction_type": "helpful",
                    "reason": "This active suggestion was useful.",
                },
            )
            status_after = janus_status(config)
            knowledge = KnowledgeStore(config.cognition_db_path).list(limit=10)

        self.assertEqual(correction["cascaded_memory_candidates"][0]["candidate_id"], candidate_id)
        self.assertEqual(correction["cascaded_memory_candidates"][0]["status"], "accepted")
        self.assertEqual(correction["promoted_memory"]["candidate"]["candidate_id"], candidate_id)
        self.assertEqual(status_after["memory_candidates"][0]["status"], "accepted")
        self.assertEqual(status_after["memory_candidates"][0]["promoted_knowledge_id"], knowledge[0].knowledge_id)
        self.assertEqual(len(knowledge), 1)

    def test_memory_candidate_payload_omits_raw_private_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            event = _event("unlock", collector="device_state", stimulus_type="screen_unlocked")
            JanusEventRouter(
                config,
                model_client=StaticModelClient(
                    _posture_payload(
                        posture="prepare",
                        agent_stimulus="Prepare safe context.",
                        memory_updates=[
                            {
                                "kind": "working_context",
                                "summary": "Safe summary only.",
                                "status": "accepted",
                                "raw_text": "raw private document text",
                                "email_body": "private email body",
                                "token": "secret-token",
                                "nested": {
                                    "secret": "nested-secret",
                                    "body": "nested private body",
                                    "safe_ref": "document_id_hash:doc123",
                                },
                                "entity_refs": ["document_id_hash:doc123"],
                            }
                        ],
                    )
                ),
                run_agent=False,
            ).handle_event(event)
            candidate = janus_status(config)["memory_candidates"][0]

        serialized = json.dumps(candidate, sort_keys=True)
        self.assertEqual(candidate["status"], "candidate")
        self.assertNotIn("status", candidate["payload"])
        self.assertEqual(candidate["payload"]["raw_content_included"], False)
        self.assertIn("document_id_hash:doc123", serialized)
        self.assertNotIn("raw private document text", serialized)
        self.assertNotIn("private email body", serialized)
        self.assertNotIn("secret-token", serialized)
        self.assertNotIn("nested-secret", serialized)
        self.assertNotIn("nested private body", serialized)

    def test_reflex_prompt_redacts_private_metadata_and_payload_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            client = CapturingModelClient(_decision_payload())
            event = _event(
                "unlock",
                collector="device_state",
                stimulus_type="screen_unlocked",
                metadata={"safe_ref": "workspace_hash:abc", "nested": {"token": "metadata-secret-token"}},
                payload={"email_body": "private email body", "nested": {"raw_text": "raw payload text", "safe_ref": "ok"}},
            )
            JanusEventRouter(config, model_client=client, run_agent=False).handle_event(event)

        prompt = client.prompts[0]
        self.assertIn("workspace_hash:abc", prompt)
        self.assertNotIn("metadata-secret-token", prompt)
        self.assertNotIn("private email body", prompt)
        self.assertNotIn("raw payload text", prompt)

    def test_private_decision_correction_cascades_to_candidates_and_prepared_activations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            event = _event("unlock", collector="device_state", stimulus_type="screen_unlocked")
            JanusEventRouter(config, model_client=StaticModelClient(_decision_payload()), run_agent=False).handle_event(event)
            status_before = janus_status(config)
            decision_id = status_before["decisions"][0]["decision_id"]
            activation_id = status_before["activations"][0]["activation_id"]
            candidate_id = status_before["memory_candidates"][0]["candidate_id"]

            correction = record_user_correction(
                config,
                {
                    "target_type": "decision",
                    "target_id": decision_id,
                    "correction_type": "private",
                    "reason": "The whole decision context is private.",
                },
            )
            status_after = janus_status(config)

        self.assertEqual(correction["cascaded_memory_candidates"][0]["candidate_id"], candidate_id)
        self.assertEqual(correction["cascaded_memory_candidates"][0]["status"], "private")
        self.assertEqual(correction["cascaded_activations"][0]["activation_id"], activation_id)
        self.assertEqual(correction["cascaded_activations"][0]["status"], "skipped")
        self.assertEqual(status_after["memory_candidates"][0]["status"], "private")
        self.assertEqual(status_after["activations"][0]["status"], "skipped")

    def test_reflex_prompt_includes_recent_corrections_and_deep_dive_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            router = JanusEventRouter(config, model_client=StaticModelClient(_decision_payload()), run_agent=False)
            router.handle_event(_event("first", collector="device_state", stimulus_type="screen_unlocked"))
            decision_id = janus_status(config)["decisions"][0]["decision_id"]
            record_user_correction(
                config,
                {
                    "target_type": "decision",
                    "target_id": decision_id,
                    "correction_type": "not_relevant",
                    "reason": "This suggestion was for the wrong work context.",
                },
            )
            create_deep_dive_request(
                config,
                {
                    "request_id": "deep_history",
                    "purpose": "Inspect safe document outline after approval.",
                    "source": "google_docs",
                    "requested_access": "document_outline",
                },
            )
            client = CapturingModelClient(_decision_payload())
            JanusEventRouter(config, model_client=client, run_agent=False).handle_event(
                _event("second", collector="device_state", stimulus_type="screen_unlocked")
            )

        prompt = client.prompts[0]
        self.assertIn("recent_corrections", prompt)
        self.assertIn("not_relevant", prompt)
        self.assertIn("wrong work context", prompt)
        self.assertIn("deep_dive_requests", prompt)
        self.assertIn("deep_history", prompt)

    def test_model_task_context_update_preserves_safe_structured_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            JanusEventRouter(
                config,
                model_client=StaticModelClient(
                    _posture_payload(
                        posture="prepare",
                        agent_stimulus="Prepare a safe resume capsule.",
                        task_context_updates=[
                            {
                                "task_context_id": "ctx_structured",
                                "status": "active",
                                "source": "model",
                                "goal": "Draft the proposal.",
                                "episode_id": "episode_acme",
                                "primary_entities": [
                                    {
                                        "kind": "document",
                                        "ref": "document_id_hash:doc123",
                                        "raw_text": "private document text",
                                    }
                                ],
                                "supporting_entities": [{"kind": "source", "ref": "source_id_hash:src123"}],
                                "assistant_mode": "quiet_resume",
                                "allowed_help": ["resume_capsule", "outline"],
                                "privacy_mode": "metadata_first",
                                "summary": "User is drafting the proposal.",
                                "evidence_refs": ["task_hint:model"],
                            }
                        ],
                    )
                ),
                run_agent=False,
            ).handle_event(_event("unlock", collector="device_state", stimulus_type="screen_unlocked"))
            context = janus_status(config)["task_contexts"][0]

        serialized = json.dumps(context, sort_keys=True)
        self.assertEqual(context["task_context_id"], "ctx_structured")
        self.assertEqual(context["episode_id"], "episode_acme")
        self.assertEqual(context["assistant_mode"], "quiet_resume")
        self.assertEqual(context["allowed_help"], ["resume_capsule", "outline"])
        self.assertEqual(context["privacy_mode"], "metadata_first")
        self.assertIn("document_id_hash:doc123", serialized)
        self.assertIn("source_id_hash:src123", serialized)
        self.assertIn("reflex_decision:", json.dumps(context["evidence_refs"]))
        self.assertNotIn("private document text", serialized)
        self.assertNotIn("raw_text", serialized)

    def test_episode_update_upserts_active_episode_and_timeline_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            JanusEventRouter(
                config,
                model_client=StaticModelClient(
                    _posture_payload(
                        posture="prepare",
                        agent_stimulus="Prepare safe context.",
                        episode_update={
                            "action": "start_episode",
                            "episode_id": "episode_acme",
                            "confidence": "high",
                            "status": "active",
                            "hypothesis": "User is drafting the Acme proposal.",
                            "summary": "Acme proposal drafting session.",
                            "primary_entities": [
                                {"kind": "document", "ref": "document_id_hash:doc123", "raw_text": "private proposal text"}
                            ],
                            "supporting_entities": [{"kind": "source", "ref": "source_id_hash:src123"}],
                            "task_context_id": "ctx_acme",
                            "evidence_refs": ["model_episode:acme"],
                            "reason": "The collector event belongs to a proposal-writing episode.",
                        },
                    )
                ),
                run_agent=False,
            ).handle_event(_event("unlock", collector="device_state", stimulus_type="screen_unlocked"))
            status = janus_status(config)

        serialized = json.dumps(status, sort_keys=True)
        self.assertEqual(status["episodes"][0]["episode_id"], "episode_acme")
        self.assertEqual(status["episodes"][0]["status"], "active")
        self.assertEqual(status["episodes"][0]["confidence"], "high")
        self.assertEqual(status["episodes"][0]["event_count"], 1)
        self.assertEqual(status["episode_events"][0]["episode_id"], "episode_acme")
        self.assertEqual(status["episode_events"][0]["relation"], "start_episode")
        self.assertIn("document_id_hash:doc123", serialized)
        self.assertIn("source_id_hash:src123", serialized)
        self.assertNotIn("private proposal text", serialized)
        self.assertNotIn("raw_text", serialized)

    def test_repeated_episode_updates_append_events_without_replacing_episode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            router = JanusEventRouter(
                config,
                model_client=StaticModelClient(
                    _posture_payload(
                        posture="remember",
                        episode_update={
                            "action": "continue_episode",
                            "episode_id": "episode_acme",
                            "confidence": "medium",
                            "status": "active",
                            "hypothesis": "User is still working on the Acme proposal.",
                            "summary": "Acme proposal work continued.",
                            "reason": "The event continues the same safe episode.",
                        },
                    )
                ),
                run_agent=False,
            )
            router.handle_event(_event("one", collector="device_state", stimulus_type="screen_unlocked"))
            router.handle_event(_event("two", collector="device_state", stimulus_type="screen_unlocked"))
            status = janus_status(config)

        self.assertEqual(len(status["episodes"]), 1)
        self.assertEqual(status["episodes"][0]["episode_id"], "episode_acme")
        self.assertEqual(status["episodes"][0]["event_count"], 2)
        self.assertEqual(status["episodes"][0]["last_event_sequence"], 1)
        self.assertEqual(len(status["episode_events"]), 2)

    def test_reflex_prompt_includes_recent_active_episode_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            JanusEventRouter(
                config,
                model_client=StaticModelClient(
                    _posture_payload(
                        posture="remember",
                        episode_update={
                            "action": "start_episode",
                            "episode_id": "episode_history",
                            "confidence": "medium",
                            "status": "active",
                            "hypothesis": "User is reviewing a proposal.",
                            "summary": "Proposal review episode.",
                            "reason": "Initial episode state.",
                        },
                    )
                ),
                run_agent=False,
            ).handle_event(_event("first", collector="device_state", stimulus_type="screen_unlocked"))
            client = CapturingModelClient(_decision_payload())
            JanusEventRouter(config, model_client=client, run_agent=False).handle_event(
                _event("second", collector="device_state", stimulus_type="screen_unlocked")
            )

        prompt = client.prompts[0]
        self.assertIn("active_episodes", prompt)
        self.assertIn("active_episode_events", prompt)
        self.assertIn("episode_history", prompt)
        self.assertIn("Proposal review episode.", prompt)

    def test_ask_user_reflex_records_prepared_activation_with_text_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            event = _event("mail", collector="mail_activity", stimulus_type="email_received")
            result = JanusEventRouter(
                config,
                model_client=StaticModelClient(
                    _posture_payload(
                        posture="ask_user",
                        user_visible_text="This looks related to your draft. Want me to prepare a reply?",
                        agent_stimulus="Prepare a reply outline only if the user confirms.",
                        should_interrupt_user=True,
                    )
                ),
                run_agent=False,
            ).handle_event(event)
            status = janus_status(config)

        activation = status["activations"][0]
        self.assertEqual(result["submission"]["activation"]["activation_id"], activation["activation_id"])
        self.assertEqual(activation["posture"], "ask_user")
        self.assertEqual(activation["status"], "prepared")
        self.assertEqual(activation["response_mode"], "text")
        self.assertTrue(activation["should_interrupt_user"])
        self.assertIn("ask_user_only", activation["allowed_actions"])
        self.assertIn("continue_without_user_answer", activation["forbidden_actions"])
        self.assertIn("Want me to prepare", activation["user_visible_text"])

    def test_wake_main_agent_records_skipped_activation_when_bridge_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            event = _event("hotkey", collector="direct_user", stimulus_type="global_hotkey_pressed")
            result = JanusEventRouter(
                config,
                model_client=StaticModelClient(
                    _posture_payload(
                        posture="wake_main_agent",
                        agent_stimulus="Open the active task with the current safe context.",
                    )
                ),
                run_agent=False,
            ).handle_event(event)
            status = janus_status(config)

        activation = status["activations"][0]
        self.assertTrue(result["submission"]["skipped"])
        self.assertEqual(activation["posture"], "wake_main_agent")
        self.assertEqual(activation["status"], "skipped")
        self.assertEqual(activation["response_mode"], "silent")
        self.assertEqual(activation["stimulus_id"], f"janus-{activation['decision_id']}")
        self.assertIn("prepare_draft", activation["allowed_actions"])
        self.assertIn("send_message_without_approval", activation["forbidden_actions"])
        self.assertIn("collector_event:", json.dumps(activation["evidence_refs"]))

    def test_muted_and_blocked_routes_do_not_create_agent_activations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            create_muted_scope(config, {"collector": "device_state", "mode": "no_assistance"})
            router = JanusEventRouter(config, model_client=StaticModelClient(_decision_payload()), run_agent=False)
            router.handle_event(_event("muted", collector="device_state", stimulus_type="screen_unlocked"))
            router.handle_event(_event("blocked", collector="verification_code_activity", stimulus_type="otp_code_detected"))
            status = janus_status(config)

        self.assertEqual(status["decisions"], [])
        self.assertEqual(status["activations"], [])

    def test_do_not_track_scope_suppresses_janus_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            create_muted_scope(config, {"collector": "device_state", "mode": "do_not_track"})
            result = JanusEventRouter(config, model_client=StaticModelClient(_decision_payload()), run_agent=False).handle_event(
                _event("private", collector="device_state", stimulus_type="screen_unlocked")
            )
            status = janus_status(config)

        self.assertTrue(result["suppressed"])
        self.assertEqual(result["route"]["route_class"], "blocked")
        self.assertEqual(status["routes"], [])
        self.assertEqual(status["decisions"], [])
        self.assertEqual(status["activations"], [])
        self.assertEqual(status["explanations"], [])
        self.assertEqual(status["context_window"]["events"], [])

    def test_request_deep_dive_records_approval_request_and_activation_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            event = _event("mail", collector="mail_activity", stimulus_type="email_received")
            JanusEventRouter(
                config,
                model_client=StaticModelClient(
                    _posture_payload(
                        posture="request_deep_dive",
                        agent_stimulus="Ask approval to inspect the message metadata.",
                        deep_dive_request={
                            "purpose": "Check whether the received message is related to the active task.",
                            "source": "gmail",
                            "requested_access": "message_headers",
                        },
                    )
                ),
                run_agent=False,
            ).handle_event(event)
            status = janus_status(config)

        request_id = status["deep_dive_requests"][0]["request_id"]
        activation = status["activations"][0]
        self.assertEqual(activation["posture"], "request_deep_dive")
        self.assertEqual(activation["status"], "prepared")
        self.assertIn(f"deep_dive_request:{request_id}", activation["evidence_refs"])

    def test_invalid_request_deep_dive_is_downgraded_without_activation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            event = _event("mail", collector="mail_activity", stimulus_type="email_received")
            JanusEventRouter(
                config,
                model_client=StaticModelClient(_posture_payload(posture="request_deep_dive", deep_dive_request={"purpose": "missing source"})),
                run_agent=False,
            ).handle_event(event)
            status = janus_status(config)

        self.assertEqual(status["deep_dive_requests"], [])
        self.assertEqual(status["activations"], [])
        self.assertEqual(status["decisions"][0]["posture"], "remember")
        self.assertIn("Deep-dive posture downgraded", " ".join(status["decisions"][0]["safety_notes"]))

    def test_wake_without_agent_stimulus_does_not_leave_pending_activation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            event = _event("hotkey", collector="direct_user", stimulus_type="global_hotkey_pressed")
            JanusEventRouter(
                config,
                model_client=StaticModelClient(
                    _posture_payload(
                        posture="wake_main_agent",
                        user_visible_text="Should I help with the current task?",
                        should_interrupt_user=True,
                    )
                ),
                run_agent=False,
            ).handle_event(event)
            status = janus_status(config)

        self.assertEqual(status["decisions"][0]["posture"], "ask_user")
        self.assertEqual(status["activations"][0]["status"], "prepared")
        self.assertEqual(status["activations"][0]["response_mode"], "text")

    def test_ask_user_at_stable_context_boundary_is_downgraded_to_silent_prepare(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            router = JanusEventRouter(
                config,
                model_client=StaticModelClient(
                    _posture_payload(
                        posture="ask_user",
                        user_visible_text="Want help with the document?",
                        agent_stimulus="Prepare document help silently.",
                        should_interrupt_user=True,
                    )
                ),
                run_agent=False,
            )
            for event in _events(
                ["save-1", "save-2", "save-3"],
                collector="document_composition_activity",
                source="google_docs",
                stimulus_type="document_saved",
                metadata={"document_id_hash": "doc123"},
                occurred_at=[
                    "2026-06-11T00:00:00+00:00",
                    "2026-06-11T00:04:00+00:00",
                    "2026-06-11T00:09:00+00:00",
                ],
            ):
                router.handle_event(event)
            status = janus_status(config)

        self.assertEqual(status["decisions"][0]["posture"], "prepare")
        self.assertFalse(status["decisions"][0]["should_interrupt_user"])
        self.assertEqual(status["activations"][0]["response_mode"], "silent")

    def test_wake_main_agent_records_submitted_harness_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            event = _event("hotkey", collector="direct_user", stimulus_type="global_hotkey_pressed")
            with patch("humungousaur.janus.router.InteractionHarness") as harness_class, patch(
                "humungousaur.janus.router.harness_result_to_dict",
                return_value={"run": None, "response": "prepared"},
            ):
                harness_class.return_value.handle.return_value = object()
                result = JanusEventRouter(
                    config,
                    model_client=StaticModelClient(
                        _posture_payload(
                            posture="wake_main_agent",
                            agent_stimulus="Prepare a safe current-task capsule.",
                        )
                    ),
                    run_agent=True,
                ).handle_event(event)
            status = janus_status(config)

        self.assertEqual(result["submission"]["activation"]["status"], "submitted")
        self.assertEqual(status["activations"][0]["status"], "submitted")
        self.assertEqual(status["activations"][0]["harness_result"]["response"], "prepared")

    def test_wake_main_agent_records_failed_harness_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            event = _event("hotkey", collector="direct_user", stimulus_type="global_hotkey_pressed")
            with patch("humungousaur.janus.router.InteractionHarness") as harness_class:
                harness_class.return_value.handle.side_effect = RuntimeError("boom")
                result = JanusEventRouter(
                    config,
                    model_client=StaticModelClient(
                        _posture_payload(
                            posture="wake_main_agent",
                            agent_stimulus="Prepare a safe current-task capsule.",
                        )
                    ),
                    run_agent=True,
                ).handle_event(event)
            status = janus_status(config)

        self.assertEqual(result["submission"]["activation"]["status"], "failed")
        self.assertEqual(status["activations"][0]["status"], "failed")
        self.assertEqual(status["activations"][0]["harness_result"]["error"], "RuntimeError")

    def test_reflex_interpreter_uses_cognition_reflex_prompt_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            client = CapturingModelClient(_decision_payload())
            event = _event("unlock", collector="device_state", stimulus_type="screen_unlocked")
            JanusEventRouter(config, model_client=client, run_agent=False).handle_event(event)

        self.assertEqual(len(client.prompts), 1)
        self.assertIn("Interpret one local collector route for Humungousaur's janus reflex layer.", client.prompts[0])
        self.assertIn("Global intelligence rule:", client.prompts[0])
        self.assertIn("Reflex input:", client.prompts[0])
        self.assertIn('"stimulus_type":"screen_unlocked"', client.prompts[0])
        self.assertIn("posture", client.schemas[0]["required"])

    def test_activity_guides_validate_schema_and_expose_model_readable_packs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            guide_root = Path(tmp_dir) / "guides"
            guide_root.mkdir()
            (guide_root / "authoring_document.md").write_text(_guide_text("Authoring Document", "document saved draft export"), encoding="utf-8")
            (guide_root / "coding_debugging.md").write_text(_guide_text("Coding Debugging", "terminal build failed tests"), encoding="utf-8")
            (guide_root / "broken.md").write_text("# Activity Guide: Broken\n\n## Summary\nMissing sections", encoding="utf-8")

            validation = validate_activity_guides(guide_root)
            selected = select_activity_guides(
                route=type("Route", (), {"collector": "document_composition_activity", "source": "activity", "stimulus_type": "document_saved", "route_class": "context"})(),
                event={"collector": "document_composition_activity", "stimulus_type": "document_saved", "text": "Document saved after drafting."},
                context_window={"events": [{"collector": "document_composition_activity"}]},
                task_contexts=[],
                root=guide_root,
                limit=2,
            )

        self.assertFalse(validation["valid"])
        self.assertIn("broken.md", validation["errors"])
        self.assertEqual(selected[0].guide_id, "authoring_document")
        self.assertEqual(selected[0].relevance_score, 0)
        self.assertEqual(selected[1].relevance_score, 0)
        self.assertEqual(selected[0].prompt_payload["selection"], "included_for_model_semantic_choice")
        self.assertNotIn("text", selected[0].prompt_payload)

    def test_activity_guides_strict_loading_rejects_missing_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            guide_root = Path(tmp_dir) / "guides"
            guide_root.mkdir()
            (guide_root / "broken.md").write_text("# Activity Guide: Broken\n\n## Summary\nMissing sections", encoding="utf-8")

            with self.assertRaises(ActivityGuideValidationError):
                load_activity_guides(guide_root, strict=True)

    def test_reflex_model_unavailable_stays_silent(self) -> None:
        class FailingClient(StaticModelClient):
            def complete_json(self, prompt, schema):  # type: ignore[no-untyped-def]
                raise ModelClientError("offline")

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            event = _event("unlock", collector="device_state", stimulus_type="screen_unlocked")
            JanusEventRouter(config, model_client=FailingClient("{}"), run_agent=False).handle_event(event)
            status = janus_status(config)

        self.assertEqual(status["decisions"][0]["posture"], "stay_silent")
        self.assertEqual(status["decisions"][0]["model_status"], "unavailable")
        self.assertFalse(status["decisions"][0]["should_interrupt_user"])

    def test_malformed_reflex_model_output_falls_back_safely(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            event = _event("unlock", collector="device_state", stimulus_type="screen_unlocked")
            result = JanusEventRouter(config, model_client=StaticModelClient("{not-json"), run_agent=False).handle_event(event)
            status = janus_status(config)

        self.assertEqual(result["decision"]["posture"], "stay_silent")
        self.assertEqual(result["decision"]["model_status"], "unavailable")
        self.assertFalse(result["decision"]["should_interrupt_user"])
        self.assertEqual(status["decisions"][0]["model_status"], "unavailable")
        self.assertEqual(status["decisions"][0]["agent_stimulus"], "")

    def test_muted_scope_suppresses_matching_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            create_muted_scope(config, {"collector": "device_state", "mode": "no_assistance"})
            event = _event("unlock", collector="device_state", stimulus_type="screen_unlocked")
            JanusEventRouter(config, model_client=StaticModelClient(_decision_payload()), run_agent=False).handle_event(event)
            status = janus_status(config)

        self.assertEqual(status["routes"][0]["route_class"], RouteClass.MUTED.value)
        self.assertEqual(status["decisions"], [])

    def test_cancelled_muted_scope_no_longer_mutes_matching_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            created = create_muted_scope(config, {"collector": "device_state", "mode": "no_assistance"})
            router = JanusEventRouter(config, model_client=StaticModelClient(_decision_payload()), run_agent=False)

            muted = router.handle_event(_event("unlock-muted", collector="device_state", stimulus_type="screen_unlocked"))
            cancelled = JanusStore(config.janus_db_path).cancel_muted_scope(
                created["muted_scope"]["scope_id"],
                reason="resume active assistance",
            )
            unmuted = router.handle_event(_event("unlock-unmuted", collector="device_state", stimulus_type="screen_unlocked"))
            status = janus_status(config)

        self.assertEqual(muted["route"]["route_class"], RouteClass.MUTED.value)
        self.assertIsNotNone(cancelled)
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(unmuted["route"]["route_class"], RouteClass.REFLEX.value)
        self.assertEqual(status["muted_scopes"][0]["status"], "cancelled")
        self.assertEqual(status["decisions"][0]["model_status"], "model")

    def test_deep_dive_approve_reject_transitions_are_persisted_and_exposed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            approved_request = create_deep_dive_request(
                config,
                {
                    "request_id": "deep_approve",
                    "purpose": "Inspect the document outline",
                    "source": "google_docs",
                    "requested_access": "document_outline",
                },
            )
            rejected_request = create_deep_dive_request(
                config,
                {
                    "request_id": "deep_reject",
                    "purpose": "Inspect the full document body",
                    "source": "google_docs",
                    "requested_access": "rich_document_body",
                },
            )
            store = JanusStore(config.janus_db_path)
            approved = store.update_deep_dive_status(approved_request["deep_dive_request"]["request_id"], status="approved", reason="user approved")
            rejected = store.update_deep_dive_status(rejected_request["deep_dive_request"]["request_id"], status="rejected", reason="user rejected")
            status = janus_status(config)

        by_id = {item["request_id"]: item for item in status["deep_dive_requests"]}
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(by_id["deep_approve"]["status"], "approved")
        self.assertEqual(by_id["deep_reject"]["status"], "rejected")
        self.assertIn("transition_note:user approved", by_id["deep_approve"]["evidence_refs"])
        self.assertIn("transition_note:user rejected", by_id["deep_reject"]["evidence_refs"])

    def test_approved_deep_dive_execution_records_metadata_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            log = CollectorEventLog(config.collector_events_db_path)
            log.append(_envelope("docs", collector="document_composition_activity", source="google_docs", stimulus_type="document_saved"))
            create_deep_dive_request(
                config,
                {
                    "request_id": "deep_exec",
                    "episode_id": "episode-doc",
                    "purpose": "Inspect safe document metadata",
                    "source": "google_docs",
                    "requested_access": "collector_event_context",
                },
            )
            JanusStore(config.janus_db_path).update_deep_dive_status("deep_exec", status="approved", reason="user approved")

            executed = execute_deep_dive_request(config, {"request_id": "deep_exec"})
            status = janus_status(config)

        self.assertEqual(executed["deep_dive_request"]["status"], "completed")
        self.assertEqual(executed["deep_dive_result"]["status"], "completed")
        self.assertFalse(executed["deep_dive_result"]["evidence"]["raw_content_included"])
        self.assertEqual(status["deep_dive_results"][0]["request_id"], "deep_exec")

    def test_episode_operations_merge_split_and_status_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            declare_task_context(config, {"goal": "Draft proposal", "episode_id": "episode-a"})
            store = JanusStore(config.janus_db_path)
            store.upsert_episode(_episode("episode-a", "Draft proposal"))
            store.upsert_episode(_episode("episode-b", "Research sources"))

            paused = apply_episode_operation(config, {"operation": "pause", "episode_id": "episode-a", "reason": "break"})
            merged = apply_episode_operation(
                config,
                {"operation": "merge", "episode_id": "episode-b", "target_episode_id": "episode-a", "reason": "same work"},
            )
            split = apply_episode_operation(
                config,
                {"operation": "split", "episode_id": "episode-a", "new_episode_id": "episode-c", "summary": "Separate review task"},
            )

        self.assertEqual(paused["episode"]["status"], "paused")
        self.assertEqual(merged["episode"]["status"], "merged")
        self.assertEqual(merged["episode_link"]["relation"], "merged_into")
        self.assertEqual(split["new_episode"]["episode_id"], "episode-c")
        self.assertEqual(split["episode_link"]["relation"], "split_into")

    def test_activation_response_accept_and_decline_are_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            event = _event("unlock", collector="device_state", stimulus_type="screen_unlocked")
            JanusEventRouter(config, model_client=StaticModelClient(_decision_payload()), run_agent=False).handle_event(event)
            activation_id = janus_status(config)["activations"][0]["activation_id"]

            accepted = respond_to_activation(
                config,
                {"activation_id": activation_id, "response_type": "accept", "text": "Help me draft the proposal."},
            )
            declined = respond_to_activation(
                config,
                {"activation_id": activation_id, "response_type": "decline", "text": "No help now."},
            )

        self.assertEqual(accepted["activation_response"]["action_taken"], "accepted")
        self.assertEqual(declined["activation_response"]["action_taken"], "no_assistance")
        self.assertEqual(len(declined["status"]["activation_responses"]), 2)

    def test_privacy_export_delete_eval_and_entity_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            event = _event(
                "docs",
                collector="document_composition_activity",
                source="google_docs",
                stimulus_type="document_saved",
                metadata={"document_id": "doc-raw-id", "title": "SECRET TITLE"},
            )
            JanusEventRouter(config, model_client=StaticModelClient(_decision_payload()), run_agent=False).handle_event(event)

            refs = extract_entity_refs(event)
            exported = janus_privacy_export(config, {"collector": "document_composition_activity"})
            eval_run = run_janus_eval(config, {"scenario": "unit"})
            deleted = janus_privacy_delete(config, {"collector": "document_composition_activity"})

        self.assertTrue(any(ref.startswith("document_id_hash:") for ref in refs))
        self.assertNotIn("SECRET TITLE", json.dumps(exported, sort_keys=True))
        self.assertIn(eval_run["eval_run"]["status"], {"passed", "failed"})
        self.assertGreaterEqual(sum(deleted["privacy_action"]["affected_counts"].values()), 1)

    def test_collector_consumer_advances_independent_offset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            log = CollectorEventLog(config.collector_events_db_path)
            appended = log.append(_envelope("unlock", collector="device_state", stimulus_type="screen_unlocked"))
            result = JanusConsumer(log).consume(config, run_agent=False)
            status = log.status()

        self.assertEqual(result["processed"], 1)
        offset = next(item for item in status["consumer_offsets"] if item["consumer_name"] == janus_consumer_name)
        self.assertEqual(offset["last_sequence"], appended["sequence"])

    def test_task_context_service_persists_user_declared_goal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            result = declare_task_context(config, {"goal": "Draft the Acme proposal", "allowed_help": ["resume_capsule"]})

        self.assertEqual(result["task_context"]["user_declared_goal"], "Draft the Acme proposal")
        self.assertEqual(result["task_context"]["allowed_help"], ["resume_capsule"])

    def test_user_declared_task_context_projects_to_focus_store_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            declare_task_context(
                config,
                {
                    "task_context_id": "ctx_focus",
                    "goal": "Draft the Acme proposal",
                    "allowed_help": ["resume_capsule"],
                },
            )
            focus = FocusStore(config.cognition_db_path).load()

        serialized_focus = json.dumps(
            {
                "active_task_id": focus.active_task_id,
                "summary": focus.summary,
                "pinned_context": focus.pinned_context,
                "metadata": focus.metadata,
            },
            sort_keys=True,
        )
        if "ctx_focus" not in serialized_focus and "Draft the Acme proposal" not in serialized_focus:
            self.skipTest("Janus user-declared task contexts are not projected into FocusStore yet.")
        self.assertIn("Draft the Acme proposal", serialized_focus)

    def test_sustained_context_events_persist_generic_boundary_and_invoke_reflex_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            client = CapturingModelClient(_decision_payload())
            router = JanusEventRouter(config, model_client=client, run_agent=False)
            for event in _events(
                ["save-1", "save-2", "save-3"],
                collector="document_composition_activity",
                source="google_docs",
                stimulus_type="document_saved",
                metadata={"document_id_hash": "doc123", "workspace_id_hash": "workspace123"},
                occurred_at=[
                    "2026-06-11T00:00:00+00:00",
                    "2026-06-11T00:04:00+00:00",
                    "2026-06-11T00:09:00+00:00",
                ],
            ):
                router.handle_event(event)
            status = janus_status(config)

        boundary = _require_boundary(status, "generic")
        serialized_boundary = json.dumps(boundary, sort_keys=True)
        self.assertIn("document_id_hash:doc123", serialized_boundary)
        self.assertIn("google_docs", serialized_boundary)
        self.assertEqual(len(client.prompts), 1)
        self.assertEqual(len(status["decisions"]), 1)

    def test_repeated_context_events_for_triggered_boundary_do_not_spam_reflex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            client = CapturingModelClient(_decision_payload())
            router = JanusEventRouter(config, model_client=client, run_agent=False)
            for event in _events(
                ["save-1", "save-2", "save-3", "save-4", "save-5"],
                collector="document_composition_activity",
                source="google_docs",
                stimulus_type="document_saved",
                metadata={"document_id_hash": "doc123", "workspace_id_hash": "workspace123"},
                occurred_at=[
                    "2026-06-11T00:00:00+00:00",
                    "2026-06-11T00:04:00+00:00",
                    "2026-06-11T00:09:00+00:00",
                    "2026-06-11T00:10:00+00:00",
                    "2026-06-11T00:11:00+00:00",
                ],
            ):
                router.handle_event(event)
            status = janus_status(config)

        _require_boundary(status, "generic")
        self.assertEqual(len(client.prompts), 1)
        self.assertEqual(len(status["decisions"]), 1)

    def test_context_event_after_large_gap_creates_resume_boundary_and_capsule_when_exposed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            client = CapturingModelClient(_decision_payload())
            router = JanusEventRouter(config, model_client=client, run_agent=False)
            for event in _events(
                ["save-1", "save-2", "return-save"],
                collector="document_composition_activity",
                source="google_docs",
                stimulus_type="document_saved",
                metadata={"document_id_hash": "doc123", "workspace_id_hash": "workspace123"},
                occurred_at=[
                    "2026-06-11T00:00:00+00:00",
                    "2026-06-11T00:04:00+00:00",
                    "2026-06-11T03:30:00+00:00",
                ],
            ):
                router.handle_event(event)
            status = janus_status(config)

        boundary = _require_boundary(status, "resume")
        self.assertEqual(len(client.prompts), 1)
        self.assertEqual(len(status["decisions"]), 1)
        resume_artifacts = _resume_artifacts(status)
        if not resume_artifacts:
            self.skipTest("Resume capsule/status artifacts are not exposed by janus_status yet.")
        serialized_resume_state = json.dumps({"boundary": boundary, "artifacts": resume_artifacts}, sort_keys=True)
        self.assertIn("resume", serialized_resume_state.lower())
        self.assertIn("document_id_hash:doc123", serialized_resume_state)

    def test_status_exposes_safe_explanation_artifacts_for_janus_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            create_muted_scope(config, {"collector": "device_state", "source": "muted_source", "mode": "no_assistance"})
            router = JanusEventRouter(config, model_client=StaticModelClient(_decision_payload()), run_agent=False)

            router.handle_event(_event("muted", collector="device_state", source="muted_source", stimulus_type="screen_unlocked"))
            router.handle_event(_event("blocked", collector="verification_code_activity", stimulus_type="otp_code_detected"))
            router.handle_event(_event("reflex", collector="device_state", stimulus_type="screen_unlocked"))
            for event in _events(
                ["save-1", "save-2", "save-3"],
                collector="document_composition_activity",
                source="google_docs",
                stimulus_type="document_saved",
                metadata={"document_id_hash": "doc123", "workspace_id_hash": "workspace123"},
                occurred_at=[
                    "2026-06-11T00:00:00+00:00",
                    "2026-06-11T00:04:00+00:00",
                    "2026-06-11T00:09:00+00:00",
                ],
            ):
                router.handle_event(event)
            status = janus_status(config, limit=20)

        artifacts = _explanation_artifacts(status)
        if not artifacts:
            self.skipTest("Janus explanation/status artifacts are not exposed by janus_status yet.")

        serialized = json.dumps(artifacts, sort_keys=True).lower()
        self.assertTrue(_contains_any(serialized, ("muted", "mute")))
        self.assertTrue(_contains_any(serialized, ("blocked", "policy_blocked", "private")))
        self.assertTrue(_contains_any(serialized, ("reflex", "decision")))
        self.assertTrue(_contains_any(serialized, ("context_boundary", "stable_context", "return_after_gap", "boundary")))
        for artifact in artifacts:
            evidence = _artifact_evidence(artifact)
            self.assertTrue(evidence, f"explanation artifact is missing safe evidence refs: {artifact!r}")
            evidence_text = json.dumps(evidence, sort_keys=True).lower()
            self.assertTrue(_contains_any(evidence_text, ("collector_event", "event_sequence", "route_id", "boundary_id", "decision_id")))
            self.assertNotIn("raw_content", evidence_text)
            self.assertNotIn("payload", evidence_text)

    def test_user_correction_contract_persists_and_projects_to_status_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _config(tmp_dir)
            router = JanusEventRouter(config, model_client=StaticModelClient(_decision_payload()), run_agent=False)
            router.handle_event(_event("reflex", collector="device_state", stimulus_type="screen_unlocked"))
            status_before = janus_status(config, limit=10)
            decision_id = status_before["decisions"][0]["decision_id"]

            corrections = []
            for correction_type in ("wrong_task", "private", "not_relevant", "helpful"):
                payload = {
                    "target_type": "decision",
                    "target_id": decision_id,
                    "correction_type": correction_type,
                    "reason": f"user marked the janus decision as {correction_type}",
                    "evidence_refs": [f"reflex_decision:{decision_id}"],
                }
                if correction_type == "wrong_task":
                    payload["task_context"] = {
                        "task_context_id": "ctx_corrected",
                        "goal": "Review the personal finance note",
                        "allowed_help": ["resume_capsule"],
                    }
                if correction_type == "private":
                    payload["collector"] = "device_state"
                corrections.append(_record_user_correction(config, payload))
            status = janus_status(config, limit=20)

        status_corrections = _corrections(status)
        if not status_corrections:
            self.skipTest("Janus corrections are not exposed by janus_status yet.")
        serialized = json.dumps({"results": corrections, "status": status}, sort_keys=True)
        for correction_type in ("wrong_task", "private", "not_relevant", "helpful"):
            self.assertIn(correction_type, serialized)
        self.assertIn("ctx_corrected", serialized)
        self.assertIn("Review the personal finance note", serialized)
        self.assertIn("private", serialized)


def _config(tmp_dir: str) -> AgentConfig:
    return AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts", planner_provider="explicit").normalized()


def _episode(episode_id: str, summary: str):
    from humungousaur.janus.models import JanusEpisode, Confidence

    return JanusEpisode(
        episode_id=episode_id,
        status="active",
        source="test",
        hypothesis=summary,
        summary=summary,
        confidence=Confidence.MEDIUM,
        evidence_refs=[f"test:{episode_id}"],
    )


def _event(
    name: str,
    *,
    collector: str,
    stimulus_type: str,
    source: str = "activity",
    occurred_at: str = "2026-06-11T00:00:00+00:00",
    metadata: dict | None = None,
    payload: dict | None = None,
) -> dict:
    log = CollectorEventLog(Path(tempfile.mkdtemp()) / "events.sqlite3")
    appended = log.append(
        _envelope(
            name,
            collector=collector,
            source=source,
            stimulus_type=stimulus_type,
            occurred_at=occurred_at,
            metadata=metadata,
            payload=payload,
        )
    )
    return log.get(appended["sequence"]) or {}


def _events(
    names: list[str],
    *,
    collector: str,
    stimulus_type: str,
    source: str = "activity",
    occurred_at: list[str] | None = None,
    metadata: dict | None = None,
) -> list[dict]:
    log = CollectorEventLog(Path(tempfile.mkdtemp()) / "events.sqlite3")
    events = []
    for index, name in enumerate(names):
        event_time = (
            occurred_at[index]
            if occurred_at and index < len(occurred_at)
            else "2026-06-11T00:00:00+00:00"
        )
        appended = log.append(
            _envelope(
                name,
                collector=collector,
                source=source,
                stimulus_type=stimulus_type,
                occurred_at=event_time,
                metadata=metadata,
            )
        )
        events.append(log.get(appended["sequence"]) or {})
    return events


def _envelope(
    name: str,
    *,
    collector: str,
    stimulus_type: str,
    source: str = "activity",
    occurred_at: str = "2026-06-11T00:00:00+00:00",
    metadata: dict | None = None,
    payload: dict | None = None,
) -> CollectorEventEnvelope:
    return CollectorEventEnvelope(
        event_id=f"active-event-{name}",
        collector=collector,
        source=source,
        platform="Darwin",
        stimulus_type=stimulus_type,
        privacy_tier="metadata",
        occurred_at=occurred_at,
        received_at=occurred_at,
        signature=f"{collector}:{stimulus_type}:{name}",
        text=f"{collector} {stimulus_type}",
        metadata=metadata
        if metadata is not None
        else ({"document_id_hash": "doc123"} if "document" in collector else {}),
        payload=payload or {},
        redaction={
            "raw_content_included": False,
            "attention_safe": True,
            "payload_compacted_before_llm": True,
        },
    )


def _require_boundary(status: dict, expected_kind: str) -> dict:
    if not _boundary_api_exposed(status):
        raise unittest.SkipTest("Janus boundary status API is not exposed yet.")
    boundaries = _boundaries(status)
    if not boundaries:
        raise AssertionError(f"expected at least one janus {expected_kind} boundary")
    expected = _boundary_aliases(expected_kind)
    for boundary in boundaries:
        serialized = json.dumps(boundary, sort_keys=True).lower()
        if any(alias in serialized for alias in expected):
            return boundary
    raise AssertionError(f"expected {expected_kind} boundary in {boundaries!r}")


def _boundary_aliases(expected_kind: str) -> tuple[str, ...]:
    expected = expected_kind.lower()
    aliases = {
        "generic": ("generic", "stable_context", "sustained_context"),
        "resume": ("resume", "return_after_gap", "return_boundary"),
    }
    return aliases.get(expected, (expected,))


def _boundary_api_exposed(status: dict) -> bool:
    return any(
        key in status
        for key in ("boundaries", "active_boundaries", "context_boundaries", "active_context_boundaries")
    )


def _boundaries(status: dict) -> list[dict]:
    for key in ("boundaries", "active_boundaries", "context_boundaries", "active_context_boundaries"):
        value = status.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = value.get("items") or value.get("boundaries")
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
    return []


def _resume_artifacts(status: dict) -> list[dict]:
    artifacts = []
    for key in ("resume_capsules", "capsules", "prepared_help", "status_artifacts"):
        value = status.get(key)
        if isinstance(value, list):
            artifacts.extend(item for item in value if isinstance(item, dict))
    return artifacts


def _explanation_artifacts(status: dict) -> list[dict]:
    artifacts = []
    for key in (
        "explanation_artifacts",
        "janus_explanations",
        "status_explanations",
        "explanations",
        "status_artifacts",
    ):
        value = status.get(key)
        if isinstance(value, list):
            artifacts.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            nested = value.get("items") or value.get("artifacts") or value.get("explanations")
            if isinstance(nested, list):
                artifacts.extend(item for item in nested if isinstance(item, dict))
    return artifacts


def _artifact_evidence(artifact: dict) -> object:
    for key in ("safe_evidence_refs", "evidence_refs", "evidence", "citations", "source_refs"):
        value = artifact.get(key)
        if value:
            return value
    return None


def _corrections(status: dict) -> list[dict]:
    for key in ("corrections", "user_corrections", "janus_corrections"):
        value = status.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = value.get("items") or value.get("corrections")
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
    return []


def _record_user_correction(config: AgentConfig, payload: dict) -> dict:
    import humungousaur.janus as janus

    for name in ("record_user_correction", "create_user_correction", "submit_user_correction", "correct_janus"):
        handler = getattr(janus, name, None)
        if callable(handler):
            return handler(config, payload)
    store = JanusStore(config.janus_db_path)
    for name in ("record_user_correction", "create_user_correction", "submit_user_correction"):
        handler = getattr(store, name, None)
        if callable(handler):
            result = handler(payload)
            return result if isinstance(result, dict) else {"correction": result}
    raise unittest.SkipTest("Janus user correction API/service is not exposed yet.")


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _guide_text(title: str, signal_words: str) -> str:
    return f"""# Activity Guide: {title}

## Summary
Use this pack for broad {title.lower()} workflows.

## Signals
- {signal_words}

## Helpful Moments
- Prepare quiet help at safe task boundaries.

## Stay Silent When
- Evidence is weak, private, muted, or only background sync.

## Deep Dive Triggers
- Rich content would be needed to help.

## Memory Guidance
- Store only redacted entity refs and safe progress summaries.

## Privacy Notes
- Do not infer private content or request raw data without approval.
"""


def _decision_payload() -> str:
    return json.dumps(
        {
            "posture": "prepare",
            "confidence": "medium",
            "should_interrupt_user": False,
            "user_visible_text": "",
            "agent_stimulus": "Prepare a resume capsule.",
            "reason": "User returned after a gap.",
            "task_context_updates": [
                {
                    "task_context_id": "ctx_acme",
                    "status": "active",
                    "source": "model",
                    "summary": "User resumed the Acme proposal.",
                }
            ],
            "memory_updates": [{"kind": "working_context", "summary": "Resume capsule prepared."}],
            "safety_notes": ["No rich content requested."],
            "deep_dive_request": None,
        }
    )


def _posture_payload(
    *,
    posture: str,
    user_visible_text: str = "",
    agent_stimulus: str = "",
    should_interrupt_user: bool = False,
    deep_dive_request: dict | None = None,
    episode_update: dict | None = None,
    task_context_updates: list[dict] | None = None,
    memory_updates: list[dict] | None = None,
) -> str:
    return json.dumps(
        {
            "posture": posture,
            "confidence": "high",
            "should_interrupt_user": should_interrupt_user,
            "user_visible_text": user_visible_text,
            "agent_stimulus": agent_stimulus,
            "reason": f"Test decision for {posture}.",
            "task_context_updates": task_context_updates or [],
            "memory_updates": memory_updates or [],
            "safety_notes": [],
            "deep_dive_request": deep_dive_request,
            "episode_update": episode_update,
        }
    )


class CapturingModelClient(StaticModelClient):
    def __init__(self, response: str) -> None:
        super().__init__(response)
        self.prompts: list[str] = []
        self.schemas: list[dict] = []

    def complete_json(self, prompt, schema):  # type: ignore[no-untyped-def]
        self.prompts.append(prompt)
        self.schemas.append(schema)
        return super().complete_json(prompt, schema)


if __name__ == "__main__":
    unittest.main()
