#!/usr/bin/env bash
# Touch empty forecast files for each calendar day from START through today.
# Usage: util/gen_daily_output_file.sh [YYYY-MM-DD]
#   START_DATE env overrides the default start when no argument is given.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/forecasts"
START="${1:-${START_DATE:-2026-03-19}}"

mkdir -p "$OUT"

cur=$(date -j -f "%Y-%m-%d" "$START" "+%Y%m%d") || {
  echo "gen_daily_output_file.sh: invalid start date: $START (use YYYY-MM-DD)" >&2
  exit 1
}
end=$(date "+%Y%m%d")

while [[ "$cur" -le "$end" ]]; do
  touch "$OUT/grok_iran_forecast-${cur}.md"
  cur=$(date -j -v+1d -f "%Y%m%d" "$cur" "+%Y%m%d")
done
