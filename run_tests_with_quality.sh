#!/bin/bash
# Script to run tests with code quality checks

set -e  # Exit on any error

echo "🔍 Running code quality checks..."

# Check version consistency
echo "📋 Checking version consistency..."
python version_manager.py validate

echo "🧾 Running type checks with pyright..."
python -m pip install pyright
pyright

# Use ruff for formatting and linting checks
echo "📏 Checking code formatting with ruff..."
ruff format --check central-core-hub/

echo "🔎 Running linting with ruff..."
ruff check central-core-hub/

echo "✅ Code quality checks passed!"

# Run tests
echo "🧪 Running unit tests..."
cd central-core-hub
python -m pytest tests/unit/ -x --tb=short
echo "🎉 All tests passed!"
