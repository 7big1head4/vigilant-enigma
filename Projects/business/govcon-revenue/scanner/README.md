# GovCon Scanner

Multi-source government contract/grant/SBIR scanner with AI scoring.
Runs on Raspberry Pi 5. Cost ≈ $0.75–$2/month.

## Sources

| Source | What | Auth |
|---|---|---|
| SAM.gov | Federal contracts, solicitations, sources sought | Free API key |
| Grants.gov | Federal grants | None |
| SBIR.gov | SBIR/STTR Phase I & II solicitations | None |
| Cal eProcure | California state contracts (dedicated API module) | None |
| **States (50 + DC)** | All state procurement portals via registry | None |
| **USAspending.gov** | Awarded-contract intel — primary (clean JSON API) | None |
| **FPDS** | Awarded-contract intel — fallback (raw ATOM, same data) | None |

### State coverage

All 50 states + DC live in `sources/states.py` `STATE_REGISTRY`, each mapped to a
portal + access method:

- **25 states — RSS/ATOM feeds:** scraped automatically every run
- **25 states — no feed:** surfaced in the digest under "State Portals to Check
  Manually" so nothing is missed (verify/upgrade these to feeds over time)
- **1 (CA):** handled by the dedicated `cal_eprocure.py` module

Limit which states you scan via `.env`: `STATES=CA,TX,NY` (empty = all).

### Awarded-contract competitive intel (USAspending.gov + FPDS)

Both list *awarded* contracts (not open ones) — same underlying data, different
APIs. USAspending.gov (`sources/usaspending.py`) is the primary source: clean
JSON REST API, no auth, richer fields. FPDS (`sources/fpds.py`) runs in parallel
as a fallback since USAspending occasionally lags on the very latest awards.

The digest shows a **top-vendors table per NAICS** (wins, average award, total $)
combining both sources — so you can see incumbents and realistic award sizes
before bidding. Set tracked codes via `.env`: `FPDS_NAICS=541512,541519`.

Quick manual lookup without running the full scanner:
```bash
python -c "from sources.usaspending import top_vendors_live as t; print(t('541512'))"
```

## Setup

```bash
# On Pi 5
git clone <this-repo> ~/scanner
cd ~/scanner
pip install -r requirements.txt
cp .env.example .env
nano .env   # add SAM_GOV_API_KEY + ANTHROPIC_API_KEY
python main.py   # first run
```

**Get SAM.gov API key:** api.sam.gov → Sign In → Request System Account → Public API

## Daily Cron (6 AM)

```bash
crontab -e
# Add:
0 6 * * * cd ~/scanner && python main.py >> ~/scanner/run.log 2>&1
```

## Manual runs

```bash
python main.py          # last 24 hours
python main.py 7        # last 7 days (good for first run)
```

## Output

Daily digest at `digests/YYYY-MM-DD-digest.md`
SQLite DB at `scanner.db` — query directly to analyze NAICS distribution.

## Week 5 NAICS Analysis

```bash
sqlite3 scanner.db "
SELECT naics, COUNT(*) as cnt, AVG(award_max) as avg_award
FROM opportunities
WHERE ai_score >= 7
GROUP BY naics
ORDER BY cnt DESC
LIMIT 10;"
```
