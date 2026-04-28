"""Generate daily markdown digest of top-scored opportunities."""
import os
from datetime import datetime
from config import MIN_SCORE, DIGEST_OUTPUT
from store import get_top


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

    content = "\n".join(lines)
    with open(outfile, "w") as f:
        f.write(content)

    print(f"Digest → {outfile} ({len(top)} opportunities)")
    return outfile
