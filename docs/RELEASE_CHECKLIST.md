# Release Checklist

Use this before publishing a new open-source release or updating website download links.

For the exact order of operations, commands, signing secrets, tag checks, GitHub asset verification, and website promotion gate, follow `docs/RELEASE_RUNBOOK.md`.

## Agent Runtime

- Confirm `.github/workflows/ci.yml` is green for backend tests, desktop parity, macOS packaging, and Windows packaging.
- `python -m pip install -e ".[browser,pdf,ocr,office,test]"`
- `python3 script/verify_release_readiness.py --require-website`
- `python3 script/verify_desktop_parity.py`
- `python3 script/verify_desktop_runtime_smoke.py`
- `python -m unittest discover -v`
- Before pushing/tagging, run `python3 script/verify_publication_state.py --require-website` and require tracked runtime and website release files plus clean working trees.
- `python scripts/smoke_agent.py --workspace .`
- `python scripts/smoke_real_world_tasks.py --workspace .`
- When Playwright is installed and local browser launch is allowed, also run `python scripts/smoke_real_world_tasks.py --workspace . --live-browser`.
- Confirm `.env.example` documents every supported provider key without real values.
- Confirm high-risk tools still require approval and write audit events.

## Desktop Apps

- Build the Windows app from `apps/windows/Humungousaur.App`.
- Build and verify the Windows app on Windows or the GitHub Actions `windows-latest` runner; the WinUI project targets `net8.0-windows` and is not expected to package from macOS/Linux.
- Build the macOS app from `apps/macos` with `swift build`.
- Generate local macOS release asset with `./script/package_macos.sh`.
- Generate local Windows release asset on Windows with `./script/package_windows.ps1`.
- Verify local macOS package structure and checksum with `./script/verify_macos_package.sh`.
- Verify local Windows package structure and checksum on Windows with `./script/verify_windows_package.ps1`.
- To pull desktop zips from GitHub Actions into the local release directory, run `python3 script/collect_release_artifacts.py --run-id <actions-run-id> --release-tag v<project.version> --require-website`.
- After generating both local assets, run `python3 script/verify_release_readiness.py --require-website --require-assets`.
- Generate a local evidence report with `python3 script/generate_release_report.py --require-website --require-assets`.
- Confirm each desktop release asset includes first-run setup instructions for workspace path, Python path, daemon port, provider/model, and required keys.
- For signed macOS public releases, configure GitHub secrets `MACOS_CERTIFICATE_P12_BASE64`, `MACOS_CERTIFICATE_PASSWORD`, `MACOS_KEYCHAIN_PASSWORD`, `MACOS_CODESIGN_IDENTITY`, `MACOS_NOTARIZE=1`, `APPLE_ID`, `APPLE_TEAM_ID`, and `APPLE_APP_SPECIFIC_PASSWORD`.
- For signed Windows public releases, configure GitHub secrets `WINDOWS_CERTIFICATE_PFX_BASE64`, `WINDOWS_CERTIFICATE_PASSWORD`, `WINDOWS_SIGN=1`, and optionally `WINDOWS_TIMESTAMP_URL`.
- Confirm the macOS release job signs with hardened runtime, notarizes, staples the app, and then regenerates `Humungousaur-macOS.zip`.
- Confirm the Windows release job signs every packaged `.exe` and Humungousaur-owned `.dll` with timestamped Authenticode before generating `Humungousaur-Windows.zip`.
- For tag releases, CI runs `./script/verify_macos_package.sh --require-signature --require-notarization` and `./script/verify_windows_package.ps1 -RequireSignature` before upload.
- Start each app against `python -m humungousaur serve --workspace . --port 8765`.
- Verify chat, tools, channels, voice status, autonomy controls, runs, approvals, and local process start/stop.
- Verify channel setup secrets are stored through OS-provided user secret storage, not plaintext repo files.

## Website

- Confirm `Humungousaur-Website/AGENTS.md` covers website source layout, content boundaries, design direction, security, and release gates.
- `npm ci`
- `npm run check:downloads`
- `npm run check:assets`
- `npm run check:publication`
- `npm run build`
- `npm audit --audit-level=moderate`
- Confirm GitHub links point at `https://github.com/bhaveshpabnani/Humungousaur`.
- Confirm Windows and macOS download links point at the latest signed/notarized release assets.
- Before promoting website changes, require `npm run check:publication` to pass with tracked website publication files and a clean website working tree.
- After publishing the tagged release, run `npm run check:release-assets` from the website repo.
- Publish release assets with the website-targeted names:
  - `Humungousaur-Windows.zip`
  - `Humungousaur-macOS.zip`
  - `checksums.txt`

## Release Artifacts

- Tag the agent repo.
- Confirm the tag matches `v<project.version>` from `pyproject.toml`.
- Use `.github/workflows/release.yml` for tagged GitHub releases when publishing from CI.
- For manual release repair from GitHub Actions, set `publish_release=true` and `release_tag=v<project.version>`; the workflow must check out that exact tag before packaging.
- Attach Windows installer/package artifacts as `Humungousaur-Windows.zip`.
- Attach macOS DMG/ZIP artifacts as `Humungousaur-macOS.zip` after signing/notarization checks.
- Publish checksums.
- Attach `release-readiness.md` from `script/generate_release_report.py` to the release.
- Update website download links and docs.
- Confirm the release workflow ran `python3 script/verify_release_readiness.py --skip-website --require-github-release --github-release-tag <tag>`.
- After the tagged GitHub release is published, run `python3 script/verify_release_readiness.py --require-website --require-github-release`.
