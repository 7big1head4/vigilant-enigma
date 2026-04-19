# Projects

Each active project lives in its own subfolder. Claude should read the relevant project file at the start of any session focused on that project.

## Structure

```
Projects/
├── software/    # Apps, tools, scripts, codebases
├── business/    # Strategy, plans, SOPs, pitches
└── personal/    # Learning goals, side projects, personal productivity
```

## How to Add a Project

Create a new `.md` file (or subfolder for complex projects) using this template:

```md
# Project Name

## Goal
One sentence: what does success look like?

## Status
Current phase and any blockers.

## Key Decisions Made
- Decision 1 — rationale
- Decision 2 — rationale

## Next Actions
- [ ] Task 1
- [ ] Task 2

## Context for Claude
Anything Claude needs to know to pick up where we left off.
```
