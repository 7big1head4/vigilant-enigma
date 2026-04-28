# GovCon Scanner — Week 2-4 Build Playbook

**Date:** 2026-04-27
**Status:** Code complete, ready to deploy

---

## What Was Built

Full scanner codebase at `Projects/business/govcon-revenue/scanner/`:

```
scanner/
├── main.py              # Orchestrator — run this daily
├── config.py            # Env + keyword config
├── store.py             # SQLite DB layer
├── filter.py            # Keyword pre-filter (before AI, saves tokens)
├── ai_score.py          # Claude Haiku scoring (1-10 fit score)
├── digest.py            # Daily markdown digest generator
├── requirements.txt
├── .env.example
├── README.md
└── sources/
    ├── sam_gov.py       # SAM.gov API v2
    ├── grants_gov.py    # Grants.gov search API
    ├── sbir_gov.py      # SBIR.gov solicitations API
    └── cal_eprocure.py  # California state portal
```

---

## Week 2 — Deploy + SAM/Grants/SBIR Live

### Day 8-9: Pi 5 Setup

```bash
# SSH into Pi 5 (or run locally first)
sudo apt install -y python3-pip python3-venv git
git clone <your-repo-url> ~/scanner
cd ~/scanner/Projects/business/govcon-revenue/scanner
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Get SAM.gov API key (15 min)

1. Go to api.sam.gov → Sign In / Register
2. After login → click your profile → Request System Account
3. System Account Type: **Public API**
4. Purpose: "Searching contract opportunities for small business development"
5. Wait for email approval (usually 24–48h)
6. Paste key into `.env`

### First run

```bash
python main.py 7   # backfill last 7 days
```

**Expected output:**
```
sam_gov: 2400 raw → 180 after keyword filter
grants_gov: 800 raw → 45 after keyword filter
sbir: 120 raw (open solicitations)
cal_eprocure: varies

[AI scoring] 345 unscored opportunities
Digest → digests/2026-XX-XX-digest.md (28 opportunities)
```

### Set cron

```bash
crontab -e
# Add (runs at 6 AM daily):
0 6 * * * cd ~/scanner/Projects/business/govcon-revenue/scanner && \
  source .venv/bin/activate && python main.py >> ~/scanner-run.log 2>&1
```

---

## Week 3 — Cal eProcure + AI Filter Tuning

### Cal eProcure status

The Cal eProcure scraper has a soft fallback — if the portal changes its API structure, it returns `[]` silently (no crash). Check if it's returning data after first run:

```bash
sqlite3 scanner.db "SELECT COUNT(*) FROM opportunities WHERE source='cal_eprocure';"
```

If 0: check the portal manually at caleprocure.ca.gov and update `sources/cal_eprocure.py` accordingly.

### Tune keyword filter

After first week of runs, open `config.py` and add/remove keywords based on what's in your digest. Too many results → tighten. Too few → broaden.

### Check AI scoring cost

```bash
# Rough estimate after first week
sqlite3 scanner.db "SELECT COUNT(*) FROM opportunities WHERE ai_score IS NOT NULL;"
# × $0.00025 per call = your weekly Claude spend
```

### Pipe digest to daily-brief

Add to your `scripts/daily-brief.sh` (already done via daily-brief template):

```bash
# Find today's digest and link it
DIGEST=$(ls ~/scanner/.../digests/$(date +%Y-%m-%d)-digest.md 2>/dev/null)
[[ -n "$DIGEST" ]] && echo "**GovCon Digest:** $DIGEST"
```

---

## Week 4 — Data Capture + NAICS Analysis Prep

### Let it run — no bidding yet

For 2 full weeks, the scanner runs automatically. You review the digest each morning in your daily brief. Tag any opportunity you like:

```bash
sqlite3 scanner.db "UPDATE opportunities SET set_aside='FLAGGED' WHERE id='sam_12345';"
```

### Week 5 NAICS query (run at end of W4)

```bash
sqlite3 scanner.db "
SELECT
  naics,
  COUNT(*) as opportunities,
  ROUND(AVG(award_max), 0) as avg_award,
  COUNT(CASE WHEN ai_score >= 8 THEN 1 END) as high_fit
FROM opportunities
WHERE ai_score >= 6
  AND naics != ''
GROUP BY naics
ORDER BY opportunities DESC
LIMIT 15;"
```

**Decision rule:**
- Top NAICS by `opportunities` × `high_fit` score = your primary NAICS
- Second highest = backup NAICS for capability statement

---

## Monitoring + Ops

| Check | Command | Frequency |
|---|---|---|
| Cron ran | `tail ~/scanner-run.log` | Daily |
| DB size | `du -sh scanner.db` | Weekly |
| API errors | `grep FAILED ~/scanner-run.log` | Daily |
| Score distribution | `sqlite3 scanner.db "SELECT ai_score, COUNT(*) FROM opportunities GROUP BY ai_score ORDER BY ai_score DESC;"` | Weekly |

### DB maintenance (monthly)

```bash
sqlite3 scanner.db "DELETE FROM opportunities WHERE fetched_at < datetime('now', '-60 days');"
sqlite3 scanner.db "VACUUM;"
```

---

## Cost Reality (Weeks 2-4)

| Item | Weekly | 3-Week Total |
|---|---|---|
| SAM.gov API | $0 | $0 |
| Grants.gov | $0 | $0 |
| SBIR.gov | $0 | $0 |
| Claude Haiku (≈200 scores/day) | ~$0.35 | ~$1.05 |
| Pi 5 electricity | ~$0.25 | ~$0.75 |
| **Total** | **~$0.60** | **~$1.80** |

---

## New Rules / Preferences to Remember

- **Week 5 NAICS rule**: Don't pick your capability focus until the SQLite query at end of Week 4
- **Soft fallback rule**: Cal eProcure scraper fails silently — check `source='cal_eprocure'` count after W2
- **Keyword tuning**: Adjust `config.py` KEYWORDS after first 7 days based on digest quality
- **No bidding in W2-4**: Data collection only — resist the urge to bid early
