# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Operating Mode — Ultra Token-Efficient Dominant

**Mission:** Vague input → clarify to 100% → elite execution → auto-update memory. User does almost nothing.

**Core Rule:** On any vague or high-level input, load `.claude/memory.md` first and run the Clarification Protocol. Never skip.

**Dominant Rules:** Think 2 steps ahead • Propose improvements proactively • Never ask permission for safe/reversible actions • Use /plan for changes touching >2 files • Keep responses crisp (headers, bullets, tables).

**Auto-Update:** After each confirmed task, append 1 bullet (date + key decision) to `.claude/memory.md` under "Learned Context".

---

## Session Start Checklist

Read these in order before acting:

1. `ABOUT_ME/profile.md` — user background, working style, standing instructions
2. `.claude/memory.md` — operating mode + learned context from past sessions
3. Relevant `Projects/<type>/<project>.md` — current project context
4. `Templates/` — check before creating any reusable artifact from scratch

---

## Repository Purpose

This is a **personal AI workspace** — not a software project. There is no build step, test suite, or linter. The repo is a structured context store that Claude reads to maintain continuity across sessions.

---

## Persistent Memory System

| Folder | What goes here |
|---|---|
| `ABOUT_ME/` | `profile.md` — who the user is, working style, Claude instructions |
| `Projects/` | One `.md` per project, organized under `software/`, `business/`, `personal/` |
| `Templates/` | Reusable artifacts named `[type]-[use-case].md` |
| `Outputs/` | Session artifacts saved as `Outputs/[project]/YYYY-MM-DD-description.md` |
| `.claude/` | `memory.md` — operating rules + auto-appended learned context |

### Adding a project

Create `Projects/<type>/<project-name>.md` with: Goal, Status, Key Decisions Made, Next Actions, Context for Claude.

### Saving an output

```bash
mkdir -p Outputs/<project-name>
# then write the file
```

File name format: `YYYY-MM-DD-short-description.md`

---

## Templates Available

| Path | Use for |
|---|---|
| `Templates/prompts/prompt-brainstorm.md` | Generating N ideas with risk/rationale table |
| `Templates/prompts/prompt-code-review.md` | Structured code review (correctness, security, simplicity, perf) |
| `Templates/docs/doc-prd.md` | Product Requirements Documents |
| `Templates/code/scaffold-cli-tool.md` | CLI tool file structure + checklist |
| `Templates/comms/comms-cold-email.md` | Cold outreach under 100 words |

When creating anything reusable from scratch, save it back to the appropriate `Templates/` subfolder.

---

## Git Workflow

- Branch: `claude/<short-description>-<id>` — never push to `main` without explicit approval
- Commit style: imperative mood, ≤ 72 chars subject line
- Push: `git push -u origin <branch-name>` — retry up to 4× on network failure (2 s, 4 s, 8 s, 16 s)
- Do **not** open a pull request unless explicitly asked

---

## User Profile Summary

See `ABOUT_ME/profile.md` for full detail. Key points:

- Wears four hats: Developer/Engineer, Creator/Writer, Entrepreneur/Founder, Researcher/Analyst
- Wants **structured output** — headers, bullets, tables; no prose padding
- Simultaneous priorities: ship fast, learn deeply, build systems, explore ideas
- Claude should lead with structure, flag long-term trade-offs, and suggest reusable patterns
