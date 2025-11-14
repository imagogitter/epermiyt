"""
run_daily.py

Wrapper to be scheduled (cron/systemd) that runs the scraper, then generates the report for yesterday (Mon-Fri)
and sends it by email.
"""
from datetime import datetime, timedelta
import os
import argparse
from generate_report import render_report
from scraper import run_scrape
from email_send import send_report
from thumbnails import generate_recent_thumbnails
import os
from addy_provider import send_via_addy


def main():
    parser = argparse.ArgumentParser(description='Run daily ePermits pipeline')
    parser.add_argument('--max-items', type=int, default=int(os.getenv('MAX_SCRAPE_ITEMS', '200')),
                        help='Maximum number of permits to scrape')
    parser.add_argument('--use-addy', action='store_true', help='Prefer Addy for sending the report')
    parser.add_argument('--require-addy', action='store_true', help='Require Addy to be configured and fail if Addy is not available')
    parser.add_argument('--addy-key', help='Addy API key to use for sending (overrides env)')
    parser.add_argument('--force-smtp', action='store_true', help='Force SMTP even if Addy is configured')
    args = parser.parse_args()

    # 1) Run the full scrape — scraping is critical and always executed unless explicitly removed from the code.
    run_scrape(max_items=args.max_items)

    # 2) Determine yesterday and skip weekends
    yesterday = datetime.utcnow() - timedelta(days=1)
    if yesterday.weekday() >= 5:
        print('Weekend - skipping report generation')
        return

    # Generate thumbnails for 30 most recent items (optional; skip in OSS mode)
    skip_thumbs = os.getenv('SKIP_THUMBS', '').lower() in ('1', 'true', 'yes')
    if not skip_thumbs:
        try:
            generate_recent_thumbnails(limit=30)
        except Exception as e:
            print('Thumbnail generation failed (continuing):', e)
    else:
        print('SKIP_THUMBS=true; skipping thumbnail generation')

    rpt = render_report(yesterday)

    # 3) Send report via SMTP or Addy depending on env
    assets_dir = rpt.parent / 'data'
    # Determine Addy usage: CLI flags override env. ADDY_ONLY forces Addy-only behavior.
    addy_key_env = os.getenv('ADDY_API_KEY')
    addy_only_env = os.getenv('ADDY_ONLY', '').lower() in ('1', 'true', 'yes')
    # CLI addy key / flag takes precedence
    addy_key = args.addy_key or addy_key_env
    use_addy = False
    if addy_only_env:
        use_addy = True
    elif args.use_addy or addy_key:
        use_addy = True
    # allow explicit force-smtp via CLI or env
    if args.force_smtp or os.getenv('FORCE_SMTP', '').lower() in ('1', 'true', 'yes'):
        use_addy = False
    # If require-addy flag or REQUIRE_ADDY env var is set, enforce that Addy is configured and available.
    require_addy_env = os.getenv('REQUIRE_ADDY', '').lower() in ('1', 'true', 'yes')
    if args.require_addy or require_addy_env:
        if not use_addy or not addy_key:
            raise SystemExit('Addy is required for this run but no Addy API key was provided (CLI --addy-key or env ADDY_API_KEY)')
    try:
        if use_addy:
            key = os.getenv('ADDY_API_KEY')
            sender = os.getenv('EMAIL_FROM')
            recipient = os.getenv('EMAIL_TO')
            html = rpt.read_text(encoding='utf8')
            ok = send_via_addy(key, sender, recipient, f'ePermits report {rpt.name}', html, assets_dir)
            if not ok:
                print('Addy send reported failure')
        else:
            send_report(rpt, assets_dir)
    except Exception as e:
        print('Failed to send email:', e)


if __name__ == '__main__':
    main()
