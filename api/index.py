from flask import Flask
import VisaBulletinChecker  # Import the module

app = Flask(__name__)
HIT_FILE = "/tmp/page_hits.json"

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

@app.route("/")
def check_bulletin():
    hits = update_hit_counts()

    # Display hit info
    hit_info = f"""
    <p>📊 Page Hits:</p>
    <ul>
        <li>Total: {hits['total']}</li>
        <li>Monthly ({datetime.utcnow().strftime('%Y-%m')}): {hits['monthly'][datetime.utcnow().strftime('%Y-%m')]}</li>
        <li>Daily ({datetime.utcnow().strftime('%Y-%m-%d')}): {hits['daily'][datetime.utcnow().strftime('%Y-%m-%d')]}</li>
    </ul>
    """

    # Main content
    msg = VisaBulletinChecker.run_check()
    return f"{hit_info}<hr><pre>{msg}</pre>"

if __name__ == "__main__":
    app.run()
