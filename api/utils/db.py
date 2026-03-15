import os
import psycopg2

DB_URL = os.getenv("DATABASE_URL")

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

def get_bulletin_history():
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT bulletin_month, final_action_date, filing_date, source_url "
                "FROM bulletin_history ORDER BY bulletin_month ASC"
            )
            rows = cur.fetchall()
        conn.close()
        return [
            {"bulletin_month": r[0], "final_action_date": r[1], "filing_date": r[2], "source_url": r[3]}
            for r in rows
        ]
    except Exception:
        return []

def get_latest_history(n=2):
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT bulletin_month, final_action_date, filing_date "
                "FROM bulletin_history ORDER BY bulletin_month DESC LIMIT %s",
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

def save_bulletin_history(month, fad, filing, url):
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bulletin_history (bulletin_month, final_action_date, filing_date, source_url)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (bulletin_month) DO UPDATE SET
                    final_action_date = EXCLUDED.final_action_date,
                    filing_date = EXCLUDED.filing_date,
                    source_url = EXCLUDED.source_url
                """,
                (month, fad, filing, url),
            )
        conn.commit()
        conn.close()
    except Exception:
        pass
