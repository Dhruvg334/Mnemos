#!/bin/sh
set -eu

case "${1:-api}" in
  api)
    exec uvicorn mnemos.main:app \
      --host 0.0.0.0 \
      --port "${PORT:-8000}" \
      --proxy-headers \
      --forwarded-allow-ips="*"
    ;;
  migrate-and-api)
    alembic upgrade head
    exec uvicorn mnemos.main:app \
      --host 0.0.0.0 \
      --port "${PORT:-8000}" \
      --proxy-headers \
      --forwarded-allow-ips="*"
    ;;
  worker)
    exec python -m mnemos.worker
    ;;
  migrate)
    exec alembic upgrade head
    ;;
  seed)
    exec python scripts/seed.py
    ;;
  *)
    exec "$@"
    ;;
esac
