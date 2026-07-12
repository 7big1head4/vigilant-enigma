import os
from dotenv import load_dotenv

load_dotenv()

SAM_GOV_API_KEY = os.environ["SAM_GOV_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
DB_PATH = os.getenv("DB_PATH", "./scanner.db")
DIGEST_OUTPUT = os.getenv("DIGEST_OUTPUT", "./digests")
MIN_SCORE = int(os.getenv("MIN_SCORE", "6"))

# States to scan (2-letter codes, comma-separated in .env). Empty = ALL states.
_states_env = os.getenv("STATES", "").strip()
STATES = [s.strip().upper() for s in _states_env.split(",") if s.strip()] or None

# NAICS codes to pull FPDS award intel for. Pre-Week-5 = broad IT/services set.
# Refine to your chosen NAICS after the Week 5 analysis.
FPDS_NAICS = [c.strip() for c in os.getenv(
    "FPDS_NAICS",
    "541511,541512,541519,541611,541715,518210,541990"
).split(",") if c.strip()]

# Broad keyword filter — pre-AI triage. Refined after Week 5 NAICS pick.
KEYWORDS = [
    "information technology", "cybersecurity", "software development",
    "AI", "artificial intelligence", "machine learning", "cloud",
    "data analytics", "system integration", "DevSecOps", "network",
    "research", "technical support", "engineering services",
    "small business", "8(a)", "SDVOSB", "WOSB", "HUBZone",
]
