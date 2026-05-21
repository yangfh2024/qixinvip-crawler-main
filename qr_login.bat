@echo off
title Qixinbao QR Login
cd /d "%~dp0"

echo ============================================
echo    Qixinbao QR Code Login
echo ============================================
echo.

REM Activate virtual environment
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo Opening browser. Please scan the QR code to login...
echo.
python qr_login.py

pause
