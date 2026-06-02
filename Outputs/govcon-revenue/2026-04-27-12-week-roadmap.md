# GovCon Revenue — 12-Week Bootstrap Roadmap

**Date:** 2026-04-27
**Project:** govcon-revenue
**Goal:** Zero → first govt contract win in 90 days. Total spend ≤ $1,000.

---

## Critical Path Overview

```
Week 1: LLC + EIN + UEI started + Scanner v1 (SAM.gov)
Week 2: UEI processing + Scanner adds Grants.gov + SBIR.gov
Week 3: SAM active + Scanner adds Cal eProcure + AI filtering
Week 4: 2 weeks of opportunity data captured
Week 5: NAICS + capability decision (data-driven) + Capability statement v1
Week 6-8: First 5-10 bid attempts (micro-purchases + sub-pitches)
Week 9-12: Iterate, refine, land first contract
```

**Hidden critical path:** UEI takes 2-4 weeks. File it Day 3 of Week 1, not Day 1 of Week 4.

---

## Week 1 — Foundation

### LLC State Decision

| State | Filing Fee | Annual Fee | Best For |
|---|---|---|---|
| **Wyoming** | $100 | $60 | Privacy, no state income tax, NO operations there |
| **New Mexico** | $50 | $0 | Cheapest, no annual report, but less privacy |
| **Home state** | varies | varies | If you'll bid on home-state contracts (avoids foreign LLC fee) |
| ~~Delaware~~ | $90 | $300 franchise | C-corp VC track only — skip for GovCon |

**Decision rule:**
- If targeting home-state contracts → form in home state
- If federal-only → Wyoming (best privacy + cost)
- If absolute minimum cost → New Mexico

### Day-by-Day

| Day | Action | Cost |
|---|---|---|
| 1 | File LLC articles online (state filing portal) | $50–$200 |
| 1 | Set up business email: `you@yourcompany.com` (Google Workspace $7/mo or Zoho free) | $0–$7 |
| 2-3 | Wait for state confirmation (varies) | — |
| 3 | Apply for EIN online at irs.gov/EIN (instant) | $0 |
| 4 | Open business bank account (Mercury, Bluevine, or local credit union) | $0 |
| 4 | Start SAM.gov + UEI registration | $0 |
| 5-7 | Build scanner v1 (SAM.gov ingestion) — see Scanner section below | $0 |

**Week 1 budget:** ~$110–$210

---

## Week 2 — UEI Processing + Scanner Expansion

While UEI processes (passive), build:

```
scanner/
├── sources/
│   ├── sam_gov.py          # /opportunities API (free)
│   ├── grants_gov.py       # XML feed (free)
│   └── sbir_gov.py         # JSON API (free)
├── filter.py               # Keyword + NAICS pre-filter
├── ai_score.py             # Claude API: score 1-10 fit
├── store.py                # SQLite local DB
└── digest.py               # Daily summary email/markdown
```

**Stack:** Python + SQLite + Claude API. Runs on your Pi 5. Cost ≈ $0 hosting + ~$2/month Claude tokens.

**Cron on Pi:**
```
0 6 * * * cd ~/scanner && python main.py >> ~/scanner/run.log 2>&1
```

---

## Week 3 — SAM Active + State Coverage + AI Filter

- Add **Cal eProcure** scraper (state portal — California)
- Wire **AI filter**: each opportunity gets a 1-10 fit score from Claude based on capability profile (which is intentionally generic in W3 — refines after W5)
- Daily digest writes to `Outputs/govcon-revenue/YYYY-MM-DD-digest.md`
- Set notification: top-5 daily picks via email or push (ntfy.sh = free)

---

## Week 4 — Data Capture (No bidding yet)

**This is the patience week.** Collect 2 weeks of scanner output. Don't bid on anything yet.

Track per opportunity:
- NAICS code
- Set-aside type (small biz, 8(a), HUBZone, SDVOSB, WOSB)
- Award size
- Agency
- Bid deadline window
- Pre-existing past-performance requirements

---

## Week 5 — Data-Driven NAICS Decision

Run analysis:

```python
# Pseudocode
SELECT naics, COUNT(*) as opps, AVG(award_size) as avg_size
FROM opportunities
WHERE ai_score >= 7 AND set_aside IN ('SBA', 'small biz')
GROUP BY naics
ORDER BY opps DESC LIMIT 10;
```

**Pick the NAICS where:**
1. Volume of fit-7+ opportunities is highest
2. Average award size is reasonable for solo work ($10k–$250k sweet spot)
3. Past-performance bar is achievable (avoid "5 prior similar contracts" requirements)

### Capability Statement v1

One-page PDF, 5 sections:

| Section | Content |
|---|---|
| Header | LLC name, UEI, CAGE code, NAICS codes, contact, business email, address |
| Core Competencies | 4-6 bullet capabilities — concrete, not buzzwords |
| Differentiators | 2-3 things that make you different (speed, AI-native, certifications) |
| Past Performance | Even small/personal projects count if accurately described |
| Corporate Data | DUNS/UEI, SAM status, NAICS codes, business size status |

Tools: Canva (free) or Google Docs. **Never** use a stock template that screams "first-timer."

---

## Week 6-8 — Bid Wave 1 (5-10 attempts)

**Two parallel tracks:**

### Track A: Micro-purchases (<$10k, <$25k for some agencies)

- Lower compliance burden (no full proposal required for many)
- Often awarded same-week
- Goal: get one win for past-performance file
- Target: GSA Advantage, agency-specific RFQs, small simplified acquisitions

### Track B: Sub-contractor pitches

- Find primes who recently won contracts in your NAICS
- Cold outreach (use `Templates/comms/comms-cold-email.md`)
- Pitch: "I can do [specific capability] as a sub on [contract X]. Here's my capability statement."
- Past performance via subbing **doesn't require you to be the prime first**

**Output template per bid:**
```
Outputs/govcon-revenue/bids/YYYY-MM-DD-<agency>-<solicitation>.md
- Solicitation #
- Bid amount
- Win probability estimate
- Submission date
- Result (pending/won/lost) — update later
```

---

## Week 9-12 — Iterate & Land

- Review bid win/loss rate weekly
- Refine AI scoring model based on which opportunities actually got responses
- Add 2nd state portal (Texas SmartBuy, NY OGS, or your home state)
- Pursue any teaming agreements that came out of Wave 1 outreach
- **Target by Week 12:** 1 win (any size) + 2 active sub-contract pitches in motion

---

## Total Budget Breakdown (12 weeks)

| Item | Cost |
|---|---|
| LLC filing (Wyoming or NM) | $50–$200 |
| Registered agent (year 1, Wyoming) | $50–$125 |
| Business email (Google Workspace, optional) | $0–$84 |
| Business bank account | $0 |
| SAM.gov + UEI | $0 |
| Capability statement design (DIY in Canva) | $0 |
| Claude API for scanner | ~$25 (12 weeks × ~$2) |
| Domain name (yourcompany.com) | $12 |
| Web host (Cloudflare Pages, free tier) | $0 |
| **Total** | **$137–$446** |

Well under $1k cap.

---

## Risk + Mitigation

| Risk | Mitigation |
|---|---|
| UEI delayed beyond 4 weeks | Start Day 3, not Week 4. Have scanner + sub-pitch track ready as parallel work |
| Lose first 10 bids in a row | Expected. Each loss = data. Pivot capability after 10 if pattern emerges |
| Capability statement looks amateur | Spend 4-6 hours, not 30 minutes. Steal layout from successful small-biz competitors |
| State filing rejected | Use registered agent for compliance; double-check name availability before filing |
| Burn out on nights/weekends | Hard cap 10 hrs/week. Scanner does the heavy lifting — your job is decisions, not data entry |

---

## Open Questions to Resolve in Week 1

- [ ] Home state vs Wyoming vs NM (depends on where you'll bid)
- [ ] LLC name (check availability in chosen state + .com domain availability)
- [ ] Banking choice (Mercury for tech-friendly, local credit union for relationship)

---

## New Rules / Preferences to Remember

- **Day 3 rule**: UEI registration starts Day 3, not later — it's the longest pole
- **Data-before-decision rule**: No NAICS commitment until 2 weeks of scanner data
- **Sub-before-prime rule**: First past-performance entries via subbing, not prime bids
- **10-hour cap rule**: Nights/weekends only — anything more violates bootstrap sustainability
