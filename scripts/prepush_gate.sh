#!/bin/bash
set -e

echo "🔒 Hefesto Pre-Push Gate"
echo "======================="

# 1. Install dependencies
echo "📦 Installing dependencies..."
python -m pip install -U pip
pip install -e ".[dev]"

# 2. Linting
echo "✨ Running linters..."
black . && isort . && flake8

# 3. Type Checking
echo "typing Running mypy..."
python -m mypy hefesto omega --ignore-missing-imports

# 4. Critical Tests
echo "🧪 Running critical tests..."
pytest -q tests/test_version.py

# Optional: Run other critical tests if they exist
if [ -f "tests/scripts/test_verify_release_tag.py" ]; then
    pytest -q tests/scripts/test_verify_release_tag.py
fi

# 5. Full Suite (fast)
echo "🚀 Running fast test suite..."
# Using -m "not slow" if markers exist, otherwise just run everything quietly
# Adjust based on actual markers in pyproject.toml
if grep -q "markers" pyproject.toml; then
    pytest -q -m "not slow and not integration"
else
    pytest -q
fi

# 6. Verify Tag (if applicable)
# Only run if we are on a tag? Or just verify the script works?
# The user's prompt implied running this check.
echo "🏷️ Verifying release tag logic..."
VERSION=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
if [ -f "scripts/verify_release_tag.py" ]; then
    python scripts/verify_release_tag.py --tag v$VERSION --project-root .
fi

echo "✅ Gate Passed! Ready to push."
