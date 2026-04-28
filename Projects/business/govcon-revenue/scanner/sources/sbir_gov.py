"""
SBIR.gov Solicitations API
No auth required.
Docs: https://www.sbir.gov/sites/default/files/api_documentation.pdf
"""
import requests

BASE = "https://api.sbir.gov/solicitations"


def fetch() -> list[dict]:
    opps, start, rows = [], 0, 100
    while True:
        resp = requests.get(BASE, params={
            "rows":  rows,
            "start": start,
            "open":  "true",
        }, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("response", {}).get("docs", [])
        if not batch:
            break
        opps.extend(batch)
        start += rows
        if start >= data.get("response", {}).get("numFound", 0):
            break

    return [_normalize(o) for o in opps]


def _normalize(o: dict) -> dict:
    return {
        "id":          f"sbir_{o.get('solicitation_id', '')}",
        "source":      "sbir",
        "title":       o.get("solicitation_title", ""),
        "agency":      o.get("agency", ""),
        "naics":       "",
        "set_aside":   "SBIR/STTR",
        "posted_date": o.get("open_date", ""),
        "close_date":  o.get("close_date", ""),
        "award_min":   float(o.get("award_amount_range_min", 0) or 0),
        "award_max":   float(o.get("award_amount_range_max", 0) or 0),
        "url":         o.get("solicitation_url", ""),
        "description": (o.get("program_title") or "")[:2000],
    }
