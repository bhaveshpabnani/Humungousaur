import json
import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.media_tools import (
    AudioTagParseTool,
    FFmpegMediaTranscodeTool,
    FFProbeMediaProbeTool,
    HEICToJPEGConvertTool,
    MediaStoryboardCreateTool,
    MediaStoryboardInspectTool,
    MediaReferenceCreateTool,
    MediaRemoteFetchPlanTool,
    MediaRootsPolicyTool,
    MediaStoreCleanupTool,
    MediaStoreImportTool,
    OutboundAttachmentPrepareTool,
    QRPairingArtifactCreateTool,
    SoundSpecCreateTool,
    SoundSpecInspectTool,
    VoiceMemoPackagePrepareTool,
)


class MediaToolTests(unittest.TestCase):
    def test_sound_spec_create_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = SoundSpecCreateTool().execute(
                {
                    "filename": "launch-jingle.md",
                    "title": "Launch Jingle",
                    "sound_type": "song",
                    "intended_use": "Internal launch celebration",
                    "duration_seconds": 30,
                    "genre": "bright synth pop",
                    "mood": "optimistic",
                    "tempo_bpm": 118,
                    "instrumentation": ["soft drums", "pluck synth", "warm bass"],
                    "lyrics": "We shipped the thing, we kept it clean.",
                    "sections": [{"name": "Hook", "start": "00:00", "duration": "10s", "notes": "Start immediately with the motif."}],
                    "licensing_constraints": ["No living-artist imitation."],
                    "reason": "Verify native sound spec creation.",
                },
                config,
            )
            inspected = SoundSpecInspectTool().execute({"path": created.output["path"]}, config)
            metadata = json.loads(Path(created.output["metadata_path"]).read_text(encoding="utf-8"))

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["sound_type"], "song")
        self.assertEqual(created.output["section_count"], 1)
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["licensing_constraint_count"], 1)
        self.assertEqual(metadata["status"], "prepared_not_generated")

    def test_media_storyboard_create_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = MediaStoryboardCreateTool().execute(
                {
                    "filename": "slack-confetti.md",
                    "title": "Slack Confetti Reaction",
                    "media_type": "gif",
                    "audience": "Product team",
                    "intended_use": "Slack celebration draft",
                    "duration_seconds": 2.5,
                    "width": 480,
                    "height": 270,
                    "style": "clean geometric",
                    "palette": ["#1d3557", "#f1faee", "#e63946"],
                    "scenes": [
                        {"label": "Start", "description": "A calm checkmark appears.", "duration_seconds": 0.8, "motion": "fade in"},
                        {"label": "Burst", "description": "Confetti arcs outward.", "duration_seconds": 1.7, "motion": "radial burst", "text": "Done"},
                    ],
                    "accessibility_notes": ["Avoid flashing."],
                    "licensing_constraints": ["No copyrighted characters."],
                    "reason": "Verify native storyboard creation.",
                },
                config,
            )
            inspected = MediaStoryboardInspectTool().execute({"path": created.output["path"]}, config)
            svg_exists = Path(created.output["svg_path"]).exists()

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertTrue(svg_exists)
        self.assertEqual(created.output["scene_count"], 2)
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["media_type"], "gif")
        self.assertIn("Slack Confetti Reaction", inspected.output["preview"])

    def test_media_storyboard_requires_scene_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = MediaStoryboardCreateTool().execute(
                {"title": "Bad Storyboard", "media_type": "video", "scenes": [{"label": "Empty"}], "reason": "Verify validation."},
                config,
            )

        self.assertEqual(result.status, ActionStatus.FAILED)
        self.assertIn("requires a description", result.summary)

    def test_native_media_store_reference_and_attachment_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            source = workspace / "tiny.png"
            source.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            imported = MediaStoreImportTool().execute({"path": "tiny.png", "reason": "Test import."}, config)
            reference = MediaReferenceCreateTool().execute(
                {"source_type": "local_file", "source": "tiny.png", "reason": "Reference media."},
                config,
            )
            attachment = OutboundAttachmentPrepareTool().execute(
                {"media_path": imported.output["path"], "channel_id": "slack", "caption": "hello", "as_voice": False, "reason": "Prepare send."},
                config,
            )
            roots = MediaRootsPolicyTool().execute({}, config)
            manifest_path_exists = Path(imported.output["manifest_path"]).exists()

        self.assertEqual(imported.status, ActionStatus.SUCCEEDED)
        self.assertEqual(imported.output["manifest"]["mime_type"], "image/png")
        self.assertTrue(manifest_path_exists)
        self.assertEqual(reference.status, ActionStatus.SUCCEEDED)
        self.assertTrue(reference.output["reference"]["trusted_local"])
        self.assertEqual(attachment.status, ActionStatus.SUCCEEDED)
        self.assertEqual(attachment.output["attachment"]["status"], "prepared_not_sent")
        self.assertIn("media_store_root", roots.output["roots"])

    def test_audio_qr_and_ffprobe_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            source = workspace / "clip.wav"
            source.write_bytes(b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 32)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            parsed = AudioTagParseTool().execute({"text": "send this [audio_as_voice] please"}, config)
            qr = QRPairingArtifactCreateTool().execute({"data": "pairing-token", "reason": "Test QR artifact."}, config)
            probed = FFProbeMediaProbeTool().execute({"path": "clip.wav"}, config)
            qr_svg_exists = Path(qr.output["svg_path"]).exists()

        self.assertEqual(parsed.status, ActionStatus.SUCCEEDED)
        self.assertTrue(parsed.output["audio_as_voice"])
        self.assertEqual(qr.status, ActionStatus.SUCCEEDED)
        self.assertTrue(qr_svg_exists)
        self.assertIn(probed.status, {ActionStatus.SUCCEEDED, ActionStatus.SKIPPED, ActionStatus.FAILED})

    def test_remote_fetch_plan_and_store_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            source = workspace / "orphan.bin"
            source.write_bytes(b"orphan")
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()
            imported = MediaStoreImportTool().execute({"path": "orphan.bin", "reason": "Import cleanup target."}, config)
            stored_path = Path(imported.output["path"])
            Path(imported.output["manifest_path"]).unlink()

            planned = MediaRemoteFetchPlanTool().execute(
                {
                    "url": "https://example.com/file.png",
                    "allowed_domains": ["example.com"],
                    "allowed_mime_types": ["image/png"],
                    "reason": "Plan remote media policy.",
                },
                config,
            )
            inspected = MediaStoreCleanupTool().execute({"media_id": stored_path.stem, "execute": False}, config)
            cleaned = MediaStoreCleanupTool().execute({"media_id": stored_path.stem, "execute": True}, config)

        self.assertEqual(planned.status, ActionStatus.SUCCEEDED)
        self.assertEqual(planned.output["plan"]["status"], "prepared_not_fetched")
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertTrue(inspected.output["candidates"][0]["missing_manifest"])
        self.assertEqual(cleaned.status, ActionStatus.SUCCEEDED)
        self.assertFalse(stored_path.exists())

    def test_heic_voice_memo_and_transcode_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            heic = workspace / "photo.heic"
            heic.write_bytes(b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64)
            wav = workspace / "voice.wav"
            wav.write_bytes(b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 32)
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            converted = HEICToJPEGConvertTool().execute({"path": "photo.heic", "reason": "Provider compatibility."}, config)
            voice = VoiceMemoPackagePrepareTool().execute(
                {"audio_path": "voice.wav", "channel_id": "signal", "caption": "memo", "reason": "Package voice memo."},
                config,
            )
            transcoded = FFmpegMediaTranscodeTool().execute({"path": "voice.wav", "target": "mp3", "max_seconds": 1, "reason": "Transcode smoke."}, config)

        self.assertIn(converted.status, {ActionStatus.SUCCEEDED, ActionStatus.SKIPPED})
        self.assertEqual(voice.status, ActionStatus.SUCCEEDED)
        self.assertTrue(voice.output["voice_memo"]["as_voice"])
        self.assertIn(transcoded.status, {ActionStatus.SUCCEEDED, ActionStatus.SKIPPED, ActionStatus.FAILED})


if __name__ == "__main__":
    unittest.main()
