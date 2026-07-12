"""
FPDS — Federal Procurement Data System (awarded contracts intel).

Unlike the other sources (which list OPEN opportunities), FPDS lists AWARDED
contracts. Use it for competitive intelligence: who won, incumbents, agency
spend patterns, typical award sizes per NAICS. No auth required.

ATOM feed: https://www.fpds.gov/ezsearch/FEEDS/ATOM?FEEDNAME=PUBLIC&q=<query>
Query syntax: field:value pairs, e.g.  NAICS_CODE:"541512"  AGENCY_NAME:"..."
Docs: https://www.fpds.gov/wiki/index.php/FPDS-NG_ATOM_Feed_Specifications
"""
import requests
import xml.etree.ElementTree as ET

BASE = "https://www.fpds.gov/ezsearch/FEEDS/ATOM"
NS = {
    "a":   "http://www.w3.org/2005/Atom",
    "ns1": "https://www.fpds.gov/FPDS",
}


def fetch(naics_codes: list[str], last_days: int = 30, max_per_naics: int = 50) -> list[dict]:
    """Pull recent awards for the given NAICS codes."""
    out = []
    for naics in naics_codes:
        q = f'LAST_MOD_DATE:([NOW-{last_days}DAYS,NOW]) NAICS_CODE:"{naics}"'
        try:
            resp = requests.get(BASE, params={
                "FEEDNAME": "PUBLIC",
                "q":        q,
            }, timeout=30, headers={"User-Agent": "govcon-scanner/1.0"})
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except Exception:
            continue

        count = 0
        for entry in root.findall("a:entry", NS):
            award = _parse_award(entry, naics)
            if award:
                out.append(award)
                count += 1
            if count >= max_per_naics:
                break
    return out


def _parse_award(entry, naics: str) -> dict | None:
    try:
        title = entry.findtext("a:title", default="", namespaces=NS)
        award = entry.find(".//ns1:award", NS)
        if award is None:
            award = entry  # some feeds inline fields

        vendor = _deep_text(award, "vendorName") or _deep_text(entry, "vendorName")
        agency = _deep_text(award, "contractingOfficeAgencyName") or _deep_text(entry, "contractingOfficeAgencyName")
        amount = _deep_text(award, "obligatedAmount") or _deep_text(award, "baseAndAllOptionsValue") or "0"
        piid = _deep_text(award, "PIID") or title
        date = _deep_text(award, "signedDate") or _deep_text(award, "effectiveDate")
        desc = _deep_text(award, "descriptionOfContractRequirement")

        return {
            "id":          f"fpds_{abs(hash(piid + naics))}",
            "naics":       naics,
            "vendor":      vendor,
            "agency":      agency,
            "amount":      _to_float(amount),
            "signed_date": date,
            "piid":        piid,
            "description": (desc or title or "")[:1000],
        }
    except Exception:
        return None


def _deep_text(node, localname: str) -> str:
    for el in node.iter():
        if el.tag.split("}")[-1] == localname and el.text:
            return el.text.strip()
    return ""


def _to_float(s: str) -> float:
    try:
        return float(str(s).replace("$", "").replace(",", "") or 0)
    except ValueError:
        return 0.0
