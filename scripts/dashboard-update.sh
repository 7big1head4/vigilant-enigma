#!/usr/bin/env bash
# Regenerates Dashboard/index.md with live system state
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DASHBOARD="$REPO_ROOT/Dashboard/index.md"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M %Z")

mkdir -p "$REPO_ROOT/Dashboard"

# --- Active projects (has brief.md) ---
ACTIVE_PROJECTS=""
while IFS= read -r brief; do
  rel="${brief#$REPO_ROOT/Projects/}"
  project="${rel%/brief.md}"
  type="${project%%/*}"
  name="${project#*/}"
  goal=$(grep -m1 "One-Sentence Goal:" "$brief" 2>/dev/null | sed 's/.*Goal: *//' | xargs)
  ACTIVE_PROJECTS+="- **$name** ($type)${goal:+ — $goal}\n"
done < <(find "$REPO_ROOT/Projects" -name "brief.md" | sort)
[[ -z "$ACTIVE_PROJECTS" ]] && ACTIVE_PROJECTS="- (no active projects)\n"

PROJECT_COUNT=$(find "$REPO_ROOT/Projects" -name "brief.md" | wc -l | xargs)
SW_COUNT=$(find "$REPO_ROOT/Projects/software" -name "brief.md" 2>/dev/null | wc -l | xargs)
BIZ_COUNT=$(find "$REPO_ROOT/Projects/business" -name "brief.md" 2>/dev/null | wc -l | xargs)
PER_COUNT=$(find "$REPO_ROOT/Projects/personal" -name "brief.md" 2>/dev/null | wc -l | xargs)

# --- Recent outputs (last 7 days) ---
RECENT_OUTPUTS=""
while IFS= read -r f; do
  rel="${f#$REPO_ROOT/}"
  RECENT_OUTPUTS+="- \`$rel\`\n"
done < <(find "$REPO_ROOT/Outputs" -name "*.md" -mtime -7 \
  -not -name "README.md" | sort -r | head -10)
[[ -z "$RECENT_OUTPUTS" ]] && RECENT_OUTPUTS="- (no outputs in last 7 days)\n"

OUTPUT_WEEK=$(find "$REPO_ROOT/Outputs" -name "*.md" -mtime -7 -not -name "README.md" | wc -l | xargs)

# --- Memory stats ---
MEMORY_FILE="$REPO_ROOT/.claude/memory.md"
MEMORY_LINES=$(wc -l < "$MEMORY_FILE" 2>/dev/null || echo 0)
LEARNED_COUNT=$(grep -c "^- " "$MEMORY_FILE" 2>/dev/null || echo 0)

# --- Template count ---
TEMPLATE_COUNT=$(find "$REPO_ROOT/Templates" -name "*.md" -not -name "README.md" | wc -l | xargs)

# --- Open actions ---
OPEN_ACTIONS=""
while IFS= read -r line; do
  OPEN_ACTIONS+="- $line\n"
done < <(grep -r "^\- \[ \]" "$REPO_ROOT/Projects" 2>/dev/null | sed 's|.*\[ \] ||' | head -10)
[[ -z "$OPEN_ACTIONS" ]] && OPEN_ACTIONS="- (none)\n"

# --- Health score (0–100) ---
SCORE=0
[[ -f "$REPO_ROOT/ABOUT_ME/profile.md" ]] && SCORE=$((SCORE + 20))
[[ "$MEMORY_LINES" -gt 5 ]] && SCORE=$((SCORE + 20))
[[ "$PROJECT_COUNT" -gt 0 ]] && SCORE=$((SCORE + 20))
[[ "$OUTPUT_WEEK" -gt 0 ]] && SCORE=$((SCORE + 20))
[[ "$TEMPLATE_COUNT" -ge 5 ]] && SCORE=$((SCORE + 20))

# --- Last weekly review ---
LAST_REVIEW=$(find "$REPO_ROOT/Outputs/weekly-reviews" -name "*.md" 2>/dev/null \
  | sort -r | head -1 | xargs basename 2>/dev/null | sed 's/-weekly-review.md//' || echo "never")

cat > "$DASHBOARD" <<EOF
# Claude System Dashboard

**Last Updated:** $TIMESTAMP
**System Status:** $([ "$SCORE" -ge 80 ] && echo "✅ All green" || echo "⚠️  Needs attention")

---

## Quick Stats

| Metric | Value |
|---|---|
| Total Projects | $PROJECT_COUNT ($SW_COUNT software / $BIZ_COUNT business / $PER_COUNT personal) |
| Outputs This Week | $OUTPUT_WEEK files |
| Memory Entries | $LEARNED_COUNT rules/preferences |
| Templates | $TEMPLATE_COUNT |
| Last Weekly Review | $LAST_REVIEW |
| Dashboard Health Score | $SCORE/100 |

---

## Active Projects

$(echo -e "$ACTIVE_PROJECTS")

---

## Recent Outputs (last 7 days)

$(echo -e "$RECENT_OUTPUTS")

---

## Open Actions

$(echo -e "$OPEN_ACTIONS")

---

## Quick Commands

\`\`\`bash
./scripts/new-project.sh software my-new-idea "Build X"
./scripts/daily-summary.sh
./scripts/weekly-review.sh
./scripts/dashboard-update.sh
\`\`\`
EOF

echo "Dashboard updated: $DASHBOARD (health: $SCORE/100)"
