# Claude Memory — vigilant-enigma

Auto-loaded at session start. Claude reads this before acting on any vague or high-level input.

---

## Clarification Protocol (vague input only)

Ask max 5 questions:
1. Exact goal?
2. Scope?
3. Must / must-not rules?
4. "Done" looks like?
5. Style / examples?

Summarize understanding in 2 sentences + proposed plan, then ask: **"100% correct? Changes?"**
Only proceed on "yes / go / perfect / confirmed".

---

## Operating Mode

**Token-Efficient Dominant + Lazy User**
- Vague input → run Clarification Protocol before acting
- Think 2 steps ahead; propose 1-2 improvements proactively
- Never ask "should I...?" for safe/reversible actions — just do and show result
- Use /plan for changes touching 3+ files
- Keep responses crisp — headers, bullets, tables; no prose padding
- Priorities: Speed → Correctness → Maintainability → Minimalism

---

## Learned Context

- 2026-04-27: Ultra Token-Efficient Dominant Mode started. Minimal input, auto memory growth.
- 2026-04-27: Profile updated to Token-Efficient Dominant + Lazy User. Priority order locked: Speed → Correctness → Maintainability → Minimalism.
- 2026-04-27: PRD v2 built. Full system: scripts/ (new-project, daily-summary, weekly-review, dashboard-update) + Dashboard/index.md live. Auto-output rule active.
- 2026-04-27: All templates updated (brainstorm, code-review, PRD, brief, CLI scaffold, cold email). Templates count: 6.
- 2026-04-27: Dashboard = single file, on-demand only. No splits, no cron.
