#!/usr/bin/env bash
set -euo pipefail

APP_NAME="HumungousaurMac"
BUNDLE_NAME="Humungousaur"
BUNDLE_ID="ai.humungousaur.mac"
MIN_SYSTEM_VERSION="14.0"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MACOS_DIR="$ROOT_DIR/apps/macos"
RELEASE_DIR="$ROOT_DIR/artifacts/release"
STAGE_DIR="$ROOT_DIR/artifacts/package/macos"
APP_BUNDLE="$STAGE_DIR/$BUNDLE_NAME.app"
APP_CONTENTS="$APP_BUNDLE/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_RESOURCES="$APP_CONTENTS/Resources"
APP_BINARY="$APP_MACOS/$APP_NAME"
INFO_PLIST="$APP_CONTENTS/Info.plist"
ZIP_PATH="$RELEASE_DIR/Humungousaur-macOS.zip"
PKG_PATH="$RELEASE_DIR/Humungousaur-macOS.pkg"
INSTALL_DOC="$STAGE_DIR/INSTALL.txt"
RUNTIME_SOURCE_DIR="$STAGE_DIR/Runtime/runtime-source"
PKG_ROOT="$ROOT_DIR/artifacts/package/macos-pkg/root"
PKG_SCRIPTS="$ROOT_DIR/artifacts/package/macos-pkg/scripts"
PKG_COMPONENT="$ROOT_DIR/artifacts/package/macos-pkg/Humungousaur-component.pkg"
PKG_IDENTIFIER="ai.humungousaur.mac.installer"
MACOS_CODESIGN_IDENTITY="${HUMUNGOUSAUR_MACOS_CODESIGN_IDENTITY:-}"
MACOS_INSTALLER_IDENTITY="${HUMUNGOUSAUR_MACOS_INSTALLER_IDENTITY:-}"
MACOS_NOTARIZE="${HUMUNGOUSAUR_MACOS_NOTARIZE:-0}"
APPLE_ID="${APPLE_ID:-}"
APPLE_TEAM_ID="${APPLE_TEAM_ID:-}"
APPLE_APP_SPECIFIC_PASSWORD="${APPLE_APP_SPECIFIC_PASSWORD:-}"
PROJECT_VERSION="$(awk -F'"' '/^version[[:space:]]*=/ { print $2; exit }' "$ROOT_DIR/pyproject.toml")"
if [[ -z "$PROJECT_VERSION" ]]; then
  echo "Unable to read project.version from pyproject.toml" >&2
  exit 1
fi

stage_runtime_source() {
  local target="$1"
  rm -rf "$target"
  mkdir -p "$target/script"
  rsync -a --delete \
    --exclude ".git" \
    --exclude ".DS_Store" \
    --exclude "__pycache__" \
    --exclude "*.pyc" \
    --exclude ".pytest_cache" \
    --exclude ".mypy_cache" \
    --exclude ".ruff_cache" \
    --exclude ".venv" \
    --exclude "artifacts" \
    --exclude "dist" \
    --exclude "external_repos" \
    "$ROOT_DIR/humungousaur" "$target/"
  rsync -a "$ROOT_DIR/skills" "$target/"
  rsync -a "$ROOT_DIR/browser_extensions" "$target/"
  rsync -a "$ROOT_DIR/script/bootstrap_runtime.py" "$target/script/"
  cp "$ROOT_DIR/pyproject.toml" "$ROOT_DIR/README.md" "$ROOT_DIR/LICENSE" "$target/"
}

swift build --package-path "$MACOS_DIR" -c release
BUILD_DIR="$(swift build --package-path "$MACOS_DIR" -c release --show-bin-path)"
BUILD_BINARY="$BUILD_DIR/$APP_NAME"

rm -rf "$STAGE_DIR"
mkdir -p "$APP_MACOS" "$APP_RESOURCES" "$RELEASE_DIR"
cp "$BUILD_BINARY" "$APP_BINARY"
chmod +x "$APP_BINARY"
cp "$MACOS_DIR/Sources/Resources/HumungousaurIcon.icns" "$APP_RESOURCES/HumungousaurIcon.icns"
find "$BUILD_DIR" -maxdepth 1 -type d \( -name "*.resources" -o -name "*.bundle" \) -exec cp -R {} "$APP_RESOURCES/" \;
stage_runtime_source "$RUNTIME_SOURCE_DIR"

cat >"$INFO_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>$APP_NAME</string>
  <key>CFBundleIdentifier</key>
  <string>$BUNDLE_ID</string>
  <key>CFBundleName</key>
  <string>$BUNDLE_NAME</string>
  <key>CFBundleIconFile</key>
  <string>HumungousaurIcon</string>
  <key>CFBundleShortVersionString</key>
  <string>$PROJECT_VERSION</string>
  <key>CFBundleVersion</key>
  <string>$PROJECT_VERSION</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSMinimumSystemVersion</key>
  <string>$MIN_SYSTEM_VERSION</string>
  <key>NSPrincipalClass</key>
  <string>NSApplication</string>
  <key>NSMicrophoneUsageDescription</key>
  <string>Humungousaur uses the microphone only when voice wake-up is enabled so it can hear your wake phrase and spoken tasks.</string>
  <key>NSSpeechRecognitionUsageDescription</key>
  <string>Humungousaur uses speech recognition only when voice wake-up is enabled to turn your spoken tasks into local agent stimuli.</string>
</dict>
</plist>
PLIST

cat >"$INSTALL_DOC" <<INSTALL
Humungousaur macOS setup
Version: $PROJECT_VERSION

Recommended public install:
1. Open Humungousaur-macOS.pkg. The installer places Humungousaur.app in Applications, installs the bundled runtime source, and runs:
   /usr/local/bin/humungousaur-bootstrap
2. If Python 3.12+ was added after install, repair the runtime with:
   /usr/local/bin/humungousaur-bootstrap
3. Start the runtime from the app with the play button, or run:
   /Library/Application Support/Humungousaur/runtime/.venv/bin/python -m humungousaur serve --workspace "$HOME" --port 8765
4. Developer source installs can still use:
   python3 -m pip install -e ".[browser,pdf,ocr,office]"
   python3 -m humungousaur serve --workspace <repo-root> --port 8765
5. Open Settings in the app and confirm:
   - workspace path: your project folder or home folder
   - Python path: /Library/Application Support/Humungousaur/runtime/.venv/bin/python, python3, or <repo-root>/.venv/bin/python
   - API URL: http://127.0.0.1:8765
   - provider/model: openai, groq, ollama, grok, or local-openai
   - model keys: OPENAI_API_KEY, GROQ_API_KEY, XAI_API_KEY, OLLAMA_API_KEY, or LOCAL_LLM_API_KEY
   - voice keys: DEEPGRAM_API_KEY, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL_ID
   - voice wake-up: enable it in the Voice tab, approve microphone and speech-recognition permissions, then say "Humungousaur" followed by a task
   - channel keys required by your enabled channel setup
6. Use the toolbar status menu to verify API, model, tools, runs, channels, voice, autonomy, and approvals before sending a task.

Release validation command:
python -m unittest discover -v

Package validation command:
./script/verify_macos_package.sh
INSTALL

if [[ -n "$MACOS_CODESIGN_IDENTITY" ]]; then
  codesign --force --deep --options runtime --timestamp --sign "$MACOS_CODESIGN_IDENTITY" "$APP_BUNDLE"
  codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"
elif [[ "$MACOS_NOTARIZE" == "1" ]]; then
  echo "HUMUNGOUSAUR_MACOS_NOTARIZE=1 requires HUMUNGOUSAUR_MACOS_CODESIGN_IDENTITY" >&2
  exit 1
else
  echo "Skipping macOS codesign; set HUMUNGOUSAUR_MACOS_CODESIGN_IDENTITY for signed release builds."
fi
if [[ "$MACOS_NOTARIZE" == "1" && -z "$MACOS_INSTALLER_IDENTITY" ]]; then
  echo "HUMUNGOUSAUR_MACOS_NOTARIZE=1 requires HUMUNGOUSAUR_MACOS_INSTALLER_IDENTITY for the .pkg installer" >&2
  exit 1
fi

rm -f "$ZIP_PATH"
(
  cd "$STAGE_DIR"
  COPYFILE_DISABLE=1 /usr/bin/ditto -c -k --norsrc . "$ZIP_PATH"
)

if [[ "$MACOS_NOTARIZE" == "1" ]]; then
  if [[ -z "$APPLE_ID" || -z "$APPLE_TEAM_ID" || -z "$APPLE_APP_SPECIFIC_PASSWORD" ]]; then
    echo "macOS notarization requires APPLE_ID, APPLE_TEAM_ID, and APPLE_APP_SPECIFIC_PASSWORD" >&2
    exit 1
  fi
  xcrun notarytool submit "$ZIP_PATH" \
    --apple-id "$APPLE_ID" \
    --team-id "$APPLE_TEAM_ID" \
    --password "$APPLE_APP_SPECIFIC_PASSWORD" \
    --wait
  xcrun stapler staple "$APP_BUNDLE"
  rm -f "$ZIP_PATH"
  (
    cd "$STAGE_DIR"
    COPYFILE_DISABLE=1 /usr/bin/ditto -c -k --norsrc . "$ZIP_PATH"
  )
fi

rm -rf "$PKG_ROOT" "$PKG_SCRIPTS" "$PKG_COMPONENT" "$PKG_PATH"
mkdir -p "$PKG_ROOT/Applications" "$PKG_ROOT/Library/Application Support/Humungousaur" "$PKG_ROOT/usr/local/bin" "$PKG_SCRIPTS"
cp -R "$APP_BUNDLE" "$PKG_ROOT/Applications/Humungousaur.app"
cp -R "$RUNTIME_SOURCE_DIR" "$PKG_ROOT/Library/Application Support/Humungousaur/runtime-source"
cat >"$PKG_ROOT/usr/local/bin/humungousaur-bootstrap" <<'BOOTSTRAP'
#!/usr/bin/env bash
set -euo pipefail
exec /usr/bin/env python3 "/Library/Application Support/Humungousaur/runtime-source/script/bootstrap_runtime.py" \
  --source "/Library/Application Support/Humungousaur/runtime-source" \
  --data-root "/Library/Application Support/Humungousaur"
BOOTSTRAP
chmod 0755 "$PKG_ROOT/usr/local/bin/humungousaur-bootstrap"
cat >"$PKG_SCRIPTS/postinstall" <<'POSTINSTALL'
#!/usr/bin/env bash
set -u
LOG="/Library/Application Support/Humungousaur/install.log"
mkdir -p "/Library/Application Support/Humungousaur"
if /usr/bin/env python3 - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 12) else 1)
PY
then
  /usr/local/bin/humungousaur-bootstrap --quiet >>"$LOG" 2>&1 || {
    echo "Runtime bootstrap failed; rerun /usr/local/bin/humungousaur-bootstrap after installing Python 3.12+." >>"$LOG"
  }
else
  echo "Python 3.12+ is required for automatic runtime setup. Install Python 3.12+, then run /usr/local/bin/humungousaur-bootstrap." >>"$LOG"
fi
exit 0
POSTINSTALL
chmod 0755 "$PKG_SCRIPTS/postinstall"
pkgbuild \
  --root "$PKG_ROOT" \
  --scripts "$PKG_SCRIPTS" \
  --identifier "$PKG_IDENTIFIER" \
  --version "$PROJECT_VERSION" \
  --install-location "/" \
  "$PKG_COMPONENT"
if [[ -n "$MACOS_INSTALLER_IDENTITY" ]]; then
  productbuild --sign "$MACOS_INSTALLER_IDENTITY" --package "$PKG_COMPONENT" "$PKG_PATH"
else
  productbuild --package "$PKG_COMPONENT" "$PKG_PATH"
fi

if [[ "$MACOS_NOTARIZE" == "1" ]]; then
  xcrun notarytool submit "$PKG_PATH" \
    --apple-id "$APPLE_ID" \
    --team-id "$APPLE_TEAM_ID" \
    --password "$APPLE_APP_SPECIFIC_PASSWORD" \
    --wait
  xcrun stapler staple "$PKG_PATH"
fi

(
  cd "$RELEASE_DIR"
  shasum -a 256 ./*.zip ./*.pkg | sed 's#  ./#  #' > checksums.txt
)

echo "Created $ZIP_PATH"
echo "Created $PKG_PATH"
