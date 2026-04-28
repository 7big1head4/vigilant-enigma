"""
Cal eProcure — California state procurement portal
API docs: https://caleprocure.ca.gov/pages/API.aspx
No auth required for search endpoint.
"""
import requests
from datetime import datetime, timedelta

BASE = "https://caleprocure.ca.gov/pages/ISearch/bid-search.aspx"
API  = "https://caleprocure.ca.gov/Pages/ISearch/bid-search-results.aspx"


def fetch(days_back: int = 1) -> list[dict]:
    opps = []
    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%m/%d/%Y")

    resp = requests.get(API, params={
        "CalEProcureSearch_PostedFrom": date_from,
        "CalEProcureSearch_Status":     "Active",
        "pageSize":                     100,
        "pageNumber":                   1,
    }, headers={"Accept": "application/json"}, timeout=30)

    if resp.status_code != 200:
        # Portal may require browser headers or session; fall back silently
        return []

    try:
        data = resp.json()
        opps = data if isinstance(data, list) else data.get("results", [])
    except Exception:
        return []

    return [_normalize(o) for o in opps]


def _normalize(o: dict) -> dict:
    return {
        "id":          f"cal_{o.get('BidId', o.get('id', ''))}",
        "source":      "cal_eprocure",
        "title":       o.get("BidTitle", o.get("title", "")),
        "agency":      o.get("EntityName", o.get("agency", "")),
        "naics":       "",
        "set_aside":   "",
        "posted_date": o.get("PostedDate", ""),
        "close_date":  o.get("DueDate", o.get("closeDate", "")),
        "award_min":   0.0,
        "award_max":   0.0,
        "url":         f"https://caleprocure.ca.gov/event/{o.get('BidId', '')}",
        "description": (o.get("BidDescription", "") or "")[:2000],
    }
