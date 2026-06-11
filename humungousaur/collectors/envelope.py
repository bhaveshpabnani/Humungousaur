from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import platform
from typing import Any

from .definitions import SENSITIVE_COLLECTORS
from .models import CollectorEvent


COLLECTOR_EVENT_SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class CollectorEventEnvelope:
    event_id: str
    collector: str
    source: str
    stimulus_type: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    redaction: dict[str, Any] = field(default_factory=dict)
    occurred_at: str = field(default_factory=utc_now)
    received_at: str = field(default_factory=utc_now)
    platform: str = field(default_factory=platform.system)
    privacy_tier: str = "metadata"
    signature: str = ""
    schema_version: int = COLLECTOR_EVENT_SCHEMA_VERSION

    @classmethod
    def from_collector_event(cls, event: CollectorEvent) -> "CollectorEventEnvelope":
        signature = event.stable_signature()
        event_id_digest = _stable_signature(
            {
                "signature": signature,
                "collector": event.collector,
                "source": event.source,
                "stimulus_type": event.stimulus_type,
                "occurred_at": event.occurred_at,
                "text": event.text,
                "metadata": event.metadata,
                "payload": event.payload,
            }
        )[:24]
        collector_platform = str(event.metadata.get("platform") or platform.system())
        privacy_tier = str(event.metadata.get("privacy_tier") or _privacy_tier_for_collector(event.collector))
        return cls(
            event_id=f"collector-{event.collector}-{event_id_digest}",
            collector=event.collector,
            source=event.source,
            stimulus_type=event.stimulus_type,
            text=event.text,
            metadata=_json_safe(event.metadata),
            payload=_json_safe(event.payload),
            redaction=_default_redaction(event, privacy_tier),
            occurred_at=event.occurred_at,
            platform=collector_platform,
            privacy_tier=privacy_tier,
            signature=signature,
        )

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CollectorEventEnvelope":
        metadata = payload.get("metadata", {})
        raw_payload = payload.get("payload", {})
        redaction = payload.get("redaction", {})
        signature = str(payload.get("signature") or "").strip()
        if not signature:
            signature = _stable_signature(
                {
                    "collector": payload.get("collector"),
                    "source": payload.get("source"),
                    "stimulus_type": payload.get("stimulus_type"),
                    "text": payload.get("text"),
                    "metadata": metadata,
                    "payload": raw_payload,
                }
            )
        collector = _required_text(payload, "collector")
        source = _required_text(payload, "source")
        stimulus_type = _required_text(payload, "stimulus_type")
        event_id_digest = _stable_signature(
            {
                "signature": signature,
                "collector": collector,
                "source": source,
                "stimulus_type": stimulus_type,
                "occurred_at": payload.get("occurred_at"),
                "text": payload.get("text"),
                "metadata": metadata,
                "payload": raw_payload,
            }
        )[:24]
        return cls(
            event_id=str(payload.get("event_id") or f"collector-{collector}-{event_id_digest}"),
            collector=collector,
            source=source,
            stimulus_type=stimulus_type,
            text=str(payload.get("text") or ""),
            metadata=metadata if isinstance(metadata, dict) else {},
            payload=raw_payload if isinstance(raw_payload, dict) else {},
            redaction=redaction if isinstance(redaction, dict) else {},
            occurred_at=str(payload.get("occurred_at") or utc_now()),
            received_at=str(payload.get("received_at") or utc_now()),
            platform=str(payload.get("platform") or platform.system()),
            privacy_tier=str(payload.get("privacy_tier") or _privacy_tier_for_collector(collector)),
            signature=signature,
            schema_version=int(payload.get("schema_version") or COLLECTOR_EVENT_SCHEMA_VERSION),
        )

    def to_collector_event(self) -> CollectorEvent:
        return CollectorEvent(
            collector=self.collector,
            source=self.source,
            stimulus_type=self.stimulus_type,
            text=self.text,
            metadata={**self.metadata, "platform": self.platform, "privacy_tier": self.privacy_tier},
            payload=self.payload,
            occurred_at=self.occurred_at,
            signature=self.signature,
        )

    def to_memory_payload(self) -> dict[str, Any]:
        return {
            "collector": self.collector,
            "source": self.source,
            "stimulus_type": self.stimulus_type,
            "text": self.text,
            "metadata": self.metadata,
            "payload": self.payload,
            "occurred_at": self.occurred_at,
            "signature": self.signature,
            "event_id": self.event_id,
            "schema_version": self.schema_version,
            "platform": self.platform,
            "privacy_tier": self.privacy_tier,
            "redaction": self.redaction,
        }

    def to_record(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "schema_version": self.schema_version,
            "collector": self.collector,
            "source": self.source,
            "platform": self.platform,
            "stimulus_type": self.stimulus_type,
            "privacy_tier": self.privacy_tier,
            "occurred_at": self.occurred_at,
            "received_at": self.received_at,
            "signature": self.signature,
            "text": self.text,
            "metadata": self.metadata,
            "payload": self.payload,
            "redaction": self.redaction,
        }


def _privacy_tier_for_collector(collector: str) -> str:
    return "sensitive_metadata" if collector in SENSITIVE_COLLECTORS else "metadata"


def _default_redaction(event: CollectorEvent, privacy_tier: str) -> dict[str, Any]:
    raw_content_included = bool(event.metadata.get("raw_content_included", False))
    return {
        "privacy_tier": privacy_tier,
        "raw_content_included": raw_content_included,
        "attention_safe": not raw_content_included,
        "paths_redacted": bool(event.metadata.get("paths_redacted", event.collector != "filesystem")),
        "payload_compacted_before_llm": True,
    }


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"Collector event envelope missing {key}")
    return value


def _stable_signature(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    return value
