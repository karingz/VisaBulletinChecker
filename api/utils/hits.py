import json
from datetime import datetime
from api.utils.db import get_db_connection

def load_hits():
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT total, daily, monthly, last_daily_reset, last_monthly_reset FROM hit_counts LIMIT 1")
        row = cur.fetchone()
        if row:
            hits = {
                "total": row[0],
                "daily": row[1],
                "monthly": row[2],
                "last_daily_reset": row[3],
                "last_monthly_reset": row[4],
            }
        else:
            hits = {"total": 0, "daily": 0, "monthly": 0, "last_daily_reset": None, "last_monthly_reset": None}
    conn.close()
    return hits

def save_hits(data):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE hit_counts
            SET total = %s, 
                daily = %s::jsonb, 
                monthly = %s::jsonb, 
                last_daily_reset = %s, 
                last_monthly_reset = %s
            WHERE id = 1
            """,
            (data["total"], json.dumps(data["daily"]), json.dumps(data["monthly"]), data["last_daily_reset"], data["last_monthly_reset"]),
        )
    conn.commit()
    conn.close()

def update_hit_counts():
    hits = load_hits()
    now = datetime.utcnow()
    today = now.date()
    first_of_month = today.replace(day=1)

    # Reset daily hits if the last reset was not today
    if hits["last_daily_reset"] != today:
        hits["daily"] = 0
        hits["last_daily_reset"] = today

    # Reset monthly hits if the last reset was not this month
    if hits["last_monthly_reset"] != first_of_month:
        hits["monthly"] = 0
        hits["last_monthly_reset"] = first_of_month

    # Update counters
    hits["total"] += 1
    hits["daily"] += 1
    hits["monthly"] += 1

    save_hits(hits)
    return hits

