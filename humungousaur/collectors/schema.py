from __future__ import annotations

from typing import Any

from .definitions import DEFINITIONS_BY_NAME


ALLOWED_PRIVACY_TIERS = {"metadata", "sensitive_metadata", "rich_capture", "blocked"}
ALLOWED_PLATFORMS = {"macos", "windows", "linux", "darwin", "Darwin", "Windows", "Linux"}
REQUIRED_ENVELOPE_FIELDS = {
    "event_id",
    "schema_version",
    "collector",
    "source",
    "platform",
    "stimulus_type",
    "privacy_tier",
    "occurred_at",
    "signature",
    "text",
    "metadata",
    "payload",
    "redaction",
}


def validate_envelope_record(payload: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_ENVELOPE_FIELDS.difference(payload))
    if missing:
        raise ValueError(f"collector event envelope missing fields: {', '.join(missing)}")
    if int(payload.get("schema_version") or 0) != 1:
        raise ValueError("collector event envelope schema_version must be 1")
    collector = _required_string(payload, "collector")
    definition = DEFINITIONS_BY_NAME.get(collector)
    if definition is None:
        raise ValueError(f"unknown collector in envelope: {collector}")
    stimulus_type = _required_string(payload, "stimulus_type")
    if stimulus_type not in definition.stimulus_types:
        raise ValueError(f"unsupported stimulus_type for {collector}: {stimulus_type}")
    if str(payload.get("privacy_tier") or "") not in ALLOWED_PRIVACY_TIERS:
        raise ValueError("collector event envelope privacy_tier is not allowed")
    if str(payload.get("platform") or "") not in ALLOWED_PLATFORMS:
        raise ValueError("collector event envelope platform is not allowed")
    for key in ("event_id", "source", "occurred_at", "signature"):
        _required_string(payload, key)
    if not isinstance(payload.get("metadata"), dict):
        raise ValueError("collector event envelope metadata must be an object")
    if not isinstance(payload.get("payload"), dict):
        raise ValueError("collector event envelope payload must be an object")
    redaction = payload.get("redaction")
    if not isinstance(redaction, dict):
        raise ValueError("collector event envelope redaction must be an object")
    for key in ("raw_content_included", "attention_safe", "payload_compacted_before_llm"):
        if not isinstance(redaction.get(key), bool):
            raise ValueError(f"collector event envelope redaction.{key} must be boolean")


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"collector event envelope {key} must be non-empty")
    return value
