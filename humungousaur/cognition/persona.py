from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .models import PersonaProfile, utc_now


class PersonaStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> PersonaProfile:
        if not self.path.exists():
            return PersonaProfile()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return PersonaProfile()
        if not isinstance(payload, dict):
            return PersonaProfile()
        return PersonaProfile(
            assistant_name=str(payload.get("assistant_name", "Humungousaur")),
            identity=str(payload.get("identity", PersonaProfile().identity)),
            communication_style=str(payload.get("communication_style", PersonaProfile().communication_style)),
            boundaries=_string_list(payload.get("boundaries")) or PersonaProfile().boundaries,
            user_preferences=_string_list(payload.get("user_preferences")),
            stable_facts=_string_list(payload.get("stable_facts")),
            evidence_refs=_string_list(payload.get("evidence_refs")),
            updated_at=str(payload.get("updated_at", utc_now())),
        )

    def save(self, profile: PersonaProfile) -> PersonaProfile:
        profile.updated_at = utc_now()
        self.path.write_text(json.dumps(asdict(profile), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return profile

    def add_preference(self, text: str, evidence_refs: list[str] | None = None) -> PersonaProfile:
        profile = self.load()
        item = _clean_text(text)
        if item and item not in profile.user_preferences:
            profile.user_preferences.append(item)
        profile.evidence_refs = _merge_strings(profile.evidence_refs, _string_list(evidence_refs))
        return self.save(profile)

    def add_fact(self, text: str, evidence_refs: list[str] | None = None) -> PersonaProfile:
        profile = self.load()
        item = _clean_text(text)
        if item and item not in profile.stable_facts:
            profile.stable_facts.append(item)
        profile.evidence_refs = _merge_strings(profile.evidence_refs, _string_list(evidence_refs))
        return self.save(profile)

    def evolve(
        self,
        *,
        assistant_name: str = "",
        identity: str = "",
        communication_style: str = "",
        add_boundaries: list[str] | None = None,
        add_user_preferences: list[str] | None = None,
        add_stable_facts: list[str] | None = None,
        evidence_refs: list[str] | None = None,
    ) -> tuple[PersonaProfile, list[str], list[str], list[str], list[str]]:
        profile = self.load()
        changed_fields: list[str] = []
        name = _clean_text(assistant_name)
        if name and name != profile.assistant_name:
            profile.assistant_name = name[:120]
            changed_fields.append("assistant_name")
        next_identity = _clean_text(identity)
        if next_identity and next_identity != profile.identity:
            profile.identity = next_identity[:1_000]
            changed_fields.append("identity")
        next_style = _clean_text(communication_style)
        if next_style and next_style != profile.communication_style:
            profile.communication_style = next_style[:1_000]
            changed_fields.append("communication_style")
        added_boundaries = _append_unique(profile.boundaries, _string_list(add_boundaries), limit=30)
        added_preferences = _append_unique(profile.user_preferences, _string_list(add_user_preferences), limit=100)
        added_facts = _append_unique(profile.stable_facts, _string_list(add_stable_facts), limit=100)
        if added_boundaries:
            changed_fields.append("boundaries")
        if added_preferences:
            changed_fields.append("user_preferences")
        if added_facts:
            changed_fields.append("stable_facts")
        if changed_fields or added_boundaries or added_preferences or added_facts:
            profile.evidence_refs = _merge_strings(profile.evidence_refs, _string_list(evidence_refs))
            saved = self.save(profile)
            return saved, changed_fields, added_boundaries, added_preferences, added_facts
        return profile, changed_fields, added_boundaries, added_preferences, added_facts


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean_text(item) for item in value if _clean_text(item)]


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())[:500]


def _append_unique(existing: list[str], incoming: list[str], *, limit: int) -> list[str]:
    added: list[str] = []
    for item in incoming:
        cleaned = _clean_text(item)
        if len(existing) >= limit:
            break
        if cleaned and cleaned not in existing:
            existing.append(cleaned)
            added.append(cleaned)
    del existing[limit:]
    return added


def _merge_strings(existing: list[str], incoming: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for item in [*existing, *incoming]:
        cleaned = _clean_text(item)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            merged.append(cleaned)
    return merged[:100]
