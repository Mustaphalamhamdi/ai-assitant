@echo off
:: Aria launcher for Windows — double-click this file to start Aria
:: The app will appear in the system tray (bottom-right corner).

cd /d "%~dp0"

:: Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

:: Install PyQt6 if not present
python -m pip show PyQt6 >nul 2>&1 || pip install PyQt6

:: Launch (pythonw hides the console window on Windows)
start "" pythonw app.py
