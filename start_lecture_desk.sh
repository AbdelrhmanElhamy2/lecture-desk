#!/usr/bin/env bash
# ============================================================================
# Lecture Desk — 1-Click Installer & Launcher for Linux
# Run: ./start_lecture_desk.sh
# ============================================================================
set -euo pipefail

cd "$(dirname "$0")"
VENV_DIR="$(pwd)/.venv"
VENV_PY="$VENV_DIR/bin/python"
STAMP_FILE="$VENV_DIR/.deps_installed"

if ! command -v python3 >/dev/null 2>&1 || ! python3 -c "import sys; assert sys.version_info >= (3, 10)" >/dev/null 2>&1; then
    echo "[!] Python 3.10 or newer is required."
    echo "    Install it via your package manager (e.g. sudo apt install python3 python3-venv) and re-run."
    exit 1
fi

# Fast path: already installed
if [ -x "$VENV_PY" ] && [ -f "$STAMP_FILE" ]; then
    if "$VENV_PY" -c "import fastapi, google.genai, reportlab, matplotlib" >/dev/null 2>&1; then
        echo "Starting Lecture Desk..."
        "$VENV_PY" launcher.py
        exit 0
    fi
fi

echo ""
echo "========================================================================"
echo "         Lecture Desk — Engineering Study Suite (First-Time Setup)"
echo "========================================================================"
echo ""

if [ ! -x "$VENV_PY" ]; then
    echo "[1/2] Creating isolated app environment (.venv)..."
    python3 -m venv "$VENV_DIR"
fi

echo "[2/2] Installing Lecture Desk packages (first time only, ~1-2 minutes)..."
"$VENV_PY" -m pip install --upgrade pip --quiet || true
"$VENV_PY" -m pip install -r requirements.txt
echo "installed" > "$STAMP_FILE"

echo ""
echo "Setup complete! Opening Lecture Desk..."
echo ""
"$VENV_PY" launcher.py
