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

# --- Open actions ---
OPEN_ACTIONS=""
while IFS= read -r line; do
  src=$(echo "$line" | cut -d: -f1 | sed "s|$REPO_ROOT/Projects/||" | sed 's|/brief.md||')
  task=$(echo "$line" | sed 's/.*\[ \] //')
  OPEN_ACTIONS+="- [$src] $task\n"
done < <(grep -rn "^\- \[ \]" "$REPO_ROOT/Projects" 2>/dev/null | head -10)
[[ -z "$OPEN_ACTIONS" ]] && OPEN_ACTIONS="- (none)\n"

# --- Recent outputs (48h) ---
RECENT=""
while IFS= read -r f; do
  rel="${f#$REPO_ROOT/}"
  RECENT+="- \`$rel\`\n"
done < <(find "$REPO_ROOT/Outputs" -name "*.md" -mtime -2 \
  -not -name "README.md" | sort -r | head -5)
[[ -z "$RECENT" ]] && RECENT="- (none)\n"

# --- Memory health ---
LEARNED=$(grep -c "^- " "$REPO_ROOT/.claude/memory.md" 2>/dev/null || echo 0)

{
cat <<EOF
# Daily Brief — $DOW, $DATE

---

## System
- Active projects: $(find "$REPO_ROOT/Projects" -name "brief.md" | wc -l | xargs)
- Outputs (48h): $(find "$REPO_ROOT/Outputs" -name "*.md" -mtime -2 -not -name "README.md" 2>/dev/null | wc -l | xargs)
- Memory entries: $LEARNED

## Active Projects
$(echo -e "$ACTIVE_PROJECTS")
## Open Actions
$(echo -e "$OPEN_ACTIONS")
## Recent Outputs (48h)
$(echo -e "$RECENT")
---

## 🌍 World Events
> Top 5-7 stories from the last 24h. Focus: tech, markets, geopolitics. One line each.

1.
2.
3.
4.
5.

---

## 📍 Orange County — Local Pulse
> Key local news, events, or opportunities in OC from the last 24h.

-
-

---

## 🪙 Crypto Ticker
> BTC, ETH, SOL prices + % change. Any easy plays or momentum moves today.

| Coin | Price | 24h % |
|------|-------|-------|
| BTC  |       |       |
| ETH  |       |       |
| SOL  |       |       |

**Easy plays today:**
1.
2.

---

## 🚗 Tesla Daily Pulse
> Price, key moves last 24-48h, Cybercab/Optimus/FSD progress, easy plays.

**Current Price:** \$___ (___% today)

**Key Moves:**
-

**Easy Plays Today:**
1.
2.

---

## 🔍 Underserved / Niche Opportunities
> One overlooked angle, gap in the market, or emerging trend worth watching today.

-
-

---

## 💰 Easy Money Opportunities
> Low-effort, fast-turnaround plays: freelance, arbitrage, content, flips, etc.

1.
2.
3.

---

## ☑️ My 9 AM Action Plan
> Top 3 things to do today based on open actions + opportunities above.

1. [ ]
2. [ ]
3. [ ]

---
Run \`./scripts/dashboard-update.sh\` for full system view.
EOF
} | tee "$OUTFILE"
