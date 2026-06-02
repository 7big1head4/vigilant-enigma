import os
from dotenv import load_dotenv

load_dotenv()

SAM_GOV_API_KEY = os.environ["SAM_GOV_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
DB_PATH = os.getenv("DB_PATH", "./scanner.db")
DIGEST_OUTPUT = os.getenv("DIGEST_OUTPUT", "./digests")
MIN_SCORE = int(os.getenv("MIN_SCORE", "6"))

# Broad keyword filter — pre-AI triage. Refined after Week 5 NAICS pick.
KEYWORDS = [
    "information technology", "cybersecurity", "software development",
    "AI", "artificial intelligence", "machine learning", "cloud",
    "data analytics", "system integration", "DevSecOps", "network",
    "research", "technical support", "engineering services",
    "small business", "8(a)", "SDVOSB", "WOSB", "HUBZone",
]
