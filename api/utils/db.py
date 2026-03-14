import os
import psycopg2

DB_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DB_URL)

def get_cached_bulletin():
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT result, bulletin_month, last_fetched FROM bulletin_cache WHERE id = 1")
        row = cur.fetchone()
    conn.close()
    if row:
        return {"result": row[0], "bulletin_month": row[1], "last_fetched": row[2]}
    return None

def save_cached_bulletin(result, bulletin_month):
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
