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
APP_BINARY="$APP_MACOS/$APP_NAME"
INFO_PLIST="$APP_CONTENTS/Info.plist"
ZIP_PATH="$RELEASE_DIR/Humungousaur-macOS.zip"
INSTALL_DOC="$STAGE_DIR/INSTALL.txt"
MACOS_CODESIGN_IDENTITY="${HUMUNGOUSAUR_MACOS_CODESIGN_IDENTITY:-}"
MACOS_NOTARIZE="${HUMUNGOUSAUR_MACOS_NOTARIZE:-0}"
APPLE_ID="${APPLE_ID:-}"
APPLE_TEAM_ID="${APPLE_TEAM_ID:-}"
APPLE_APP_SPECIFIC_PASSWORD="${APPLE_APP_SPECIFIC_PASSWORD:-}"
PROJECT_VERSION="$(awk -F'"' '/^version[[:space:]]*=/ { print $2; exit }' "$ROOT_DIR/pyproject.toml")"
if [[ -z "$PROJECT_VERSION" ]]; then
  echo "Unable to read project.version from pyproject.toml" >&2
  exit 1
fi

swift build --package-path "$MACOS_DIR" -c release
BUILD_BINARY="$(swift build --package-path "$MACOS_DIR" -c release --show-bin-path)/$APP_NAME"

rm -rf "$STAGE_DIR"
mkdir -p "$APP_MACOS" "$RELEASE_DIR"
cp "$BUILD_BINARY" "$APP_BINARY"
chmod +x "$APP_BINARY"

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
</dict>
</plist>
PLIST

cat >"$INSTALL_DOC" <<INSTALL
Humungousaur macOS setup
Version: $PROJECT_VERSION

1. Move Humungousaur.app to Applications.
2. From the Humungousaur repo, install the runtime into your chosen Python:
   python3 -m pip install -e ".[browser,pdf,ocr,office]"
3. Start the runtime from the app with the play button, or run:
   python3 -m humungousaur serve --workspace <repo-root> --port 8765
4. Open Settings in the app and confirm:
   - workspace path: <repo-root>
   - Python path: python3 or <repo-root>/.venv/bin/python
   - API URL: http://127.0.0.1:8765
   - provider/model: openai, groq, ollama, grok, or local-openai
   - model keys: OPENAI_API_KEY, GROQ_API_KEY, XAI_API_KEY, OLLAMA_API_KEY, or LOCAL_LLM_API_KEY
   - voice keys: DEEPGRAM_API_KEY, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL_ID
   - channel keys required by your enabled channel setup
5. Use the toolbar status menu to verify API, model, tools, runs, channels, voice, autonomy, and approvals before sending a task.

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

(
  cd "$RELEASE_DIR"
  shasum -a 256 ./*.zip | sed 's#  ./#  #' > checksums.txt
)

echo "Created $ZIP_PATH"
