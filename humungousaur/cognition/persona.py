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
            updated_at=str(payload.get("updated_at", utc_now())),
        )

    def save(self, profile: PersonaProfile) -> PersonaProfile:
        profile.updated_at = utc_now()
        self.path.write_text(json.dumps(asdict(profile), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return profile

    def add_preference(self, text: str) -> PersonaProfile:
        profile = self.load()
        item = _clean_text(text)
        if item and item not in profile.user_preferences:
            profile.user_preferences.append(item)
        return self.save(profile)

    def add_fact(self, text: str) -> PersonaProfile:
        profile = self.load()
        item = _clean_text(text)
        if item and item not in profile.stable_facts:
            profile.stable_facts.append(item)
        return self.save(profile)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean_text(item) for item in value if _clean_text(item)]


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())[:500]
