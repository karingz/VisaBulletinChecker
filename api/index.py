from flask import Flask, request
import VisaBulletinChecker  # Import the module
import os
import json
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

app = Flask(__name__)

HIT_FILE = "/tmp/page_hits.json"
SUB_FILE = "/tmp/subscriptions.json"  # or use a persistent DB later

def load_hits():
    if not os.path.exists(HIT_FILE):
        return {"total": 0, "monthly": {}, "daily": {}}
    with open(HIT_FILE, "r") as f:
        return json.load(f)

def save_hits(data):
    with open(HIT_FILE, "w") as f:
        json.dump(data, f, indent=2)

def update_hit_counts():
    hits = load_hits()
    now = datetime.utcnow()
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")

    # Update counters
    hits["total"] += 1
    hits["daily"][today] = hits["daily"].get(today, 0) + 1
    hits["monthly"][month] = hits["monthly"].get(month, 0) + 1

    # Keep only the last 30 days in 'daily'
    recent_days = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]
    hits["daily"] = {k: v for k, v in hits["daily"].items() if k in recent_days}

    # Keep only the last 12 months in 'monthly'
    recent_months = [(now - relativedelta(months=i)).strftime("%Y-%m") for i in range(12)]
    hits["monthly"] = {k: v for k, v in hits["monthly"].items() if k in recent_months}

    save_hits(hits)
    return hits

def load_subscriptions():
    if not os.path.exists(SUB_FILE):
        return {"emails": [], "last_sent_month": ""}
    with open(SUB_FILE, "r") as f:
        return json.load(f)

def save_subscriptions(data):
    with open(SUB_FILE, "w") as f:
        json.dump(data, f, indent=2)

def handle_subscription(email, bulletin_month):
    subs = load_subscriptions()

    if email not in subs["emails"]:
        subs["emails"].append(email)

    if subs["last_sent_month"] != bulletin_month:
        print(f"📧 Simulated sending bulletin to: {email}")
        subs["last_sent_month"] = bulletin_month
        save_subscriptions(subs)
        return f"<p>✅ Subscribed and email sent to: {email}</p>"
    else:
        save_subscriptions(subs)
        return f"<p>✅ Subscribed. Email already sent for {bulletin_month}.</p>"


@app.route("/", methods=["GET", "POST"])
def check_bulletin():
    hits = update_hit_counts()

    email_form = """
        <form method="post">
            <input type="email" name="email" placeholder="Enter email to subscribe" required>
            <button type="submit">Subscribe</button>
        </form><br/>
    """

    result, bulletin_month = VisaBulletinChecker.run_check(return_month=True)

    msg = ""
    if request.method == "POST":
        email = request.form.get("email")
        if email:
            msg = handle_subscription(email, bulletin_month)

    hit_info = f"""
    <p>📊 Page Hits:</p>
    <ul>
        <li>Total: {hits['total']}</li>
        <li>Monthly ({datetime.utcnow().strftime('%Y-%m')}): {hits['monthly'][datetime.utcnow().strftime('%Y-%m')]}</li>
        <li>Daily ({datetime.utcnow().strftime('%Y-%m-%d')}): {hits['daily'][datetime.utcnow().strftime('%Y-%m-%d')]}</li>
    </ul>
    """

    return f"{email_form}{msg}{hit_info}<hr><pre>{result}</pre>"

if __name__ == "__main__":
    app.run()