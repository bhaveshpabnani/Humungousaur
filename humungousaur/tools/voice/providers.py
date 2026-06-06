from __future__ import annotations

from dataclasses import dataclass
import base64
import http.client
import json
import mimetypes
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


VOICE_PROVIDER_USER_AGENT = "humungousaur/0.1"
DEEPGRAM_BASE_URL = "https://api.deepgram.com"
ELEVENLABS_BASE_URL = "https://api.elevenlabs.io"
VOICE_AUDIO_MAX_BYTES = 50_000_000
ELEVENLABS_RESPONSE_BYTES = 20_000_000


class SpeechProviderError(RuntimeError):
    pass


def classify_provider_error(error: str) -> dict[str, Any]:
    payload: dict[str, Any] = {"raw": error}
    marker = "HTTP "
    if marker in error:
        after_http = error.split(marker, 1)[1]
        status_text, _, detail = after_http.partition(":")
        try:
            payload["http_status"] = int(status_text.strip())
        except ValueError:
            payload["http_status"] = None
        detail = detail.strip()
        if detail:
            payload["detail"] = _json_provider_detail(detail)
    detail_payload = payload.get("detail", {})
    if isinstance(detail_payload, dict):
        detail_inner = detail_payload.get("detail", detail_payload)
        if isinstance(detail_inner, dict):
            payload["provider_type"] = detail_inner.get("type", "")
            payload["provider_code"] = detail_inner.get("code", "")
            payload["provider_status"] = detail_inner.get("status", "")
            payload["provider_message"] = detail_inner.get("message", "")
            payload["request_id"] = detail_inner.get("request_id", "")
    code = str(payload.get("provider_code") or payload.get("provider_status") or "").strip()
    if code in {"payment_required", "paid_plan_required"}:
        payload["category"] = "provider_entitlement"
        payload["user_action"] = "Use an ElevenLabs voice available to this account through the API, or upgrade the ElevenLabs plan for library voice API access."
    elif code in {"detected_unusual_activity", "quota_exceeded", "rate_limit_exceeded"}:
        payload["category"] = "provider_account"
        payload["user_action"] = "Resolve the ElevenLabs account status or quota in the provider dashboard, then rerun the smoke test."
    elif payload.get("http_status") in {401, 403}:
        payload["category"] = "provider_auth"
        payload["user_action"] = "Check the ElevenLabs API key and account permissions."
    elif payload.get("http_status") == 429:
        payload["category"] = "provider_rate_limit"
        payload["user_action"] = "Wait for provider rate limits to reset or lower request volume."
    else:
        payload["category"] = "provider_error"
        payload["user_action"] = "Inspect the provider error details and retry after the provider-side issue is fixed."
    return payload


@dataclass(slots=True)
class SpeechTranscription:
    provider: str
    transcript: str
    confidence: float | None
    language: str
    model: str
    raw_shape: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "transcript": self.transcript,
            "confidence": self.confidence,
            "language": self.language,
            "model": self.model,
            "raw_shape": self.raw_shape,
        }


@dataclass(slots=True)
class SpeechSynthesis:
    provider: str
    audio_path: Path
    voice_id: str
    model: str
    output_format: str
    mime_type: str
    byte_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "audio_path": str(self.audio_path),
            "voice_id": self.voice_id,
            "model": self.model,
            "output_format": self.output_format,
            "mime_type": self.mime_type,
            "byte_count": self.byte_count,
        }


def deepgram_transcribe_file(
    audio_path: Path,
    *,
    api_key: str | None = None,
    api_key_env: str = "DEEPGRAM_API_KEY",
    base_url: str | None = None,
    model: str = "",
    language: str = "",
    smart_format: bool = True,
    mime_type: str = "",
    timeout_seconds: float = 60.0,
) -> SpeechTranscription:
    key = api_key or os.environ.get(api_key_env)
    if not key:
        raise SpeechProviderError(f"{api_key_env} is required for Deepgram speech-to-text.")
    resolved = audio_path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise SpeechProviderError(f"Audio file does not exist: {resolved}")
    size = resolved.stat().st_size
    if size <= 0:
        raise SpeechProviderError("Audio file is empty.")
    if size > VOICE_AUDIO_MAX_BYTES:
        raise SpeechProviderError(f"Audio file exceeds the {VOICE_AUDIO_MAX_BYTES} byte speech limit.")

    query: dict[str, str] = {}
    if model:
        query["model"] = model
    if language:
        query["language"] = language
    if smart_format:
        query["smart_format"] = "true"
    url = f"{(base_url or os.environ.get('DEEPGRAM_BASE_URL') or DEEPGRAM_BASE_URL).rstrip('/')}/v1/listen"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    detected_mime = mime_type or mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
    request = urllib.request.Request(
        url,
        data=resolved.read_bytes(),
        headers={
            "Authorization": f"Token {key}",
            "Content-Type": detected_mime,
            "User-Agent": VOICE_PROVIDER_USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SpeechProviderError(f"Deepgram STT failed: HTTP {exc.code}: {_provider_error(detail)}") from exc
    except (urllib.error.URLError, http.client.HTTPException, json.JSONDecodeError) as exc:
        raise SpeechProviderError(f"Deepgram STT request failed: {exc}") from exc

    transcript, confidence = _deepgram_transcript(payload)
    return SpeechTranscription(
        provider="deepgram",
        transcript=transcript,
        confidence=confidence,
        language=language,
        model=model,
        raw_shape=_shape(payload),
    )


def local_whisper_status() -> dict[str, Any]:
    model_path = _local_whisper_model_path()
    return {
        "configured": model_path.exists(),
        "provider": "faster_whisper",
        "model": os.environ.get("HUMUNGOUSAUR_LOCAL_WHISPER_MODEL") or os.environ.get("LOCAL_WHISPER_MODEL") or "tiny.en",
        "model_path": str(model_path) if model_path.exists() else "",
        "device": os.environ.get("HUMUNGOUSAUR_LOCAL_WHISPER_DEVICE") or os.environ.get("LOCAL_WHISPER_DEVICE") or "cpu",
        "compute_type": os.environ.get("HUMUNGOUSAUR_LOCAL_WHISPER_COMPUTE_TYPE") or os.environ.get("LOCAL_WHISPER_COMPUTE_TYPE") or "int8",
    }


def local_whisper_transcribe_file(
    audio_path: Path,
    *,
    model: str = "",
    language: str = "",
    timeout_seconds: float = 120.0,
) -> SpeechTranscription:
    del timeout_seconds
    resolved = audio_path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise SpeechProviderError(f"Audio file does not exist: {resolved}")
    if resolved.stat().st_size <= 0:
        raise SpeechProviderError("Audio file is empty.")
    model_name = model or os.environ.get("HUMUNGOUSAUR_LOCAL_WHISPER_MODEL") or os.environ.get("LOCAL_WHISPER_MODEL") or "tiny.en"
    model_path = _local_whisper_model_path(model_name)
    if not model_path.exists():
        raise SpeechProviderError(
            "Local Whisper model is not available. "
            "Set HUMUNGOUSAUR_LOCAL_WHISPER_MODEL_DIR or run the voice-wakeup bootstrap once."
        )
    whisper_model_class = _faster_whisper_model_class()
    device = os.environ.get("HUMUNGOUSAUR_LOCAL_WHISPER_DEVICE") or os.environ.get("LOCAL_WHISPER_DEVICE") or "cpu"
    compute_type = os.environ.get("HUMUNGOUSAUR_LOCAL_WHISPER_COMPUTE_TYPE") or os.environ.get("LOCAL_WHISPER_COMPUTE_TYPE") or "int8"
    try:
        whisper_model = whisper_model_class(str(model_path), device=device, compute_type=compute_type)
        segments, info = whisper_model.transcribe(
            str(resolved),
            language=language or None,
            vad_filter=True,
            beam_size=1,
        )
        text_parts = [segment.text.strip() for segment in segments if getattr(segment, "text", "").strip()]
    except Exception as exc:
        raise SpeechProviderError(f"Local Whisper STT failed: {exc}") from exc
    transcript = " ".join(text_parts).strip()
    confidence = getattr(info, "language_probability", None)
    try:
        parsed_confidence = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        parsed_confidence = None
    detected_language = language or str(getattr(info, "language", "") or "")
    return SpeechTranscription(
        provider="local-whisper",
        transcript=transcript,
        confidence=parsed_confidence,
        language=detected_language,
        model=model_name,
        raw_shape={"type": "faster_whisper", "model_path": str(model_path), "device": device, "compute_type": compute_type},
    )


def elevenlabs_synthesize_to_file(
    text: str,
    output_dir: Path,
    *,
    response_id: str,
    api_key: str | None = None,
    api_key_env: str = "ELEVENLABS_API_KEY",
    base_url: str | None = None,
    voice_id: str = "",
    model: str = "",
    output_format: str = "",
    allow_voice_lookup: bool = False,
    timeout_seconds: float = 60.0,
) -> SpeechSynthesis:
    key = api_key or _elevenlabs_api_key(api_key_env)
    if not key:
        raise SpeechProviderError(f"{api_key_env} is required for ElevenLabs text-to-speech.")
    resolved_voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID", "")
    resolved_base_url = (base_url or os.environ.get("ELEVENLABS_BASE_URL") or ELEVENLABS_BASE_URL).rstrip("/")
    if not resolved_voice_id and allow_voice_lookup:
        resolved_voice_id = elevenlabs_first_voice_id(
            api_key=key,
            base_url=resolved_base_url,
            timeout_seconds=timeout_seconds,
        )
    if not resolved_voice_id:
        raise SpeechProviderError("ElevenLabs voice_id is required. Set ELEVENLABS_VOICE_ID or pass allow_voice_lookup=true.")

    resolved_model = model or os.environ.get("ELEVENLABS_MODEL_ID", "")
    resolved_output_format = output_format or os.environ.get("ELEVENLABS_OUTPUT_FORMAT", "")
    query = {"output_format": resolved_output_format} if resolved_output_format else {}
    url = f"{resolved_base_url}/v1/text-to-speech/{urllib.parse.quote(resolved_voice_id, safe='')}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    payload: dict[str, Any] = {"text": text}
    if resolved_model:
        payload["model_id"] = resolved_model
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "xi-api-key": key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
            "User-Agent": VOICE_PROVIDER_USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            audio = response.read(ELEVENLABS_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SpeechProviderError(f"ElevenLabs TTS failed: HTTP {exc.code}: {_provider_error(detail)}") from exc
    except (urllib.error.URLError, http.client.HTTPException) as exc:
        raise SpeechProviderError(f"ElevenLabs TTS request failed: {exc}") from exc
    if len(audio) > ELEVENLABS_RESPONSE_BYTES:
        raise SpeechProviderError("ElevenLabs TTS response exceeded the local safety limit.")
    if not audio:
        raise SpeechProviderError("ElevenLabs TTS returned an empty audio response.")

    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = output_dir / f"{_safe_file_stem(response_id)}.{_audio_extension(resolved_output_format)}"
    audio_path.write_bytes(audio)
    return SpeechSynthesis(
        provider="elevenlabs",
        audio_path=audio_path,
        voice_id=resolved_voice_id,
        model=resolved_model,
        output_format=resolved_output_format,
        mime_type=_mime_type_for_output(resolved_output_format),
        byte_count=len(audio),
    )


def windows_sapi_synthesize_to_file(
    text: str,
    output_dir: Path,
    *,
    response_id: str,
    rate: int = 0,
    volume: int = 100,
    timeout_seconds: float = 60.0,
) -> SpeechSynthesis:
    if platform.system().lower() != "windows":
        raise SpeechProviderError("Windows SAPI synthesis is available on Windows only.")
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = output_dir / f"{_safe_file_stem(response_id)}.wav"
    result = _run_powershell_audio(
        _windows_sapi_wave_script(text=text, path=audio_path, rate=max(-10, min(rate, 10)), volume=max(0, min(volume, 100))),
        timeout_seconds=timeout_seconds,
    )
    if result.get("status") != "ok":
        raise SpeechProviderError(result.get("error") or "Windows SAPI synthesis failed.")
    if not audio_path.exists() or audio_path.stat().st_size <= 0:
        raise SpeechProviderError("Windows SAPI synthesis produced no audio file.")
    return SpeechSynthesis(
        provider="windows_sapi",
        audio_path=audio_path,
        voice_id="windows_sapi",
        model="windows_sapi",
        output_format="wav",
        mime_type="audio/wav",
        byte_count=audio_path.stat().st_size,
    )


def elevenlabs_first_voice_id(
    *,
    api_key: str,
    base_url: str | None = None,
    timeout_seconds: float = 30.0,
) -> str:
    request = urllib.request.Request(
        f"{(base_url or ELEVENLABS_BASE_URL).rstrip('/')}/v1/voices",
        headers={
            "xi-api-key": api_key,
            "User-Agent": VOICE_PROVIDER_USER_AGENT,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SpeechProviderError(f"ElevenLabs voice lookup failed: HTTP {exc.code}: {_provider_error(detail)}") from exc
    except (urllib.error.URLError, http.client.HTTPException, json.JSONDecodeError) as exc:
        raise SpeechProviderError(f"ElevenLabs voice lookup failed: {exc}") from exc
    voices = payload.get("voices") if isinstance(payload, dict) else None
    if not isinstance(voices, list):
        raise SpeechProviderError("ElevenLabs voice lookup returned no voices array.")
    for voice in voices:
        if isinstance(voice, dict) and str(voice.get("voice_id") or "").strip():
            return str(voice["voice_id"]).strip()
    raise SpeechProviderError("ElevenLabs account returned no usable voices.")


def _elevenlabs_api_key(primary_env: str) -> str | None:
    return (
        os.environ.get(primary_env)
        or os.environ.get("ELEVEN_LABS_API_KEY")
        or os.environ.get("ELEVAN_LABS_API_KEY")
        or os.environ.get("ELEVANLABS_API_KEY")
    )


def _local_whisper_model_path(model: str | None = None) -> Path:
    configured = os.environ.get("HUMUNGOUSAUR_LOCAL_WHISPER_MODEL_DIR") or os.environ.get("LOCAL_WHISPER_MODEL_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    model_name = model or os.environ.get("HUMUNGOUSAUR_LOCAL_WHISPER_MODEL") or os.environ.get("LOCAL_WHISPER_MODEL") or "tiny.en"
    repo_dir = f"Systran--faster-whisper-{model_name}"
    return (Path.home() / "Desktop" / "Umang" / "voice-wakeup" / "artifacts" / "models" / repo_dir).resolve()


def _faster_whisper_model_class():
    try:
        from faster_whisper import WhisperModel

        return WhisperModel
    except ImportError:
        site_packages = Path.home() / "Desktop" / "Umang" / "voice-wakeup" / ".venv" / "Lib" / "site-packages"
        if site_packages.exists():
            sys.path.append(str(site_packages))
        try:
            from faster_whisper import WhisperModel

            return WhisperModel
        except ImportError as exc:
            raise SpeechProviderError(
                "faster-whisper is not installed in this environment and the voice-wakeup venv was not usable."
            ) from exc


def play_audio_file(path: Path, *, timeout_seconds: float = 60.0) -> dict[str, str]:
    resolved = path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        return {"status": "failed", "error": f"Audio file does not exist: {resolved}"}
    if platform.system().lower() != "windows":
        return {"status": "failed", "error": "Audio playback is currently implemented for Windows only."}
    return _run_powershell_audio(_windows_media_play_script(resolved), timeout_seconds=timeout_seconds)


def _deepgram_transcript(payload: Any) -> tuple[str, float | None]:
    if not isinstance(payload, dict):
        return "", None
    channels = payload.get("results", {}).get("channels", [])
    if not isinstance(channels, list) or not channels:
        return "", None
    alternatives = channels[0].get("alternatives", []) if isinstance(channels[0], dict) else []
    if not isinstance(alternatives, list) or not alternatives:
        return "", None
    first = alternatives[0]
    if not isinstance(first, dict):
        return "", None
    transcript = str(first.get("transcript") or "").strip()
    confidence = first.get("confidence")
    try:
        parsed_confidence = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        parsed_confidence = None
    return transcript, parsed_confidence


def _provider_error(detail: str) -> str:
    try:
        payload = json.loads(detail)
    except json.JSONDecodeError:
        return detail[:500]
    if isinstance(payload, dict):
        error = payload.get("error") or payload.get("err_msg") or payload.get("message")
        if isinstance(error, dict):
            return "; ".join(f"{key}={str(value)[:240]}" for key, value in error.items())[:500]
        if error:
            return str(error)[:500]
    return detail[:500]


def _json_provider_detail(detail: str) -> Any:
    try:
        return json.loads(detail)
    except json.JSONDecodeError:
        return detail[:500]


def _shape(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return {"type": "object", "keys": sorted(str(key) for key in payload.keys())[:20]}
    if isinstance(payload, list):
        return {"type": "array", "length": len(payload)}
    return {"type": type(payload).__name__}


def _audio_extension(output_format: str) -> str:
    value = output_format.strip().lower()
    if "wav" in value:
        return "wav"
    if "pcm" in value:
        return "pcm"
    if "ulaw" in value:
        return "ulaw"
    return "mp3"


def _mime_type_for_output(output_format: str) -> str:
    extension = _audio_extension(output_format)
    if extension == "wav":
        return "audio/wav"
    if extension == "pcm":
        return "audio/L16"
    if extension == "ulaw":
        return "audio/basic"
    return "audio/mpeg"


def _safe_file_stem(value: str) -> str:
    safe = "".join(char for char in value if char.isalnum() or char in {"-", "_"})
    return safe or "voice-response"


def _run_powershell_audio(script: str, *, timeout_seconds: float) -> dict[str, str]:
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                encoded,
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
    if completed.returncode != 0:
        return {"status": "failed", "error": (completed.stderr or completed.stdout or "PowerShell audio playback failed.").strip()}
    return {"status": "ok", "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}


def _windows_media_play_script(path: Path) -> str:
    return f"""
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName PresentationCore
$player = New-Object System.Windows.Media.MediaPlayer
$done = $false
$player.add_MediaEnded({{ $script:done = $true }})
$player.add_MediaFailed({{ throw "Media playback failed." }})
$player.Open([Uri]{json.dumps(str(path))})
while (-not $player.NaturalDuration.HasTimeSpan) {{ Start-Sleep -Milliseconds 50 }}
$player.Play()
$deadline = (Get-Date).AddSeconds(60)
while (-not $done -and (Get-Date) -lt $deadline) {{ Start-Sleep -Milliseconds 100 }}
$player.Close()
if (-not $done) {{ throw "Media playback timed out." }}
"""


def _windows_sapi_wave_script(text: str, path: Path, rate: int, volume: int) -> str:
    encoded_path = base64.b64encode(str(path).encode("utf-8")).decode("ascii")
    encoded_text = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"""
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = {rate}
$synth.Volume = {volume}
$wavePath = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String({json.dumps(encoded_path)}))
$speakText = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String({json.dumps(encoded_text)}))
$synth.SetOutputToWaveFile($wavePath)
$synth.Speak($speakText)
$synth.Dispose()
"""
