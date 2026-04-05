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
TODAY=$(date +%Y-%m-%d)
YEAR=$(date +%Y)
MONTH=$(date +%m)
REPORT_DIR="${DAILYREPORT_REPORT_DIR:-${DAILYREPORT_DATA_DIR:-${PROJECT_DIR}/data}/report}"
REPORT_FILE="${REPORT_DIR}/${YEAR}/${MONTH}/${TODAY}.md"

python3 "${PROJECT_DIR}/digest/main.py" --date "$TODAY" "$@"

if [ -f "$REPORT_FILE" ]; then
  python3 "${PROJECT_DIR}/digest/send_report.py" \
    --report "$REPORT_FILE" \
    --subject "Daily Report ${TODAY}"
fi
