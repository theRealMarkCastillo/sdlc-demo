#!/usr/bin/env bash
# deterministic-check.sh — Mechanical referee for SDLC Test/CI stage
#
# Runs three deterministic checks sequentially:
#   1. ruff lint — style & logic errors
#   2. mypy — static type checking
#   3. bandit — security SAST scan
#
# Exit: 0 if all pass, non-zero if any fail.
# Designed to run AFTER all 3 reviewers pass, BEFORE deploy.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Activate venv if present
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

PASSED=0
FAILED=0

echo "========================================"
echo "  DETERMINISTIC CHECK — SDLC Referee"
echo "========================================"
echo ""

# --- 1. ruff lint ---
echo "[1/3] ruff lint..."
if ruff check app.py 2>&1; then
    echo "  PASS: ruff lint clean"
    ((PASSED++))
else
    echo "  FAIL: ruff found issues"
    ((FAILED++))
fi
echo ""

# --- 2. mypy type check ---
echo "[2/3] mypy type check..."
if python3 -m mypy app.py 2>&1; then
    echo "  PASS: mypy type check clean"
    ((PASSED++))
else
    echo "  FAIL: mypy found type errors"
    ((FAILED++))
fi
echo ""

# --- 3. bandit SAST scan ---
# Config (skips, excludes) lives in pyproject.toml [tool.bandit]
echo "[3/3] bandit SAST scan..."
if bandit -r app.py -c pyproject.toml -ll 2>&1; then
    echo "  PASS: bandit SAST scan clean"
    ((PASSED++))
else
    echo "  FAIL: bandit found security issues"
    ((FAILED++))
fi
echo ""

# --- Summary ---
echo "========================================"
echo "  SUMMARY: $PASSED passed, $FAILED failed"
echo "========================================"

if [ "$FAILED" -gt 0 ]; then
    echo "DETERMINISTIC CHECK FAILED — deploy blocked"
    exit 1
else
    echo "DETERMINISTIC CHECK PASSED — proceed to deploy"
    exit 0
fi
