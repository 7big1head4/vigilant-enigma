# GovCon Scanner

Multi-source government contract/grant/SBIR scanner with AI scoring.
Runs on Raspberry Pi 5. Cost ≈ $0.75–$2/month.

## Sources

| Source | What | Auth |
|---|---|---|
| SAM.gov | Federal contracts, solicitations, sources sought | Free API key |
| Grants.gov | Federal grants | None |
| SBIR.gov | SBIR/STTR Phase I & II solicitations | None |
| Cal eProcure | California state contracts | None |

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
