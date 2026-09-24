#!/usr/bin/env bash
# Run the checks in .github/workflows/ci.yml the way CI runs them, before pushing:
# Python 3.11 on Linux (in Docker), plain `pytest` from central-core-hub/,
# `ruff check .` and `pyright` from the repo root. Keep in step with ci.yml.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

echo "==> version files agree"
python3 version_manager.py validate

echo "==> ruff + pytest on Python 3.11 (as CI)"
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v "$PWD":/src -w /src python:3.11 bash -euo pipefail -c '
  pip install -q --root-user-action=ignore --disable-pip-version-check -r requirements.txt
  pip install -q --root-user-action=ignore --disable-pip-version-check -r central-core-hub/requirements.txt || true
  pip install -q --root-user-action=ignore --disable-pip-version-check -r requirements-dev.txt pyyaml ruff pytest-cov
  ruff check .
  cd central-core-hub && pytest -q -p no:cacheprovider
'

echo "==> pyright (as CI)"
npx --yes pyright

echo "==> local CI passed"
