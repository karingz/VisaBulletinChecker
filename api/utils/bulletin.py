import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil.relativedelta import relativedelta
import os

BASE_URL = "https://travel.state.gov"
INDEX_URL = f"{BASE_URL}/content/travel/en/legal/visa-law0/visa-bulletin.html"

# Utility Functions
def get_month_slug(dt):
    return dt.strftime("visa-bulletin/%Y/visa-bulletin-for-%B-%Y.html").lower()

def get_bulletin_date_from_slug(slug):
    parts = slug.split("/")[-1].replace("visa-bulletin-for-", "").replace(".html", "")
    month_name, year = parts.split("-")
    return month_name.capitalize(), year

# Scraping Functions
def fetch_index_page():
    try:
        resp = requests.get(INDEX_URL)
        resp.raise_for_status()
        return BeautifulSoup(resp.content, "html.parser")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch index page: {e}")

def find_current_bulletin_link(soup):
    current_section = soup.find("li", class_="current")
    if not current_section:
        raise ValueError("Could not find the 'Current Visa Bulletin' section.")
    link = current_section.find("a", class_="btn btn-lg btn-success")
    if not link or not link.get("href"):
        raise ValueError("Could not find a valid link to the current visa bulletin.")
    return link.get("href")

def fetch_bulletin_page(link):
    try:
        resp = requests.get(link)
        resp.raise_for_status()
        return BeautifulSoup(resp.content, "html.parser")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch bulletin page: {e}")

def extract_target_table(soup):
    for bold in soup.find_all("b"):
        if "Employment-" in bold.get_text():
            table = bold.find_parent("table")
            if table:
                return table
    raise ValueError("Could not find the target table in the bulletin page.")

# Formatting Functions
def format_table_html(table):
    table_html = '<table width="100%" border="1" cellspacing="0" cellpadding="3">'
    for row_index, row in enumerate(table.select("tr"), start=1):
        style = ' style="background-color: yellow;"' if row_index == 3 else ""
        table_html += f"<tr{style}>"
        for col_index, col in enumerate(row.find_all(["th", "td"]), start=1):
            tag = "th" if col.name == "th" else "td"
            table_html += f"<{tag}>{col.get_text(strip=True).replace('\xa0', ' ')}</{tag}>"
        table_html += "</tr>"
    table_html += "</table>"
    return table_html

def format_message(matched_link, bulletin_month, bulletin_year, table_html, is_current):
    if is_current:
        msg = f"""
        <pre><h2>📢 [Visa Bulletin] {bulletin_month}-{bulletin_year} Released!</h2></pre>
        <pre><span>🔗 <a href="{matched_link}" target="_blank">Official Visa Bulletin for {bulletin_month} {bulletin_year}</a></span></pre>
        <pre><h3>📄 FINAL ACTION DATES FOR EMPLOYMENT-BASED CASES:</h3></pre>
        <pre>{table_html}</pre>
        """
    else:
        msg = f"""
        <pre><h2>📢 [Visa Bulletin] {datetime.now().strftime('%B')}-{datetime.now().year} hasn't been released yet!</h2></pre>
        <pre><p>Showing the bulletin for {bulletin_month}-{bulletin_year}.</p></pre>
        <pre><p>🔗 <a href="{matched_link}" target="_blank">Official Visa Bulletin for {bulletin_month} {bulletin_year}</a></p></pre>
        <pre><h3>📄 FINAL ACTION DATES FOR EMPLOYMENT-BASED CASES:</h3></pre>
        <pre>{table_html}</pre>"""
    return msg

def append_last_updated_time(msg):
    from datetime import timezone as tz
    from zoneinfo import ZoneInfo

    kst_time = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M")
    pst_time = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M")
    cst_time = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M")
    est_time = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M")

    msg += f"""
    <pre><table>
        <tr><td colspan="2">⌛ Last updated time:</td></tr>
        <tr><td>KST (Seoul)</td><td>{kst_time}</td></tr>
        <tr><td>PST (LA)</td><td>{pst_time}</td></tr>
        <tr><td>CST (Chicago)</td><td>{cst_time}</td></tr>
        <tr><td>EST (NY)</td><td>{est_time}</td></tr>
    </table></pre>
    """
    return msg

# Main Function
def run_check(return_month=False):
    try:
        # Step 1: Determine which months to check
        now = os.getenv("TEST_DATE")
        now = datetime.strptime(now, "%Y-%m-%d") if now else datetime.now()
        slugs_to_try = [get_month_slug(now), get_month_slug(now - relativedelta(months=1))]

        # Step 2: Scrape the index page and find the current bulletin link
        index_soup = fetch_index_page()
        href = find_current_bulletin_link(index_soup)
        matched_link = BASE_URL + href if href.startswith("/") else href
        matched_slug = href.split("/")[-1]

        # Step 3: Check if the current bulletin matches the current month
        bulletin_month, bulletin_year = get_bulletin_date_from_slug(matched_slug)
        is_current = bulletin_month.lower() == now.strftime("%B").lower() and bulletin_year == str(now.year)
        if not is_current:
            matched_slug = slugs_to_try[1].split("/")[-1]
            bulletin_month, bulletin_year = get_bulletin_date_from_slug(matched_slug)

        # Step 4: Scrape the bulletin page and extract the target table
        bulletin_soup = fetch_bulletin_page(matched_link)
        target_table = extract_target_table(bulletin_soup)

        # Step 5: Format the table and message
        table_html = format_table_html(target_table)
        msg = format_message(matched_link, bulletin_month, bulletin_year, table_html, is_current)
        msg = append_last_updated_time(msg)

        if return_month:
            return msg, f"{bulletin_year}-{bulletin_month}"
        return msg
    except Exception as e:
        error_msg = f"<p>❌ An error occurred: {str(e)}</p>"
        if return_month:
            return error_msg, ""
        return error_msg