#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
APP_NAME="HumungousaurMac"
BUNDLE_ID="ai.humungousaur.mac"
MIN_SYSTEM_VERSION="14.0"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MACOS_DIR="$ROOT_DIR/apps/macos"
DIST_DIR="$ROOT_DIR/dist"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
APP_CONTENTS="$APP_BUNDLE/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_RESOURCES="$APP_CONTENTS/Resources"
APP_BINARY="$APP_MACOS/$APP_NAME"
INFO_PLIST="$APP_CONTENTS/Info.plist"
PROJECT_VERSION="$(awk -F'"' '/^version[[:space:]]*=/ { print $2; exit }' "$ROOT_DIR/pyproject.toml")"
if [[ -z "$PROJECT_VERSION" ]]; then
  echo "Unable to read project.version from pyproject.toml" >&2
  exit 1
fi

pkill -x "$APP_NAME" >/dev/null 2>&1 || true

swift build --package-path "$MACOS_DIR"
BUILD_DIR="$(swift build --package-path "$MACOS_DIR" --show-bin-path)"
BUILD_BINARY="$BUILD_DIR/$APP_NAME"

rm -rf "$APP_BUNDLE"
mkdir -p "$APP_MACOS" "$APP_RESOURCES"
cp "$BUILD_BINARY" "$APP_BINARY"
chmod +x "$APP_BINARY"
cp "$MACOS_DIR/Sources/Resources/HumungousaurIcon.icns" "$APP_RESOURCES/HumungousaurIcon.icns"
find "$BUILD_DIR" -maxdepth 1 -type d \( -name "*.resources" -o -name "*.bundle" \) -exec cp -R {} "$APP_RESOURCES/" \;

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
  <string>Humungousaur</string>
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

open_app() {
  /usr/bin/open -n "$APP_BUNDLE"
}

case "$MODE" in
  run)
    open_app
    ;;
  --debug|debug)
    lldb -- "$APP_BINARY"
    ;;
  --logs|logs)
    open_app
    /usr/bin/log stream --info --style compact --predicate "process == \"$APP_NAME\""
    ;;
  --telemetry|telemetry)
    open_app
    /usr/bin/log stream --info --style compact --predicate "subsystem == \"$BUNDLE_ID\""
    ;;
  --verify|verify)
    open_app
    sleep 1
    pgrep -x "$APP_NAME" >/dev/null
    ;;
  *)
    echo "usage: $0 [run|--debug|--logs|--telemetry|--verify]" >&2
    exit 2
    ;;
esac
