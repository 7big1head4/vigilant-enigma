# PRD: Comprehensive Claude Knowledge Base + Automation System (v2 — Dashboard Edition)

**Version:** 2.0
**Date:** 2026-04-27
**Owner:** Jeffrey
**Status:** Active

## Problem Statement
I spend too much time re-explaining my preferences, style, and context to Claude every session. I want a single, self-improving system where I can give vague prompts and Claude automatically clarifies to 100%, executes at elite level, remembers everything, and gets smarter over time — with almost zero ongoing effort from me. The system must also include a live dashboard that is always up-to-date so I can see the current state at a glance.

## Goals
- Turn Claude into a true "dominant force" partner that requires minimal input from me
- Create a living knowledge base that grows automatically
- Add automation so common tasks (new projects, summaries, structure maintenance) are one-command
- Add a real-time dashboard that is always current and "running on point"
- Keep token usage extremely low while maximizing intelligence and consistency

## Success Metrics
- Launch a new complex project with 1 vague sentence + 3 short answers
- Claude never forgets preferences or past decisions
- All significant work is automatically documented in Outputs/
- Dashboard regenerates in <5 seconds and always reflects latest state
- Token usage per session stays under 2k for core instructions
- <5 minutes per week maintaining the system

## Core Components
1. `ABOUT_ME/profile.md` — Permanent identity + standing instructions
2. `Projects/` — Structured project briefs with standardized template
3. `Templates/` — 5 high-leverage reusable prompts
4. `Outputs/` — Single source of truth with strict naming + automatic daily summaries
5. `scripts/` — Automation layer (new-project, daily-summary, weekly-review, dashboard-update)
6. `Dashboard/` — Live auto-updating overview of entire system

## Constraints
- Must work with both claude.ai Projects and Claude Code
- Keep total injected context minimal
- All scripts must be simple bash (no complex dependencies)
- Dashboard must be pure markdown (no external dependencies)

## Out of Scope (v2)
- Web UI
- Integration with external tools (Notion, Linear, etc.)
- Multi-user support

## Milestones
- [x] Profile + memory system (v1.0)
- [x] Templates + Projects system
- [x] Weekly-review script (v1.1)
- [x] Dashboard-update script (v2.0)
- [ ] Backup/sync script (v2.1)
- [ ] Test full flow with 3 real projects

## Decisions Locked
- Dashboard: single file (`Dashboard/index.md`) — no splits
- Refresh: on-demand only (`./scripts/dashboard-update.sh`) — no auto/cron

**Approved by:** Jeffrey — 2026-04-27
