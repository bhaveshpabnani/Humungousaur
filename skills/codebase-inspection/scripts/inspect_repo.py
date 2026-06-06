# humungousaur-skill-script: {"name":"inspect-repo","description":"Inspect a repository's top-level structure, manifest files, and sampled language/file suffix counts without modifying files.","input_schema":{"type":"object","additionalProperties":true,"properties":{"path":{"type":"string","description":"Optional repo-relative or absolute path to inspect."},"max_files":{"type":"integer","minimum":1,"maximum":5000}}}}
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys


MANIFEST_NAMES = {
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "package-lock.json",
    "pyproject.toml",
    "requirements.txt",
    "poetry.lock",
    "Cargo.toml",
    "go.mod",
    "deno.json",
    "tsconfig.json",
    "vite.config.ts",
    "next.config.js",
    "README.md",
}


def main() -> int:
    envelope = json.loads(sys.stdin.read() or "{}")
    workspace = Path(envelope.get("workspace", ".")).resolve()
    raw_path = str(envelope.get("input", {}).get("path") or ".")
    root = (workspace / raw_path).resolve() if not Path(raw_path).is_absolute() else Path(raw_path).resolve()
    allowed = [Path(item).resolve() for item in envelope.get("allowed_read_roots", [workspace])]
    if not any(root == base or base in root.parents for base in allowed):
        print(json.dumps({"error": "path outside allowed read roots", "path": str(root)}, indent=2))
        return 2
    max_files = int(envelope.get("input", {}).get("max_files") or 2000)
    max_files = max(1, min(max_files, 5000))
    top_dirs = []
    top_files = []
    manifests = []
    suffix_counts: Counter[str] = Counter()
    sampled = 0
    if root.exists() and root.is_dir():
        for item in sorted(root.iterdir(), key=lambda value: value.name.lower()):
            if item.name.startswith(".git"):
                continue
            if item.is_dir():
                top_dirs.append(item.name)
            else:
                top_files.append(item.name)
            if item.name in MANIFEST_NAMES:
                manifests.append(item.name)
        for item in root.rglob("*"):
            if sampled >= max_files:
                break
            if ".git" in item.parts or not item.is_file():
                continue
            suffix_counts[item.suffix.lower() or "<none>"] += 1
            sampled += 1
    payload = {
        "root": str(root),
        "exists": root.exists(),
        "top_dirs": top_dirs[:80],
        "top_files": top_files[:80],
        "manifests": manifests,
        "sampled_file_count": sampled,
        "suffix_counts": dict(sorted(suffix_counts.items(), key=lambda item: (-item[1], item[0]))[:40]),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
