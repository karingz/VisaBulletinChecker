from api.utils.db import get_db_connection
from api.utils.email import send_email

def load_subscriptions():
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT email, last_sent_month FROM subscriptions")
        subscriptions = [{"email": row[0], "last_sent_month": row[1]} for row in cur.fetchall()]
    conn.close()
    return subscriptions

def save_subscriptions(data):
    conn = get_db_connection()
    with conn.cursor() as cur:
        for email in data["emails"]:
            # Insert or update the subscription with the correct last_sent_month
            cur.execute(
                """
                INSERT INTO subscriptions (email, last_sent_month)
                VALUES (%s, %s)
                ON CONFLICT (email)
                DO UPDATE SET last_sent_month = EXCLUDED.last_sent_month
                """,
                (email, data["last_sent_month"]),
            )
    conn.commit()
    conn.close()

def get_subscriber_count():
    subs = load_subscriptions()
    return len(subs)  # Count the number of subscribers

def unsubscribe_email(email):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM subscriptions WHERE email = %s RETURNING email", (email,))
        deleted_email = cur.fetchone()
    conn.commit()
    conn.close()
    return deleted_email is not None

def handle_subscription(email, result, bulletin_month, unsubscribe=False):
    subs = load_subscriptions()

    if unsubscribe:
        # Check if the email exists in the subscriptions
        for subscription in subs:
            if subscription["email"] == email:
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM subscriptions WHERE email = %s", (email,))
                conn.commit()
                conn.close()
                return f"<p>❌ Unsubscribed: {email}</p>"
        return f"<p>ℹ️ Email not found: {email}</p>"

    # Always send the email upon resubscription
    subject = f"Visa Bulletin for {bulletin_month}"
    body = result.split("⌛ Last updated time:")[0]  # Remove the last updated time
    send_email(email, subject, body, bulletin_month)

    # Update the subscription in the database
    save_subscriptions({"emails": [email], "last_sent_month": bulletin_month})
    return f"<p>✅ Subscribed and email sent to: {email}</p>"
