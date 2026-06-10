from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from .definitions import DEFAULT_COLLECTOR_RATE_LIMITS_PER_MINUTE, DEFAULT_COLLECTORS, DEFAULT_RICH_CAPTURE_OPT_IN


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class CollectorProfile:
    enabled: bool = False
    privacy_mode: str = "privacy_first"
    poll_seconds: float = 5.0
    response_mode: str = "silent"
    submit_to_harness: bool = True
    run_autonomous_cycle: bool = False
    max_events_per_tick: int = 8
    collectors: dict[str, bool] = field(default_factory=lambda: dict(DEFAULT_COLLECTORS))
    rich_capture_opt_in: dict[str, bool] = field(default_factory=lambda: dict(DEFAULT_RICH_CAPTURE_OPT_IN))
    collector_rate_limits_per_minute: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_COLLECTOR_RATE_LIMITS_PER_MINUTE))
    watch_paths: list[str] = field(default_factory=list)
    max_file_events: int = 5
    max_text_chars: int = 2000
    dwell_seconds: float = 8.0
    batch_seconds: float = 20.0
    llm_attention_interval_seconds: float = 60.0
    screenshot_min_interval_seconds: float = 60.0
    ocr_min_interval_seconds: float = 90.0
    video_frame_min_interval_seconds: float = 120.0
    audio_sample_seconds: float = 1.5
    audio_rms_threshold: float = 0.02
    note: str = ""
    updated_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class CollectorEvent:
    collector: str
    source: str
    stimulus_type: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    occurred_at: str = field(default_factory=utc_now)
    signature: str = ""

    def stable_signature(self) -> str:
        if self.signature:
            return self.signature
        body = json.dumps(
            {
                "collector": self.collector,
                "source": self.source,
                "stimulus_type": self.stimulus_type,
                "text": self.text,
                "metadata": self.metadata,
                "payload": self.payload,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def stimulus(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "source": self.source,
            "metadata": {
                **self.metadata,
                "collector": self.collector,
                "stimulus_type": self.stimulus_type,
                "payload": self.payload,
            },
            "stimulus_id": f"collector-{self.collector}-{self.stable_signature()[:12]}",
            "occurred_at": self.occurred_at,
        }


@dataclass(slots=True)
class CollectorTickResult:
    profile: dict[str, Any]
    collected: list[dict[str, Any]]
    submitted: list[dict[str, Any]]
    skipped: list[dict[str, Any]]
    attention_batches: list[dict[str, Any]] = field(default_factory=list)
    semantic_events: list[dict[str, Any]] = field(default_factory=list)
    action_candidates: list[dict[str, Any]] = field(default_factory=list)
    current_context: dict[str, Any] | None = None
    loop: dict[str, Any] | None = None
    started_at: str = field(default_factory=utc_now)
    finished_at: str = ""
    duration_ms: float = 0.0
