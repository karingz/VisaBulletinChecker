from flask import Flask
from api.utils.bulletin import run_check
from api.utils.db import save_cached_bulletin
from api.utils.subscription import load_subscriptions, save_subscriptions
from api.utils.email import send_email

app = Flask(__name__)

@app.route("/", methods=["GET"])
def check_bulletin():
    # Always scrape fresh and update cache
    result, bulletin_month = run_check(return_month=True)
    if bulletin_month:
        save_cached_bulletin(result, bulletin_month)

    # Send emails to subscribers who haven't received this bulletin
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
                save_subscriptions({"emails": [email], "unsubscribe": True})
                failed += 1
            else:
                save_subscriptions({"emails": [email], "last_sent_month": bulletin_month})
                sent += 1

    return {
        "statusCode": 200,
        "body": {
            "bulletin_month": bulletin_month,
            "emails_sent": sent,
            "emails_failed": failed,
        }
    }
