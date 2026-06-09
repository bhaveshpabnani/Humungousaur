# humungousaur-skill-script: {"name":"redact-text","description":"Redact likely tokens, private keys, and credential assignments from supplied text while preserving surrounding context.","input_schema":{"type":"object","additionalProperties":false,"properties":{"text":{"type":"string"},"replacement":{"type":"string"}},"required":["text"]}}
from __future__ import annotations

import json
import re
import sys


PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
    re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*['\"]?[^'\"\s]+"),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
]


def main() -> int:
    envelope = json.loads(sys.stdin.read() or "{}")
    user_input = envelope.get("input", {})
    text = str(user_input.get("text") or "")
    replacement = str(user_input.get("replacement") or "[REDACTED]")
    redacted = text
    counts = []
    for pattern in PATTERNS:
        redacted, count = pattern.subn(replacement, redacted)
        counts.append(count)
    payload = {
        "redacted_text": redacted,
        "replacement": replacement,
        "total_replacements": sum(counts),
        "pattern_replacements": counts,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
