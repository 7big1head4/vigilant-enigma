#!/usr/bin/env bash
# Generates a daily summary from today's git activity and saves to Outputs/
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATE=$(date +%Y-%m-%d)
OUTDIR="$REPO_ROOT/Outputs/daily-summaries"
OUTFILE="$OUTDIR/$DATE-daily-summary.md"

mkdir -p "$OUTDIR"

TODAY_COMMITS=$(git -C "$REPO_ROOT" log --since="$DATE 00:00" --until="$DATE 23:59" \
  --pretty=format:"- %s" 2>/dev/null || echo "- (no commits today)")

CHANGED_FILES=$(git -C "$REPO_ROOT" diff --name-only "HEAD~1" HEAD 2>/dev/null \
  | sed 's/^/- /' || echo "- (no changes)")

cat > "$OUTFILE" <<EOF
# Daily Summary — $DATE

## What Was Done
$TODAY_COMMITS

## Files Changed
$CHANGED_FILES

## Key Decisions Made


## Next Steps


## New Rules / Preferences to Remember

EOF

echo "Saved: $OUTFILE"
