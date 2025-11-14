import os
import sys
import tempfile
from pathlib import Path

# ensure project root is on sys.path so imports like `from db import DB` work when running tests directly
PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from db import DB


def test_db_upsert_and_query():
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    try:
        db = DB(path)
        db.upsert_permit('TEST-1', '1 Main St', 39.0, -104.0, {'a': 1}, '2025-11-13T00:00:00', None)
        rows = db.get_recent(10)
        assert len(rows) == 1
        assert rows[0]['permit_number'] == 'TEST-1'
        db.upsert_permit('TEST-1', '1 Main St', 39.0, -104.0, {'a': 2}, '2025-11-14T00:00:00', None)
        rows = db.get_recent(10)
        assert len(rows) == 1
        assert '2025-11-14' in rows[0]['scraped_at']
    finally:
        try:
            os.remove(path)
        except Exception:
            pass

if __name__ == '__main__':
    test_db_upsert_and_query()
    print('db test passed')
