"""Fast keyword pre-filter — runs before Claude scoring to cut API cost."""
from config import KEYWORDS


def passes(opp: dict) -> bool:
    """Return True if any keyword appears in title or description."""
    text = f"{opp.get('title', '')} {opp.get('description', '')}".lower()
    return any(kw.lower() in text for kw in KEYWORDS)
