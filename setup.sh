#!/bin/bash
set -e

echo "============================================"
echo "   启信宝企业数据爬虫 — 一键部署"
echo "============================================"
echo ""

echo "[1/4] 检查 Python..."
if ! command -v python3 &> /dev/null; then
    echo "[失败] 未检测到 Python3，请先安装 Python 3.10+"
    exit 1
fi
echo "[OK] Python $(python3 --version)"

echo ""
echo "[2/4] 创建虚拟环境..."
if [ -d "venv" ]; then
    echo "[跳过] 虚拟环境已存在"
else
    python3 -m venv venv
    echo "[OK] 虚拟环境已创建"
fi

echo ""
echo "[3/4] 安装依赖..."
source venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
echo "[OK] 依赖安装完成"

echo ""
echo "[4/4] 下载 Playwright 浏览器..."
python3 -m playwright install chromium
echo "[OK] 浏览器下载完成"

echo ""
echo "============================================"
echo "    安装完成！"
echo "============================================"
echo ""
echo "下一步："
echo "  1. 运行 bash qr_login.sh 扫码登录"
echo "  2. 运行 bash start.sh 启动服务"
echo "  3. 访问 http://localhost:8000/docs"
echo ""
