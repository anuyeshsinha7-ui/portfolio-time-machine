#!/usr/bin/env bash
# One command to bring the site's data up to the latest trading day (run it on your own computer: NSE blocks cloud servers).
#   bash scripts/update_data.sh            → download, clean, recompute, test, rebuild; nothing is published
#   bash scripts/update_data.sh --publish  → the same, then commit the new snapshot and push (GitHub redeploys the site)
# Stops at the first failure, so a bad download or a failing test never reaches the live site.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-/opt/anaconda3/envs/fra/bin/python}"
[ -x "$PY" ] || PY=python

"$PY" scripts/fetch_data.py --refresh
"$PY" scripts/clean_data.py
"$PY" scripts/precompute.py
"$PY" scripts/run_analysis.py
"$PY" scripts/write_docs.py
"$PY" -m pytest tests -q
"$PY" scripts/build_site.py

asof=$("$PY" -c "import json; print(json.load(open('data/metadata.json'))['as_of'])")
echo "Data now runs to $asof. Review data/restatements_vs_previous_snapshot.csv and docs/DATA_QUALITY.md."
if [ "${1:-}" = "--publish" ]; then
  git add data results docs README.md
  git commit -m "Data refresh to $asof"
  git push
  echo "Pushed. GitHub Actions will test and redeploy the site in a few minutes."
fi
