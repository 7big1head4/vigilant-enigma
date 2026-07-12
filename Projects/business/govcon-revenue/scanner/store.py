import sqlite3
import json
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS opportunities (
                id          TEXT PRIMARY KEY,
                source      TEXT NOT NULL,           -- sam_gov | grants_gov | sbir | cal_eprocure
                title       TEXT,
                agency      TEXT,
                naics       TEXT,
                set_aside   TEXT,
                posted_date TEXT,
                close_date  TEXT,
                award_min   REAL,
                award_max   REAL,
                url         TEXT,
                description TEXT,
                ai_score    INTEGER,
                ai_summary  TEXT,
                raw         TEXT,                    -- full JSON blob
                fetched_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_score ON opportunities(ai_score)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON opportunities(source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_posted ON opportunities(posted_date)")

        # FPDS awarded-contract intel (competitive intelligence, not opportunities)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS awards (
                id          TEXT PRIMARY KEY,
                naics       TEXT,
                vendor      TEXT,
                agency      TEXT,
                amount      REAL,
                signed_date TEXT,
                piid        TEXT,
                description TEXT,
                fetched_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_awards_naics ON awards(naics)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_awards_vendor ON awards(vendor)")


def upsert(opp: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO opportunities
                (id, source, title, agency, naics, set_aside, posted_date,
                 close_date, award_min, award_max, url, description, raw)
            VALUES
                (:id, :source, :title, :agency, :naics, :set_aside, :posted_date,
                 :close_date, :award_min, :award_max, :url, :description, :raw)
            ON CONFLICT(id) DO UPDATE SET
                ai_score   = excluded.ai_score,
                ai_summary = excluded.ai_summary,
                fetched_at = datetime('now')
        """, {**opp, "raw": json.dumps(opp)})


def get_unscored(limit=50):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM opportunities WHERE ai_score IS NULL LIMIT ?", (limit,)
        ).fetchall()


def update_score(opp_id: str, score: int, summary: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE opportunities SET ai_score=?, ai_summary=? WHERE id=?",
            (score, summary, opp_id),
        )


def get_top(min_score: int, days_back: int = 1):
    with get_conn() as conn:
        return conn.execute("""
            SELECT * FROM opportunities
            WHERE ai_score >= ?
              AND fetched_at >= datetime('now', ? || ' days')
            ORDER BY ai_score DESC
        """, (min_score, f"-{days_back}")).fetchall()


def upsert_award(award: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO awards
                (id, naics, vendor, agency, amount, signed_date, piid, description)
            VALUES
                (:id, :naics, :vendor, :agency, :amount, :signed_date, :piid, :description)
            ON CONFLICT(id) DO UPDATE SET fetched_at = datetime('now')
        """, award)


def award_intel(naics: str | None = None, limit: int = 10):
    """Top vendors + avg award size — competitive intel for the digest."""
    with get_conn() as conn:
        where = "WHERE naics = ?" if naics else ""
        params = (naics,) if naics else ()
        return conn.execute(f"""
            SELECT vendor,
                   COUNT(*)      as wins,
                   ROUND(AVG(amount), 0) as avg_amount,
                   ROUND(SUM(amount), 0) as total
            FROM awards
            {where}
            GROUP BY vendor
            HAVING vendor != ''
            ORDER BY total DESC
            LIMIT ?
        """, (*params, limit)).fetchall()
