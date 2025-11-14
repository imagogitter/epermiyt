# Denver ePermits scraper & daily report

This project scrapes the Denver ePermits site for records matching "%demo%", stores them in a central SQLite database, generates an interactive daily HTML report (mon-fri), and emails the report.

Files added:
- `scraper.py` — Playwright-based scraper that logs in and scrapes permit details into `data/epermits.db`.
- `db.py` — SQLite helper and schema.
- `generate_report.py` — produces interactive HTML report using Leaflet and Esri Satellite tiles.
- `templates/report.html` — Jinja2 template for the report.
- `email_send.py` — sends the generated HTML with images via SMTP (inline attachments using cid).
- `run_daily.py` — wrapper to run scraping, generate the report for yesterday, and send email.
- `config.example.env` — example environment variables.
- `requirements.txt` — Python dependencies.

Setup
1. Create a Python venv and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Install Playwright browsers once:

```bash
python -m playwright install
```

3. Copy `config.example.env` to `.env` and fill in your credentials (username/password), SMTP credentials, and optional `GOOGLE_API_KEY` for streetview thumbnails.

Usage
- Run the scraper manually: `python scraper.py`
- Generate yesterday's report: `python generate_report.py`
- Send report: `python email_send.py data/reports/report-YYYY-MM-DD.html`
- Run full daily pipeline: `python run_daily.py`

Sending options
- SMTP (default): configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_FROM`, `EMAIL_TO` in `.env`.
- Addy HTTP API (anonymous/transactional): set `ADDY_API_KEY` and optionally `ADDY_API_URL` in `.env`, or pass `--use-addy --addy-key` to `email_send.py`.
 - Addy HTTP API (anonymous/transactional): set `ADDY_API_KEY` and optionally `ADDY_API_URL` in `.env`, or pass `--use-addy --addy-key` to `email_send.py`.

OSS-friendly mode
- To run the project as an "OSS-only" pipeline (no proprietary tile providers, no thumbnails, Addy-only sending):
	- Set `ADDY_API_KEY` (or use `--use-addy`) and set `ADDY_ONLY=true` in `.env` to avoid SMTP entirely.
	- Optionally set `SKIP_THUMBS=true` to skip thumbnail generation and embedding.
	- The report now uses OpenStreetMap tiles (OSS) by default.

	Require Addy
	- If your deployment requires Addy-only delivery and should fail when Addy is not configured, set `REQUIRE_ADDY=true` in `.env` or pass `--require-addy` to `run_daily.py`. The run will abort early if no `ADDY_API_KEY` is provided.

Additional developer commands
- Generate thumbnails for the 30 most recent DB records (creates missing thumbnails):
	- `python thumbnails.py`
- Run tests:
	- `./run_tests.sh`

If you want to send via Addy HTTP API instead of SMTP (e.g., anonymous transactional send), call:

```bash
python email_send.py data/reports/test-email.html --use-addy --addy-key YOUR_ADDY_KEY --from you@domain --to recipient@inboxes.com
```

Notes on running locally
- Ensure `playwright` is installed if you intend to run scraping or the inbox polling using Playwright:

```bash
pip install playwright
python -m playwright install
```

Scheduling
Add a cron entry to run weekdays at e.g. 07:00 UTC (adjust for your timezone):

```cron
0 7 * * 1-5 cd /home/x/epermiyt && /home/x/epermiyt/.venv/bin/python run_daily.py >> run_daily.log 2>&1
```

Notes & assumptions
- Selectors in `scraper.py` are based on the provided Playwright recording and may need tuning if the site structure changes.
- Geocoding uses Nominatim (OpenStreetMap). Respect their usage policy; set `GEOCODER_EMAIL` in `.env`.
- Street View thumbnails require `GOOGLE_API_KEY`. If omitted, thumbnails will not be fetched.
- The generated HTML in `data/reports` contains a `data/` subfolder with image files so the HTML can be emailed as a single package.

Security note
- Do NOT commit `.env` to source control. If you put real SMTP passwords (GMX or otherwise) into `.env`, rotate them after testing.
- GMX and other providers often require app-specific passwords or enabling SMTP in account settings; if you see `535 Authentication credentials invalid`, try creating an app password or verifying SMTP access.

Next steps / improvements
- Add retry/backoff and more robust parsing for permit details.
- Add unit tests and linters.
- Add configuration for how many recent thumbnails to generate and thumbnail sizes.
