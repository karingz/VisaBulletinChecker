import os
import psycopg2

DB_URL = os.getenv("DATABASE_URL")

COUNTRY_DB_COLUMNS = {
    'all_other': ('final_action_date', 'filing_date'),
    'china': ('fad_china', 'filing_china'),
    'india': ('fad_india', 'filing_india'),
    'mexico': ('fad_mexico', 'filing_mexico'),
    'philippines': ('fad_philippines', 'filing_philippines'),
}

def get_db_connection():
    return psycopg2.connect(DB_URL)

def get_cached_bulletin():
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT result, bulletin_month, last_fetched FROM bulletin_cache WHERE id = 1")
            row = cur.fetchone()
        conn.close()
        if row:
            return {"result": row[0], "bulletin_month": row[1], "last_fetched": row[2]}
    except Exception:
        pass
    return None

def save_cached_bulletin(result, bulletin_month):
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bulletin_cache (id, result, bulletin_month, last_fetched)
                VALUES (1, %s, %s, NOW())
                ON CONFLICT (id)
                DO UPDATE SET result = EXCLUDED.result,
                              bulletin_month = EXCLUDED.bulletin_month,
                              last_fetched = NOW()
                """,
                (result, bulletin_month),
            )
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_bulletin_history(country='all_other'):
    fad_col, filing_col = COUNTRY_DB_COLUMNS.get(country, COUNTRY_DB_COLUMNS['all_other'])
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT bulletin_month, {fad_col}, {filing_col}, source_url "
                f"FROM bulletin_history ORDER BY bulletin_month ASC"
            )
            rows = cur.fetchall()
        conn.close()
        return [
            {"bulletin_month": r[0], "final_action_date": r[1], "filing_date": r[2], "source_url": r[3]}
            for r in rows
        ]
    except Exception:
        return []

def get_latest_history(n=2, country='all_other'):
    fad_col, filing_col = COUNTRY_DB_COLUMNS.get(country, COUNTRY_DB_COLUMNS['all_other'])
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT bulletin_month, {fad_col}, {filing_col} "
                f"FROM bulletin_history ORDER BY bulletin_month DESC LIMIT %s",
                (n,),
            )
            rows = cur.fetchall()
        conn.close()
        return [
            {"bulletin_month": r[0], "final_action_date": r[1], "filing_date": r[2]}
            for r in rows
        ]
    except Exception:
        return []

def save_bulletin_history(month, countries, url):
    """Save EB-2 history for all countries.
    countries: {country_key: {'fad': str, 'filing': str}}"""
    try:
        conn = get_db_connection()
        ao = countries.get('all_other', {})
        ch = countries.get('china', {})
        ind = countries.get('india', {})
        mx = countries.get('mexico', {})
        ph = countries.get('philippines', {})
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bulletin_history (
                    bulletin_month, final_action_date, filing_date, source_url,
                    fad_china, filing_china, fad_india, filing_india,
                    fad_mexico, filing_mexico, fad_philippines, filing_philippines
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (bulletin_month) DO UPDATE SET
                    final_action_date = EXCLUDED.final_action_date,
                    filing_date = EXCLUDED.filing_date,
                    source_url = EXCLUDED.source_url,
                    fad_china = EXCLUDED.fad_china,
                    filing_china = EXCLUDED.filing_china,
                    fad_india = EXCLUDED.fad_india,
                    filing_india = EXCLUDED.filing_india,
                    fad_mexico = EXCLUDED.fad_mexico,
                    filing_mexico = EXCLUDED.filing_mexico,
                    fad_philippines = EXCLUDED.fad_philippines,
                    filing_philippines = EXCLUDED.filing_philippines
                """,
                (
                    month, ao.get('fad'), ao.get('filing'), url,
                    ch.get('fad'), ch.get('filing'),
                    ind.get('fad'), ind.get('filing'),
                    mx.get('fad'), mx.get('filing'),
                    ph.get('fad'), ph.get('filing'),
                ),
            )
        conn.commit()
        conn.close()
    except Exception:
        pass
