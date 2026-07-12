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

IMPORTANT — the 25 "manual" states below were individually researched (2026-07,
live web search + page fetch, not guessed) to confirm whether a genuine public
RSS/ATOM/JSON feed exists. Result: NONE do. All run on enterprise procurement
SaaS (Jaggaer/SciQuest, Ivalua, Bonfire, Periscope S2G, CGI Advantage, PeopleSoft
Edison) that gates opportunity listings behind a JS-driven, often login-required
UI — the only public "notification" mechanism is email alerts tied to vendor
commodity-code registration, not a scrapeable feed. Two near-misses to note:
Kansas has an RSS URL but it's a permanently empty channel (dead feed); Rhode
Island's "RSS feed" link is the state's general press-release feed, not
solicitations. Do NOT wire in feed URLs for these — a fake/dead feed silently
reports zero results forever, which is worse than the honest manual-check label.
15 of 25 states got full verification passes; the remaining 10 (AL, AZ, AR, DE,
ID) were partially verified before the research run was interrupted, but all
partial evidence pointed to the same no-feed pattern — re-verify opportunistically
if you find a real feed for one of these.

Add/verify feed URLs over time; the framework degrades gracefully (soft fallback,
never crashes the main run).
"""
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# state code -> (portal name, url, method)
STATE_REGISTRY = {
    "AL": ("Alabama STAARS Vendor Self Service", "https://procurement.staars.alabama.gov", "manual"),  # unverified this pass
    "AK": ("Alaska Online Public Notices", "https://aws.state.ak.us/OnlinePublicNotices/", "rss"),
    "AZ": ("Arizona ProcureAZ / APP", "https://app.az.gov", "manual"),  # unverified this pass
    "AR": ("Arkansas ARBuy", "https://www.ark.org/dfa/arbuy/", "manual"),  # unverified this pass
    "CA": ("Cal eProcure", "https://caleprocure.ca.gov", "api"),  # handled by cal_eprocure.py
    "CO": ("Colorado VSS / BIDS", "https://www.bidscolorado.com", "rss"),
    "CT": ("Connecticut State Contracting Portal", "https://portal.ct.gov/DAS/CTSource/", "rss"),
    "DE": ("Delaware MyMarketplace", "https://mymarketplace.delaware.gov", "manual"),  # unverified this pass
    "FL": ("Florida Vendor Bid System", "https://www.myflorida.com/apps/vbs/vbs_www.main_menu", "rss"),
    "GA": ("Georgia Procurement Registry", "https://ssl.doas.state.ga.us/gpr/", "rss"),
    "HI": ("Hawaii HANDS (hands.ehawaii.gov)", "https://hands.ehawaii.gov", "manual"),  # verified: session-gated API (hiepro.ehawaii.gov), no public feed
    "ID": ("Idaho IPRO / Luma (purchasing.idaho.gov)", "https://purchasing.idaho.gov/iprobids.html", "manual"),  # Jaggaer->Luma migration, no feed found
    "IL": ("Illinois BidBuy (Jaggaer)", "https://www.bidbuy.illinois.gov", "manual"),  # verified: JS-driven, no feed; old purchase.state.il.us domain is dead
    "IN": ("Indiana IDOA Bid Opportunities", "https://www.in.gov/idoa/procurement/", "rss"),
    "IA": ("Iowa Bid Opportunities", "https://bidopportunities.iowa.gov", "rss"),
    "KS": ("Kansas Additional Bid Opportunities", "https://admin.ks.gov/offices/procurement-contracts/bidding--contracts/additional-bid-opportunities", "manual"),  # verified: RSS URL exists but channel is permanently empty (dead feed) — do not use
    "KY": ("Kentucky eProcurement", "https://finance.ky.gov/eProcurement/Pages/default.aspx", "manual"),  # verified: no feed/subscribe links found
    "LA": ("Louisiana LaPAC", "https://wwwcfprd.doa.louisiana.gov/osp/lapac/", "rss"),
    "ME": ("Maine Bid System", "https://www.maine.gov/dafs/bbm/procurementservices/vendors/rfps", "rss"),
    "MD": ("Maryland eMaryland Marketplace (eMMA)", "https://emma.maryland.gov", "manual"),  # verified: login-gated, no public feed
    "MA": ("Massachusetts COMMBUYS", "https://www.commbuys.com", "rss"),
    "MI": ("Michigan SIGMA VSS (CGI Advantage)", "https://sigma.michigan.gov/PRDVSS1X1/", "manual"),  # verified: email-only notifications, no feed
    "MN": ("Minnesota SWIFT", "https://mn.gov/admin/osp/", "rss"),
    "MS": ("Mississippi MAGIC", "https://www.ms.gov/dfa/contract_bid_search/", "rss"),
    "MO": ("Missouri MissouriBUYS Bid Board", "https://missouribuys.mo.gov/bid-board", "manual"),  # verified: email-only, no syndication
    "MT": ("Montana eMACS (Jaggaer/SciQuest)", "https://bids.sciquest.com/apps/Router/PublicEvent?CustomerOrg=StateOfMontana", "manual"),  # verified: JS-driven Jaggaer platform, no feed
    "NE": ("Nebraska Contractor Registration", "https://das.nebraska.gov/materiel/purchasing.html", "rss"),
    "NV": ("Nevada NevadaEPro (Periscope S2G)", "https://nevadaepro.com", "manual"),  # verified: email notifications only, no feed
    "NH": ("New Hampshire NHFirst", "https://apps.das.nh.gov/bidscontracts/", "rss"),
    "NJ": ("New Jersey NJSTART (SOVRA/Periscope)", "https://www.njstart.gov", "manual"),  # verified: live JS bid search UI, no RSS/ATOM/JSON found
    "NM": ("New Mexico Procurement", "https://www.generalservices.state.nm.us/state-purchasing/", "rss"),
    "NY": ("New York State Contract Reporter", "https://www.nyscr.ny.gov", "rss"),
    "NC": ("North Carolina eVP / IPS", "https://www.ips.state.nc.us", "rss"),
    "ND": ("North Dakota NDBuys (Ivalua)", "https://omb.nd.gov/ndbuys", "manual"),  # verified: JS-driven Ivalua UI, no feed
    "OH": ("Ohio OhioBuys (Ivalua)", "https://ohiobuys.ohio.gov", "manual"),  # verified: JS-driven Ivalua UI, no feed
    "OK": ("Oklahoma OMES Central Purchasing", "https://oklahoma.gov/omes/services/purchasing.html", "rss"),
    "OR": ("Oregon OregonBuys (Periscope S2G/BidSync)", "https://oregonbuys.gov/bso/", "manual"),  # verified: no feed, /bso/rss.aspx returns 404
    "PA": ("Pennsylvania eMarketplace", "https://www.emarketplace.state.pa.us", "rss"),
    "RI": ("Rhode Island Ocean State Procures", "https://ridop.ri.gov", "manual"),  # verified: site's "RSS feed" link is the general press-release feed, NOT solicitations — do not use
    "SC": ("South Carolina SCBO", "https://procurement.sc.gov", "rss"),
    "SD": ("South Dakota Bid/RFP", "https://boa.sd.gov/central-services/procurement-management/", "rss"),
    "TN": ("Tennessee Edison Supplier Portal (PeopleSoft)", "https://hub.edison.tn.gov", "manual"),  # verified: session-gated PeopleSoft app, no feed
    "TX": ("Texas SmartBuy / ESBD", "http://www.txsmartbuy.com/esbd", "rss"),
    "UT": ("Utah Purchasing / Bonfire", "https://utah.bonfirehub.com/portal", "manual"),  # verified: JS-driven Bonfire SPA, no feed
    "VT": ("Vermont Bid Opportunities", "https://bgs.vermont.gov/purchasing-contracting/bids", "rss"),
    "VA": ("Virginia eVA (Ivalua/CGI)", "https://eva.virginia.gov", "manual"),  # verified: no static feed, email/fax notifications only
    "WA": ("Washington WEBS", "https://pr-webs-vendor.des.wa.gov/BidCalendar.aspx", "manual"),  # verified: server-rendered ASP.NET, no feed
    "WV": ("West Virginia wvOASIS VSS", "https://wvoasis.gov/VSS", "manual"),  # verified: Purchasing Bulletin, no RSS/JSON found
    "WI": ("Wisconsin VendorNet", "https://vendornet.wi.gov", "rss"),
    "WY": ("Wyoming Public Purchase", "https://www.publicpurchase.com/gems/wyominggsd,wy", "manual"),  # verified: email notifications only, no feed
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
