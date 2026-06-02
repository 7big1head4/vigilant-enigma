"""
SAM.gov Opportunities API v2
Free key: https://api.sam.gov/cs/ui/  (register → request System Account → Public API)
Docs: https://open.gsa.gov/api/opportunities-api/
"""
import requests
from datetime import datetime, timedelta
from config import SAM_GOV_API_KEY

BASE = "https://api.sam.gov/opportunities/v2/search"


def fetch(days_back: int = 1) -> list[dict]:
    posted_from = (datetime.now() - timedelta(days=days_back)).strftime("%m/%d/%Y")
    posted_to = datetime.now().strftime("%m/%d/%Y")

    opps, offset, limit = [], 0, 100
    while True:
        resp = requests.get(BASE, params={
            "api_key":    SAM_GOV_API_KEY,
            "limit":      limit,
            "offset":     offset,
            "postedFrom": posted_from,
            "postedTo":   posted_to,
            "ptype":      "o,k,r",   # solicitation, combined synopsis, sources sought
        }, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("opportunitiesData", [])
        if not batch:
            break
        opps.extend(batch)
        offset += limit
        if offset >= data.get("totalRecords", 0):
            break

    return [_normalize(o) for o in opps]


def _normalize(o: dict) -> dict:
    awards = o.get("award", {}) or {}
    return {
        "id":          f"sam_{o.get('noticeId', o.get('solicitationNumber', ''))}",
        "source":      "sam_gov",
        "title":       o.get("title", ""),
        "agency":      o.get("fullParentPathName", o.get("organizationHierarchy", "")),
        "naics":       o.get("naicsCode", ""),
        "set_aside":   o.get("typeOfSetAside", ""),
        "posted_date": o.get("postedDate", ""),
        "close_date":  o.get("responseDeadLine", ""),
        "award_min":   float(awards.get("amount", 0) or 0),
        "award_max":   float(awards.get("amount", 0) or 0),
        "url":         f"https://sam.gov/opp/{o.get('noticeId', '')}/view",
        "description": (o.get("description") or "")[:2000],
    }
