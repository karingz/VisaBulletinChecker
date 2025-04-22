import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil.relativedelta import relativedelta
import os

BASE_URL = "https://travel.state.gov"
INDEX_URL = f"{BASE_URL}/content/travel/en/legal/visa-law0/visa-bulletin.html"
# LAST_NOTIFIED_FILE = "last_notified.txt"

def get_month_slug(dt):
    return dt.strftime("visa-bulletin/%Y/visa-bulletin-for-%B-%Y.html").lower()

def get_bulletin_date_from_slug(slug):
    # Extract the month and year from the slug (e.g., "visa-bulletin-for-{month}-{year}.html")
    parts = slug.split("/")[-1].replace("visa-bulletin-for-", "").replace(".html", "")
    month_name, year = parts.split("-")
    return month_name.capitalize(), year  # Returns both month and year

# Step 1: Determine which months to check (this month, fallback to last month)
now = datetime.now()
now = datetime(2025, 5, 1)  # For testing purposes, set a specific date
slugs_to_try = [get_month_slug(now + relativedelta(months=1)), get_month_slug(now)]

# Step 2: Fetch bulletin links from index page
resp = requests.get(INDEX_URL)
soup = BeautifulSoup(resp.content, "html.parser")
links = soup.select("a[href*='visa-bulletin-for']")

matched_slug = None
matched_link = None
for slug in slugs_to_try:
    for a in links:
        href = a.get("href", "")
        if slug in href:
            matched_link = BASE_URL + href if href.startswith("/") else href
            matched_slug = slug
            break
    if matched_link:
        break

if not matched_link:
    print("🔁 No bulletin found for this or last month.")
    exit()

# Step 4: Scrape the bulletin page and find the target table
resp = requests.get(matched_link)
soup = BeautifulSoup(resp.content, "html.parser")

# Find the <b> tag that contains "Employment-" and get its parent table
target_table = None
for bold in soup.find_all("b"):
    if "Employment-" in bold.get_text():
        table = bold.find_parent("table")
        if table:
            target_table = table
            break

if not target_table:
    print("❌ Could not find the target table.")
    exit()

# Step 5: Extract the table into clean text format
rows = []
for row in target_table.select("tr"):
    cols = [col.get_text(strip=True).replace('\xa0', ' ') for col in row.find_all(["th", "td"])]
    rows.append(" | ".join(cols))
table_text = "\n".join(rows)

# Step 6: Format message and print it
bulletin_month, bulletin_year = get_bulletin_date_from_slug(matched_slug)

# Check if the matched bulletin is for the current month
if datetime.strptime(bulletin_month, "%B").month == (now + relativedelta(months=1)).month:
    message_month = bulletin_month
    msg = f"""
📢 [Visa Bulletin] {message_month}-{bulletin_year} Released!

🔗 {matched_link}

📄 FINAL ACTION DATES FOR EMPLOYMENT-BASED CASES:
{table_text}
"""
else:
    msg = f"""
    📢 [Visa Bulletin] {(now + relativedelta(months=1)).strftime('%B')}-{now.year} hasn't been released yet! Showing the bulletin for {bulletin_month}-{bulletin_year}.

🔗 {matched_link}

📄 FINAL ACTION DATES FOR EMPLOYMENT-BASED CASES:
{table_text}
"""

print(msg)

# # Step 7: Save as last notified
# with open(LAST_NOTIFIED_FILE, "w") as f:
#     f.write(matched_slug)
