# humungousaur-skill-script: {"name":"profile-csv","description":"Profile a CSV file with row sample count, columns, missing counts, and simple numeric ranges using only the Python standard library.","input_schema":{"type":"object","additionalProperties":false,"properties":{"path":{"type":"string"},"max_rows":{"type":"integer","minimum":1,"maximum":10000}},"required":["path"]}}
from __future__ import annotations

import csv
import json
from pathlib import Path
import sys


def main() -> int:
    envelope = json.loads(sys.stdin.read() or "{}")
    workspace = Path(envelope.get("workspace", ".")).resolve()
    user_input = envelope.get("input", {})
    raw_path = str(user_input.get("path") or "")
    path = (workspace / raw_path).resolve() if not Path(raw_path).is_absolute() else Path(raw_path).resolve()
    allowed = [Path(item).resolve() for item in envelope.get("allowed_read_roots", [workspace])]
    if not any(path == base or base in path.parents for base in allowed):
        print(json.dumps({"error": "path outside allowed read roots", "path": str(path)}, indent=2))
        return 2
    max_rows = max(1, min(int(user_input.get("max_rows") or 1000), 10000))
    missing: dict[str, int] = {}
    numeric: dict[str, list[float]] = {}
    row_count = 0
    columns: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        missing = {column: 0 for column in columns}
        numeric = {column: [] for column in columns}
        for row in reader:
            row_count += 1
            for column in columns:
                value = (row.get(column) or "").strip()
                if value == "":
                    missing[column] += 1
                    continue
                try:
                    numeric[column].append(float(value.replace(",", "")))
                except ValueError:
                    pass
            if row_count >= max_rows:
                break
    numeric_ranges = {
        column: {"min": min(values), "max": max(values), "sample_count": len(values)}
        for column, values in numeric.items()
        if values
    }
    payload = {
        "path": str(path),
        "columns": columns,
        "sampled_rows": row_count,
        "missing_counts": missing,
        "numeric_ranges": numeric_ranges,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
