from __future__ import annotations

from typing import Any


def signature_seen(signatures: dict[str, Any], stimulus_type: str, signature: str) -> bool:
    previous = signatures.get(stimulus_type)
    if isinstance(previous, list):
        return signature in previous
    return previous == signature


def remember_signature(signatures: dict[str, Any], stimulus_type: str, signature: str) -> None:
    previous = signatures.get(stimulus_type)
    if isinstance(previous, list):
        next_values = [item for item in previous if isinstance(item, str)]
    elif isinstance(previous, str) and previous:
        next_values = [previous]
    else:
        next_values = []
    if signature not in next_values:
        next_values.append(signature)
    signatures[stimulus_type] = next_values[-256:]
