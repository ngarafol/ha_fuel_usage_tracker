#!/usr/bin/env bash
# Cut a release in one command: bump manifest.json, commit, tag and push.
#
#   scripts/release.sh 0.6.4
#
# The CHANGELOG section must already exist (and be written by a human):
#   ## [0.6.4] - 2026-10-20
#
# The GitHub workflow then turns the pushed tag into a Release with that section
# as its notes. Pushing a tag whose commit disagrees with manifest.json is what
# makes that workflow fail, which is why the bump happens here and not by hand.
set -euo pipefail

version="${1:-}"
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "usage: $0 X.Y.Z   (e.g. $0 0.6.4)" >&2
  exit 2
fi

cd "$(git rev-parse --show-toplevel)"
manifest="custom_components/fuelusagetracker/manifest.json"
tag="v${version}"

if ! grep -q "^## \[${version}\]" CHANGELOG.md; then
  echo "error: CHANGELOG.md has no '## [${version}]' section." >&2
  echo "       Add it first, then re-run this script." >&2
  exit 1
fi

unrelated="$(git status --porcelain | grep -v -E "(^| )(${manifest}|CHANGELOG\.md)$" || true)"
if [ -n "$unrelated" ]; then
  echo "error: unrelated working-tree changes; commit them first:" >&2
  echo "$unrelated" >&2
  exit 1
fi

python3 - "$version" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path("custom_components/fuelusagetracker/manifest.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["version"] = sys.argv[1]
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY

git add "$manifest" CHANGELOG.md
if ! git diff --cached --quiet; then
  git commit -q -m "chore: release ${version}"
fi

git tag -f -a "$tag" -m "Fuel Usage Tracker ${version}" >/dev/null
echo "tagged ${tag} at $(git rev-parse --short HEAD)"

git push origin HEAD
# The tag may already exist remotely from a failed attempt, so it is forced.
git push --force origin "refs/tags/${tag}"
echo "done: the Release workflow is creating ${tag} now."
