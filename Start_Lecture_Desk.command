#!/usr/bin/env bash
# ============================================================================
# Lecture Desk — 1-Click Installer & Launcher for macOS
# Double-click this file in Finder to install (first time) and open Lecture Desk.
# ============================================================================
set -euo pipefail

cd "$(dirname "$0")"
VENV_DIR="$(pwd)/.venv"
VENV_PY="$VENV_DIR/bin/python"
STAMP_FILE="$VENV_DIR/.deps_installed"

find_python() {
    for cmd in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
        if command -v "$cmd" >/dev/null 2>&1; then
            if "$cmd" -c "import sys; assert sys.version_info >= (3, 10)" >/dev/null 2>&1; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

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

if ! PYTHON_CMD="$(find_python)"; then
    echo "[!] Python 3.10 or newer is required to run Lecture Desk."
    echo "    Opening the official Python download page..."
    echo "    Install Python, then double-click Start_Lecture_Desk.command again."
    open "https://www.python.org/downloads/macos/" || true
    read -r -p "Press Enter to close..."
    exit 1
fi

echo "[OK] Found Python: $("$PYTHON_CMD" --version)"
echo ""

if [ ! -x "$VENV_PY" ]; then
    echo "[1/2] Creating isolated app environment (.venv)..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
fi

echo "[2/2] Installing Lecture Desk packages (first time only, ~1-2 minutes)..."
"$VENV_PY" -m pip install --upgrade pip --quiet || true
"$VENV_PY" -m pip install -r requirements.txt
echo "installed" > "$STAMP_FILE"

echo ""
echo "Setup complete! Opening Lecture Desk..."
echo ""
"$VENV_PY" launcher.py
