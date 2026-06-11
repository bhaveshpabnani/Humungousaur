# Humungousaur Native Collectors

Native collectors are platform-specific event producers. They should observe OS
and application signals, redact locally, and emit the shared collector event
envelope. Humungousaur owns privacy policy, durable event storage, attention
batching, semantic interpretation, memory, UI streaming, and autonomy.

Recommended implementation languages:

- `macos/`: Swift, with tiny C or Objective-C shims only where Apple APIs need it.
- `windows/`: C#/.NET, with selective C++ helpers for ETW, hooks, or low-level COM.
- `linux/`: Rust or C for daemon and kernel/desktop integrations.

All platform collectors must target `shared/event-envelope.schema.json`.

Each long-running helper should also report helper health to the Humungousaur
runtime with:

- `helper_id`
- `collector`
- `platform`
- `status`: `starting`, `running`, `degraded`, `permission_denied`, `stopped`, or `failed`
- `permission_state`
- `last_event_at`
- `restart_count`

If an OS permission is missing, report `permission_denied` and keep raw capture
off. The Python runtime owns durable storage, retention, consumer offsets,
dead-letter handling, and the compact attention boundary.
