# humungousaur-skill-script: {"name":"build-markdown-index","description":"Build a JSON index of markdown files with titles, relative paths, and outbound wikilink/markdown-link counts.","input_schema":{"type":"object","additionalProperties":true,"properties":{"root":{"type":"string"},"max_files":{"type":"integer","minimum":1,"maximum":5000}}}}
from __future__ import annotations

import json
from pathlib import Path
import re
import sys


MD_LINK_RE = re.compile(r"\[[^\]]+\]\([^)]+\)")
WIKI_LINK_RE = re.compile(r"\[\[[^\]]+\]\]")


def title_for(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[:80]:
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
    except OSError:
        return ""
    return path.stem


def main() -> int:
    envelope = json.loads(sys.stdin.read() or "{}")
    workspace = Path(envelope.get("workspace", ".")).resolve()
    raw_root = str(envelope.get("input", {}).get("root") or ".")
    root = (workspace / raw_root).resolve() if not Path(raw_root).is_absolute() else Path(raw_root).resolve()
    allowed = [Path(item).resolve() for item in envelope.get("allowed_read_roots", [workspace])]
    if not any(root == base or base in root.parents for base in allowed):
        print(json.dumps({"error": "root outside allowed read roots", "root": str(root)}, indent=2))
        return 2
    max_files = max(1, min(int(envelope.get("input", {}).get("max_files") or 500), 5000))
    records = []
    for path in sorted(root.rglob("*.md"))[:max_files]:
        if ".git" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        records.append(
            {
                "path": path.relative_to(root).as_posix(),
                "title": title_for(path),
                "markdown_links": len(MD_LINK_RE.findall(text)),
                "wikilinks": len(WIKI_LINK_RE.findall(text)),
            }
        )
    payload = {"root": str(root), "markdown_file_count": len(records), "records": records}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
