"""
addy_provider.py

Simple HTTP adapter for sending email via Addy.io-like transactional API.

This implementation POSTs a JSON payload to the configured endpoint with a Bearer API key.
It embeds local image assets as data URIs into the HTML so attachments aren't required.

Note: confirm the exact Addy API endpoint and field names for production usage. The URL used here
is a reasonable default placeholder and can be overridden via the `ADDY_API_URL` env var.
"""
import os
import base64
from pathlib import Path
from utils import get_requests_session, retry_backoff
import logging

_session = get_requests_session(retries=3, backoff_factor=0.5)


def _embed_images_into_html(html: str, assets_dir: Path | None):
    if not assets_dir or not assets_dir.exists():
        return html
    assets_dir = Path(assets_dir)
    for img in assets_dir.iterdir():
        if img.suffix.lower() in ('.png', '.jpg', '.jpeg', '.gif'):
            try:
                b = img.read_bytes()
                mime = 'image/jpeg' if img.suffix.lower() in ('.jpg', '.jpeg') else f'image/{img.suffix.lstrip('.')}'
                data = base64.b64encode(b).decode('ascii')
                data_uri = f'data:{mime};base64,{data}'
                html = html.replace(f'data/{img.name}', data_uri)
            except Exception:
                continue
    return html


@retry_backoff(max_attempts=4, initial_delay=0.5, factor=2.0, exceptions=(Exception,))
def send_via_addy(api_key: str, email_from: str, email_to: str, subject: str, html: str, assets_dir: Path | None = None, api_url: str | None = None) -> bool:
    """
    Send email via Addy HTTP API. Returns True on accepted (2xx) response.
    Retries transient errors.
    """
    api_url = api_url or os.getenv('ADDY_API_URL', 'https://api.addy.io/v1/messages')
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

    # embed images as data URIs so we don't need multipart uploads
    html_embedded = _embed_images_into_html(html, assets_dir)

    payload = {
        'from': email_from,
        'to': email_to,
        'subject': subject,
        'html': html_embedded,
    }

    try:
        r = _session.post(api_url, json=payload, headers=headers, timeout=20)
    except Exception:
        logging.exception('Addy request failed (network/DNS)')
        raise

    # Log status & body for diagnostics
    try:
        txt = r.text
    except Exception:
        txt = '<unreadable body>'
    logging.info('Addy response status=%s body=%s', r.status_code, txt[:2000])

    # Accept 200-299; some Addy-compatible endpoints may return 201
    if 200 <= r.status_code < 300:
        return True
    else:
        # Try to parse JSON error for clearer logging
        try:
            j = r.json()
            logging.error('Addy returned error JSON: %s', j)
        except Exception:
            logging.error('Addy returned non-JSON error: %s', txt[:1000])
        return False
