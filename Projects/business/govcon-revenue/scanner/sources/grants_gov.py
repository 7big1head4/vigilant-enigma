"""
Grants.gov Opportunity Search API
No auth required.
Docs: https://www.grants.gov/api-tools-resources/api-documentation
"""
import requests
from datetime import datetime, timedelta

BASE = "https://apply07.grants.gov/grantsws/OppRestServices/opp/search/"


def fetch(days_back: int = 1) -> list[dict]:
    opps, start, rows = [], 0, 100
    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%m%d%Y")

    while True:
        resp = requests.post(BASE, json={
            "startRecordNum": start,
            "rows":           rows,
            "oppStatuses":    "forecasted|posted",
            "dateRange":      "custom",
            "startDate":      date_from,
            "endDate":        datetime.now().strftime("%m%d%Y"),
        }, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("oppHits", [])
        if not batch:
            break
        opps.extend(batch)
        start += rows
        if start >= data.get("hitCount", 0):
            break

    return [_normalize(o) for o in opps]


def _normalize(o: dict) -> dict:
    return {
        "id":          f"grants_{o.get('id', '')}",
        "source":      "grants_gov",
        "title":       o.get("title", ""),
        "agency":      o.get("agencyName", ""),
        "naics":       "",
        "set_aside":   "",
        "posted_date": o.get("openDate", ""),
        "close_date":  o.get("closeDate", ""),
        "award_min":   float(o.get("awardCeiling", 0) or 0),
        "award_max":   float(o.get("awardCeiling", 0) or 0),
        "url":         f"https://www.grants.gov/search-results-detail/{o.get('id', '')}",
        "description": (o.get("synopsis") or "")[:2000],
    }
