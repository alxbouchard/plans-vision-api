#!/usr/bin/env bash
set -euo pipefail

# Minimal, portable test summary for macOS and Linux.
# Goal: produce a stable, copy-pastable summary for docs/DOC_STATUS.md

VENV_PY="${VENV_PY:-python3}"

echo "=== Environment ==="
echo "date: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "pwd: $(pwd)"
echo "python: $($VENV_PY --version 2>/dev/null || true)"
echo "git_head: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo

echo "=== Pytest collection (count) ==="
COLLECT_OUT="$($VENV_PY -m pytest --collect-only -q 2>/dev/null || true)"
if [[ -z "$COLLECT_OUT" ]]; then
  echo "collect_only: failed (pytest not available or configuration error)"
else
  TEST_COUNT=$(echo "$COLLECT_OUT" | grep -E '::' | wc -l | tr -d ' ')
  echo "collected_tests_estimate: $TEST_COUNT"
fi
echo

echo "=== Last test run (optional) ==="
echo "If you ran pytest recently, paste the terminal summary here manually."
echo "Recommended command:"
echo "  OPENAI_API_KEY=dummy pytest -v"
