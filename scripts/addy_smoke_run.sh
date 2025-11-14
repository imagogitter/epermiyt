#!/usr/bin/env bash
set -euo pipefail

# addy_smoke_run.sh
# Quick smoke script to validate Addy connectivity and run the pipeline.
# Usage:
#   ./scripts/addy_smoke_run.sh
# It will load .env (if present), run DNS/TLS/cURL checks, and then run run_daily.py --use-addy

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Load .env if present (simple parsing; ignores export/complex shells)
if [ -f .env ]; then
  echo "Loading .env"
  # shellcheck disable=SC1091
  set -a
  # read lines of the form KEY=VALUE, ignoring comments
  grep -E '^[A-Z0-9_]+=.*' .env | sed 's/^/export /' > /tmp/epermits_env.sh
  # shellcheck disable=SC1091
  source /tmp/epermits_env.sh || true
  set +a
fi

: "${ADDY_API_URL:=https://api.addy.io/v1/messages}"
: "${ADDY_API_KEY:=}"

echo "Using ADDY_API_URL=$ADDY_API_URL"
if [ -z "$ADDY_API_KEY" ]; then
  echo "Warning: ADDY_API_KEY is empty. Export ADDY_API_KEY or set it in .env to run real tests."
fi

echo
echo "=== DNS lookup ==="
if command -v nslookup >/dev/null 2>&1; then
  nslookup_host() { nslookup "$1" 2>&1 || true; }
  nslookup_host "$(echo "$ADDY_API_URL" | sed -E 's#https?://##; s#/.*##')"
else
  echo "nslookup not available; skipping DNS check"
fi

echo
echo "=== TLS/connectivity test (Python) ==="
python3 - <<'PY' || true
import socket, ssl, sys
from urllib.parse import urlparse
url = "$ADDY_API_URL"
host = urlparse(url).hostname
port = 443
try:
    s = socket.create_connection((host, port), timeout=5)
    ctx = ssl.create_default_context()
    ss = ctx.wrap_socket(s, server_hostname=host)
    print('TLS version:', ss.version())
    ss.close()
except Exception as e:
    print('TLS/connect error:', e)
    sys.exit(2)
PY

echo
echo "=== curl HEAD (auth header test) ==="
if command -v curl >/dev/null 2>&1; then
  if [ -n "$ADDY_API_KEY" ]; then
    curl -v -H "Authorization: Bearer $ADDY_API_KEY" -I "$ADDY_API_URL" || true
  else
    curl -v -I "$ADDY_API_URL" || true
  fi
else
  echo "curl not installed; skipping HTTP checks"
fi

echo
echo "=== Optional small POST smoke (won't include HTML report) ==="
if command -v curl >/dev/null 2>&1 && [ -n "$ADDY_API_KEY" ]; then
  curl -v -H "Authorization: Bearer $ADDY_API_KEY" -H "Content-Type: application/json" \
    -d '{"from":"reports@example.com","to":"you@example.com","subject":"Addy smoke","html":"<b>smoke</b>"}' \
    "$ADDY_API_URL" || true
else
  echo "Skipping POST test (curl missing or no ADDY_API_KEY)"
fi

echo
echo "=== Running pipeline (run_daily.py --use-addy) ==="
python3 run_daily.py --use-addy || true

echo
echo "Script complete. Check logs above for errors. If Addy is unreachable you will see NameResolutionError or TLS/connect errors."
