import json
from flask import Flask, request, render_template
from datetime import datetime

from api.utils.bulletin import run_check
from api.utils.db import get_cached_bulletin, save_cached_bulletin, get_bulletin_history
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

# ── History helpers ──

def parse_priority_date(date_str):
    """Parse a priority date string like '01JAN22' to a date object."""
    if not date_str or date_str.strip().upper() in ('C', 'U', ''):
        return None
    date_str = date_str.strip()
    for fmt in ("%d%b%y", "%d%b%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None

def compute_diff_html(current_str, previous_str):
    """Compute diff HTML between two priority date strings."""
    if not current_str or not previous_str:
        return ''
    curr = current_str.strip().upper()
    prev = previous_str.strip().upper()
    if curr == prev:
        if curr in ('C', 'U'):
            return '<span style="color:#64748b;">—</span>'
    if curr == 'C' and prev != 'C':
        return '<span style="color:#4ade80;">→ C</span>'
    if curr != 'C' and prev == 'C':
        return '<span style="color:#f87171;">C →</span>'
    if curr == 'U' and prev != 'U':
        return '<span style="color:#f87171;">→ U</span>'
    if curr != 'U' and prev == 'U':
        return '<span style="color:#4ade80;">U →</span>'
    curr_date = parse_priority_date(current_str)
    prev_date = parse_priority_date(previous_str)
    if curr_date and prev_date:
        diff = (curr_date - prev_date).days
        if diff > 0:
            return f'<span style="color:#4ade80;">▲ +{diff}d</span>'
        elif diff < 0:
            return f'<span style="color:#f87171;">▼ {diff}d</span>'
        return '<span style="color:#64748b;">—</span>'
    return ''

@app.route("/history")
def history():
    rows = get_bulletin_history()
    history_data = []
    for i, row in enumerate(rows):
        entry = {
            'bulletin_month': row['bulletin_month'],
            'month_label': row['bulletin_month'].strftime('%b %Y'),
            'final_action_date': row['final_action_date'] or '—',
            'filing_date': row['filing_date'] or '—',
            'source_url': row['source_url'],
        }
        if i > 0:
            prev = rows[i - 1]
            entry['fad_diff'] = compute_diff_html(row['final_action_date'], prev['final_action_date'])
            entry['filing_diff'] = compute_diff_html(row['filing_date'], prev['filing_date'])
        else:
            entry['fad_diff'] = ''
            entry['filing_diff'] = ''
        history_data.append(entry)

    chart_fad = []
    chart_filing = []
    for row in rows:
        month_iso = row['bulletin_month'].isoformat()
        fad = parse_priority_date(row['final_action_date'])
        filing = parse_priority_date(row['filing_date'])
        if fad:
            chart_fad.append({'x': month_iso, 'y': fad.isoformat()})
        if filing:
            chart_filing.append({'x': month_iso, 'y': filing.isoformat()})

    history_data.reverse()
    return render_template(
        "history.html",
        history=history_data,
        chart_fad=json.dumps(chart_fad),
        chart_filing=json.dumps(chart_filing),
        entry_count=len(rows),
    )


if __name__ == "__main__":
    app.run()
