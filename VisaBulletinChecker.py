import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil.relativedelta import relativedelta
import os

def run_check():
    try:
        # Step 1: Determine which months to check
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
            return "🔁 No bulletin found for this or last month."

        # Step 4: Scrape the bulletin page and find the target table
        resp = requests.get(matched_link)
        soup = BeautifulSoup(resp.content, "html.parser")

        target_table = None
        for bold in soup.find_all("b"):
            if "Employment-" in bold.get_text():
                table = bold.find_parent("table")
                if table:
                    target_table = table
                    break

        if not target_table:
            return "❌ Could not find the target table."

        # Step 5: Extract the table into clean text format
        rows = []
        for row in target_table.select("tr"):
            cols = [col.get_text(strip=True).replace('\xa0', ' ') for col in row.find_all(["th", "td"])]
            rows.append(" | ".join(cols))
        table_text = "\n".join(rows)

        # Step 6: Format message and return it
        bulletin_month, bulletin_year = get_bulletin_date_from_slug(matched_slug)

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
        return msg
    except Exception as e:
        return f"❌ An error occurred: {str(e)}"