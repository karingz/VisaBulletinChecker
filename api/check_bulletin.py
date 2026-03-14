import os
from flask import Flask, request
from api.utils.bulletin import run_check
from api.utils.db import get_cached_bulletin, save_cached_bulletin
from api.utils.subscription import load_subscriptions, save_subscriptions
from api.utils.email import send_email

CRON_SECRET = os.getenv("CRON_SECRET")

app = Flask(__name__)

@app.route("/api/check_bulletin", methods=["GET"])
def check_bulletin():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not CRON_SECRET or token != CRON_SECRET:
        return {"statusCode": 401, "body": "Unauthorized"}, 401
    # Check what's currently cached
    cache = get_cached_bulletin()
    cached_month = cache["bulletin_month"] if cache else None

    # Scrape fresh
    result, bulletin_month = run_check(return_month=True)
    if not bulletin_month:
        return {"statusCode": 200, "body": {"error": "Failed to fetch bulletin"}}

    # Update cache
    save_cached_bulletin(result, bulletin_month)

    # Only send emails if the bulletin month has changed from the cache
    if cached_month == bulletin_month:
        return {
            "statusCode": 200,
            "body": {
                "bulletin_month": bulletin_month,
                "status": "no change",
            }
        }

    # New bulletin detected — notify subscribers
    subscriptions = load_subscriptions()
    sent = 0
    failed = 0
    for subscription in subscriptions:
        email = subscription["email"]
        last_sent_month = subscription["last_sent_month"]

        if last_sent_month != bulletin_month:
            subject = f"Visa Bulletin for {bulletin_month}"
            body = result.split("⌛ Last updated time:")[0]
            if not send_email(email, subject, body, bulletin_month):
                failed += 1
            else:
                save_subscriptions({"emails": [email], "last_sent_month": bulletin_month})
                sent += 1

    return {
        "statusCode": 200,
        "body": {
            "bulletin_month": bulletin_month,
            "status": "new bulletin",
            "emails_sent": sent,
            "emails_failed": failed,
        }
    }
