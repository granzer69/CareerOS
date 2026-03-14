#!/usr/bin/env bash
set -euo pipefail

echo "Starting CareerOS API..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
