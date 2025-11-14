"""
email_send.py

Sends an HTML report (and its local images) via SMTP.
Configure SMTP via environment variables (see config.example.env).
This module also supports programmatic and CLI overrides for one-off tests.
"""
import os
import smtplib
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT') or 587)
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASS = os.getenv('SMTP_PASS')
EMAIL_FROM = os.getenv('EMAIL_FROM')
EMAIL_TO = os.getenv('EMAIL_TO')


def send_report(html_path: Path, assets_dir: Path | None = None, subject: str | None = None,
                smtp_host: str | None = None, smtp_port: int | None = None,
                smtp_user: str | None = None, smtp_pass: str | None = None,
                email_from: str | None = None, email_to: str | None = None):
    """
    Send report HTML. Any of the SMTP or email parameters, if provided, override environment values.
    This allows one-off CLI tests without writing credentials to disk.
    """
    html_path = Path(html_path)
    assets_dir = Path(assets_dir) if assets_dir else None
    html = html_path.read_text(encoding='utf8')

    # resolve settings with overrides
    _smtp_host = smtp_host or SMTP_HOST
    _smtp_port = int(smtp_port or SMTP_PORT)
    _smtp_user = smtp_user or SMTP_USER
    _smtp_pass = smtp_pass or SMTP_PASS
    _from = email_from or EMAIL_FROM
    _to = email_to or EMAIL_TO

    msg = EmailMessage()
    msg['From'] = _from
    msg['To'] = _to
    msg['Subject'] = subject or f'ePermits daily report {html_path.name}'
    msg.set_content('This is an HTML report. If you see this text, your client does not support HTML.')

    # Prepare inline image attachments and map filenames -> CIDs
    cid_map = {}
    if assets_dir and assets_dir.exists():
        for img in assets_dir.iterdir():
            if img.suffix.lower() in ('.png', '.jpg', '.jpeg', '.gif'):
                cid = make_msgid(domain='epermits')
                with open(img, 'rb') as fh:
                    content = fh.read()
                maintype = 'image'
                subtype = img.suffix.lstrip('.').lower()
                msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=img.name, headers={'Content-ID': f'<{cid.strip("<>")}>', 'Content-Disposition': 'inline'})
                cid_map[img.name] = cid.strip('<>')
                html = html.replace(f'data/{img.name}', f'cid:{cid_map[img.name]}')

    # Add HTML part
    msg.add_alternative(html, subtype='html')

    # Choose transport: SSL on 465, otherwise STARTTLS on given port
    try:
        if _smtp_port == 465:
            with smtplib.SMTP_SSL(_smtp_host, _smtp_port) as s:
                if _smtp_user and _smtp_pass:
                    s.login(_smtp_user, _smtp_pass)
                s.send_message(msg)
        else:
            with smtplib.SMTP(_smtp_host, _smtp_port) as s:
                s.ehlo()
                s.starttls()
                s.ehlo()
                if _smtp_user and _smtp_pass:
                    s.login(_smtp_user, _smtp_pass)
                s.send_message(msg)
        print('Email sent to', _to)
    except Exception as e:
        print('Failed to send email:', e)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Send HTML report via SMTP (overrides env vars)')
    parser.add_argument('html', help='path to html file to send')
    parser.add_argument('--assets-dir', help='directory with images to embed (default: <html parent>/data)')
    parser.add_argument('--smtp-host')
    parser.add_argument('--smtp-port', type=int)
    parser.add_argument('--smtp-user')
    parser.add_argument('--smtp-pass')
    parser.add_argument('--from')
    parser.add_argument('--to')
    parser.add_argument('--use-addy', action='store_true', help='Send via Addy HTTP API instead of SMTP')
    parser.add_argument('--addy-key', help='Addy API key (overrides env)')
    parser.add_argument('--force-smtp', action='store_true', help='Force using SMTP even if ADDY_API_KEY is set in env')
    args = parser.parse_args()
    rpt = Path(args.html)
    assets = Path(args.assets_dir) if args.assets_dir else rpt.parent / 'data'
    # Decide whether to use Addy: CLI flag, or env var ADDY_API_KEY, unless forced to use SMTP
    addy_key = args.addy_key or os.getenv('ADDY_API_KEY')
    prefer_addy = bool(args.use_addy or addy_key) and not args.force_smtp
    if prefer_addy:
        try:
            # lazy import
            from addy_provider import send_via_addy
        except Exception as e:
            print('Addy provider import failed:', e)
            raise
        key = addy_key
        if not key:
            print('Addy key required (cli --addy-key or env ADDY_API_KEY)')
            raise SystemExit(2)
        html = rpt.read_text(encoding='utf8')
        try:
            # allow user override of endpoint via env var ADDY_API_URL
            api_url = os.getenv('ADDY_API_URL')
            success = send_via_addy(key, args.__dict__.get('from') or EMAIL_FROM, args.to or EMAIL_TO, f'ePermits report {rpt.name}', html, assets, api_url=api_url)
            if success:
                print('Sent via Addy')
            else:
                print('Addy reported failure; falling back to SMTP')
                send_report(rpt, assets, smtp_host=args.smtp_host, smtp_port=args.smtp_port, smtp_user=args.smtp_user, smtp_pass=args.smtp_pass, email_from=args.__dict__.get('from'), email_to=args.to)
        except Exception as e:
            # Network/DNS or other transport-level error. Log and fallback to SMTP.
            print('Addy send error (network/transport):', e)
            print('Falling back to SMTP send')
            try:
                send_report(rpt, assets, smtp_host=args.smtp_host, smtp_port=args.smtp_port, smtp_user=args.smtp_user, smtp_pass=args.smtp_pass, email_from=args.__dict__.get('from'), email_to=args.to)
            except Exception as e2:
                print('Fallback SMTP send also failed:', e2)
    else:
        send_report(rpt, assets, smtp_host=args.smtp_host, smtp_port=args.smtp_port, smtp_user=args.smtp_user, smtp_pass=args.smtp_pass, email_from=args.__dict__.get('from'), email_to=args.to)
