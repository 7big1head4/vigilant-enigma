#!/usr/bin/env python3
"""
GovCon Scanner — main orchestrator
Run daily via cron: 0 6 * * * cd ~/scanner && python main.py >> run.log 2>&1
"""
import sys
from datetime import datetime

import store
import filter as pre_filter
import ai_score
import digest
from sources import sam_gov, grants_gov, sbir_gov, cal_eprocure


def run(days_back: int = 1):
    print(f"\n[{datetime.now().isoformat()}] Scanner starting (days_back={days_back})")
    store.init_db()

    # 1. Fetch from all sources
    sources = {
        "sam_gov":      lambda: sam_gov.fetch(days_back),
        "grants_gov":   lambda: grants_gov.fetch(days_back),
        "sbir":         sbir_gov.fetch,       # always fetches open solicitations
        "cal_eprocure": lambda: cal_eprocure.fetch(days_back),
    }

    fetched_total = 0
    for name, fn in sources.items():
        try:
            opps = fn()
            print(f"  {name}: {len(opps)} raw")
        except Exception as e:
            print(f"  {name}: FAILED — {e}", file=sys.stderr)
            continue

        # 2. Keyword pre-filter
        passing = [o for o in opps if pre_filter.passes(o)]
        print(f"  {name}: {len(passing)} after keyword filter")

        # 3. Upsert into DB
        for opp in passing:
            store.upsert(opp)
        fetched_total += len(passing)

    # 4. AI score any unscored rows (batched to control API cost)
    unscored = store.get_unscored(limit=100)
    print(f"\n[AI scoring] {len(unscored)} unscored opportunities")
    for row in unscored:
        try:
            score, summary = ai_score.score(dict(row))
            store.update_score(row["id"], score, summary)
        except Exception as e:
            print(f"  Scoring failed for {row['id']}: {e}", file=sys.stderr)

    # 5. Generate digest
    digest.generate()
    print(f"\n[Done] {fetched_total} opportunities stored, digest generated.")


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run(days)
