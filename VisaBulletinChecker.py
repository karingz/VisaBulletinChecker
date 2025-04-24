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
        now = os.getenv("TEST_DATE")
        if now:
            now = datetime.strptime(now, "%Y-%m-%d")
        else:
            now = datetime.now()

        slugs_to_try = [get_month_slug(now), get_month_slug(now - relativedelta(months=1))]

        # Step 2: Check the "Current Visa Bulletin" section on the index page
        resp = requests.get(INDEX_URL)
        soup = BeautifulSoup(resp.content, "html.parser")
        current_bulletin_section = soup.find("li", class_="current")

        if not current_bulletin_section:
            return ("<p>❌ Could not find the 'Current Visa Bulletin' section.</p>"
                    "<p>Please notice me with the screenshot of this page: <a href='mailto:imaginaryground@gmail.com'>imaginaryground@gmail.com</a></p>"), ""

        current_bulletin_link = current_bulletin_section.find("a", class_="btn btn-lg btn-success")
        if not current_bulletin_link:
            return ("<p>❌ Could not find the link to the current visa bulletin.</p>"
                    "<p>Please notice me with the screenshot of this page: <a href='mailto:imaginaryground@gmail.com'>imaginaryground@gmail.com</a></p>"), ""

        href = current_bulletin_link.get("href", "")
        if not href:
            return ("<p>❌ The current visa bulletin link is empty.</p>"
                    "<p>Please notice me with the screenshot of this page: <a href='mailto:imaginaryground@gmail.com'>imaginaryground@gmail.com</a></p>"), ""

        matched_link = BASE_URL + href if href.startswith("/") else href
        matched_slug = href.split("/")[-1]

        # Check if the current bulletin matches the current month
        bulletin_month, bulletin_year = get_bulletin_date_from_slug(matched_slug)
        if bulletin_month.lower() != now.strftime("%B").lower() or bulletin_year != str(now.year):
            # Proceed with the previous month's bulletin
            matched_slug = slugs_to_try[1].split("/")[-1]   # changing the slug to the previous month
            bulletin_month, bulletin_year = get_bulletin_date_from_slug(matched_slug)

        # Step 3: Scrape the bulletin page and find the target table
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

        # Step 4: Extract the table into clean HTML format
        table_html = '<table width="100%" border="1" cellspacing="0" cellpadding="3">'
        for row_index, row in enumerate(target_table.select("tr"), start=1):
            table_html += "<tr>"
            for col_index, col in enumerate(row.find_all(["th", "td"]), start=1):
                tag = "th" if col.name == "th" else "td"
                style = ' style="background-color: yellow; font-weight: bold;"' if row_index == 3 and col_index == 2 else ""
                table_html += f"<{tag}{style}>{col.get_text(strip=True).replace('\xa0', ' ')}</{tag}>"
            table_html += "</tr>"
        table_html += "</table>"

        # Step 5: Format message and return it
        bulletin_month, bulletin_year = get_bulletin_date_from_slug(matched_slug)

        if bulletin_month.lower() == now.strftime("%B").lower() and bulletin_year == str(now.year):
            msg = f"""
<h2>📢 [Visa Bulletin] {bulletin_month}-{bulletin_year} Released!</h2>
<span>🔗 <a href="{matched_link}" target="_blank">Official Visa Bulletin for {bulletin_month} {bulletin_year}</a></span>
<h3>📄 FINAL ACTION DATES FOR EMPLOYMENT-BASED CASES:</h3>
{table_html}"""
        else:
            msg = f"""
<h2>📢 [Visa Bulletin] {now.strftime('%B')}-{now.year} hasn't been released yet!</h2>
<p>Showing the bulletin for {bulletin_month}-{bulletin_year}.</p>
<p>🔗 <a href="{matched_link}" target="_blank">Official Visa Bulletin for {bulletin_month} {bulletin_year}</a></p>
<h3>📄 FINAL ACTION DATES FOR EMPLOYMENT-BASED CASES:</h3>
{table_html}"""

        # Step 6: Get current time to show last updated time
        from datetime import timezone as tz
        from zoneinfo import ZoneInfo

        kst_time = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M")
        pst_time = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M")
        cst_time = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M")
        est_time = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M")

        msg += """
        <table>
            <tr><td colspan="2">⌛ Last updated time:</td></tr>
            <tr><td>KST (Seoul)</td><td>{kst_time}</td></tr>
            <tr><td>PST (LA)</td><td>{pst_time}</td></tr>
            <tr><td>CST (Chicago)</td><td>{cst_time}</td></tr>
            <tr><td>EST (NY)</td><td>{est_time}</td></tr>
        </table>
        """.format(kst_time=kst_time, pst_time=pst_time, cst_time=cst_time, est_time=est_time)

        if return_month:
            return msg, f"{bulletin_year}-{bulletin_month}"
        return msg
    except Exception as e:
        error_msg = f"<p>❌ An error occurred: {str(e)}</p>"
        if return_month:
            return error_msg, ""  # Ensure two values are returned
        return error_msg
