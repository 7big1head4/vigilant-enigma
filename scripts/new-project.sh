#!/usr/bin/env bash
# Usage: ./scripts/new-project.sh [software|business|personal] [name] "one-sentence goal"
set -euo pipefail

TYPE=${1:?Usage: $0 [software|business|personal] [name] "goal"}
NAME=${2:?Usage: $0 [software|business|personal] [name] "goal"}
GOAL=${3:?Usage: $0 [software|business|personal] [name] "goal"}

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_DIR="$REPO_ROOT/Projects/$TYPE/$NAME"
OUTPUT_DIR="$REPO_ROOT/Outputs/$NAME"

if [[ ! "$TYPE" =~ ^(software|business|personal)$ ]]; then
  echo "Error: type must be software, business, or personal" >&2
  exit 1
fi

mkdir -p "$PROJECT_DIR" "$OUTPUT_DIR"

cat > "$PROJECT_DIR/brief.md" <<EOF
**Project Name:** $NAME
**Type:** $TYPE
**One-Sentence Goal:** $GOAL
**Success Looks Like (measurable):**
**Hard Constraints / Must-Nots:**
**Current State (what already exists):**
**First Action I Want:**
**Priority:** High / Medium / Low
**Deadline (if any):**
EOF

echo "Created:"
echo "  $PROJECT_DIR/brief.md"
echo "  $OUTPUT_DIR/"
