from flask import Flask, request
import VisaBulletinChecker  # Import the module
import os
import json
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

app = Flask(__name__)

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


import psycopg2

DB_URL = os.getenv("DATABASE_URL")  # Set this in your Vercel environment variables

def get_db_connection():
    return psycopg2.connect(DB_URL)

def load_subscriptions():
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT email FROM subscriptions")
        emails = [row[0] for row in cur.fetchall()]

        cur.execute("SELECT last_sent_month FROM subscriptions LIMIT 1")
        last_sent_month = cur.fetchone()
        last_sent_month = last_sent_month[0] if last_sent_month else ""

    conn.close()
    return {"emails": emails, "last_sent_month": last_sent_month}

def save_subscriptions(data):
    conn = get_db_connection()
    with conn.cursor() as cur:
        for email in data["emails"]:
            cur.execute(
                "INSERT INTO subscriptions (email) VALUES (%s) ON CONFLICT (email) DO NOTHING",
                (email,),
            )

        if data["last_sent_month"]:
            cur.execute(
                "UPDATE subscriptions SET last_sent_month = %s WHERE email = %s",
                (data["last_sent_month"], data["emails"][0]),  # Update for the first email
            )

    conn.commit()
    conn.close()

def get_subscriber_count():
    subs = load_subscriptions()
    return len(subs["emails"])

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_SERVER = "smtp.gmail.com"  # Replace with your SMTP server
SMTP_PORT = 587
SMTP_USER = os.getenv("SMTP_USER")  # Set your email in environment variables
SMTP_PASS = os.getenv("SMTP_PASS")  # Set your email password in environment variables

def send_email(to_email, subject, body, bulletin_month):
    try:
        # Append the link and unsubscribe note to the email body
        body += f"""
                <br><br>
                <p>🚀 <a href="https://visa-bulletin-checker.vercel.app/" target="_blank">Visit Visa Bulletin Checker Page</a></p>
                <p>🔕 <a href="https://visa-bulletin-checker.vercel.app/unsubscribe?email={to_email}" target="_blank">Unsubscribe here</a></p>
                """

        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        print(f"📧 Email sent to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def handle_subscription(email, result, bulletin_month, unsubscribe=False):
    subs = load_subscriptions()

    if unsubscribe:
        if email in subs["emails"]:
            subs["emails"].remove(email)
            save_subscriptions(subs)
            return f"<p>❌ Unsubscribed: {email}</p>"
        else:
            return f"<p>ℹ️ Email not found: {email}</p>"

    if email not in subs["emails"]:
        subs["emails"].append(email)

    if subs["last_sent_month"] != bulletin_month:
        # Send real email
        subject = f"Visa Bulletin for {bulletin_month}"
        result = result.split("Last updated time:")[0]  # Remove the last updated time
        body = f"{result}"
        send_email(email, subject, body, bulletin_month)

        subs["last_sent_month"] = bulletin_month
        save_subscriptions(subs)
        return f"<p>✅ Subscribed and email sent to: {email}</p>"
    else:
        save_subscriptions(subs)
        return f"<p>✅ Subscribed. Email already sent for {bulletin_month}.</p>"


@app.route("/", methods=["GET", "POST"])
def check_bulletin():
    hits = update_hit_counts()
    subscriber_count = get_subscriber_count()

    result, bulletin_month = VisaBulletinChecker.run_check(return_month=True)

    # Fetch all subscribers
    subscriptions = load_subscriptions()
    emails = subscriptions["emails"]
    last_sent_month = subscriptions["last_sent_month"]

    # Check and send emails to subscribers if needed
    for email in emails:
        if last_sent_month != bulletin_month:
            subject = f"Visa Bulletin for {bulletin_month}"
            body = result.split("Last updated time:")[0]  # Remove the last updated time
            send_email(email, subject, body, bulletin_month)

            # Update last_sent_month for the subscriber
            save_subscriptions({"emails": [email], "last_sent_month": bulletin_month})



    email_form = """
        <form method="post">
            <input type="email" name="email" placeholder="Enter email" required>
            <label style="margin-left: 10px;">
                <input type="checkbox" name="unsubscribe"> Unsubscribe
            </label>
            <button type="submit">Submit</button>
        </form><br/>
    """

    subs_msg = ""
    if request.method == "POST":
        email = request.form.get("email")
        unsubscribe = request.form.get("unsubscribe") == "on"
        if email:
            subs_msg = handle_subscription(email, result, bulletin_month, unsubscribe=unsubscribe)

    hit_info = f"""
    <p>📊 Page Hits:</p>
    <ul>
        <li>Total: {hits['total']}</li>
        <li>Monthly ({datetime.utcnow().strftime('%Y-%m')}): {hits['monthly']}</li>
        <li>Daily ({datetime.utcnow().strftime('%Y-%m-%d')}): {hits['daily']}</li>
    </ul>
    <p>👥 Subscriber Count: {subscriber_count}</p>
    """

    return f"{hit_info}<hr><pre>{result}</pre>{email_form}{subs_msg}"

if __name__ == "__main__":
    app.run()