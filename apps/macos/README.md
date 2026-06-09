# Humungousaur for Mac

Native SwiftUI desktop shell for the Humungousaur local agent runtime.

## Run

```bash
./script/build_and_run.sh
```

The run script builds the SwiftPM executable, stages `dist/HumungousaurMac.app`, and launches it as a normal macOS app bundle. Use the verification mode for a local build-and-launch smoke:

```bash
./script/build_and_run.sh --verify
```

For compile-only validation, run:

```bash
swift build --package-path apps/macos
```

The app talks to the local daemon at `http://127.0.0.1:8765` by default. It can also start the daemon with:

```bash
python3 -m humungousaur serve --workspace <repo-root> --port 8765
```

To build the distributable desktop zip and verify its setup docs, bundle metadata, checksum, and signature mode, run:

```bash
./script/package_macos.sh
./script/verify_macos_package.sh
```

## Capability Surface

The macOS app is a native SwiftUI client for the shared Humungousaur agent API. It exposes:

- chat/stimulus submission with response modes
- tool catalog and risk metadata
- channel gateway setup, requirements, doctor, smoke tests, inbound preview, prepared outbound messages, approval-gated sends, listener polling, and outbox review
- voice provider status and STT/TTS settings
- bounded autonomy cycles
- recent runs, run cancellation, pending approvals, approve/reject actions
- local daemon start/stop from the configured Python/workspace/port

Channel tokens and provider API keys are stored in the macOS Keychain. Non-secret preferences use `UserDefaults`.

## Design Direction

The interface follows macOS conventions: a persistent sidebar for major modes, an integrated toolbar, a calm command canvas, a right inspector for workspace/runtime context, SF Symbols, soft separators, and compact pro-tool controls. API keys are stored in the macOS Keychain; non-secret preferences use `UserDefaults`.
