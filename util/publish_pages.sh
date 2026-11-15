#!/usr/bin/env bash
# Push the rebuilt dashboard to GitHub Pages (docs/index.html on main).
# Requires: gh auth login with repo scope; remote origin set.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 util/parse_forecasts.py

if [[ ! -f docs/index.html ]]; then
  echo "docs/index.html missing after parse" >&2
  exit 1
fi

git add docs/index.html analysis/grok_iran_forecast.html analysis/memo_longitudinal.md analysis/structured util/dashboard_client.js util/parse_forecasts.py
git status --short

if git diff --cached --quiet; then
  echo "No Pages-related changes to commit."
else
  git commit -m "$(cat <<'EOF'
Update Gulf normality dashboard for GitHub Pages.

EOF
)"
fi

git push -u origin HEAD

echo "Pages URL (after deploy): https://tripp-smith.github.io/iran-forecast/"
