import requests
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://travel.state.gov"
INDEX_URL = f"{BASE_URL}/content/travel/en/legal/visa-law0/visa-bulletin.html"

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

def extract_target_tables(soup):
    tables = []
    for bold in soup.find_all("b"):
        text = bold.get_text()
        if "Employment-" in text:
            table = bold.find_parent("table")
            if table and table not in tables:
                tables.append(table)
    if not tables:
        raise ValueError("Could not find the target tables in the bulletin page.")
    return tables

def extract_eb2_all_other(soup):
    """Extract EB-2 'All Other' priority dates from a bulletin page.
    Returns (final_action_date, filing_date). filing_date is None for pre-2015."""
    try:
        tables = extract_target_tables(soup)
    except ValueError:
        return None, None

    def _get_eb2_value(table):
        for row in table.select("tr"):
            cells = row.find_all(["th", "td"])
            if not cells:
                continue
            first_cell = cells[0].get_text(strip=True).replace('\xa0', ' ')
            if "2nd" in first_cell and len(cells) > 1:
                return cells[1].get_text(strip=True).replace('\xa0', ' ')
        return None

    fad = _get_eb2_value(tables[0]) if tables else None
    filing = _get_eb2_value(tables[1]) if len(tables) > 1 else None
    return fad, filing

# Formatting Functions
def format_table_html(table):
    header_style = (
        'style="background-color:#06284c; color:#ffffff; padding:10px 14px;'
        ' font-size:14px; font-weight:600; text-align:left;'
        ' border-bottom:2px solid #0e3d6b; font-variant-numeric:tabular-nums;"'
    )
    highlight_row_style = 'style="background-color:#fff3cd;"'
    odd_row_style = 'style="background-color:#f0f4fa;"'
    even_row_style = 'style="background-color:#ffffff;"'
    cell_style = (
        'style="padding:10px 14px; border-bottom:1px solid #e2e8f0;'
        ' font-size:13px; text-align:left; font-variant-numeric:tabular-nums;"'
    )

    table_html = (
        '<table width="100%" cellspacing="0" cellpadding="0"'
        ' style="border-collapse:collapse; border:1px solid #d1d9e6;'
        ' border-radius:8px; overflow:hidden; font-family:Arial, sans-serif;">'
    )
    for row_index, row in enumerate(table.select("tr"), start=1):
        if row_index == 1:
            row_attr = ""
        elif row_index == 3:
            row_attr = f' class="eb2-row" {highlight_row_style}'
        elif row_index % 2 == 0:
            row_attr = f" {even_row_style}"
        else:
            row_attr = f" {odd_row_style}"
        table_html += f"<tr{row_attr}>"
        for col in row.find_all(["th", "td"]):
            text = col.get_text(separator=' ', strip=True).replace('\xa0', ' ')
            text = _shorten_label(text)
            if row_index == 1:
                table_html += f"<th {header_style}>{text}</th>"
            else:
                table_html += f"<td {cell_style}>{text}</td>"
        table_html += "</tr>"
    table_html += "</table>"
    return table_html

def _shorten_label(text):
    replacements = {
        "All Chargeability Areas Except Those Listed": "All Other",
        "CHINA- mainland born": "China",
        "CHINA-mainland born": "China",
        "Certain Religious Workers": "Religious Workers",
        "Employment- based": "Category",
        "Employment-based": "Category",
    }
    for long, short in replacements.items():
        if text == long:
            return short
    # Shorten 5th preference variants — keywords may be inside or outside parens
    if text.startswith("5th"):
        if "High Unemployment" in text:
            return "5th High Unemp."
        if "Infrastructure" in text:
            return "5th Infrastructure"
        if "Rural" in text:
            return "5th Rural"
        if "Unreserved" in text:
            return "5th Unreserved"
    return text

def format_message(matched_link, bulletin_month, bulletin_year, final_action_html, filing_dates_html):
    link_style = 'style="color:#2563eb; text-decoration:none;"'
    section_title_style = (
        'style="font-size:15px; font-weight:600; color:#334155;'
        ' margin:24px 0 12px 0; padding:0;"'
    )

    header = (
        f'<h2 style="font-size:22px; color:#06284c; margin:0 0 8px 0;">'
        f'📢 Visa Bulletin for {bulletin_month} {bulletin_year}</h2>'
        f'<p style="margin:0 0 20px 0;">'
        f'🔗 <a href="{matched_link}" target="_blank" {link_style}>'
        f'View Official Bulletin</a></p>'
    )

    msg = header
    msg += f'<h3 {section_title_style}>📄 Final Action Dates</h3>'
    msg += final_action_html
    if filing_dates_html:
        msg += f'<h3 {section_title_style}>📄 Dates for Filing</h3>'
        msg += filing_dates_html
    return msg

def append_last_updated_time(msg):
    from zoneinfo import ZoneInfo

    kst_time = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M")
    pst_time = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M")
    cst_time = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M")
    est_time = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M")

    label_style = 'style="padding:4px 12px 4px 0; color:#64748b; font-size:12px;"'
    time_style = 'style="padding:4px 0; color:#334155; font-size:12px; font-variant-numeric:tabular-nums;"'

    msg += f"""
    <table style="margin-top:24px; border-collapse:collapse; font-family:Arial, sans-serif;">
        <tr><td colspan="2" style="padding:4px 0 8px 0; font-size:12px; color:#94a3b8; font-weight:600;">⌛ Last updated time:</td></tr>
        <tr><td {label_style}>KST (Seoul)</td><td {time_style}>{kst_time}</td></tr>
        <tr><td {label_style}>PST (LA)</td><td {time_style}>{pst_time}</td></tr>
        <tr><td {label_style}>CST (Chicago)</td><td {time_style}>{cst_time}</td></tr>
        <tr><td {label_style}>EST (NY)</td><td {time_style}>{est_time}</td></tr>
    </table>
    """
    return msg

# Main Function
def run_check(return_month=False, return_eb2=False):
    try:
        # Step 1: Scrape the index page and find the current bulletin link
        index_soup = fetch_index_page()
        href = find_current_bulletin_link(index_soup)
        matched_link = BASE_URL + href if href.startswith("/") else href

        # Step 2: Extract month/year from the bulletin link
        matched_slug = href.split("/")[-1]
        bulletin_month, bulletin_year = get_bulletin_date_from_slug(matched_slug)

        # Step 3: Scrape the bulletin page and extract the target tables
        bulletin_soup = fetch_bulletin_page(matched_link)
        tables = extract_target_tables(bulletin_soup)

        # Step 4: Format the tables and message
        final_action_html = format_table_html(tables[0])
        filing_dates_html = format_table_html(tables[1]) if len(tables) > 1 else ""
        msg = format_message(matched_link, bulletin_month, bulletin_year, final_action_html, filing_dates_html)
        msg = append_last_updated_time(msg)

        if return_month and return_eb2:
            fad, filing = extract_eb2_all_other(bulletin_soup)
            return msg, f"{bulletin_year}-{bulletin_month}", fad, filing, matched_link
        if return_month:
            return msg, f"{bulletin_year}-{bulletin_month}"
        return msg
    except Exception as e:
        error_msg = f"<p>❌ An error occurred: {str(e)}</p>"
        if return_month and return_eb2:
            return error_msg, "", None, None, None
        if return_month:
            return error_msg, ""
        return error_msg
