"""
USAspending.gov — awarded-contract intel (modern replacement/complement to FPDS).

Same underlying data as FPDS but a clean, documented JSON REST API. No auth
required. Preferred over fpds.py where possible; fpds.py kept as a fallback
since USAspending occasionally lags on the very latest awards.

Docs: https://api.usaspending.gov/docs/endpoints
Endpoint used: POST /api/v2/search/spending_by_award/
"""
import requests
from datetime import datetime, timedelta

BASE = "https://api.usaspending.gov/api/v2/search/spending_by_award/"

FIELDS = [
    "Award ID", "Recipient Name", "Awarding Agency", "Awarding Sub Agency",
    "Start Date", "End Date", "Award Amount", "Total Outlays",
    "Contract Award Type", "NAICS Code", "NAICS Description",
    "Description", "def_codes",
]


def fetch(naics_codes: list[str], last_days: int = 30, limit_per_naics: int = 50) -> list[dict]:
    """Pull recent contract awards for the given NAICS codes."""
    date_from = (datetime.now() - timedelta(days=last_days)).strftime("%Y-%m-%d")
    date_to = datetime.now().strftime("%Y-%m-%d")

    out = []
    for naics in naics_codes:
        try:
            resp = requests.post(BASE, json={
                "filters": {
                    "award_type_codes": ["A", "B", "C", "D"],  # contracts (all types)
                    "time_period": [{"start_date": date_from, "end_date": date_to}],
                    "naics_codes": {"require": [naics]},
                },
                "fields": FIELDS,
                "page": 1,
                "limit": limit_per_naics,
                "sort": "Award Amount",
                "order": "desc",
            }, timeout=30, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except Exception:
            continue

        for r in results:
            out.append(_normalize(r, naics))

    return out


def _normalize(r: dict, naics: str) -> dict:
    amount = r.get("Award Amount") or 0
    return {
        "id":          f"usa_{r.get('Award ID', '')}_{naics}",
        "naics":       naics,
        "vendor":      r.get("Recipient Name", "") or "",
        "agency":      r.get("Awarding Agency", "") or "",
        "amount":      float(amount or 0),
        "signed_date": r.get("Start Date", "") or "",
        "piid":        r.get("Award ID", "") or "",
        "description": (r.get("Description") or r.get("NAICS Description") or "")[:1000],
    }


def top_vendors_live(naics: str, last_days: int = 90, limit: int = 10) -> list[dict]:
    """
    Direct, no-DB lookup for quick manual checks:
    python -c "from sources.usaspending import top_vendors_live as t; print(t('541512'))"
    """
    awards = fetch([naics], last_days=last_days, limit_per_naics=limit * 5)
    tally: dict[str, dict] = {}
    for a in awards:
        v = a["vendor"] or "(unknown)"
        entry = tally.setdefault(v, {"vendor": v, "wins": 0, "total": 0.0})
        entry["wins"] += 1
        entry["total"] += a["amount"]
    ranked = sorted(tally.values(), key=lambda x: x["total"], reverse=True)
    return ranked[:limit]
