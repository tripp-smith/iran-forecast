#!/usr/bin/env bash
# Push analysis/grok_iran_forecast.html (and optional qualitative memo) to the public dashboard gist.
# Requires: gh auth login (or GH_TOKEN / GITHUB_TOKEN with gist scope).
#
# Gistpreview default URL (?gist_id with no path) uses the *first* key in gist.files (GitHub: lexicographic).
# Keep grok_iran_forecast.html sorting before any companion .md (e.g. memo_* sorts after grok_*).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GIST_ID="c597082b35f0c457274c80daadfa5ff0"
HTML="${ROOT}/analysis/grok_iran_forecast.html"
MEMO="${ROOT}/analysis/memo_persian_gulf_qualitative.md"

gh gist edit "$GIST_ID" \
  --filename grok_iran_forecast.html \
  "$HTML"

if [[ -f "$MEMO" ]]; then
  if [[ "$(gh api "gists/${GIST_ID}" --jq '.files | has("memo_persian_gulf_qualitative.md")')" == "true" ]]; then
    gh gist edit "$GIST_ID" \
      --filename memo_persian_gulf_qualitative.md \
      "$MEMO"
  else
    gh gist edit "$GIST_ID" --add "$MEMO"
  fi
fi
