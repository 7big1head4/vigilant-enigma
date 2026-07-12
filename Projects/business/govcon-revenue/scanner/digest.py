"""Generate daily markdown digest of top-scored opportunities + FPDS intel."""
import os
from datetime import datetime
from config import MIN_SCORE, DIGEST_OUTPUT, FPDS_NAICS
from store import get_top, award_intel
from sources.states import manual_portals


def generate() -> str:
    os.makedirs(DIGEST_OUTPUT, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    outfile = os.path.join(DIGEST_OUTPUT, f"{date}-digest.md")

    top = get_top(MIN_SCORE, days_back=1)
    lines = [
        f"# GovCon Digest — {date}",
        f"",
        f"**Opportunities scored {MIN_SCORE}+:** {len(top)}",
        f"",
    ]

    if not top:
        lines.append("No qualifying opportunities today. Lower MIN_SCORE or broaden KEYWORDS.")
    else:
        for o in top:
            lines += [
                f"---",
                f"## [{o['title']}]({o['url']}) — Score: {o['ai_score']}/10",
                f"- **Source:** {o['source']}",
                f"- **Agency:** {o['agency']}",
                f"- **NAICS:** {o['naics'] or 'N/A'}  |  **Set-aside:** {o['set_aside'] or 'None'}",
                f"- **Award:** ${o['award_min']:,.0f}–${o['award_max']:,.0f}",
                f"- **Closes:** {o['close_date'] or 'TBD'}",
                f"- **AI take:** {o['ai_summary']}",
                f"",
            ]

    # --- FPDS competitive intel ---
    lines += ["", "---", "", "## 🏆 Competitive Intel (FPDS — who's winning)", ""]
    any_intel = False
    for naics in FPDS_NAICS:
        rows = award_intel(naics, limit=5)
        if not rows:
            continue
        any_intel = True
        lines.append(f"**NAICS {naics} — top vendors (last 30d awards):**")
        lines.append("")
        lines.append("| Vendor | Wins | Avg $ | Total $ |")
        lines.append("|---|---|---|---|")
        for r in rows:
            lines.append(
                f"| {r['vendor'][:40]} | {r['wins']} | ${r['avg_amount']:,.0f} | ${r['total']:,.0f} |"
            )
        lines.append("")
    if not any_intel:
        lines.append("_No FPDS award data yet — run once with network access to populate._")

    # --- Manual state portals reminder ---
    portals = manual_portals()
    if portals:
        lines += ["", "---", "", f"## 📋 State Portals to Check Manually ({len(portals)})",
                  "_These states have no machine-readable feed — check weekly:_", ""]
        for p in portals:
            lines.append(f"- **{p['state']}** — [{p['portal']}]({p['url']})")

    content = "\n".join(lines)
    with open(outfile, "w") as f:
        f.write(content)

    print(f"Digest → {outfile} ({len(top)} opportunities)")
    return outfile
