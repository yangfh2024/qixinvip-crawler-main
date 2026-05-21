"""
启动入口——启动 FastAPI Web 服务

和 python app/main.py 的区别：
- python app/main.py 会启动带热重载的 dev 模式
- python run.py 用于生产环境，不带热重载

在 Windows 上需要先配置事件循环策略，
否则 Playwright 的异步操作会报错。
"""
import asyncio
import sys

if sys.platform == "win32":
    # Windows 必须用 ProactorEventLoop，
    # 否则 Playwright 的子进程管理会出问题
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.set_event_loop(asyncio.ProactorEventLoop())

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",     # FastAPI 应用实例的位置
        host="0.0.0.0",     # 监听所有网络接口（局域网也能访问）
        port=8004,          # 端口号
        reload=False,       # 生产环境不自动重启
    )
