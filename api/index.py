from flask import Flask, request, render_template
from datetime import datetime

from api.utils.bulletin import run_check
from api.utils.hits import update_hit_counts
from api.utils.subscription import load_subscriptions, save_subscriptions, handle_subscription, get_subscriber_count
from api.utils.email import is_valid_email, send_email

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def check_bulletin():
    hits = update_hit_counts()
    subscriber_count = get_subscriber_count()

    result, bulletin_month = run_check(return_month=True)

    subscriptions = load_subscriptions()
    for subscription in subscriptions:
        email = subscription["email"]
        last_sent_month = subscription["last_sent_month"]

        if last_sent_month != bulletin_month:
            subject = f"Visa Bulletin for {bulletin_month}"
            body = result.split("⌛ Last updated time:")[0]
            if not send_email(email, subject, body, bulletin_month):
                # Remove the email from the database if sending fails
                save_subscriptions({"emails": [email], "unsubscribe": True})
                print(f"❌ Failed to send email to {email}. Unsubscribing.")
            else:
                save_subscriptions({"emails": [email], "last_sent_month": bulletin_month})

    subs_msg = ""
    if request.method == "POST":
        email = request.form.get("email")
        unsubscribe = request.form.get("unsubscribe") == "on"
        if email:
            if is_valid_email(email):
                subs_msg = handle_subscription(email, result, bulletin_month, unsubscribe=unsubscribe)
            else:
                subs_msg = "<p>❌ Invalid email address provided.</p>"

    return render_template(
        "index.html",
        hits=hits,
        subscriber_count=subscriber_count,
        current_month=datetime.utcnow().strftime('%Y-%m'),
        current_date=datetime.utcnow().strftime('%Y-%m-%d'),
        result=result,
        subs_msg=subs_msg,
    )

@app.template_filter('comma')
def format_with_commas(value):
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return value


if __name__ == "__main__":
    app.run()