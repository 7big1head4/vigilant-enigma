**Project Name:** govcon-revenue
**Type:** business
**One-Sentence Goal:** Build a multi-source govt contract/grant/SBIR scanner, form an LLC from scratch, and turn evidence-based opportunities into paid contracts on a <$1k bootstrap budget.

**Success Looks Like (measurable):**
- Scanner ingests SAM.gov + Grants.gov + at least one state portal (Cal eProcure) + SBIR.gov daily, with AI filtering for fit
- LLC formed (state TBD, target ≤ $300 setup), EIN issued, SAM.gov/UEI active, capability statement v1 drafted
- ≥ 5 qualified opportunities surfaced per week (matched to capability + bid feasibility)
- First micro-purchase or sub-contract win within 90 days
- Total spend ≤ $1,000 for first 12 months (filing fees + registered agent + minimal tooling)

**Hard Constraints / Must-Nots:**
- Bootstrap only — no debt, no equity, no founders' fees
- Nights/weekends time budget — automation > manual labor wherever possible
- No misrepresentation of capabilities or past performance
- All compliance items (SAM, UEI, NAICS, set-asides) handled correctly the first time
- Capability/NAICS choice is data-driven — pick after 2 weeks of scanner output, not before

**Current State (what already exists):**
- No LLC yet, no EIN, no SAM/UEI, no capability statement
- Pi 5 setup in progress (could host the scanner — kills hosting cost)
- Claude API access (already used for rpi5-ai-pentester)

**First Action I Want:**
Build a complete 12-week roadmap covering: scanner architecture + MVP, LLC formation playbook (state choice, filing, EIN, SAM/UEI), capability statement template, first-bid playbook, weekly review cadence.

**Priority:** High
**Deadline (if any):** First contract win in 90 days

## Open Actions
- [ ] Pick LLC state (Wyoming vs home state vs NM) and file articles
- [ ] Get EIN from IRS (free, 1 day)
- [ ] Register UEI on SAM.gov (free, 2-4 weeks lead time — start immediately)
- [ ] Build scanner v1: SAM.gov + Grants.gov + SBIR.gov ingestion
- [ ] Add Cal eProcure (state portal) to scanner
- [ ] Wire AI filtering (Claude) to score opportunities by fit
- [ ] After 2 weeks of data: pick primary NAICS + capability focus
- [ ] Draft capability statement v1
- [ ] Submit first micro-purchase bid (<$10k) or sub-contract pitch
- [ ] First win within 90 days
