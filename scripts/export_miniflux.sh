#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -f "${PROJECT_DIR}/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT_DIR}/.env"
  set +a
fi

cd "$PROJECT_DIR"

if [ -z "${MINIFLUX_API_KEY:-}" ]; then
  echo "MINIFLUX_API_KEY is not set"
  exit 1
fi

python3 "${PROJECT_DIR}/miniflux/export_miniflux.py" \
  --url "${MINIFLUX_URL:-http://127.0.0.1:8080}" \
  --api-key "${MINIFLUX_API_KEY}" \
  "$@"
