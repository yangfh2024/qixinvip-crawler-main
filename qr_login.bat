@echo off
chcp 65001 > nul
title 启信宝扫码登录

echo ============================================
echo    启信宝扫码登录助手
echo ============================================
echo.

REM 激活虚拟环境
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo 正在打开浏览器，请在页面中扫码登录...
echo.
python qr_login.py

pause
