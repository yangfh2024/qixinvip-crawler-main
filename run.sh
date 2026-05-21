#!/bin/bash
# 启信宝数据爬虫 — Linux/Mac 启动入口
# 用法: bash run.sh [单公司名|batch|interactive|api|qr]
set -e

MODE="${1:-single}"

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
fi

case "$MODE" in
    api)
        python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
        ;;
    qr)
        python3 qr_login.py
        ;;
    single|batch|interactive)
        python3 main.py
        ;;
    *)
        echo "用法: bash run.sh [公司名|batch|interactive|api|qr]"
        echo "  公司名     — 直接爬取指定公司"
        echo "  batch      — 批量爬取模式"
        echo "  interactive — 交互式模式"
        echo "  api        — 启动 FastAPI 服务"
        echo "  qr         — 扫码登录"
        exit 1
        ;;
esac
