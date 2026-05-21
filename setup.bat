@echo off
chcp 65001 > nul
title 启信宝爬虫 - 环境安装

echo ============================================
echo    启信宝企业数据爬虫 — 一键部署
echo ============================================
echo.
echo [1/4] 检查 Python...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [失败] 未检测到 Python，请先安装 Python 3.10+
    echo       下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%i in ('python --version 2^>^&1') do set pyver=%%i
echo [OK] Python %pyver%

echo.
echo [2/4] 创建虚拟环境...
if exist "venv\" (
    echo [跳过] 虚拟环境已存在
) else (
    python -m venv venv
    echo [OK] 虚拟环境已创建
)

echo.
echo [3/4] 安装依赖...
call venv\Scripts\activate.bat
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if %errorlevel% neq 0 (
    echo [失败] 依赖安装失败，请检查网络连接
    pause
    exit /b 1
)
echo [OK] 依赖安装完成

echo.
echo [4/4] 下载 Playwright 浏览器...
python -m playwright install chromium
if %errorlevel% neq 0 (
    echo [失败] 浏览器下载失败，请检查网络连接
    pause
    exit /b 1
)
echo [OK] 浏览器下载完成

echo.
echo ============================================
echo     安装完成！
echo ============================================
echo.
echo 下一步：
echo   1. 运行 qr_login.bat 扫码登录
echo   2. 运行 start.bat 启动服务
echo   3. 访问 http://localhost:8000/docs
echo.
pause
