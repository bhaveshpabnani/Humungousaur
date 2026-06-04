import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.voice_tools import VoiceProviderStatusTool, VoiceResponsePrepareTool, VoiceSpeakTool, VoiceTranscribeTool


class VoiceProviderTests(unittest.TestCase):
    def test_voice_provider_status_redacts_key_presence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            with patch.dict("os.environ", {"DEEPGRAM_API_KEY": "dg-secret", "ELEVAN_LABS_API_KEY": "el-secret"}, clear=False):
                result = VoiceProviderStatusTool().execute({}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertTrue(result.output["stt"]["deepgram"]["configured"])
        self.assertTrue(result.output["tts"]["elevenlabs"]["configured"])
        self.assertNotIn("dg-secret", json.dumps(result.output))
        self.assertNotIn("el-secret", json.dumps(result.output))

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
                result = VoiceTranscribeTool().execute({"audio_path": str(audio), "reason": "test"}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertEqual(result.output["transcript"], "hello from deepgram")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.deepgram.com/v1/listen?smart_format=true")
        self.assertEqual(request.headers["Authorization"], "Token dg-test")

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


if __name__ == "__main__":
    unittest.main()
