#!/usr/bin/env python3
"""
One-time backfill script to scrape all historical EB-2 'All Other' priority dates
from the U.S. State Department Visa Bulletin archives.

Usage:
    DATABASE_URL="postgres://..." python scripts/backfill_history.py

Requires the bulletin_history table to exist (see Step 1 in the plan).
Rate-limited to 1 request/sec. Idempotent (ON CONFLICT DO NOTHING).
"""

import os
import sys
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import psycopg2

BASE_URL = "https://travel.state.gov"
INDEX_URL = f"{BASE_URL}/content/travel/en/legal/visa-law0/visa-bulletin.html"
DB_URL = os.getenv("DATABASE_URL")

MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]


def get_db_connection():
    return psycopg2.connect(DB_URL)


COUNTRY_COLUMNS = {
    'all_other': 1,
    'china': 2,
    'india': 3,
    'mexico': 4,
    'philippines': 5,
}

CATEGORIES = ['1st', '2nd', '3rd']

def extract_eb2_all_categories(soup):
    """Extract employment data for all categories and countries."""
    tables = []
    for bold in soup.find_all("b"):
        text = bold.get_text()
        if "Employment-" in text or "Employment" in text:
            table = bold.find_parent("table")
            if table and table not in tables:
                tables.append(table)

    if not tables:
        return None

    def _get_all_values(table):
        results = {}
        for row in table.select("tr"):
            cells = row.find_all(["th", "td"])
            if not cells:
                continue
            first_cell = cells[0].get_text(strip=True).replace('\xa0', ' ')
            cat = None
            for c in CATEGORIES:
                if c in first_cell:
                    cat = c
                    break
            if not cat:
                continue
            results[cat] = {}
            for country, idx in COUNTRY_COLUMNS.items():
                if idx < len(cells):
                    results[cat][country] = cells[idx].get_text(strip=True).replace('\xa0', ' ')
        return results

    fad_data = _get_all_values(tables[0])
    filing_data = _get_all_values(tables[1]) if len(tables) > 1 else {}

    records = []
    for cat in CATEGORIES:
        for country in COUNTRY_COLUMNS:
            fad = fad_data.get(cat, {}).get(country)
            filing = filing_data.get(cat, {}).get(country)
            if fad is not None:
                records.append({'category': cat, 'country': country, 'fad': fad, 'filing': filing})
    return records if records else None


def find_all_bulletin_links():
    """Crawl the State Dept archive to find all individual bulletin page links."""
    bulletin_links = []
    visited_years = set()

    print("Fetching main index page...")
    resp = requests.get(INDEX_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "html.parser")

    # Collect year page URLs from the main index
    year_urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/visa-bulletin/" not in href:
            continue
        full_url = urljoin(BASE_URL, href)
        filename = href.rstrip("/").split("/")[-1].replace(".html", "")

        # Year archive page (e.g., /visa-bulletin/2024.html)
        if filename.isdigit() and len(filename) == 4 and filename not in visited_years:
            visited_years.add(filename)
            year_urls.append(full_url)
        # Direct bulletin link on index page
        elif "visa-bulletin-for-" in filename.lower():
            if full_url not in bulletin_links:
                bulletin_links.append(full_url)

    print(f"Found {len(year_urls)} year archive pages")

    # Crawl each year page for bulletin links
    for year_url in sorted(year_urls):
        time.sleep(1)
        print(f"  Crawling {year_url}...")
        try:
            resp = requests.get(year_url, timeout=30)
            if not resp.ok:
                print(f"    WARN: HTTP {resp.status_code}")
                continue
            year_soup = BeautifulSoup(resp.content, "html.parser")
            for a in year_soup.find_all("a", href=True):
                href = a["href"]
                if "visa-bulletin-for-" in href.lower():
                    full_url = urljoin(BASE_URL, href)
                    if full_url not in bulletin_links:
                        bulletin_links.append(full_url)
        except Exception as e:
            print(f"    ERROR: {e}")

    return bulletin_links


def parse_month_from_url(url):
    """Extract bulletin month as a date from the URL slug.
    Returns date(YYYY, MM, 1) or None."""
    slug = url.split("/")[-1].replace(".html", "").lower()
    slug = slug.replace("visa-bulletin-for-", "")

    # Handle formats like "february-2025" or "february2025"
    for i, month_name in enumerate(MONTH_NAMES, 1):
        if month_name in slug:
            # Extract year: look for 4-digit number after the month name
            remainder = slug.replace(month_name, "").strip("-_ ")
            year = None
            for part in remainder.split("-"):
                part = part.strip()
                if part.isdigit() and len(part) == 4:
                    year = int(part)
                    break
            if year is None:
                # Try extracting year from any 4-digit sequence
                import re
                match = re.search(r'(\d{4})', remainder)
                if match:
                    year = int(match.group(1))
            if year and 1990 <= year <= 2030:
                return datetime(year, i, 1).date()

    return None


def main():
    if not DB_URL:
        print("ERROR: Set DATABASE_URL environment variable")
        sys.exit(1)

    print("=== Visa Bulletin EB-2 History Backfill ===\n")

    links = find_all_bulletin_links()
    print(f"\nFound {len(links)} total bulletin links\n")

    conn = get_db_connection()
    inserted = 0
    skipped = 0
    errors = 0

    for url in sorted(links):
        month = parse_month_from_url(url)
        if not month:
            print(f"  SKIP (can't parse month): {url}")
            skipped += 1
            continue

        time.sleep(1)  # Rate limiting
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")
            records = extract_eb2_all_categories(soup)

            if records is None:
                print(f"  SKIP (no EB-2 data): {month} — {url}")
                skipped += 1
                continue

            for r in records:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO bulletin_history (bulletin_month, category, country, final_action_date, filing_date, source_url)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (bulletin_month, category, country) DO UPDATE SET
                            final_action_date = EXCLUDED.final_action_date,
                            filing_date = EXCLUDED.filing_date,
                            source_url = EXCLUDED.source_url
                        """,
                        (month, r['category'], r['country'], r.get('fad'), r.get('filing'), url),
                    )
            conn.commit()
            inserted += 1
            print(f"  OK: {month} — {len(records)} records")
        except Exception as e:
            errors += 1
            print(f"  ERROR: {month} — {e}")

    conn.close()
    print(f"\nDone: {inserted} inserted, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    main()
