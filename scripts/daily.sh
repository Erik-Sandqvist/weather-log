#!/usr/bin/env bash
# Daily job: sync with main, log yesterday's weather, commit and push.
set -euo pipefail
cd "$(dirname "$0")/.."

git fetch origin main
git checkout -B main FETCH_HEAD

python3 scripts/update.py

git add -A
if git diff --cached --quiet; then
  echo "No changes to commit."
  exit 0
fi

git -c user.name="Erik" -c user.email="104572224+Erik-Sandqvist@users.noreply.github.com" \
  commit -m "Weather log: $(TZ=Europe/Stockholm date +%F)"

for delay in 0 2 4 8 16; do
  sleep "$delay"
  if git push origin HEAD:main; then
    echo "Pushed."
    exit 0
  fi
done
echo "Push failed." >&2
exit 1
