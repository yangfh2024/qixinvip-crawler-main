@echo off
title Qixinbao Crawler API Service
cd /d "%~dp0"

echo ============================================
echo    Starting Qixinbao Crawler API Service
echo ============================================
echo.

REM Check config file
if not exist "config.json" (
    copy config.example.json config.json > nul
    echo [INFO] Created config.json from template
)

REM Check Cookie
if exist "cookie.txt" (
    echo [OK] Found cookie.txt
) else (
    echo [WARN] cookie.txt not found. Some features may be limited.
    echo        Run qr_login.bat to login first.
)

REM Activate virtual environment and start
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo [INFO] No virtual environment found, using system Python
)

echo Starting server...
python run.py

echo.
echo Visit http://localhost:8004/docs for API documentation
echo Full API docs: see api_docs.md

pause
