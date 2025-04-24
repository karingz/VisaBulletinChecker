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
                <p>🚀 <a href="https://visa-bulletin-checker.vercel.app/" target="_blank">Visit Visa Bulletin Checker Page</a> ⬅ 🔕 Unsubscribe here</p>
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

def is_valid_email(email):
    import re
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(email_regex, email) is not None


@app.route("/unsubscribe", methods=["GET"])
def unsubscribe():
    email = request.args.get("email")
    if not email:
        return "<p>❌ Email not provided.</p>", 400

    subs = load_subscriptions()
    for subscription in subs:
        if subscription["email"] == email:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("DELETE FROM subscriptions WHERE email = %s", (email,))
            conn.commit()
            conn.close()
            return f"<p>✅ Successfully unsubscribed: {email}</p>"

    return f"<p>ℹ️ Email not found: {email}</p>", 404

@app.route("/", methods=["GET", "POST"])
def check_bulletin():
    hits = update_hit_counts()
    subscriber_count = get_subscriber_count()

    result, bulletin_month = VisaBulletinChecker.run_check(return_month=True)

    # Fetch all subscribers
    subscriptions = load_subscriptions()

    # Check and send emails to subscribers if needed
    for subscription in subscriptions:
        email = subscription["email"]
        last_sent_month = subscription["last_sent_month"]

        if last_sent_month != bulletin_month:
            subject = f"Visa Bulletin for {bulletin_month}"
            body = result.split("⌛ Last updated time:")[0]  # Remove the last updated time
            send_email(email, subject, body, bulletin_month)

            # Update last_sent_month for the subscriber
            save_subscriptions({"emails": [email], "last_sent_month": bulletin_month})

    email_form = """
        <form method="post">
            <input type="email" name="email" placeholder="Enter email" required>
            <label style="margin-left: 10px;">
                <input type="checkbox" name="unsubscribe" id="unsubscribe-checkbox" onchange="updateButtonText()" style="color: red;"> Unsubscribe
            </label>
            <button type="submit" id="submit-button">🔔 <strong>Submit</strong></button>
        </form><br/>
        <script>
            function updateButtonText() {
                const checkbox = document.getElementById('unsubscribe-checkbox');
                const button = document.getElementById('submit-button');
                    button.innerHTML = checkbox.checked ? '🔕 <strong>Submit</strong>' : '🔔 <strong>Submit</strong>';
            }
        </script>
    """

    subs_msg = ""
    if request.method == "POST":
        email = request.form.get("email")
        unsubscribe = request.form.get("unsubscribe") == "on"
        if email:
            if is_valid_email(email):
                subs_msg = handle_subscription(email, result, bulletin_month, unsubscribe=unsubscribe)
            else:
                subs_msg = "<p>❌ Invalid email address provided.</p>"

    hit_info = f"""
    <p style="font-size: 0.7em;">📊 Page Hits:</p>
    <table style="font-size: 0.7em; margin: 5px 0;">
        <tr>
            <td style="padding-right: 20px;">Total: {hits['total']:,}</td>
            <td style="padding-right: 20px;">Monthly ({datetime.utcnow().strftime('%Y-%m')}): {hits['monthly']:,}</td>
            <td>Daily ({datetime.utcnow().strftime('%Y-%m-%d')}): {hits['daily']:,}</td>
        </tr>
    </table>
    <p style="font-size: 0.9em;">👥 Subscriber Count: {subscriber_count:,}</p>
    """

    return ("""
        <html>
        <head>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css" rel="stylesheet">
            <style>
                body {{
                    font-family: Arial, sans-serif; /* Unified font for the page */
                }}
                a {{
                    color: grey; /* Set link font color to grey */
                    text-decoration: none; /* Remove underline from links */
                }}
                a:hover {{
                    text-decoration: underline; /* Add underline on hover for better UX */
                }}
            </style>
        </head>
        <body>
            {hit_info}
            <hr>
            result}
            {email_form}
            {subs_msg}<br>
            <p><a href='https://github.com/karingz/VisaBulletinChecker' target='_blank'><i class='fab fa-github'></i> Visit the GitHub Page</a></p>
            <p>📧 <a href='mailto:imaginaryground@gmail.com'>Shoot me an email</a></p>
        </body>
        </html>
    """.format(hit_info=hit_info, result=result, email_form=email_form, subs_msg=subs_msg))

if __name__ == "__main__":
    app.run()