"""
Score each opportunity 1-10 using Claude.
Uses claude-haiku-4-5-20251001 (cheapest model) — ~$0.00025 per call.
At 100 calls/day = ~$0.75/month.
"""
import json
import re
import anthropic
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM = """You are a GovCon analyst scoring federal/state contract opportunities for a small LLC.
The LLC's capabilities: IT services, software development, cybersecurity, AI/ML, data analytics, research.
The LLC is new (no past performance yet), 1-person, small business registered.

Score each opportunity 1-10:
10 = perfect fit (capability match + accessible to new small biz + reasonable size)
7-9 = strong fit
4-6 = possible with caveats
1-3 = poor fit (too large, requires clearance, past perf required, wrong domain)

Respond ONLY with valid JSON: {"score": <int>, "summary": "<one sentence reason>"}"""


def score(opp: dict) -> tuple[int, str]:
    prompt = f"""Title: {opp.get('title', '')}
Agency: {opp.get('agency', '')}
NAICS: {opp.get('naics', 'unknown')}
Set-aside: {opp.get('set_aside', 'none')}
Award range: ${opp.get('award_min', 0):,.0f}–${opp.get('award_max', 0):,.0f}
Close date: {opp.get('close_date', 'unknown')}
Description: {opp.get('description', '')[:800]}"""

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()

    # Parse JSON robustly
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        data = json.loads(match.group())
        return int(data.get("score", 5)), str(data.get("summary", ""))
    return 5, text[:200]
