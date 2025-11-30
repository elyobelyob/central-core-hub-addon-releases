#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/release.sh [--dry-run] [<version>]
# If <version> is omitted, bumps the patch version (x.y.Z -> x.y.(Z+1)).
# If --dry-run is provided, the script will run tests and print the actions
# it would take without committing, tagging, or pushing.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_JSON="$ROOT_DIR/repository.json"
ADDON_JSON="$ROOT_DIR/central-core-hub/config.json"
ADDON_YAML="$ROOT_DIR/central-core-hub/config.yaml"

# Prefer the project's virtualenv Python if available
if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/.venv/bin/python"
else
  PYTHON="python"
fi

DRY_RUN=0
if [[ "${1-}" == "--dry-run" ]]; then
  DRY_RUN=1
  shift
fi

if [[ -n "${1-}" ]]; then
  NEW_VERSION="$1"
else
  # Read version from repository.json using python for robust parsing
  CUR_VERSION=$($PYTHON - <<'PY'
import json,sys
fn=sys.argv[1]
with open(fn) as f:
    v=json.load(f).get('version')
print(v)
PY
  "$REPO_JSON")

  if [[ -z "$CUR_VERSION" ]]; then
    echo "Could not determine current version" >&2
    exit 1
  fi

  IFS='.' read -r MAJOR MINOR PATCH <<< "$CUR_VERSION"
  PATCH=$((PATCH+1))
  NEW_VERSION="$MAJOR.$MINOR.$PATCH"
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[DRY-RUN] Releasing version $NEW_VERSION"
else
  echo "Releasing version $NEW_VERSION"
fi

# Update repository.json
$PYTHON - <<PY
import json,sys
fn=sys.argv[1]
v=sys.argv[2]
with open(fn) as f:
    j=json.load(f)
j['version']=v
with open(fn,'w') as f:
    json.dump(j,f,indent=1)
    f.write('\n')
PY
"$REPO_JSON" "$NEW_VERSION"

# Update central-core-hub/config.json
$PYTHON - <<PY
import json,sys
fn=sys.argv[1]
v=sys.argv[2]
with open(fn) as f:
    j=json.load(f)
j['version']=v
with open(fn,'w') as f:
    json.dump(j,f,indent=2)
    f.write('\n')
PY
"$ADDON_JSON" "$NEW_VERSION"

# Update central-core-hub/config.yaml - replace version: "..."
if grep -q '^version:' "$ADDON_YAML"; then
  # Use python to safely rewrite the YAML line to avoid relying on sed portability
  $PYTHON - <<PY
from pathlib import Path
p=Path(sys.argv[1])
v=sys.argv[2]
txt=p.read_text()
lines=txt.splitlines()
for i,l in enumerate(lines):
    if l.strip().startswith('version:'):
        # preserve indentation and quoting style
        indent=l[:l.index('v')]
        lines[i]=f'{indent}version: "{v}"'
        break
p.write_text('\n'.join(lines)+"\n")
PY
  "$ADDON_YAML" "$NEW_VERSION"
else
  echo "version: \"$NEW_VERSION\"" >> "$ADDON_YAML"
fi

# Run tests
echo "Running test suite..."
if [[ -x "$PYTHON" ]]; then
  "$PYTHON" -m pytest -q
else
  python -m pytest -q
fi

echo "Staging version files and creating release commit"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[DRY-RUN] git add $REPO_JSON $ADDON_JSON $ADDON_YAML"
  echo "[DRY-RUN] git commit -m \"chore(release): bump version to $NEW_VERSION\""
  echo "[DRY-RUN] git tag -a v$NEW_VERSION -m \"v$NEW_VERSION\""
  echo "[DRY-RUN] git push origin HEAD --follow-tags"
  echo "[DRY-RUN] Release v$NEW_VERSION simulated"
else
  git add "$REPO_JSON" "$ADDON_JSON" "$ADDON_YAML"
  git commit -m "chore(release): bump version to $NEW_VERSION"

  echo "Creating annotated tag v$NEW_VERSION"
  git tag -a "v$NEW_VERSION" -m "v$NEW_VERSION"

  echo "Pushing commit and tag to origin"
  git push origin HEAD --follow-tags

  echo "Release v$NEW_VERSION complete"
fi
