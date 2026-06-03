from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .models import SpecialistRecord, new_id, utc_now


class SpecialistStore:
    """Durable specialist contracts.

    This store never selects specialists from user language. It only persists
    contracts that model-led planning or explicit tool calls may reference by
    name in task graphs.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list(self, limit: int = 20) -> list[SpecialistRecord]:
        records = self._load_all()
        records.sort(key=lambda item: (item.confidence, item.usage_count, item.updated_at), reverse=True)
        return records[: max(1, min(limit, 200))]

    def get_by_name(self, name: str) -> SpecialistRecord | None:
        normalized = _normalize_name(name)
        for record in self._load_all():
            if _normalize_name(record.name) == normalized or _normalize_name(record.specialist_id) == normalized:
                return record
        return None

    def upsert(
        self,
        name: str,
        purpose: str,
        contract: str,
        tools: list[str] | None = None,
        success_criteria: list[str] | None = None,
        permission_notes: list[str] | None = None,
        confidence: float = 0.5,
    ) -> SpecialistRecord:
        records = self._load_all()
        normalized = _normalize_name(name)
        existing = next((item for item in records if _normalize_name(item.name) == normalized), None)
        if existing is None:
            existing = SpecialistRecord(
                specialist_id=new_id("specialist"),
                name=_clean(name) or "Unnamed specialist",
                purpose=_clean(purpose),
                contract=_clean(contract),
            )
            records.append(existing)
        existing.purpose = _clean(purpose) or existing.purpose
        existing.contract = _clean(contract) or existing.contract
        existing.tools = _string_list(tools) if tools is not None else existing.tools
        existing.success_criteria = _string_list(success_criteria) if success_criteria is not None else existing.success_criteria
        existing.permission_notes = _string_list(permission_notes) if permission_notes is not None else existing.permission_notes
        existing.confidence = max(0.0, min(float(confidence), 1.0))
        existing.updated_at = utc_now()
        self._save_all(records)
        return existing

    def mark_used(self, name: str) -> bool:
        records = self._load_all()
        normalized = _normalize_name(name)
        matched = False
        for record in records:
            if _normalize_name(record.name) == normalized or _normalize_name(record.specialist_id) == normalized:
                record.usage_count += 1
                record.last_used_at = utc_now()
                record.updated_at = record.last_used_at
                matched = True
        if matched:
            self._save_all(records)
        return matched

    def _load_all(self) -> list[SpecialistRecord]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        raw_items = payload.get("specialists") if isinstance(payload, dict) else None
        if not isinstance(raw_items, list):
            return []
        records: list[SpecialistRecord] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            records.append(
                SpecialistRecord(
                    specialist_id=str(item.get("specialist_id") or new_id("specialist")),
                    name=str(item.get("name") or "Unnamed specialist"),
                    purpose=str(item.get("purpose") or ""),
                    contract=str(item.get("contract") or ""),
                    tools=_string_list(item.get("tools")),
                    success_criteria=_string_list(item.get("success_criteria")),
                    permission_notes=_string_list(item.get("permission_notes")),
                    confidence=max(0.0, min(float(item.get("confidence") or 0.5), 1.0)),
                    usage_count=max(0, int(item.get("usage_count") or 0)),
                    last_used_at=str(item.get("last_used_at") or ""),
                    updated_at=str(item.get("updated_at") or utc_now()),
                )
            )
        return records

    def _save_all(self, records: list[SpecialistRecord]) -> None:
        payload = {"specialists": [asdict(record) for record in records], "updated_at": utc_now()}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _normalize_name(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())[:1_500]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean(item) for item in value if _clean(item)]
