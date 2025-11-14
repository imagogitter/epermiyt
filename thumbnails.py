"""
thumbnails.py

Generate thumbnails for the N most recent permits in the DB.
"""
import os
from pathlib import Path
from db import DB
from geo_imagery import fetch_streetview_thumbnail, fetch_satellite_thumbnail

DATA_DIR = Path(os.getenv('DATA_DIR', './data'))
DB_PATH = DATA_DIR / 'epermits.db'


def generate_recent_thumbnails(limit: int = 30, size=(400, 300)):
    db = DB(DB_PATH)
    rows = db.get_recent(limit)
    generated = []
    for r in rows:
        permit = r['permit_number']
        lat = r['lat']
        lon = r['lon']
        thumb = r['thumbnail_path']
        if not (lat and lon):
            continue
        if thumb and Path(thumb).exists():
            continue
        fname = DATA_DIR / 'thumbs' / f"{permit.replace('/', '_')}.jpg"
        # try streetview first (may fallback internally)
        out = fetch_streetview_thumbnail(lat, lon, fname, size=size)
        if out:
            db.upsert_permit(permit, r['address'], lat, lon, r['details_json'] and r['details_json'], r['scraped_at'], str(out))
            generated.append(str(out))
    db.close()
    return generated


if __name__ == '__main__':
    print('Generating thumbnails for recent permits...')
    outs = generate_recent_thumbnails()
    print('Generated', len(outs), 'thumbnails')
