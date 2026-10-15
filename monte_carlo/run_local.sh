#!/usr/bin/env bash
# Run the Monte Carlo lab locally with the active Python environment.
#
# PDF reports are built in-process with ReportLab, so no Redis, Celery worker
# or browser is needed.
set -euo pipefail
cd "$(dirname "$0")"

export PORT="${PORT:-8052}"
exec python app.py
