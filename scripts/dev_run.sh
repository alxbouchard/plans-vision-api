#!/usr/bin/env bash
# dev_run.sh - Single command to start the API with dev settings
#
# Usage:
#   ./scripts/dev_run.sh              # Normal dev mode (flag OFF)
#   ./scripts/dev_run.sh --phase3.3   # Enable Phase 3.3 spatial labeling
#
# Prerequisites:
#   - Python 3.11+
#   - Virtual environment at .venv/ (optional, auto-detected)
#   - OPENAI_API_KEY in .env or environment (for real vision calls)

set -e

cd "$(dirname "$0")/.."

# Auto-activate venv if present
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Load .env if present
if [ -f ".env" ]; then
    echo "Loading .env file..."
    set -a
    source .env
    set +a
fi

# Set dev defaults
export LOG_LEVEL="${LOG_LEVEL:-DEBUG}"
export PLANS_VISION_DEMO_KEY="${PLANS_VISION_DEMO_KEY:-demo-key-for-testing}"

# Parse args
for arg in "$@"; do
    case $arg in
        --phase3.3)
            export ENABLE_PHASE3_3_SPATIAL_LABELING=true
            echo "Phase 3.3 Spatial Labeling: ENABLED"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--phase3.3]"
            echo ""
            echo "Options:"
            echo "  --phase3.3    Enable Phase 3.3 spatial room labeling"
            echo ""
            echo "Environment variables (can also be set in .env):"
            echo "  OPENAI_API_KEY                     - Required for vision calls"
            echo "  ENABLE_PHASE3_3_SPATIAL_LABELING   - true/false"
            echo "  LOG_LEVEL                          - DEBUG/INFO/WARNING/ERROR"
            exit 0
            ;;
    esac
done

echo ""
echo "Starting Plans Vision API in dev mode..."
echo "  API: http://localhost:8000"
echo "  Docs: http://localhost:8000/docs"
echo "  Debug flags: http://localhost:8000/debug/flags"
echo "  Demo API key: $PLANS_VISION_DEMO_KEY"
echo ""

# Run with uvicorn
python -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
