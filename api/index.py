import json
from flask import Flask, request, render_template
from datetime import datetime

from api.utils.bulletin import run_check
from api.utils.db import get_cached_bulletin, save_cached_bulletin, get_bulletin_history, get_latest_history
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

    # Compute EB-2 change from previous bulletin
    fad_diff_html = ''
    filing_diff_html = ''
    latest = get_latest_history(2)
    if len(latest) >= 2:
        curr, prev = latest[0], latest[1]
        fad_diff_html = compute_diff_html(
            curr['final_action_date'], prev['final_action_date'],
            curr['bulletin_month'], prev['bulletin_month']
        )
        filing_diff_html = compute_diff_html(
            curr['filing_date'], prev['filing_date'],
            curr['bulletin_month'], prev['bulletin_month']
        )

    return render_template(
        "index.html",
        hits=hits,
        subscriber_count=subscriber_count,
        current_month=datetime.utcnow().strftime('%Y-%m'),
        current_date=datetime.utcnow().strftime('%Y-%m-%d'),
        result=result,
        subs_msg=subs_msg,
        fad_diff=json.dumps(fad_diff_html),
        filing_diff=json.dumps(filing_diff_html),
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

def compute_diff_html(current_str, previous_str, current_month=None, previous_month=None):
    """Compute diff HTML between two priority date strings.
    C is resolved to the 15th of its bulletin month."""
    if not current_str or not previous_str:
        return ''
    curr = current_str.strip().upper()
    prev = previous_str.strip().upper()

    # U transitions
    if curr == 'U' and prev == 'U':
        return '<span style="color:#64748b;">—</span>'
    if curr == 'U':
        return '<span style="color:#f87171;">→ U</span>'
    if prev == 'U':
        return '<span style="color:#4ade80;">U →</span>'

    # Resolve dates (C = 15th of bulletin month)
    curr_date = current_month.replace(day=15) if curr == 'C' and current_month else parse_priority_date(current_str)
    prev_date = previous_month.replace(day=15) if prev == 'C' and previous_month else parse_priority_date(previous_str)

    if curr_date and prev_date:
        diff = (curr_date - prev_date).days
        suffix = ' (C)' if curr == 'C' else ''
        if diff > 0:
            return f'<span style="color:#4ade80;">▲ +{diff}d{suffix}</span>'
        elif diff < 0:
            return f'<span style="color:#f87171;">▼ {diff}d{suffix}</span>'
        if suffix:
            return f'<span style="color:#64748b;">—{suffix}</span>'
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
            entry['fad_diff'] = compute_diff_html(
                row['final_action_date'], prev['final_action_date'],
                row['bulletin_month'], prev['bulletin_month']
            )
            entry['filing_diff'] = compute_diff_html(
                row['filing_date'], prev['filing_date'],
                row['bulletin_month'], prev['bulletin_month']
            )
        else:
            entry['fad_diff'] = ''
            entry['filing_diff'] = ''
        history_data.append(entry)

    # Build aligned chart data: Y = days from current (negative or 0)
    # C = 0, regular dates = (priority_date - bulletin_15th).days
    chart_fad = []
    chart_filing = []
    last_fad_y = None
    last_filing_y = None

    for row in rows:
        month_iso = row['bulletin_month'].isoformat()
        bm_mid = row['bulletin_month'].replace(day=15)

        # FAD: days from current
        fad_str = (row['final_action_date'] or '').strip().upper()
        if fad_str == 'C':
            fad_y = 0
        elif fad_str and fad_str != 'U':
            fd = parse_priority_date(row['final_action_date'])
            fad_y = (fd - bm_mid).days if fd else last_fad_y
        else:
            fad_y = last_fad_y

        # Filing: days from current
        filing_str = (row['filing_date'] or '').strip().upper()
        if filing_str == 'C':
            filing_y = 0
        elif filing_str and filing_str != 'U':
            fd = parse_priority_date(row['filing_date'])
            filing_y = (fd - bm_mid).days if fd else last_filing_y
        else:
            filing_y = last_filing_y

        if fad_y is not None:
            last_fad_y = fad_y
        if filing_y is not None:
            last_filing_y = filing_y

        chart_fad.append({'x': month_iso, 'y': fad_y})
        chart_filing.append({'x': month_iso, 'y': filing_y})

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
