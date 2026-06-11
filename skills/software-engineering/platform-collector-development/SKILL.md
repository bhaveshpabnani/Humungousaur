---
name: native-collector-development
description: Design, implement, organize, document, and verify Humungousaur native OS collectors for macOS, Windows, or Linux using official OS API references, shared event envelopes, helper health, privacy-first metadata, and repo-native adapter boundaries.
---

# Native Collector Development

## Purpose

Implement Humungousaur native collectors as organized platform helpers that observe OS or app signals, redact locally, emit shared collector event envelopes, and let the Python runtime own durable ingestion.

## When To Use

Use when adding, extending, organizing, reviewing, or debugging collectors under `native_collectors/macos`, `native_collectors/windows`, or `native_collectors/linux`; when wiring a matching Python bridge adapter; or when choosing the right OS API for collector stimuli.

## Inputs And Evidence

- User's target OS, collector name, stimulus types, and privacy level.
- `docs/COLLECTOR_ARCHITECTURE.md`.
- `native_collectors/shared/event-envelope.schema.json`.
- Existing platform helper layout under `native_collectors/<os>/`.
- Relevant Python bridge adapters under `humungousaur/collectors/adapters/` and registry wiring in `humungousaur/collectors/registry.py`.
- Official OS API docs or man pages for the native surface. Start with `references/os-api-references.md`, then refresh with web lookup when APIs may have changed.

## Tool Map

- `codebase-inspection`
- `skill-authoring`
- `read_file`
- `search_workspace`
- `list_files`
- `run_shell_command`
- `web_search`
- `fetch_web_page`

## Repository Boundaries

- Native code lives only under `native_collectors/macos`, `native_collectors/windows`, or `native_collectors/linux`.
- Do not add old root-level collector adapters under `humungousaur/collectors`.
- If Python integration is needed, update only the relevant adapter under `humungousaur/collectors/adapters/` and keep registration in `humungousaur/collectors/registry.py`.
- Treat JSONL/native bridge as ingress only. Python owns SQLite event log, consumers, batching, memory, attention compaction, and the LLM boundary.
- Use the existing shared contract at `native_collectors/shared/event-envelope.schema.json`.

## Organization Pattern

For each platform, keep helpers modular before adding more collectors:

```text
native_collectors/<os>/
  README.md
  shared/event writer or package metadata
  host/runtime entrypoint
  bridge/spool/health code
  collector-category folders
  OS support readers
```

For macOS, preserve this shape:

```text
Sources/CollectorHost/
  main.swift
  Runtime/
  Bridge/
  CoreOSContext/
  MacOSSupport/
```

Add one focused collector file per collector or closely related collector pair. Add shared OS API wrappers under the support folder instead of duplicating raw API calls.

## OS Reference Workflow

1. Before implementation, read local architecture docs and current platform helper code.
2. Check official OS documentation or man pages for the exact API surface. Use bundled `references/os-api-references.md` as the first index, then use `web_search` and `fetch_web_page` for current official docs.
3. Prefer primary sources:
   - Apple Developer documentation for macOS AppKit, CoreGraphics, Accessibility, IOKit, Text Input Sources, and pasteboard APIs.
   - Microsoft Learn for Win32, WMI, UI Automation, WinEvent, ETW, power/session, and device APIs.
   - Linux man pages, freedesktop specs, GNOME AT-SPI docs, systemd/udev docs, kernel docs, and desktop portal specs.
4. Record the chosen API in code comments only where helpful and in `native_collectors/<os>/README.md`.
5. If a source is stale, unofficial, or unclear, use it only as a hint and verify against a primary source.

## Implementation Workflow

1. Identify the collector definition and allowed stimulus types in `humungousaur/collectors/definitions.py`.
2. Inspect existing bridge adapters for the collector family.
3. Choose the least invasive native API that can emit metadata-only evidence.
4. Implement native helper code inside the OS folder using platform conventions:
   - macOS: Swift, with AppKit/CoreGraphics/Accessibility/IOKit/FSEvents/Text Input Sources as appropriate.
   - Windows: C#/.NET, with WMI/UIAutomation/WinEvent/ETW/PowerShell only when appropriate.
   - Linux: Rust, with inotify/DBus/udev/AT-SPI/fanotify/desktop portals as appropriate.
5. Emit one valid shared envelope per observation into `collector_spool/<collector>.jsonl`.
6. Emit helper health through the existing helper-health contract when the runtime API is available; also provide local diagnostics without raw content.
7. Update `native_collectors/<os>/README.md` with build/run commands, APIs used, permission requirements, privacy behavior, and collector list.
8. Keep new files organized by category before adding more behavior.

## Privacy Rules

- Default to metadata or sensitive metadata.
- Do not collect raw screen pixels, audio, typed text, clipboard contents, selected text, field values, IME candidate text, prompt text, or raw document content unless an explicit rich opt-in collector contract requires it.
- Hash or bucket risky metadata such as window titles, paths, sizes, and timings where exact values are not needed.
- Include `raw_content_included: false` metadata and redaction fields for native envelopes.
- If a permission is missing, report `permission_denied` or degraded helper health instead of silently collecting more invasive data.

## Verification

Run the checks that match the touched OS and Python surface:

```sh
swift build
dotnet build
cargo test
```

Validate native output:

```sh
python3 - <<'PY'
import json
from pathlib import Path
import jsonschema
schema = json.loads(Path("native_collectors/shared/event-envelope.schema.json").read_text())
for path in Path("artifacts/collector_spool").glob("*.jsonl"):
    for line in path.read_text().splitlines():
        if line.strip():
            jsonschema.validate(json.loads(line), schema)
PY
```

Run Humungousaur collector acceptance checks:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_collectors.py tests/test_collector_event_log.py tests/test_api.py -q
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from humungousaur.collectors.registry import collector_registry
from humungousaur.collectors.definitions import COLLECTOR_DEFINITIONS
print(len(collector_registry.names()), len(COLLECTOR_DEFINITIONS), collector_registry.validate_complete())
PY
```

When adding or changing this skill, run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_workspace_skill_format.py -q
```

## Failure Modes

- Building a monolithic host that becomes hard to extend.
- Treating bridge JSONL as durable storage.
- Adding Python collector files outside `humungousaur/collectors/adapters/`.
- Emitting valid JSON that does not match the shared event envelope.
- Capturing raw text, clipboard values, window titles, screenshots, paths, audio, or IME contents by accident.
- Implementing from memory instead of checking current OS documentation.

## References

- `references/os-api-references.md`.
- `docs/COLLECTOR_ARCHITECTURE.md`.
- `native_collectors/shared/event-envelope.schema.json`.
