#!/usr/bin/env bash
# Backs up the repo to a local destination via git bundle or rsync.
# Usage: ./scripts/backup-sync.sh [destination]
# Default destination: ~/claude-system-backup
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$HOME/claude-system-backup}"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)

mkdir -p "$DEST"

# --- Git bundle (portable, complete history) ---
BUNDLE="$DEST/vigilant-enigma-$TIMESTAMP.bundle"
git -C "$REPO_ROOT" bundle create "$BUNDLE" --all
echo "Bundle: $BUNDLE"

# --- Verify bundle ---
if git bundle verify "$BUNDLE" > /dev/null 2>&1; then
  echo "Verified: OK"
else
  echo "Error: bundle verification failed" >&2
  exit 2
fi

# --- Prune bundles older than 30 days ---
find "$DEST" -name "vigilant-enigma-*.bundle" -mtime +30 -delete
REMAINING=$(find "$DEST" -name "vigilant-enigma-*.bundle" | wc -l | xargs)
echo "Bundles kept: $REMAINING (30-day window)"

# --- Append to memory ---
MEMORY="$REPO_ROOT/.claude/memory.md"
echo "- $DATE: Backup created → $BUNDLE" >> "$MEMORY"

echo "Backup complete: $DEST"
