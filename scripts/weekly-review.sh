#!/usr/bin/env bash
# Generates a weekly review from the last 7 days of git activity and outputs
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATE=$(date +%Y-%m-%d)
WEEK_START=$(date -d "7 days ago" +%Y-%m-%d 2>/dev/null || date -v-7d +%Y-%m-%d)
OUTDIR="$REPO_ROOT/Outputs/weekly-reviews"
OUTFILE="$OUTDIR/$DATE-weekly-review.md"

mkdir -p "$OUTDIR"

COMMITS=$(git -C "$REPO_ROOT" log --since="$WEEK_START" \
  --pretty=format:"- %ad %s" --date=short 2>/dev/null || echo "- (no commits this week)")

NEW_OUTPUTS=$(find "$REPO_ROOT/Outputs" -name "*.md" -newer "$REPO_ROOT/Outputs/README.md" \
  -not -path "*/weekly-reviews/*" -not -path "*/daily-summaries/*" 2>/dev/null \
  | sort | sed "s|$REPO_ROOT/||" | sed 's/^/- /' || echo "- (none)")

ACTIVE_PROJECTS=$(find "$REPO_ROOT/Projects" -name "brief.md" 2>/dev/null \
  | sort | sed "s|$REPO_ROOT/Projects/||" | sed 's|/brief.md||' | sed 's/^/- /' || echo "- (none)")

MEMORY_LINES=$(wc -l < "$REPO_ROOT/.claude/memory.md" 2>/dev/null || echo 0)

cat > "$OUTFILE" <<EOF
# Weekly Review — $DATE (covering $WEEK_START → $DATE)

## Commits This Week
$COMMITS

## Outputs Created
$NEW_OUTPUTS

## Active Projects
$ACTIVE_PROJECTS

## Memory File Size
$MEMORY_LINES lines in .claude/memory.md

## What Worked Well


## What to Improve


## Decisions to Lock In


## Next Week Priorities
1.
2.
3.
EOF

echo "Saved: $OUTFILE"
