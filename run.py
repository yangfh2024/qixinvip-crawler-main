"""启动入口：先配好事件循环策略，再启动 uvicorn"""
import asyncio
import sys

if sys.platform == "win32":
    # 强制使用 ProactorEventLoop（uv 的 Python 在 uvicorn 下可能默认走 SelectorEventLoop）
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.set_event_loop(asyncio.ProactorEventLoop())

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8004, reload=False)
