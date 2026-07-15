@echo off
cd /d "%~dp0"

.venv\Scripts\python.exe --version >nul 2>&1
if errorlevel 1 (
    echo Virtual environment is broken or missing. Recreating...
    rmdir /s /q .venv >nul 2>&1
    python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

python main.py
