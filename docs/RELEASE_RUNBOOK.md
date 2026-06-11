# Release Runbook

This is the ordered path for publishing a production Humungousaur release with matching Windows and macOS desktop assets, checksums, and website downloads.

## 1. Preflight the Source Tree

Run from the agent repository:

```bash
python3 -m py_compile script/verify_open_source_hygiene.py script/verify_publication_state.py script/verify_release_readiness.py script/generate_release_report.py script/collect_release_artifacts.py script/verify_desktop_parity.py script/verify_desktop_runtime_smoke.py
python3 -m unittest discover -v
python3 script/verify_desktop_parity.py
python3 script/verify_desktop_runtime_smoke.py
python3 script/verify_open_source_hygiene.py
python3 scripts/smoke_real_world_tasks.py --workspace .
python3 script/verify_release_readiness.py --require-website --release-tag v0.1.0
python3 script/generate_release_report.py --require-website --check-github-release
```

If Playwright is installed and local browser launch is allowed, run the stronger local browser proof before tagging:

```bash
python3 scripts/smoke_real_world_tasks.py --workspace . --live-browser
```

Before pushing the open-source release branch or tag, run the final publication-state gate:

```bash
python3 script/verify_publication_state.py --require-website
```

This must pass only after all required runtime release files are tracked, the sibling website publication gate passes, and both working trees are clean. Use `python3 script/verify_publication_state.py` without `--require-website` only for a backend-only diagnostic.

For the final tracking review, inspect both repositories before committing:

```bash
git status --short
git diff --stat
git diff --check

cd ../Humungousaur-Website
git status --short
git diff --stat
git diff --check
```

Review the expected website image replacement as a paired change: the old PNG assets should be removed, the optimized JPEG assets should be tracked, and `npm run check:assets` should pass. Do not publish from a tree where `verify_publication_state.py --require-website` or `npm run check:publication` is only failing because required files were left untracked.

Run from the website repository:

```bash
npm ci
npm run lint
npm run check:downloads
npm run check:assets
npm run check:publication
npm run build
npm audit --audit-level=moderate
```

`npm run check:publication` must pass only after the website download scripts,
workflow, source files, and documentation are tracked and the website working
tree is clean.

The release tag must match the Python package version in `pyproject.toml`. For version `0.1.0`, the release tag is `v0.1.0`.

## 2. Configure Public Release Secrets

Tag releases are expected to be signed. Configure these repository secrets before pushing the tag.

macOS:

```text
MACOS_CERTIFICATE_P12_BASE64
MACOS_CERTIFICATE_PASSWORD
MACOS_KEYCHAIN_PASSWORD
MACOS_CODESIGN_IDENTITY
MACOS_INSTALLER_IDENTITY
MACOS_NOTARIZE=1
APPLE_ID
APPLE_TEAM_ID
APPLE_APP_SPECIFIC_PASSWORD
```

Windows:

```text
WINDOWS_CERTIFICATE_PFX_BASE64
WINDOWS_CERTIFICATE_PASSWORD
WINDOWS_SIGN=1
WINDOWS_TIMESTAMP_URL
```

`WINDOWS_TIMESTAMP_URL` is optional when the default timestamp URL is acceptable. Unsigned local packages are allowed for development, but public tag releases must pass the signature-required CI gates.

Windows packaging and verification must run on Windows because the app targets `net8.0-windows` and WinUI. Use the GitHub Actions `windows-latest` release job or a local Windows machine with the .NET 8 SDK installed; macOS/Linux release preparation should rely on the workflow artifacts for `Humungousaur-Windows-Setup.zip` and `Humungousaur-Windows.zip`.

For public tag releases, `script/package_macos.sh` must sign the app, sign `Humungousaur-macOS.pkg`, notarize/staple the package, and `script/verify_macos_package.sh --require-signature --require-notarization` must confirm the app code signature, Gatekeeper assessment, package signature, and stapled notarization ticket before upload.

For public tag releases, `script/package_windows.ps1` signs every packaged `.exe` and Humungousaur-owned `.dll`, and `script/verify_windows_package.ps1 -RequireSignature` must confirm every one of those app-owned Windows binaries has a valid timestamped Authenticode signature.

Both desktop package scripts must rebuild from clean staging directories before creating public installers and legacy zips. The macOS script clears `artifacts/package/macos` and `artifacts/package/macos-pkg`, and the Windows script clears `artifacts/package/windows/publish` and `artifacts/package/windows/installer`, so stale local publish output cannot leak into release assets.

## 3. Publish the Tagged Agent Release

Create and push the matching tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The release workflow can also be started manually with `workflow_dispatch` from GitHub Actions. For a real publish or repair run, set:

```text
publish_release=true
release_tag=v0.1.0
```

Manual publish runs validate that `release_tag` is present, starts with `v`, and exists as a git tag. Every workflow job checks out that exact tag before packaging so manual repair releases cannot accidentally package branch-only changes.

The `.github/workflows/release.yml` workflow must install test extras, compile the release scripts, run source readiness, run `python script/verify_desktop_runtime_smoke.py`, run `python -m unittest discover -v`, build both desktop apps, sign macOS and Windows assets on tag builds, generate fresh checksums, and publish:

```text
Humungousaur-Windows.zip
Humungousaur-macOS.zip
Humungousaur-Windows-Setup.zip
Humungousaur-macOS.pkg
checksums.txt
release-readiness.md
```

The `publish` job must explicitly depend on `preflight`, `macos`, and `windows` with `needs: [preflight, macos, windows]` so GitHub release creation cannot run without the backend regression gate and both platform package jobs.

The workflow token must be least-privilege: CI and release jobs default to `contents: read`, and only the `publish` job may request `contents: write` for GitHub release creation and asset repair.

The `publish` job must also run `actions/setup-python@v6` and `python -m pip install -e ".[browser,pdf,ocr,office,test]"` before generating `release-readiness.md`, because the generated release evidence runs the backend regression a final time.

The workflow is rerunnable. It should use `gh release view`, `gh release create`, or `gh release upload --clobber` so a failed or partial run can be repaired without renaming the release. Post-publish verification should use `gh release download` for `checksums.txt`, both desktop zips, `Humungousaur-Windows-Setup.zip`, and `Humungousaur-macOS.pkg`, then confirm each downloaded zip matches its SHA-256 row or package checksum row.

The publish job must verify the exact staged upload directory before release creation:

```bash
python3 ./script/verify_release_readiness.py --skip-website --require-assets --release-dir artifacts/release/final --release-tag "$GITHUB_REF_NAME"
```

For manual publish runs, the workflow uses `$HUMUNGOUSAUR_RELEASE_TAG` from the validated `release_tag` input in the same commands.

The generated readiness report should use the same `--release-dir artifacts/release/final` path so the manifest and preflight describe the exact assets uploaded to GitHub. It must include a `Backend Regression` section from `python -m unittest discover -v`, so the uploaded release evidence carries the backend test result. When run locally with `--require-website`, it should also include website lint, download source check, release asset self-test, build, and audit sections. When GitHub release verification is requested, it should include a website live release asset check; exact tag reports should run it with `HUMUNGOUSAUR_RELEASE_TAG=v0.1.0`.

Before publishing, the final upload directory must contain exactly:

```text
Humungousaur-Windows.zip
Humungousaur-macOS.zip
Humungousaur-Windows-Setup.zip
Humungousaur-macOS.pkg
checksums.txt
release-readiness.md
```

No extra files should be uploaded to the GitHub release.

The workflow must run `script/verify_release_report.py` on `artifacts/release/final/release-readiness.md` before publishing, with `--require-pass-status` on tag releases. This catches missing report sections or accidental failing evidence before the report becomes a public asset.

After publishing, the workflow must re-check the exact staged upload directory and the published GitHub release assets together:

```bash
python3 ./script/verify_release_readiness.py --skip-website --require-assets --release-dir artifacts/release/final --require-github-release --github-release-tag "$HUMUNGOUSAUR_RELEASE_TAG" --release-tag "$HUMUNGOUSAUR_RELEASE_TAG"
```

## 4. Verify Published Assets

After the GitHub Actions release workflow completes, run the exact tag check from the agent repository:

```bash
python3 script/verify_release_readiness.py --require-website --require-github-release --github-release-tag v0.1.0
```

If both local artifacts have been downloaded to `artifacts/release`, run the strict local artifact preflight:

```bash
python3 script/verify_release_readiness.py --require-website --require-assets --release-tag v0.1.0
```

The strict local preflight must see `Humungousaur-Windows-Setup.zip`, `Humungousaur-macOS.pkg`, `Humungousaur-Windows.zip`, `Humungousaur-macOS.zip`, and `checksums.txt`, and `checksums.txt` must contain rows for both desktop zips plus the installer/package assets.

To collect the desktop installers and zips from a successful GitHub Actions release workflow run into `artifacts/release` and regenerate local checksums, run:

```bash
python3 script/collect_release_artifacts.py --run-id <actions-run-id> --release-tag v0.1.0 --require-website
```

If `--run-id` is omitted, the helper selects the latest successful `Release Desktop Apps` workflow run. Use an explicit run id for release evidence.

Both desktop package verifiers must also reject unsafe or platform metadata zip entries, including absolute paths, parent-directory traversal, `__MACOSX`, `.DS_Store`, and AppleDouble `._*` files.

## 5. Promote Website Downloads

The website download links point at the latest GitHub release assets. After publishing the tagged release, verify the live release assets from the website repository:

```bash
npm run check:publication
npm run check:release-assets
```

For an exact tag check instead of latest:

```bash
HUMUNGOUSAUR_RELEASE_TAG=v0.1.0 npm run check:release-assets
```

The website CI workflow also has manual `verify_release_assets` and `release_tag` inputs. Use an exact tag such as `v0.1.0` before promoting website changes, then use the latest-release check before announcing the desktop downloads.

## 6. Final Release Evidence

Attach or retain the generated `release-readiness.md`. The report should show:

- backend tests and desktop parity passed
- shared desktop runtime API smoke passed
- open-source hygiene passed
- release source preflight passed
- Windows and macOS package verification passed
- GitHub release asset verification passed
- website build and download checks passed
- website release asset self-test and audit passed
- website live release asset check passed for the promoted tag or latest release

Do not announce the release until the latest-release website check passes against the published GitHub assets.
