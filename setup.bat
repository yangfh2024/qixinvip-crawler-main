@echo off
title Qixinbao Crawler - Setup

REM Switch to the directory where this batch file is located
cd /d "%~dp0"

echo ============================================
echo    Qixinbao Enterprise Data Crawler Setup
echo ============================================
echo.

echo [1/4] Checking Python...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] Python not found. Please install Python 3.10-3.12
    echo        Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%i in ('python --version 2^>^&1') do set pyver=%%i
echo [OK] Python %pyver%

REM Check Python version (must be 3.10~3.12, 3.13+ is incompatible)
if not "%pyver:~0,4%"=="3.10" if not "%pyver:~0,4%"=="3.11" if not "%pyver:~0,4%"=="3.12" (
    echo [FAIL] Python %pyver% is not compatible with required libraries
    echo        Please install Python 3.10, 3.11, or 3.12
    echo        Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo [2/4] Creating virtual environment...
if exist "venv\" (
    echo [SKIP] Virtual environment already exists
) else (
    python -m venv venv
    echo [OK] Virtual environment created
)

echo.
echo [3/4] Installing dependencies...
call venv\Scripts\activate.bat
pip install -r "%~dp0requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
if %errorlevel% neq 0 (
    echo [FAIL] Dependency installation failed. Check network connection.
    pause
    exit /b 1
)
echo [OK] Dependencies installed

echo.
echo [4/4] Downloading Playwright browser...
python -m playwright install chromium
if %errorlevel% neq 0 (
    echo [FAIL] Browser download failed. Check network connection.
    pause
    exit /b 1
)
echo [OK] Browser downloaded

echo.
echo ============================================
echo     Setup Complete!
echo ============================================
echo.
echo Next steps:
echo   1. Run qr_login.bat to scan QR code and login
echo   2. Run start.bat to start the API server
echo   3. Visit http://localhost:8004/docs for API docs
echo.
pause
