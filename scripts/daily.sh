#!/usr/bin/env bash
# Daily job: sync with main, log yesterday's weather, commit and push.
set -euo pipefail
cd "$(dirname "$0")/.."

# Sync with main first, then restart so the newest version of this script runs.
if [ -z "${DAILY_SYNCED:-}" ]; then
  git fetch origin main
  git checkout -B main FETCH_HEAD
  DAILY_SYNCED=1 exec bash scripts/daily.sh "$@"
fi

python3 scripts/update.py

git add -A
if git diff --cached --quiet; then
  echo "No changes to commit."
  exit 0
fi

# Erik is the author (this is what counts on the GitHub contribution graph);
# the committer is whoever runs the script, so commits stay signed/verified.
git commit --author="Erik <104572224+Erik-Sandqvist@users.noreply.github.com>" \
  -m "Weather log: $(TZ=Europe/Stockholm date +%F)"

for delay in 0 2 4 8 16; do
  sleep "$delay"
  if git push origin HEAD:main; then
    echo "Pushed."
    exit 0
  fi
done
echo "Push failed." >&2
exit 1
