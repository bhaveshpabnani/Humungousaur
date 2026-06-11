from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile


CREDENTIAL_ACTIVITY_STIMULUS_TYPES = {
    "password_manager_opened",
    "credential_selected",
    "credential_copied",
    "credential_filled",
    "credential_save_prompt_shown",
    "credential_update_prompt_shown",
    "credential_fill_failed",
}
PASSKEY_ACTIVITY_STIMULUS_TYPES = {
    "passkey_prompt_shown",
    "passkey_created",
    "passkey_used",
    "passkey_failed",
    "biometric_auth_requested",
    "security_key_requested",
}
AUTOFILL_ACTIVITY_STIMULUS_TYPES = {
    "autofill_suggestion_shown",
    "autofill_suggestion_accepted",
    "autofill_suggestion_dismissed",
    "payment_autofill_prompt_shown",
    "address_autofill_prompt_shown",
    "form_autofill_failed",
}
VERIFICATION_CODE_ACTIVITY_STIMULUS_TYPES = {
    "otp_code_detected",
    "otp_autofill_suggested",
    "otp_autofill_accepted",
    "verification_code_prompt_shown",
    "verification_code_failed",
    "backup_code_prompt_shown",
}


def collect_credential_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "credential_activity", CREDENTIAL_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)


def collect_passkey_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "passkey_activity", PASSKEY_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)


def collect_autofill_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "autofill_activity", AUTOFILL_ACTIVITY_STIMULUS_TYPES, source="browser", max_events=20)


def collect_verification_code_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "verification_code_activity", VERIFICATION_CODE_ACTIVITY_STIMULUS_TYPES, source="system", max_events=20)
