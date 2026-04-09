#!/bin/bash
# Aria launcher for macOS — double-click this file to start Aria
# The app will appear in the system menu bar (top-right corner).

cd "$(dirname "$0")"

# Prefer the Anaconda Python (where all packages are installed)
if [ -f "/opt/anaconda3/bin/python3" ]; then
    PYTHON="/opt/anaconda3/bin/python3"
elif [ -d "venv" ]; then
    source venv/bin/activate
    PYTHON="python3"
else
    PYTHON="python3"
fi

# Install PyQt6 if not already installed
"$PYTHON" -m pip show PyQt6 &>/dev/null || "$PYTHON" -m pip install PyQt6

# Launch
"$PYTHON" app.py
