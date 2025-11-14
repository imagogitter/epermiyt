"""
geo_imagery.py

Shared geocoding and imagery helpers used by the scraper and thumbnail generator.
This module avoids importing Playwright so it can be used in lightweight environments.
"""
import os
import math
from pathlib import Path
from io import BytesIO
from PIL import Image
from utils import get_requests_session, retry_backoff

_session = get_requests_session()

GEOCODER_URL = os.getenv('GEOCODER_URL', 'https://nominatim.openstreetmap.org/search')
GEOCODER_EMAIL = os.getenv('GEOCODER_EMAIL', '')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')


@retry_backoff(max_attempts=4, initial_delay=0.5, factor=2.0, exceptions=(Exception,))
def geocode_address(address: str):
    params = {'q': address, 'format': 'json', 'limit': 1}
    if GEOCODER_EMAIL:
        params['email'] = GEOCODER_EMAIL
    resp = _session.get(GEOCODER_URL, params=params, timeout=15)
    if resp.status_code == 200:
        j = resp.json()
        if j:
            return float(j[0]['lat']), float(j[0]['lon'])
    return None, None


def _deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile


def fetch_satellite_thumbnail(lat, lon, outpath: Path, size=(400, 300), zoom=18, tiles=3, tilesize=256):
    """
    Build a satellite thumbnail by downloading `tiles x tiles` tiles from Esri World Imagery and stitching them.
    """
    outpath = Path(outpath)
    headers = {'User-Agent': 'epermits-scraper/1.0 (+https://example.com)'}

    center_x, center_y = _deg2num(lat, lon, zoom)
    half = tiles // 2
    canvas_size = tiles * tilesize
    canvas = Image.new('RGB', (canvas_size, canvas_size))

    for dx in range(-half, half + 1):
        for dy in range(-half, half + 1):
            tx = center_x + dx
            ty = center_y + dy
            url = f'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{zoom}/{ty}/{tx}'
            try:
                r = _session.get(url, timeout=10)
                if r.status_code == 200:
                    tile_img = Image.open(BytesIO(r.content)).convert('RGB')
                else:
                    tile_img = Image.new('RGB', (tilesize, tilesize), (200, 200, 200))
            except Exception:
                tile_img = Image.new('RGB', (tilesize, tilesize), (200, 200, 200))

            px = (dx + half) * tilesize
            py = (dy + half) * tilesize
            canvas.paste(tile_img, (px, py))

    cx = canvas.width // 2
    cy = canvas.height // 2
    w, h = size
    left = max(0, cx - w // 2)
    top = max(0, cy - h // 2)
    cropped = canvas.crop((left, top, left + w, top + h))
    outpath.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(outpath, format='JPEG', quality=85)
    return str(outpath)


def fetch_streetview_thumbnail(lat, lon, outpath: Path, size=(400, 300)):
    """
    Try Google Street View if API key present; otherwise fall back to satellite thumbnail.
    """
    outpath = Path(outpath)
    if GOOGLE_API_KEY:
        try:
            url = 'https://maps.googleapis.com/maps/api/streetview'
            params = {'size': f'{size[0]}x{size[1]}', 'location': f'{lat},{lon}', 'key': GOOGLE_API_KEY}
            r = _session.get(url, params=params, stream=True, timeout=20)
            if r.status_code == 200:
                outpath.parent.mkdir(parents=True, exist_ok=True)
                with open(outpath, 'wb') as fh:
                    for chunk in r.iter_content(1024):
                        fh.write(chunk)
                return str(outpath)
        except Exception:
            pass
    # fallback
    return fetch_satellite_thumbnail(lat, lon, outpath, size=size)
