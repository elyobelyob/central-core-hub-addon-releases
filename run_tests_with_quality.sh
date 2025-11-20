#!/bin/bash
# Script to run tests with code quality checks

set -e  # Exit on any error

echo "🔍 Running code quality checks..."

# Run black (formatter) in check mode
echo "📏 Checking code formatting with black..."
black --check --diff central-core-hub/

# Run flake8 (linter)
echo "🔎 Running linting with flake8..."
flake8 central-core-hub/

echo "✅ Code quality checks passed!"

# Run tests
echo "🧪 Running unit tests..."
cd central-core-hub
python -m pytest tests/unit/ -x --tb=short
echo "🎉 All tests passed!"