import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil.relativedelta import relativedelta
import os

BASE_URL = "https://travel.state.gov"
INDEX_URL = f"{BASE_URL}/content/travel/en/legal/visa-law0/visa-bulletin.html"

def get_month_slug(dt):
    return dt.strftime("visa-bulletin/%Y/visa-bulletin-for-%B-%Y.html").lower()

def get_bulletin_date_from_slug(slug):
    parts = slug.split("/")[-1].replace("visa-bulletin-for-", "").replace(".html", "")
    month_name, year = parts.split("-")
    return month_name.capitalize(), year

def run_check(return_month=False):
    try:
        # Step 1: Determine which months to check
        now = datetime.now()
        now = datetime(2025, 1, 1)
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
            return "<p>🔁 No bulletin found for this or last month.</p>"

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
            return "<p>❌ Could not find the target table.</p>"

        # Step 5: Extract the table into clean HTML format
        table_html = '<table width="100%" border="1" cellspacing="0" cellpadding="3">'
        for row_index, row in enumerate(target_table.select("tr"), start=1):
            table_html += "<tr>"
            for col_index, col in enumerate(row.find_all(["th", "td"]), start=1):
                tag = "th" if col.name == "th" else "td"
                style = ' style="background-color: yellow; font-weight: bold;"' if row_index == 3 and col_index == 2 else ""
                table_html += f"<{tag}{style}>{col.get_text(strip=True).replace('\xa0', ' ')}</{tag}>"
            table_html += "</tr>"
        table_html += "</table>"

        # Step 6: Format message and return it
        bulletin_month, bulletin_year = get_bulletin_date_from_slug(matched_slug)

        if datetime.strptime(bulletin_month, "%B").month == (now + relativedelta(months=1)).month:
            message_month = bulletin_month
            msg = f"""
            <h2>📢 [Visa Bulletin] {message_month}-{bulletin_year} Released!</h2>
            <p>🔗 <a href="{matched_link}" target="_blank">{matched_link}</a></p>
            <h3>📄 FINAL ACTION DATES FOR EMPLOYMENT-BASED CASES:</h3>
            {table_html}
            """
        else:
            msg = f"""
            <h2>📢 [Visa Bulletin] {(now + relativedelta(months=1)).strftime('%B')}-{now.year} hasn't been released yet!</h2>
            <p>Showing the bulletin for {bulletin_month}-{bulletin_year}.</p>
            <p>🔗 <a href="{matched_link}" target="_blank">{matched_link}</a></p>
            <h3>📄 FINAL ACTION DATES FOR EMPLOYMENT-BASED CASES:</h3>
            {table_html}
            """

        last_updated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        # Get current time in KST, Texas, and California
        from pytz import timezone

        kst_time = datetime.now(timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M KST")
        pst_time = datetime.now(timezone("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M PST")
        cst_time = datetime.now(timezone("America/Chicago")).strftime("%Y-%m-%d %H:%M CST")
        est_time = datetime.now(timezone("America/New_York")).strftime("%Y-%m-%d %H:%M EST")

        msg += f"<p>KST: {kst_time}</p>"
        msg += f"<p>PST: {pst_time}</p>"
        msg += f"<p>CST: {cst_time}</p>"
        msg += f"<p>EST: {est_time}</p>"
        msg += f"<p>Last updated: {last_updated}</p>"

        if return_month:
            return msg, f"{bulletin_year}-{bulletin_month}"
        return msg
    except Exception as e:
        return f"<p>❌ An error occurred: {str(e)}</p>"
