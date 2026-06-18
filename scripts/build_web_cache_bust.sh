#!/usr/bin/env bash
# =============================================================================
# build_web_cache_bust.sh — cache-busting build helper for vibecomfy web assets
#
# Copies the full vibecomfy/comfy_nodes/web/ ESM tree into a versioned
# directory under web_dist/ so relative ESM imports (./foo.js) keep working
# when served from a static host like ComfyUI's web serving.
#
# Usage:
#   bash scripts/build_web_cache_bust.sh [--sha] [--hash] [--dir <name>]
#
#   --sha    Use the current Git commit SHA as the version tag (default).
#   --hash   Use a content hash (sha256 over all web/ files) as the version tag.
#   --dir    Use an explicit directory name.
#
# Output:
#   vibecomfy/comfy_nodes/web_dist/<tag>/
#
# The web_dist/ tree is generated output and should not be committed.
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB_SRC="${REPO_ROOT}/vibecomfy/comfy_nodes/web"
WEB_DIST="${REPO_ROOT}/vibecomfy/comfy_nodes/web_dist"

# --- helpers ---

get_git_sha() {
  if command -v git &>/dev/null && git -C "${REPO_ROOT}" rev-parse --git-dir &>/dev/null; then
    git -C "${REPO_ROOT}" rev-parse HEAD
  else
    echo "error: not a git repository or git not available" >&2
    return 1
  fi
}

get_content_hash() {
  # sha256 over all non-bak web/ files, sorted for determinism
  local tmp
  tmp="$(mktemp)"
  # shellcheck disable=SC2044
  for f in $(find "${WEB_SRC}" -maxdepth 1 -type f -name '*.js' -o -name '*.png' -o -name '*.css' -o -name '*.json' | sort); do
    shasum -a 256 "$f" >> "$tmp"
  done
  # Take the first 12 hex chars of the hash-of-hashes
  local hash
  hash="$(shasum -a 256 "$tmp" | cut -d' ' -f1 | cut -c1-12)"
  rm -f "$tmp"
  echo "$hash"
}

# --- parse args ---

TAG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --sha)   TAG="$(get_git_sha)" ;;
    --hash)  TAG="$(get_content_hash)" ;;
    --dir)   shift; TAG="$1" ;;
    *)       echo "Unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done

if [[ -z "${TAG}" ]]; then
  # default: git sha, fallback to content hash
  TAG="$(get_git_sha 2>/dev/null || get_content_hash)"
fi

# --- copy ---

DEST="${WEB_DIST}/${TAG}"

if [[ -d "${DEST}" ]]; then
  echo "[build_web_cache_bust] Destination already exists: ${DEST}" >&2
  echo "[build_web_cache_bust] Remove it first if you want a fresh copy:" >&2
  echo "  rm -rf ${DEST}" >&2
  exit 1
fi

echo "[build_web_cache_bust] Tag:  ${TAG}"
echo "[build_web_cache_bust] Src:  ${WEB_SRC}"
echo "[build_web_cache_bust] Dest: ${DEST}"

mkdir -p "${DEST}"

# Copy all distributable web assets (exclude .bak files)
for f in "${WEB_SRC}"/*; do
  base="$(basename "$f")"
  case "${base}" in
    *.bak|*~|*.orig|*.tmp) continue ;;
  esac
  cp "${f}" "${DEST}/"
done

# Verify the copy
COPIED_COUNT="$(find "${DEST}" -maxdepth 1 -type f | wc -l | tr -d ' ')"
echo "[build_web_cache_bust] Copied ${COPIED_COUNT} files."
echo "[build_web_cache_bust] Done."

# --- developer note ---
# To serve these assets, point ComfyUI or your static server at:
#   vibecomfy/comfy_nodes/web_dist/<tag>/
#
# Each build produces a new tag, so clients fetching the old URL will use
# their cached copy while new deploys get the fresh version via the changed
# path. Clean up old tags periodically to reclaim disk space.
