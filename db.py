import sqlite3
import json
from pathlib import Path
from typing import Optional, Dict, Any, List


DB_SCHEMA = '''
CREATE TABLE IF NOT EXISTS permits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    permit_number TEXT UNIQUE,
    address TEXT,
    lat REAL,
    lon REAL,
    details_json TEXT,
    thumbnail_path TEXT,
    scraped_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_permits_scraped_at ON permits(scraped_at);
'''


class DB:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self):
        cur = self.conn.cursor()
        cur.executescript(DB_SCHEMA)
        self.conn.commit()

    def upsert_permit(self, permit_number: str, address: str | None, lat: Optional[float], lon: Optional[float], details: Dict[str, Any], scraped_at: str, thumbnail_path: str | None = None):
        cur = self.conn.cursor()
        details_json = json.dumps(details, ensure_ascii=False)
        cur.execute(
            '''INSERT INTO permits (permit_number, address, lat, lon, details_json, thumbnail_path, scraped_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(permit_number) DO UPDATE SET
                   address=excluded.address,
                   lat=excluded.lat,
                   lon=excluded.lon,
                   details_json=excluded.details_json,
                   thumbnail_path=excluded.thumbnail_path,
                   scraped_at=excluded.scraped_at
            ''',
            (permit_number, address, lat, lon, details_json, thumbnail_path, scraped_at)
        )
        self.conn.commit()

    def get_recent(self, limit: int = 30) -> List[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM permits ORDER BY scraped_at DESC LIMIT ?', (limit,))
        return cur.fetchall()

    def get_since(self, since_date: str) -> List[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM permits WHERE date(scraped_at) = date(?) ORDER BY scraped_at ASC', (since_date,))
        return cur.fetchall()

    def close(self):
        self.conn.close()


if __name__ == '__main__':
    print('Creating sample DB at ./data/epermits.db')
    db = DB('./data/epermits.db')
    db.upsert_permit('TEST-0001', '123 Main St, Denver, CO', 39.7392, -104.9903, {'type': 'demo'}, '2025-11-13T20:00:00', None)
    rows = db.get_recent()
    for r in rows:
        print(dict(r))
    db.close()
