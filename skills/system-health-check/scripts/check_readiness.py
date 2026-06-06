# humungousaur-skill-script: {"name":"check-readiness","description":"Collect local readiness facts for workspace, data directory, skills, Python runtime, and redacted provider environment presence.","input_schema":{"type":"object","additionalProperties":true,"properties":{"env_names":{"type":"array","items":{"type":"string"},"description":"Optional environment variable names to check by presence only."}}}}
from __future__ import annotations

import json
import os
from pathlib import Path
import sys


DEFAULT_ENV_NAMES = [
    "OPENAI_API_KEY",
    "GROQ_API_KEY",
    "OLLAMA_HOST",
    "DEEPGRAM_API_KEY",
    "ELEVENLABS_API_KEY",
    "SLACK_BOT_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "DISCORD_BOT_TOKEN",
    "WHATSAPP_ACCESS_TOKEN",
]


def main() -> int:
    envelope = json.loads(sys.stdin.read() or "{}")
    workspace = Path(envelope.get("workspace", ".")).resolve()
    data_dir = Path(envelope.get("data_dir", workspace / "artifacts")).resolve()
    requested_env = envelope.get("input", {}).get("env_names") or DEFAULT_ENV_NAMES
    env_names = [str(name) for name in requested_env if str(name).strip()][:100]
    skills_dir = workspace / "skills"
    skill_count = len([item for item in skills_dir.iterdir() if item.is_dir()]) if skills_dir.exists() else 0
    payload = {
        "workspace": str(workspace),
        "workspace_exists": workspace.exists(),
        "data_dir": str(data_dir),
        "data_dir_exists": data_dir.exists(),
        "skills_dir_exists": skills_dir.exists(),
        "skill_directory_count": skill_count,
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "env_presence": {name: bool(os.environ.get(name)) for name in env_names},
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
