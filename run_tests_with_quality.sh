#!/bin/bash
# Script to run tests with code quality checks

set -e  # Exit on any error

echo "🔍 Running code quality checks..."

# Check version consistency
PYTHON="./.venv/bin/python3"
PYRIGHT="./.venv/bin/pyright"
RUFF="./.venv/bin/ruff"

echo "📋 Checking version consistency..."
$PYTHON version_manager.py validate

echo "🧾 Running type checks with pyright..."
$PYTHON -m pip install pyright ruff
$PYRIGHT

echo "🔎 Running linting with ruff..."
$RUFF check .

echo "✅ Code quality checks passed!"

# Run tests
echo "🧪 Running unit tests with coverage..."
PYTHONPATH=.venv/lib/python3.14/site-packages $PYTHON -m pytest central-core-hub/tests/unit/ -q --cov=central-core-hub --cov-report=xml:coverage.xml --cov-report=term-missing
echo "🎉 All tests passed!"
