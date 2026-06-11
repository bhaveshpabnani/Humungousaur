#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="$ROOT_DIR"
DATA_DIR="$ROOT_DIR/artifacts"
WATCH_ARGS=()
PASSTHROUGH=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workspace)
      WORKSPACE="$2"
      shift 2
      ;;
    --data-dir)
      DATA_DIR="$2"
      shift 2
      ;;
    --watch)
      WATCH_ARGS+=(--watch "$2")
      shift 2
      ;;
    *)
      PASSTHROUGH+=("$1")
      shift
      ;;
  esac
done

if [[ ${#WATCH_ARGS[@]} -eq 0 ]]; then
  WATCH_ARGS+=(--watch "$WORKSPACE")
fi

exec swift run --package-path "$ROOT_DIR/native_collectors/macos" HumungousaurMacCollectorHost \
  --workspace "$WORKSPACE" \
  --data-dir "$DATA_DIR" \
  "${WATCH_ARGS[@]}" \
  "${PASSTHROUGH[@]}"
