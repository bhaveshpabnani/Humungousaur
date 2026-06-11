from __future__ import annotations

import importlib.util
from pathlib import Path
import platform
import shutil
import subprocess
import time
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.os_tools import ScreenshotCaptureTool

from ..models import CollectorEvent, CollectorProfile


def collect_clipboard(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del config, state
    text = _clipboard_text()
    if not text:
        return []
    trimmed = text[: profile.max_text_chars]
    return [
        CollectorEvent(
            collector="clipboard",
            source="activity",
            stimulus_type="clipboard_changed",
            text=f"Clipboard changed: {trimmed}",
            metadata={"text_length": len(text), "truncated": len(text) > len(trimmed), "platform": platform.system()},
            payload={"text_preview": trimmed, "text_length": len(text)},
        )
    ]


def collect_screenshot(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    if not _interval_elapsed(state, "screenshot", profile.screenshot_min_interval_seconds):
        return []
    result = ScreenshotCaptureTool().execute({"reason": "Opt-in continuous screenshot stimulus collector."}, config)
    if result.status != ActionStatus.SUCCEEDED:
        return []
    state.setdefault("last_capture_at", {})["screenshot"] = time.time()
    output = dict(result.output)
    return [
        CollectorEvent(
            collector="screenshot",
            source="screen_ocr",
            stimulus_type="screenshot_captured",
            text=f"Screenshot captured: {output.get('filename', '')}",
            metadata={"filename": output.get("filename", ""), "width": output.get("width"), "height": output.get("height")},
            payload={key: value for key, value in output.items() if key != "path"},
        )
    ]


def collect_screen_ocr(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    if not _interval_elapsed(state, "screen_ocr", profile.ocr_min_interval_seconds):
        return []
    result = ScreenshotCaptureTool().execute({"reason": "Opt-in OCR stimulus collector screenshot."}, config)
    if result.status != ActionStatus.SUCCEEDED:
        return []
    path = Path(str(result.output.get("path") or ""))
    text = _ocr_image(path)
    state.setdefault("last_capture_at", {})["screen_ocr"] = time.time()
    if not text:
        return []
    trimmed = text[: profile.max_text_chars]
    return [
        CollectorEvent(
            collector="screen_ocr",
            source="screen_ocr",
            stimulus_type="screen_text_changed",
            text=f"Screen OCR: {trimmed}",
            metadata={"filename": path.name, "text_length": len(text), "truncated": len(text) > len(trimmed)},
            payload={"text_preview": trimmed, "screenshot_filename": path.name},
        )
    ]


def collect_video_frame(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    if not _interval_elapsed(state, "video_frame", profile.video_frame_min_interval_seconds):
        return []
    result = ScreenshotCaptureTool().execute({"reason": "Opt-in video keyframe stimulus collector."}, config)
    if result.status != ActionStatus.SUCCEEDED:
        return []
    state.setdefault("last_capture_at", {})["video_frame"] = time.time()
    output = dict(result.output)
    return [
        CollectorEvent(
            collector="video_frame",
            source="screen_ocr",
            stimulus_type="video_keyframe_captured",
            text=f"Video keyframe captured: {output.get('filename', '')}",
            metadata={"filename": output.get("filename", ""), "width": output.get("width"), "height": output.get("height")},
            payload={key: value for key, value in output.items() if key != "path"},
        )
    ]


def collect_audio_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del config, state
    sample = _audio_rms_sample(profile.audio_sample_seconds)
    if sample is None:
        return []
    rms = float(sample.get("rms", 0.0))
    if rms < profile.audio_rms_threshold:
        return []
    return [
        CollectorEvent(
            collector="audio_activity",
            source="audio_transcript",
            stimulus_type="voice_activity_detected",
            text="Microphone voice activity detected without transcript.",
            metadata={"rms": round(rms, 6), "sample_seconds": profile.audio_sample_seconds},
            payload=sample,
            signature=f"voice_activity:{int(time.time() // 10)}",
        )
    ]


def _clipboard_text() -> str:
    system = platform.system().lower()
    if system == "darwin":
        output = _run(["pbpaste"])
        return output.get("stdout", "") if output.get("returncode") == 0 else ""
    if system == "windows":
        output = _run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"], timeout=3.0)
        return output.get("stdout", "") if output.get("returncode") == 0 else ""
    for command in (["wl-paste", "-n"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "-b", "-o"]):
        if shutil.which(command[0]):
            output = _run(command, timeout=3.0)
            return output.get("stdout", "") if output.get("returncode") == 0 else ""
    return ""


def _ocr_image(path: Path) -> str:
    if path.exists() and shutil.which("tesseract"):
        output = _run(["tesseract", str(path), "stdout"], timeout=20.0)
        if output.get("returncode") == 0:
            return output.get("stdout", "").strip()
    return ""


def _audio_rms_sample(seconds: float) -> dict[str, Any] | None:
    if importlib.util.find_spec("sounddevice") is None or importlib.util.find_spec("numpy") is None:
        return None
    try:
        import numpy as np  # type: ignore[import-not-found]
        import sounddevice as sd  # type: ignore[import-not-found]

        sample_rate = 16_000
        audio = sd.rec(int(seconds * sample_rate), samplerate=sample_rate, channels=1, dtype="float32")
        sd.wait()
        rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
        return {"rms": rms, "sample_rate": sample_rate, "sample_seconds": seconds, "source": "sounddevice"}
    except Exception:
        return None


def _interval_elapsed(state: dict[str, Any], key: str, seconds: float) -> bool:
    last = float(state.get("last_capture_at", {}).get(key, 0.0) or 0.0)
    return time.time() - last >= seconds


def _run(command: list[str], *, timeout: float = 5.0) -> dict[str, Any]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        return {"returncode": -1, "stdout": "", "stderr": str(exc)}
    return {"returncode": completed.returncode, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}
