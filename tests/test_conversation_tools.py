from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.conversation import (
    ConsultQuestionPrepareTool,
    ConsultQuestionResolveTool,
    TalkContextUpdateTool,
    TalkOutputActivityRecordTool,
    TalkSessionRecordTurnTool,
    TalkSessionStartTool,
    TalkSessionStatusTool,
    TalkTranscriptReadTool,
    default_conversation_tools,
)


def _config(root: Path) -> AgentConfig:
    return AgentConfig(
        workspace=root,
        data_dir=root / ".humungousaur",
        allowed_write_roots=(root,),
    )


def test_default_conversation_tools_include_native_talk_and_consult_tools() -> None:
    tools = default_conversation_tools()

    assert "talk_session_start" in tools
    assert "talk_session_record_turn" in tools
    assert "talk_context_update" in tools
    assert "talk_output_activity_record" in tools
    assert "talk_session_status" in tools
    assert "talk_transcript_read" in tools
    assert "consult_question_prepare" in tools
    assert "consult_question_resolve" in tools


def test_talk_session_lifecycle_persists_context_transcript_and_output_activity() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        config = _config(root)

        started = TalkSessionStartTool().execute(
            {
                "activation_names": ["Humungousaur", "Agent"],
                "provider": "synthetic",
                "mode": "mixed",
                "fast_context": "Initial context.",
                "reason": "native talk parity smoke.",
            },
            config,
        )
        assert started.status is ActionStatus.SUCCEEDED
        session_id = started.output["session"]["session_id"]
        session_path = Path(started.output["path"])
        assert session_path.exists()

        context = TalkContextUpdateTool().execute(
            {
                "session_id": session_id,
                "fast_context": "Updated fast context.",
                "turn_context": "Current turn context.",
                "reason": "Need bounded talk context.",
            },
            config,
        )
        assert context.status is ActionStatus.SUCCEEDED
        assert context.output["fast_context"] == "Updated fast context."

        user_turn = TalkSessionRecordTurnTool().execute(
            {"session_id": session_id, "speaker": "user", "text": "Can you inspect this?", "modality": "voice"},
            config,
        )
        assistant_turn = TalkSessionRecordTurnTool().execute(
            {
                "session_id": session_id,
                "speaker": "assistant",
                "text": "Yes, I prepared the next step.",
                "modality": "text",
                "output_produced": True,
            },
            config,
        )
        assert user_turn.status is ActionStatus.SUCCEEDED
        assert assistant_turn.status is ActionStatus.SUCCEEDED

        activity = TalkOutputActivityRecordTool().execute(
            {
                "session_id": session_id,
                "produced_output": True,
                "modality": "text",
                "summary": "Prepared next step.",
            },
            config,
        )
        assert activity.status is ActionStatus.SUCCEEDED

        transcript = TalkTranscriptReadTool().execute({"session_id": session_id, "limit": 10}, config)
        assert transcript.status is ActionStatus.SUCCEEDED
        assert "user: Can you inspect this?" in transcript.output["replay"]
        assert "assistant: Yes, I prepared the next step." in transcript.output["replay"]

        status = TalkSessionStatusTool().execute({"session_id": session_id, "include_transcript": True}, config)
        assert status.status is ActionStatus.SUCCEEDED
        session = status.output["session"]
        assert session["activation_names"] == ["Humungousaur", "Agent"]
        assert session["fast_context"] == "Updated fast context."
        assert len(session["transcript"]) == 2
        assert len(session["output_activity"]) == 1

        stored = json.loads(session_path.read_text(encoding="utf-8"))
        assert stored["turn_context"] == "Current turn context."


def test_consult_question_prepare_and_resolve_attach_to_talk_session() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        config = _config(root)

        started = TalkSessionStartTool().execute({"mode": "text", "reason": "Need consult fixture."}, config)
        session_id = started.output["session"]["session_id"]

        prepared = ConsultQuestionPrepareTool().execute(
            {
                "session_id": session_id,
                "question": "Should I send the message now?",
                "choices": ["yes", "no"],
                "blocking": True,
                "reason": "Requires human confirmation.",
            },
            config,
        )
        assert prepared.status is ActionStatus.SUCCEEDED
        consult_id = prepared.output["consult"]["consult_id"]
        assert prepared.output["consult"]["blocking"] is True
        assert Path(prepared.output["path"]).exists()

        session = TalkSessionStatusTool().execute({"session_id": session_id, "include_transcript": True}, config)
        assert consult_id in session.output["session"]["consults"]

        resolved = ConsultQuestionResolveTool().execute(
            {"consult_id": consult_id, "status": "answered", "answer": "Yes, send it."},
            config,
        )
        assert resolved.status is ActionStatus.SUCCEEDED
        assert resolved.output["consult"]["status"] == "answered"
        assert resolved.output["consult"]["answer"] == "Yes, send it."
