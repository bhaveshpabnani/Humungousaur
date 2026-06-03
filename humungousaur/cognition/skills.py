from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .models import SkillRecord, new_id, utc_now


class SkillStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list(self, limit: int = 20) -> list[SkillRecord]:
        skills = self._load_all()
        skills.sort(key=lambda item: (item.confidence, item.usage_count, item.updated_at), reverse=True)
        return skills[: max(1, min(limit, 200))]

    def upsert(
        self,
        name: str,
        purpose: str,
        when_to_use: str,
        tools: list[str] | None = None,
        verification_steps: list[str] | None = None,
        failure_modes: list[str] | None = None,
        confidence: float = 0.5,
    ) -> SkillRecord:
        skills = self._load_all()
        normalized = _normalize_name(name)
        existing = next((item for item in skills if _normalize_name(item.name) == normalized), None)
        if existing is None:
            existing = SkillRecord(
                skill_id=new_id("skill"),
                name=_clean(name) or "Unnamed skill",
                purpose=_clean(purpose),
                when_to_use=_clean(when_to_use),
            )
            skills.append(existing)
        existing.purpose = _clean(purpose) or existing.purpose
        existing.when_to_use = _clean(when_to_use) or existing.when_to_use
        existing.tools = _string_list(tools) if tools is not None else existing.tools
        existing.verification_steps = _string_list(verification_steps) if verification_steps is not None else existing.verification_steps
        existing.failure_modes = _string_list(failure_modes) if failure_modes is not None else existing.failure_modes
        existing.confidence = max(0.0, min(float(confidence), 1.0))
        existing.updated_at = utc_now()
        self._save_all(skills)
        return existing

    def mark_used(self, skill_id: str) -> bool:
        skills = self._load_all()
        matched = False
        for skill in skills:
            if skill.skill_id == skill_id:
                skill.usage_count += 1
                skill.last_used_at = utc_now()
                skill.updated_at = skill.last_used_at
                matched = True
        if matched:
            self._save_all(skills)
        return matched

    def _load_all(self) -> list[SkillRecord]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        raw_items = payload.get("skills") if isinstance(payload, dict) else None
        if not isinstance(raw_items, list):
            return []
        records: list[SkillRecord] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            records.append(
                SkillRecord(
                    skill_id=str(item.get("skill_id") or new_id("skill")),
                    name=str(item.get("name") or "Unnamed skill"),
                    purpose=str(item.get("purpose") or ""),
                    when_to_use=str(item.get("when_to_use") or ""),
                    tools=_string_list(item.get("tools")),
                    verification_steps=_string_list(item.get("verification_steps")),
                    failure_modes=_string_list(item.get("failure_modes")),
                    usage_count=max(0, int(item.get("usage_count") or 0)),
                    confidence=max(0.0, min(float(item.get("confidence") or 0.5), 1.0)),
                    last_used_at=str(item.get("last_used_at") or ""),
                    updated_at=str(item.get("updated_at") or utc_now()),
                )
            )
        return records

    def _save_all(self, skills: list[SkillRecord]) -> None:
        payload = {"skills": [asdict(skill) for skill in skills], "updated_at": utc_now()}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _normalize_name(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())[:1_000]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean(item) for item in value if _clean(item)]
