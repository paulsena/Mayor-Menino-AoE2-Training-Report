#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "venv not found. Creating venv and installing dependencies..."
    python3 -m venv venv
    venv/bin/pip install --quiet -r requirements.txt
    echo "NOTE: mgz patches must be applied manually — see CLAUDE.md for instructions."
fi

exec "$VENV_PYTHON" analyze.py "$@"
