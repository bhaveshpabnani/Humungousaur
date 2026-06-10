import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import urllib.error

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.voice_tools import VoiceProviderStatusTool, VoiceResponsePrepareTool, VoiceSpeakTool, VoiceTranscribeTool
from humungousaur.tools.voice.providers import SpeechProviderError, SpeechSynthesis, SpeechTranscription


class VoiceProviderTests(unittest.TestCase):
    def test_voice_provider_status_redacts_key_presence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with patch.dict("os.environ", {"DEEPGRAM_API_KEY": "dg-secret", "ELEVAN_LABS_API_KEY": "el-secret"}, clear=False):
                result = VoiceProviderStatusTool().execute({}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertTrue(result.output["stt"]["deepgram"]["configured"])
        self.assertIn("local-whisper", result.output["stt"])
        self.assertTrue(result.output["tts"]["elevenlabs"]["configured"])
        self.assertNotIn("dg-secret", json.dumps(result.output))
        self.assertNotIn("el-secret", json.dumps(result.output))

    def test_voice_provider_status_uses_runtime_secrets_without_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(
                workspace=Path(tmp_dir),
                data_dir=Path(tmp_dir) / "artifacts",
                runtime_secrets={"DEEPGRAM_API_KEY": "dg-runtime", "ELEVENLABS_API_KEY": "el-runtime"},
            ).normalized()
            with patch.dict("os.environ", {}, clear=True):
                result = VoiceProviderStatusTool().execute({}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertTrue(result.output["stt"]["deepgram"]["configured"])
        self.assertTrue(result.output["tts"]["elevenlabs"]["configured"])
        self.assertNotIn("dg-runtime", json.dumps(result.output))
        self.assertNotIn("el-runtime", json.dumps(result.output))

    def test_voice_provider_status_reports_macos_system_voice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with patch("platform.system", return_value="Darwin"):
                result = VoiceProviderStatusTool().execute({}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertTrue(result.output["tts"]["system"]["configured"])
        self.assertEqual(result.output["tts"]["system"]["provider"], "macos_say")

    def test_voice_transcribe_deepgram_parses_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            audio = workspace / "sample.wav"
            audio.write_bytes(b"RIFF....WAVEfmt ")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            response = _FakeResponse(
                json.dumps(
                    {
                        "results": {
                            "channels": [
                                {
                                    "alternatives": [
                                        {"transcript": "hello from deepgram", "confidence": 0.91}
                                    ]
                                }
                            ]
                        }
                    }
                ).encode("utf-8")
            )

            with (
                patch.dict("os.environ", {"DEEPGRAM_API_KEY": "dg-test"}, clear=False),
                patch("urllib.request.urlopen", return_value=response) as urlopen,
            ):
                result = VoiceTranscribeTool().execute({"audio_path": str(audio), "provider": "deepgram", "reason": "test"}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertEqual(result.output["transcript"], "hello from deepgram")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.deepgram.com/v1/listen?smart_format=true")
        self.assertEqual(request.headers["Authorization"], "Token dg-test")

    def test_voice_transcribe_defaults_to_local_whisper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            audio = workspace / "sample.wav"
            audio.write_bytes(b"RIFF....WAVEfmt ")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            with patch(
                "humungousaur.tools.voice.implementation.local_whisper_transcribe_file",
                return_value=SpeechTranscription(
                    provider="local-whisper",
                    transcript="hello locally",
                    confidence=0.8,
                    language="en",
                    model="tiny.en",
                    raw_shape={"type": "faster_whisper"},
                ),
            ) as transcribe:
                result = VoiceTranscribeTool().execute({"audio_path": str(audio), "reason": "test"}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertEqual(result.output["provider"], "local-whisper")
        self.assertEqual(result.output["transcript"], "hello locally")
        self.assertTrue(transcribe.called)

    def test_voice_response_prepare_elevenlabs_writes_audio_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with (
                patch.dict("os.environ", {"ELEVENLABS_API_KEY": "el-test"}, clear=False),
                patch("urllib.request.urlopen", return_value=_FakeResponse(b"audio-bytes")) as urlopen,
            ):
                result = VoiceResponsePrepareTool().execute(
                    {
                        "text": "hello there",
                        "reason": "test",
                        "tts_provider": "elevenlabs",
                        "voice_id": "voice-1",
                    },
                    config,
                )

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertTrue(Path(result.output["audio"]["audio_path"]).exists())
            self.assertTrue(Path(result.output["path"]).exists())
            request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.elevenlabs.io/v1/text-to-speech/voice-1")
        self.assertEqual(request.headers["Xi-api-key"], "el-test")

    def test_voice_response_prepare_elevenlabs_reports_paid_plan_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            error_body = json.dumps(
                {
                    "detail": {
                        "type": "payment_required",
                        "code": "paid_plan_required",
                        "message": "Free users cannot use library voices via the API.",
                        "status": "payment_required",
                    }
                }
            ).encode("utf-8")
            with (
                patch.dict("os.environ", {"ELEVENLABS_API_KEY": "el-test"}, clear=False),
                patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("url", 402, "Payment Required", {}, _FakeResponse(error_body))),
            ):
                result = VoiceResponsePrepareTool().execute(
                    {
                        "text": "hello there",
                        "reason": "test",
                        "tts_provider": "elevenlabs",
                        "voice_id": "library-voice",
                    },
                    config,
                )

        self.assertEqual(result.status, ActionStatus.FAILED)
        provider_error = result.output["provider_error"]
        self.assertEqual(provider_error["http_status"], 402)
        self.assertEqual(provider_error["provider_code"], "paid_plan_required")
        self.assertEqual(provider_error["category"], "provider_entitlement")
        self.assertIn("upgrade", provider_error["user_action"])

    def test_voice_response_prepare_elevenlabs_can_fallback_to_system(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            audio = workspace / "fallback.wav"
            audio.write_bytes(b"RIFF....WAVEfmt ")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            with (
                patch(
                    "humungousaur.tools.voice.implementation.elevenlabs_synthesize_to_file",
                    side_effect=SpeechProviderError("blocked"),
                ),
                patch(
                    "humungousaur.tools.voice.implementation.windows_sapi_synthesize_to_file",
                    return_value=SpeechSynthesis(
                        provider="windows_sapi",
                        audio_path=audio,
                        voice_id="windows_sapi",
                        model="windows_sapi",
                        output_format="wav",
                        mime_type="audio/wav",
                        byte_count=audio.stat().st_size,
                    ),
                ),
            ):
                result = VoiceResponsePrepareTool().execute(
                    {
                        "text": "hello with fallback",
                        "reason": "test",
                        "tts_provider": "elevenlabs",
                        "fallback_tts_provider": "system",
                    },
                    config,
                )

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertEqual(result.output["primary_tts_provider"], "elevenlabs")
        self.assertEqual(result.output["tts_provider"], "system")
        self.assertEqual(result.output["fallback_tts_provider"], "system")
        self.assertEqual(result.output["audio"]["provider"], "windows_sapi")

    def test_voice_speak_elevenlabs_can_synthesize_without_playback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with (
                patch.dict("os.environ", {"ELEVENLABS_API_KEY": "el-test"}, clear=False),
                patch("urllib.request.urlopen", return_value=_FakeResponse(b"audio-bytes")),
            ):
                result = VoiceSpeakTool().execute(
                    {
                        "text": "hello",
                        "reason": "test",
                        "provider": "elevenlabs",
                        "voice_id": "voice-1",
                        "playback": False,
                    },
                    config,
                )

            self.assertEqual(result.status, ActionStatus.SUCCEEDED)
            self.assertFalse(result.output["speech_played"])
            self.assertTrue(Path(result.output["audio"]["audio_path"]).exists())

    def test_voice_response_prepare_system_writes_audio_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            audio = workspace / "system.wav"
            audio.write_bytes(b"RIFF....WAVEfmt ")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            with (
                patch("platform.system", return_value="Windows"),
                patch(
                    "humungousaur.tools.voice.implementation.windows_sapi_synthesize_to_file",
                    return_value=SpeechSynthesis(
                        provider="windows_sapi",
                        audio_path=audio,
                        voice_id="windows_sapi",
                        model="windows_sapi",
                        output_format="wav",
                        mime_type="audio/wav",
                        byte_count=audio.stat().st_size,
                    ),
                ),
            ):
                result = VoiceResponsePrepareTool().execute(
                    {
                        "text": "hello from system voice",
                        "reason": "test",
                        "tts_provider": "system",
                    },
                    config,
                )
            artifact_path_exists = Path(result.output["path"]).exists()

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertEqual(result.output["audio"]["provider"], "windows_sapi")
        self.assertTrue(artifact_path_exists)

    def test_voice_response_prepare_system_writes_macos_audio_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            audio = workspace / "system.aiff"
            audio.write_bytes(b"FORM....AIFF")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            with (
                patch("platform.system", return_value="Darwin"),
                patch(
                    "humungousaur.tools.voice.implementation.macos_say_synthesize_to_file",
                    return_value=SpeechSynthesis(
                        provider="macos_say",
                        audio_path=audio,
                        voice_id="macos_say",
                        model="macos_say",
                        output_format="aiff",
                        mime_type="audio/aiff",
                        byte_count=audio.stat().st_size,
                    ),
                ),
            ):
                result = VoiceResponsePrepareTool().execute(
                    {
                        "text": "hello from mac system voice",
                        "reason": "test",
                        "tts_provider": "system",
                    },
                    config,
                )
            artifact_path_exists = Path(result.output["path"]).exists()

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertEqual(result.output["audio"]["provider"], "macos_say")
        self.assertTrue(artifact_path_exists)

    def test_voice_speak_system_uses_macos_say(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with (
                patch("platform.system", return_value="Darwin"),
                patch("humungousaur.tools.voice.implementation.macos_say_speak_text", return_value={"status": "ok"}),
            ):
                result = VoiceSpeakTool().execute(
                    {
                        "text": "hello from mac",
                        "reason": "test",
                        "provider": "system",
                    },
                    config,
                )

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertEqual(result.output["source"], "macos_say")


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            return self.body
        return self.body[:size]

    def close(self) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
