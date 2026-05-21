#!/bin/bash

echo "============================================"
echo "   启动启信宝爬虫 API 服务"
echo "============================================"
echo ""

# Check config
if [ ! -f "config.json" ]; then
    cp config.example.json config.json
    echo "[提示] 已创建 config.json，请检查配置"
fi

# Check cookie
if [ -f "cookie.txt" ]; then
    echo "[OK] 已找到 cookie.txt"
else
    echo "[警告] 未找到 cookie.txt，部分功能可能受限"
    echo "       请运行 bash qr_login.sh 扫码登录"
fi

# Activate venv
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "[提示] 未找到虚拟环境，使用系统 Python"
fi

echo "启动服务中..."
echo "访问 http://localhost:8000/docs 查看 API 文档"
echo "按 Ctrl+C 停止服务"
echo ""

python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
