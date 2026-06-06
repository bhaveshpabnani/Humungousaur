# humungousaur-skill-script: {"name":"inspect-skill-pack","description":"Inspect one local skill pack for frontmatter, optional files, scripts, references, and native-boundary language.","input_schema":{"type":"object","additionalProperties":true,"properties":{"skill_dir":{"type":"string","description":"Skill directory path relative to workspace, for example skills/system-health-check."}}}}
from __future__ import annotations

import json
from pathlib import Path
import sys


BOUNDARY_TERMS = ["native", "humungousaur-owned", "do not import", "do not execute", "reference"]


def main() -> int:
    envelope = json.loads(sys.stdin.read() or "{}")
    workspace = Path(envelope.get("workspace", ".")).resolve()
    raw_dir = str(envelope.get("input", {}).get("skill_dir") or "skills")
    skill_dir = (workspace / raw_dir).resolve() if not Path(raw_dir).is_absolute() else Path(raw_dir).resolve()
    allowed = [Path(item).resolve() for item in envelope.get("allowed_read_roots", [workspace])]
    if not any(skill_dir == base or base in skill_dir.parents for base in allowed):
        print(json.dumps({"error": "skill_dir outside allowed read roots", "skill_dir": str(skill_dir)}, indent=2))
        return 2
    skill_md = skill_dir / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8") if skill_md.exists() else ""
    files = [item.relative_to(skill_dir).as_posix() for item in skill_dir.rglob("*") if item.is_file()] if skill_dir.exists() else []
    payload = {
        "skill_dir": str(skill_dir),
        "exists": skill_dir.exists(),
        "has_skill_md": skill_md.exists(),
        "has_frontmatter": content.startswith("---\n"),
        "file_count": len(files),
        "script_files": [item for item in files if item.startswith("scripts/")],
        "reference_files": [item for item in files if item.startswith("references/")],
        "asset_files": [item for item in files if item.startswith("assets/")],
        "mentions_native_boundary": any(term in content.lower() for term in BOUNDARY_TERMS),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
