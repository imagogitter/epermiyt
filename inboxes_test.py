"""
inboxes_test.py

Generates a disposable inbox at inboxes.com, sends a test HTML to it using provided SMTP credentials (overrides),
then opens the inbox in a headless browser (Playwright) and polls for the incoming email.

Usage example (one-off, passes SMTP creds on CLI so they are not persisted):
python inboxes_test.py --smtp-user jer.lis@gmx.com --smtp-pass secret --smtp-host smtp.gmx.com --smtp-port 465

"""
import time
import secrets
from datetime import datetime
from pathlib import Path
import argparse

from playwright.sync_api import sync_playwright

from email_send import send_report


def make_localpart():
    stamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    rnd = secrets.token_hex(3)
    return f'service-{stamp}-{rnd}'


def send_to_inboxes(html_path: Path, smtp_host, smtp_port, smtp_user, smtp_pass, recipient):
    assets = Path(html_path).parent / 'data'
    send_report(html_path, assets, smtp_host=smtp_host, smtp_port=smtp_port, smtp_user=smtp_user, smtp_pass=smtp_pass, email_to=recipient)


def poll_inbox(localpart, timeout=60, poll_interval=5):
    urls = [
        f'https://inboxes.com/{localpart}',
        f'https://inboxes.com/mailbox/{localpart}',
        f'https://inboxes.com/inbox/{localpart}',
        f'https://inboxes.com/messages/{localpart}',
    ]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        start = time.time()
        while time.time() - start < timeout:
            for url in urls:
                try:
                    page.goto(url, timeout=15000)
                except Exception:
                    continue
                # Try common selectors for disposable inbox messages
                possible = [
                    'table.mailbox tbody tr',
                    'ul.messages li',
                    'div.message',
                    'article',
                    'tbody tr',
                    '.inbox-list-item',
                ]
                for sel in possible:
                    try:
                        els = page.query_selector_all(sel)
                        if els and len(els) > 0:
                            # Click first message if clickable
                            try:
                                els[0].click()
                                page.wait_for_timeout(1000)
                            except Exception:
                                pass
                            # extract text from message view
                            body_text = ''
                            try:
                                body_text = page.inner_text('body')
                            except Exception:
                                body_text = page.content()
                            browser.close()
                            return True, url, body_text
                    except Exception:
                        continue
            time.sleep(poll_interval)

        browser.close()
        return False, None, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smtp-host', required=True)
    parser.add_argument('--smtp-port', type=int, required=True)
    parser.add_argument('--smtp-user', required=True)
    parser.add_argument('--smtp-pass', required=True)
    parser.add_argument('--html', default='data/reports/test-email.html')
    args = parser.parse_args()

    local = make_localpart()
    recipient = f'{local}@inboxes.com'
    print('Generated recipient:', recipient)

    # send
    print('Sending test email...')
    send_to_inboxes(args.html, args.smtp_host, args.smtp_port, args.smtp_user, args.smtp_pass, recipient)

    # poll
    print('Polling inbox for up to 90s...')
    ok, url, body = poll_inbox(local, timeout=90)
    if ok:
        print('Message found at', url)
        print('Message excerpt:')
        print(body[:800])
    else:
        print('No message detected within timeout')


if __name__ == '__main__':
    main()
