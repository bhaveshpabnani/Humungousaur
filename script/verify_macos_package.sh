#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ZIP_PATH="$ROOT_DIR/artifacts/release/Humungousaur-macOS.zip"
CHECKSUM_PATH="$ROOT_DIR/artifacts/release/checksums.txt"
REQUIRE_SIGNATURE=0
REQUIRE_NOTARIZATION=0
PROJECT_VERSION="$(awk -F'"' '/^version[[:space:]]*=/ { print $2; exit }' "$ROOT_DIR/pyproject.toml")"
if [[ -z "$PROJECT_VERSION" ]]; then
  echo "Unable to read project.version from pyproject.toml" >&2
  exit 1
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --zip-path)
      ZIP_PATH="$2"
      shift 2
      ;;
    --checksums)
      CHECKSUM_PATH="$2"
      shift 2
      ;;
    --require-signature)
      REQUIRE_SIGNATURE=1
      shift
      ;;
    --require-notarization)
      REQUIRE_SIGNATURE=1
      REQUIRE_NOTARIZATION=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ ! -f "$ZIP_PATH" ]]; then
  echo "Missing macOS release zip: $ZIP_PATH" >&2
  exit 1
fi

ZIP_ENTRIES="$(/usr/bin/unzip -Z1 "$ZIP_PATH")"
while IFS= read -r entry; do
  normalized="${entry//\\//}"
  basename="${normalized##*/}"
  if [[ "$normalized" == /* || "$normalized" == ../* || "$normalized" == */../* || "$normalized" == __MACOSX/* || "$normalized" == */__MACOSX/* || "$basename" == ".DS_Store" || "$basename" == ._* ]]; then
    echo "macOS package contains unsafe or platform metadata zip entry: $entry" >&2
    exit 1
  fi
done <<<"$ZIP_ENTRIES"

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

/usr/bin/ditto -x -k "$ZIP_PATH" "$TMP_DIR"

APP_BUNDLE="$TMP_DIR/Humungousaur.app"
APP_BINARY="$APP_BUNDLE/Contents/MacOS/HumungousaurMac"
INFO_PLIST="$APP_BUNDLE/Contents/Info.plist"
APP_ICON="$APP_BUNDLE/Contents/Resources/HumungousaurIcon.icns"
APP_RESOURCE_BUNDLE="$APP_BUNDLE/Contents/Resources/HumungousaurMac_HumungousaurMac.bundle"
STATUS_BAR_ICON="$APP_RESOURCE_BUNDLE/humungousaur-logo-mark-32.png"
INSTALL_DOC="$TMP_DIR/INSTALL.txt"

for path in "$INSTALL_DOC" "$APP_BUNDLE" "$APP_BINARY" "$INFO_PLIST" "$APP_ICON" "$APP_RESOURCE_BUNDLE" "$STATUS_BAR_ICON"; do
  if [[ ! -e "$path" ]]; then
    echo "macOS package is missing $(basename "$path")" >&2
    exit 1
  fi
done

/usr/bin/plutil -lint "$INFO_PLIST" >/dev/null
PLIST_ICON="$(/usr/bin/plutil -extract CFBundleIconFile raw "$INFO_PLIST")"
if [[ "$PLIST_ICON" != "HumungousaurIcon" ]]; then
  echo "macOS Info.plist icon mismatch. Expected HumungousaurIcon, got $PLIST_ICON" >&2
  exit 1
fi
PLIST_VERSION="$(/usr/bin/plutil -extract CFBundleShortVersionString raw "$INFO_PLIST")"
PLIST_BUILD="$(/usr/bin/plutil -extract CFBundleVersion raw "$INFO_PLIST")"
if [[ "$PLIST_VERSION" != "$PROJECT_VERSION" || "$PLIST_BUILD" != "$PROJECT_VERSION" ]]; then
  echo "macOS Info.plist version mismatch. Expected $PROJECT_VERSION, got version=$PLIST_VERSION build=$PLIST_BUILD" >&2
  exit 1
fi

for expected in \
  "Version: $PROJECT_VERSION" \
  'python3 -m pip install -e ".[browser,pdf,ocr,office]"' \
  "python3 -m humungousaur serve" \
  "http://127.0.0.1:8765" \
  "OPENAI_API_KEY" \
  "DEEPGRAM_API_KEY" \
  "channels, voice, autonomy, and approvals" \
  "./script/verify_macos_package.sh"; do
  if ! grep -Fq "$expected" "$INSTALL_DOC"; then
    echo "macOS INSTALL.txt is missing expected setup text: $expected" >&2
    exit 1
  fi
done

if [[ -f "$CHECKSUM_PATH" ]]; then
  EXPECTED_HASH="$(awk '$2 == "Humungousaur-macOS.zip" { print $1 }' "$CHECKSUM_PATH")"
  ACTUAL_HASH="$(shasum -a 256 "$ZIP_PATH" | awk '{ print $1 }')"
  if [[ -z "$EXPECTED_HASH" || "$EXPECTED_HASH" != "$ACTUAL_HASH" ]]; then
    echo "macOS checksum mismatch or missing row in $CHECKSUM_PATH" >&2
    exit 1
  fi
fi

if [[ "$REQUIRE_SIGNATURE" == "1" ]]; then
  codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"
  spctl -a -t exec -vv "$APP_BUNDLE"
fi

if [[ "$REQUIRE_NOTARIZATION" == "1" ]]; then
  xcrun stapler validate "$APP_BUNDLE"
fi

echo "Verified $ZIP_PATH"
