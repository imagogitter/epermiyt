#!/usr/bin/env bash
# Run unit tests without triggering Playwright browser downloads and with project on PYTHONPATH.
set -euo pipefail
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"
export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

# Run tests directly to avoid system pytest plugins interfering in this environment.
python3 tests/test_db.py
