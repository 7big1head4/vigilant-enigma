#!/usr/bin/env bash
# Prints today's brief to stdout and saves to Outputs/daily-briefs/
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATE=$(date +%Y-%m-%d)
DOW=$(date +%A)
OUTDIR="$REPO_ROOT/Outputs/daily-briefs"
OUTFILE="$OUTDIR/$DATE-brief.md"
mkdir -p "$OUTDIR"

# --- Active projects ---
ACTIVE_PROJECTS=""
while IFS= read -r brief; do
  rel="${brief#$REPO_ROOT/Projects/}"
  project="${rel%/brief.md}"
  type="${project%%/*}"
  name="${project#*/}"
  goal=$(grep -m1 "One-Sentence Goal:" "$brief" 2>/dev/null | sed 's/.*Goal: *//' | xargs)
  priority=$(grep -m1 "Priority:" "$brief" 2>/dev/null | sed 's/.*Priority: *//' | xargs)
  ACTIVE_PROJECTS+="- **$name** ($type)${priority:+ [$priority]}${goal:+ — $goal}\n"
done < <(find "$REPO_ROOT/Projects" -name "brief.md" | sort)
[[ -z "$ACTIVE_PROJECTS" ]] && ACTIVE_PROJECTS="- (no active projects)\n"

# --- Open actions across all project briefs ---
OPEN_ACTIONS=""
while IFS= read -r line; do
  src=$(echo "$line" | cut -d: -f1 | sed "s|$REPO_ROOT/Projects/||" | sed 's|/brief.md||')
  task=$(echo "$line" | sed 's/.*\[ \] //')
  OPEN_ACTIONS+="- [$src] $task\n"
done < <(grep -rn "^\- \[ \]" "$REPO_ROOT/Projects" 2>/dev/null | head -10)
[[ -z "$OPEN_ACTIONS" ]] && OPEN_ACTIONS="- (no open actions)\n"

# --- Recent outputs (last 2 days) ---
RECENT=""
while IFS= read -r f; do
  rel="${f#$REPO_ROOT/}"
  RECENT+="- \`$rel\`\n"
done < <(find "$REPO_ROOT/Outputs" -name "*.md" -mtime -2 \
  -not -name "README.md" | sort -r | head -5)
[[ -z "$RECENT" ]] && RECENT="- (no outputs in last 48 hours)\n"

# --- Memory health ---
LEARNED=$(grep -c "^- " "$REPO_ROOT/.claude/memory.md" 2>/dev/null || echo 0)

{
cat <<EOF
# Daily Brief — $DOW, $DATE

## Active Projects
$(echo -e "$ACTIVE_PROJECTS")
## Open Actions
$(echo -e "$OPEN_ACTIONS")
## Recent Outputs (48h)
$(echo -e "$RECENT")
## Memory
$LEARNED learned rules/preferences in .claude/memory.md

---

## Tesla Daily Pulse
> Pull latest on Tesla — current stock price, major news from last 24-48h, Cybercab/Optimus/FSD progress, any easy plays or angles. Keep it tight and actionable.

**Current Price:** \$___ (___% today)

**Key Moves Right Now:**
-

**Easy Tesla-Related Plays Today:**
1.
2.

---
Run \`./scripts/dashboard-update.sh\` for full system view.
EOF
} | tee "$OUTFILE"
