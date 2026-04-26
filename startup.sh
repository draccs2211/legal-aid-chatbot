#!/usr/bin/env bash
set -e

echo "=== NyayMitra Startup ==="
echo "PORT: $PORT"

exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-10000}"
