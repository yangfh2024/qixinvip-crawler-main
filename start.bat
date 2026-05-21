@echo off
chcp 65001 > nul
title 启信宝爬虫 API 服务

echo ============================================
echo    启动启信宝爬虫 API 服务
echo ============================================
echo.

REM 检查配置文件
if not exist "config.json" (
    copy config.example.json config.json > nul
    echo [提示] 已创建 config.json，请检查配置
)

REM 检查 Cookie
if exist "cookie.txt" (
    echo [OK] 已找到 cookie.txt
) else (
    echo [警告] 未找到 cookie.txt，部分功能可能受限
    echo       请运行 qr_login.bat 扫码登录
)

REM 激活虚拟环境并启动
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo [提示] 未找到虚拟环境，使用系统 Python
)

echo 启动服务中...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

echo.
echo 访问 http://localhost:8000/docs 查看 API 文档
echo 详细 API 说明见 api_docs.md

pause
