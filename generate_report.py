"""
generate_report.py

Creates a daily HTML report for yesterday's scraped records.
The HTML is interactive (Leaflet with satellite tiles) and includes thumbnails (if available)
and hover details. It writes the HTML to data/report-YYYY-MM-DD.html
"""
import os
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
from db import DB

load_dotenv()

DATA_DIR = Path(os.getenv('DATA_DIR', './data'))
DB_PATH = DATA_DIR / 'epermits.db'
TEMPLATES_DIR = Path(__file__).parent / 'templates'
OUT_DIR = DATA_DIR / 'reports'
OUT_DIR.mkdir(parents=True, exist_ok=True)


def render_report(for_date: datetime):
    db = DB(DB_PATH)
    rows = db.get_since(for_date.isoformat())
    records = []
    for r in rows:
        rec = dict(r)
        # details JSON -> dict
        try:
            import json
            rec['details'] = json.loads(rec['details_json']) if rec['details_json'] else {}
        except Exception:
            rec['details'] = {}
        records.append(rec)
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template('report.html')
    outname = OUT_DIR / f'report-{for_date.date().isoformat()}.html'
    # copy thumbnails into report folder (so HTML can be sent standalone), unless SKIP_THUMBS
    skip_thumbs = os.getenv('SKIP_THUMBS', '').lower() in ('1', 'true', 'yes')
    assets_dir = OUT_DIR / 'data'
    if not skip_thumbs:
        assets_dir.mkdir(parents=True, exist_ok=True)
        for r in records:
            if r.get('thumbnail_path'):
                src = Path(r['thumbnail_path'])
                if src.exists():
                    dst = assets_dir / src.name
                    try:
                        from shutil import copyfile
                        copyfile(src, dst)
                        # update path to be referenced relative to report file
                        r['thumbnail_path'] = str(dst)
                    except Exception:
                        pass
    else:
        # ensure assets dir exists but leave empty
        assets_dir.mkdir(parents=True, exist_ok=True)

    html = template.render(records=records, title=f'ePermits updates for {for_date.date().isoformat()}')
    outname.write_text(html, encoding='utf8')
    print('Wrote', outname)
    db.close()
    return outname


if __name__ == '__main__':
    yesterday = datetime.utcnow() - timedelta(days=1)
    # Only Mon-Fri as per requirement: skip weekends
    if yesterday.weekday() >= 5:
        print('Yesterday was weekend; no report generated (Mon-Fri only)')
    else:
        render_report(yesterday)
