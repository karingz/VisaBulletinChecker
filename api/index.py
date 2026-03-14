from flask import Flask, request, render_template
from datetime import datetime

from api.utils.bulletin import run_check
from api.utils.db import get_cached_bulletin, save_cached_bulletin
from api.utils.hits import update_hit_counts
from api.utils.subscription import handle_subscription, get_subscriber_count, unsubscribe_email
from api.utils.email import is_valid_email

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def check_bulletin():
    user_agent = (request.headers.get("User-Agent") or "").lower()
    is_bot = any(kw in user_agent for kw in [
        "bot", "crawler", "spider", "slurp", "curl", "wget", "python",
        "scraper", "headless", "phantom", "lighthouse", "pingdom",
        "uptimerobot", "monitor", "check", "scan", "fetch",
    ])
    visitor_ip = request.headers.get("x-forwarded-for", request.remote_addr)
    hits = update_hit_counts(ip=visitor_ip if not is_bot else None)
    subscriber_count = get_subscriber_count()

    # Use cached bulletin if available, otherwise scrape and cache
    cache = get_cached_bulletin()
    if cache and cache["result"]:
        result = cache["result"]
        bulletin_month = cache["bulletin_month"]
    else:
        result, bulletin_month = run_check(return_month=True)
        if bulletin_month:
            save_cached_bulletin(result, bulletin_month)

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

@app.route("/unsubscribe", methods=["GET"])
def unsubscribe():
    email = request.args.get("email", "")
    if email and unsubscribe_email(email):
        return render_template("unsubscribe.html", message=f"✅ {email} has been unsubscribed.")
    return render_template("unsubscribe.html", message="❌ Email not found or already unsubscribed.")

@app.template_filter('comma')
def format_with_commas(value):
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return value


if __name__ == "__main__":
    app.run()
