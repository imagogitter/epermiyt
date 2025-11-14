"""
scraper.py

Usage: python scraper.py

This script uses Playwright to log into the Denver ePermits site and search for "%demo%".
It scrapes permit list results, visits each permit page, extracts key details, attempts to geocode addresses
and stores records in a central sqlite DB (see `db.py`).

Configure via .env (see config.example.env).
"""
import os
import time
import json
from datetime import datetime
from pathlib import Path
import requests
from geo_imagery import geocode_address, fetch_streetview_thumbnail, fetch_satellite_thumbnail
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from db import DB

load_dotenv()

EP_USER = os.getenv('EPERMITS_USERNAME')
EP_PASS = os.getenv('EPERMITS_PASSWORD')
DATA_DIR = Path(os.getenv('DATA_DIR', './data'))
DB_PATH = DATA_DIR / 'epermits.db'
GEOCODER_URL = os.getenv('GEOCODER_URL', 'https://nominatim.openstreetmap.org/search')
GEOCODER_EMAIL = os.getenv('GEOCODER_EMAIL', '')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

DATA_DIR.mkdir(parents=True, exist_ok=True)


# geocoding and thumbnail functions moved to geo_imagery.py and imported above


def parse_permit_detail(page):
    # Try to extract common fields; these selectors are based on the Playwright recording and may need tuning.
    def safe_text(sel):
        try:
            el = page.query_selector(sel)
            return el.inner_text().strip() if el else None
        except Exception:
            return None

    data = {}
    # Permit number
    data['permit_number'] = safe_text('#ctl00_PlaceHolderMain_lblCapID') or safe_text('span.permit-number') or None
    # Address
    data['address'] = safe_text('#ctl00_PlaceHolderMain_lblAddress') or safe_text('div.address') or None
    # Owner
    data['owner'] = safe_text('#ctl00_PlaceHolderMain_lblOwner') or None
    # More free text fallback: capture main content text
    try:
        body = page.inner_text('body')
        data['raw_text'] = body
    except Exception:
        data['raw_text'] = ''
    return data


def run_scrape(max_items=200):
    db = DB(DB_PATH)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Login flow based on recording
        page.goto('https://aca-prod.accela.com/DENVER/Login.aspx')
        # Some pages embed login in iframe; try top-level selectors first
        try:
            page.fill('#username', EP_USER)
            page.fill('#passwordRequired', EP_PASS)
            page.click('text=SIGN IN')
            page.wait_for_load_state('networkidle', timeout=15000)
        except Exception:
            print('Login attempt failed with top-level selectors; you may need to adapt selectors or check the page structure')

        # Navigate to development permit search
        page.goto('https://aca-prod.accela.com/DENVER/Cap/CapHome.aspx?module=Development')

        # Fill general search with %demo% (wildcard) and click search
        try:
            page.fill('#ctl00_PlaceHolderMain_generalSearchForm_txtGSPermitNumber', '%demo%')
            page.click('#ctl00_PlaceHolderMain_btnNewSearch')
            page.wait_for_load_state('networkidle', timeout=15000)
        except Exception:
            print('Search controls not found; please verify selectors')

        # Collect result permit links across paginated results
        permits = []
        seen_hrefs = set()
        max_pages = 25
        for page_idx in range(max_pages):
            # try known table selector first
            rows = page.query_selector_all('#ctl00_PlaceHolderMain_dgvPermitList_gdvPermitList td a') or page.query_selector_all('a')
            for a in rows:
                try:
                    text = a.inner_text().strip()
                    href = a.get_attribute('href')
                    if text and href and href not in seen_hrefs:
                        seen_hrefs.add(href)
                        permits.append({'text': text, 'href': href})
                except Exception:
                    continue

            # attempt to navigate to next page - several possible selectors
            next_clicked = False
            for sel in ['a[aria-label="Next"]', 'a:has-text("Next")', 'a:has-text("next")', 'a[title="Next"]', 'a.pager-next', 'text="Next"']:
                try:
                    btn = page.query_selector(sel)
                    if btn:
                        # check if disabled via class or aria-disabled
                        disabled = btn.get_attribute('aria-disabled') or btn.get_attribute('class')
                        if disabled and ('disabled' in (disabled or '').lower() or disabled == 'true'):
                            next_clicked = False
                            continue
                        btn.click()
                        page.wait_for_load_state('networkidle', timeout=10000)
                        time.sleep(1)
                        next_clicked = True
                        break
                except Exception:
                    continue

            if not next_clicked:
                break

        print(f'Found {len(permits)} permit links (will visit up to {max_items})')

        count = 0
        for item in permits:
            if count >= max_items:
                break
            try:
                page.goto(item['href'])
                page.wait_for_load_state('networkidle', timeout=10000)
                data = parse_permit_detail(page)
                permit_number = data.get('permit_number') or item['text']
                address = data.get('address')
                lat = lon = None
                # Try to find lat/lon on the page
                try:
                    # many ePermits include a map iframe with lat/lon in a href or script; naive search in page text
                    body = page.content()
                    import re
                    m = re.search(r'([-+]?[0-9]{1,3}\.[0-9]{4,}),\s*([-+]?[0-9]{1,3}\.[0-9]{4,})', body)
                    if m:
                        lat = float(m.group(1))
                        lon = float(m.group(2))
                except Exception:
                    pass

                if (not lat or not lon) and address:
                    lat, lon = geocode_address(address)
                    time.sleep(1)  # be polite to geocoder

                scraped_at = datetime.utcnow().isoformat()

                # fetch thumbnail (Street View preferred, satellite fallback)
                thumb_path = None
                if lat and lon:
                    fname = DATA_DIR / 'thumbs' / f'{permit_number.replace("/","_")}.jpg'
                    DATA_DIR.joinpath('thumbs').mkdir(parents=True, exist_ok=True)
                    try:
                        thumb = fetch_streetview_thumbnail(lat, lon, fname)
                        if thumb:
                            thumb_path = thumb
                    except Exception:
                        # last resort: try satellite directly
                        try:
                            thumb = fetch_satellite_thumbnail(lat, lon, fname)
                            if thumb:
                                thumb_path = thumb
                        except Exception:
                            thumb_path = None

                db.upsert_permit(permit_number, address, lat, lon, data, scraped_at, thumb_path)
                count += 1
                print(f'Scraped {permit_number} ({count})')
            except Exception as e:
                print('Error scraping item', item, e)

        db.close()
        browser.close()


if __name__ == '__main__':
    run_scrape()
