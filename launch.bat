@echo off
setlocal

:: Switch to the directory where this batch file is located
cd /d "%~dp0"

echo [Ludexicon] Checking for virtual environment...
if not exist ".venv" (
    echo [Ludexicon] No virtual environment found. Creating .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment. Ensure python is installed and in your PATH.
        pause
        exit /b 1
    )
    
    echo [Ludexicon] Activating virtual environment...
    call .venv\Scripts\activate.bat
    
    echo [Ludexicon] Upgrading pip...
    python -m pip install --upgrade pip
    
    echo [Ludexicon] Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies from requirements.txt.
        pause
        exit /b 1
    )
) else (
    echo [Ludexicon] Activating virtual environment...
    call .venv\Scripts\activate.bat
)

echo [Ludexicon] Launching application...
:: Use start to launch pythonw so the command window can exit
start "" pythonw src\main.py

endlocal
exit
