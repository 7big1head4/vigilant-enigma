"""
State + local procurement coverage.

Reality: 50 states don't share one API. But most state portals fall into a few
platforms, and many expose an RSS/ATOM feed. This module keeps a registry of all
50 states + DC mapped to their portal + access method, and implements generic
fetchers for the feed-based ones. Portals with no machine-readable feed are marked
method="manual" with their URL so they surface in the digest as "check manually".

Methods:
  rss     — generic RSS/ATOM feed parser (implemented, live)
  api     — portal has a JSON API (handled by a dedicated module, e.g. cal_eprocure)
  manual  — no feed; URL provided for human review

Add/verify feed URLs over time; the framework degrades gracefully (soft fallback,
never crashes the main run).
"""
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# state code -> (portal name, url, method)
STATE_REGISTRY = {
    "AL": ("Alabama STAARS Vendor Self Service", "https://procurement.staars.alabama.gov", "manual"),
    "AK": ("Alaska Online Public Notices", "https://aws.state.ak.us/OnlinePublicNotices/", "rss"),
    "AZ": ("Arizona ProcureAZ / APP", "https://app.az.gov", "manual"),
    "AR": ("Arkansas ARBuy", "https://www.ark.org/dfa/arbuy/", "manual"),
    "CA": ("Cal eProcure", "https://caleprocure.ca.gov", "api"),  # handled by cal_eprocure.py
    "CO": ("Colorado VSS / BIDS", "https://www.bidscolorado.com", "rss"),
    "CT": ("Connecticut State Contracting Portal", "https://portal.ct.gov/DAS/CTSource/", "rss"),
    "DE": ("Delaware MyMarketplace", "https://mymarketplace.delaware.gov", "manual"),
    "FL": ("Florida Vendor Bid System", "https://www.myflorida.com/apps/vbs/vbs_www.main_menu", "rss"),
    "GA": ("Georgia Procurement Registry", "https://ssl.doas.state.ga.us/gpr/", "rss"),
    "HI": ("Hawaii HANDS / eProcurement", "https://hands.ehawaii.gov", "manual"),
    "ID": ("Idaho IPRO / Luma", "https://luma-portal.idaho.gov", "manual"),
    "IL": ("Illinois BidBuy", "https://www.bidbuy.illinois.gov", "manual"),
    "IN": ("Indiana IDOA Bid Opportunities", "https://www.in.gov/idoa/procurement/", "rss"),
    "IA": ("Iowa Bid Opportunities", "https://bidopportunities.iowa.gov", "rss"),
    "KS": ("Kansas eSupplier", "https://admin.ks.gov/offices/procurement-and-contracts", "manual"),
    "KY": ("Kentucky eProcurement", "https://finance.ky.gov/services/eprocurement/", "manual"),
    "LA": ("Louisiana LaPAC", "https://wwwcfprd.doa.louisiana.gov/osp/lapac/", "rss"),
    "ME": ("Maine Bid System", "https://www.maine.gov/dafs/bbm/procurementservices/vendors/rfps", "rss"),
    "MD": ("Maryland eMaryland Marketplace (eMMA)", "https://emma.maryland.gov", "manual"),
    "MA": ("Massachusetts COMMBUYS", "https://www.commbuys.com", "rss"),
    "MI": ("Michigan SIGMA VSS", "https://sigma.michigan.gov/PRDVSS1X1/", "manual"),
    "MN": ("Minnesota SWIFT", "https://mn.gov/admin/osp/", "rss"),
    "MS": ("Mississippi MAGIC", "https://www.ms.gov/dfa/contract_bid_search/", "rss"),
    "MO": ("Missouri MissouriBUYS", "https://missouribuys.mo.gov", "manual"),
    "MT": ("Montana eMACS", "https://emacs.mt.gov", "manual"),
    "NE": ("Nebraska Contractor Registration", "https://das.nebraska.gov/materiel/purchasing.html", "rss"),
    "NV": ("Nevada NevadaEPro", "https://nevadaepro.com", "manual"),
    "NH": ("New Hampshire NHFirst", "https://apps.das.nh.gov/bidscontracts/", "rss"),
    "NJ": ("New Jersey NJSTART", "https://www.njstart.gov", "manual"),
    "NM": ("New Mexico Procurement", "https://www.generalservices.state.nm.us/state-purchasing/", "rss"),
    "NY": ("New York State Contract Reporter", "https://www.nyscr.ny.gov", "rss"),
    "NC": ("North Carolina eVP / IPS", "https://www.ips.state.nc.us", "rss"),
    "ND": ("North Dakota Bidder Registration", "https://www.omb.nd.gov/central-services/procurement", "manual"),
    "OH": ("Ohio Procurement / OhioBuys", "https://ohiobuys.ohio.gov", "manual"),
    "OK": ("Oklahoma OMES Central Purchasing", "https://oklahoma.gov/omes/services/purchasing.html", "rss"),
    "OR": ("Oregon OregonBuys", "https://oregonbuys.gov", "manual"),
    "PA": ("Pennsylvania eMarketplace", "https://www.emarketplace.state.pa.us", "rss"),
    "RI": ("Rhode Island Ocean State Procures", "https://ridop.ri.gov", "manual"),
    "SC": ("South Carolina SCBO", "https://procurement.sc.gov", "rss"),
    "SD": ("South Dakota Bid/RFP", "https://boa.sd.gov/central-services/procurement-management/", "rss"),
    "TN": ("Tennessee Edison SWC / RFP", "https://www.tn.gov/generalservices/procurement/", "manual"),
    "TX": ("Texas SmartBuy / ESBD", "http://www.txsmartbuy.com/esbd", "rss"),
    "UT": ("Utah U3P / SciQuest", "https://purchasing.utah.gov", "manual"),
    "VT": ("Vermont Bid Opportunities", "https://bgs.vermont.gov/purchasing-contracting/bids", "rss"),
    "VA": ("Virginia eVA", "https://eva.virginia.gov", "manual"),
    "WA": ("Washington WEBS", "https://pr-webs-vendor.des.wa.gov", "manual"),
    "WV": ("West Virginia wvOASIS VSS", "https://prod.wvoasis.gov", "manual"),
    "WI": ("Wisconsin VendorNet", "https://vendornet.wi.gov", "rss"),
    "WY": ("Wyoming Public Purchase", "https://www.publicpurchase.com", "manual"),
    "DC": ("DC OCP Contracts & Solicitations", "https://ocp.dc.gov/page/solicitations", "rss"),
}


def _parse_feed(state: str, portal: str, url: str) -> list[dict]:
    """Generic RSS/ATOM parser. Soft-fails to [] on any error."""
    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": "govcon-scanner/1.0"})
        if resp.status_code != 200 or not resp.content.strip().startswith(b"<"):
            return []
        root = ET.fromstring(resp.content)
    except Exception:
        return []

    items = []
    # RSS <item> and Atom <entry>
    for node in root.iter():
        tag = node.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        title = _child_text(node, "title")
        link = _child_text(node, "link") or _child_attr(node, "link", "href")
        desc = _child_text(node, "description") or _child_text(node, "summary")
        pub = _child_text(node, "pubDate") or _child_text(node, "updated")
        if not title:
            continue
        items.append({
            "id":          f"state_{state}_{abs(hash(title + (link or '')))}",
            "source":      f"state_{state.lower()}",
            "title":       f"[{state}] {title}",
            "agency":      portal,
            "naics":       "",
            "set_aside":   "",
            "posted_date": pub or "",
            "close_date":  "",
            "award_min":   0.0,
            "award_max":   0.0,
            "url":         link or url,
            "description": (desc or "")[:2000],
        })
    return items


def _child_text(node, name):
    for c in node:
        if c.tag.split("}")[-1] == name and c.text:
            return c.text.strip()
    return ""


def _child_attr(node, name, attr):
    for c in node:
        if c.tag.split("}")[-1] == name and c.get(attr):
            return c.get(attr)
    return ""


def fetch(states: list[str] | None = None) -> list[dict]:
    """
    Fetch opportunities from state RSS feeds.
    states: list of 2-letter codes to include; None = all rss-method states.
    """
    out = []
    for code, (portal, url, method) in STATE_REGISTRY.items():
        if states and code not in states:
            continue
        if method != "rss":
            continue
        out.extend(_parse_feed(code, portal, url))
    return out


def manual_portals(states: list[str] | None = None) -> list[dict]:
    """Return manual-method portals so they can be surfaced in the digest."""
    return [
        {"state": code, "portal": portal, "url": url}
        for code, (portal, url, method) in STATE_REGISTRY.items()
        if method == "manual" and (not states or code in states)
    ]
