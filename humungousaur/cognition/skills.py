from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .models import SkillLifecycleStatus, SkillRecord, new_id, utc_now


class SkillStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list(self, limit: int = 20, *, include_retired: bool = False) -> list[SkillRecord]:
        skills = self._load_all()
        if not include_retired:
            skills = [skill for skill in skills if skill.status == SkillLifecycleStatus.ACTIVE]
        skills.sort(key=lambda item: (item.confidence, item.usage_count, item.updated_at), reverse=True)
        return skills[: max(1, min(limit, 200))]

    def get(self, skill_id: str) -> SkillRecord | None:
        cleaned_id = str(skill_id or "").strip()
        if not cleaned_id:
            return None
        return next((skill for skill in self._load_all() if skill.skill_id == cleaned_id), None)

    def upsert(
        self,
        name: str,
        purpose: str,
        when_to_use: str,
        tools: list[str] | None = None,
        verification_steps: list[str] | None = None,
        failure_modes: list[str] | None = None,
        evidence_refs: list[str] | None = None,
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
        existing.evidence_refs = _merge_strings(existing.evidence_refs, _string_list(evidence_refs)) if evidence_refs is not None else existing.evidence_refs
        existing.confidence = max(0.0, min(float(confidence), 1.0))
        existing.status = SkillLifecycleStatus.ACTIVE
        existing.retired_at = ""
        existing.retirement_reason = ""
        existing.updated_at = utc_now()
        self._save_all(skills)
        return existing

    def update_exact(
        self,
        skill_id: str,
        *,
        name: str | None = None,
        purpose: str | None = None,
        when_to_use: str | None = None,
        tools: list[str] | None = None,
        verification_steps: list[str] | None = None,
        failure_modes: list[str] | None = None,
        evidence_refs: list[str] | None = None,
        confidence: float | None = None,
    ) -> SkillRecord | None:
        cleaned_id = str(skill_id or "").strip()
        if not cleaned_id:
            return None
        skills = self._load_all()
        updated: SkillRecord | None = None
        for skill in skills:
            if skill.skill_id != cleaned_id or skill.status != SkillLifecycleStatus.ACTIVE:
                continue
            skill.name = _clean(name) or skill.name if name is not None else skill.name
            skill.purpose = _clean(purpose) or skill.purpose if purpose is not None else skill.purpose
            skill.when_to_use = _clean(when_to_use) or skill.when_to_use if when_to_use is not None else skill.when_to_use
            skill.tools = _string_list(tools) if tools is not None else skill.tools
            skill.verification_steps = _string_list(verification_steps) if verification_steps is not None else skill.verification_steps
            skill.failure_modes = _string_list(failure_modes) if failure_modes is not None else skill.failure_modes
            skill.evidence_refs = _merge_strings(skill.evidence_refs, _string_list(evidence_refs)) if evidence_refs is not None else skill.evidence_refs
            if confidence is not None:
                skill.confidence = max(0.0, min(float(confidence), 1.0))
            skill.updated_at = utc_now()
            updated = skill
            break
        if updated is not None:
            self._save_all(skills)
        return updated

    def retire(self, skill_id: str, reason: str = "", evidence_refs: list[str] | None = None) -> SkillRecord | None:
        cleaned_id = str(skill_id or "").strip()
        if not cleaned_id:
            return None
        skills = self._load_all()
        retired: SkillRecord | None = None
        for skill in skills:
            if skill.skill_id != cleaned_id or skill.status != SkillLifecycleStatus.ACTIVE:
                continue
            skill.status = SkillLifecycleStatus.RETIRED
            skill.retired_at = utc_now()
            skill.retirement_reason = _clean(reason)
            skill.evidence_refs = _merge_strings(skill.evidence_refs, _string_list(evidence_refs))
            skill.updated_at = skill.retired_at
            retired = skill
            break
        if retired is not None:
            self._save_all(skills)
        return retired

    def mark_used(self, skill_id: str) -> bool:
        skills = self._load_all()
        matched = False
        for skill in skills:
            if skill.skill_id == skill_id and skill.status == SkillLifecycleStatus.ACTIVE:
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
                    evidence_refs=_string_list(item.get("evidence_refs")),
                    usage_count=max(0, int(item.get("usage_count") or 0)),
                    confidence=max(0.0, min(float(item.get("confidence") or 0.5), 1.0)),
                    status=_skill_status(item.get("status")),
                    retired_at=str(item.get("retired_at") or ""),
                    retirement_reason=str(item.get("retirement_reason") or ""),
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


def _merge_strings(existing: list[str], incoming: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for item in [*existing, *incoming]:
        cleaned = _clean(item)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            merged.append(cleaned)
    return merged[:50]


def _skill_status(value: object) -> SkillLifecycleStatus:
    try:
        return SkillLifecycleStatus(str(value or SkillLifecycleStatus.ACTIVE.value))
    except ValueError:
        return SkillLifecycleStatus.ACTIVE
