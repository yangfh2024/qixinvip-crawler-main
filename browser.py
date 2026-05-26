"""
浏览器管理模块

负责：
1. 启动/关闭 Chromium 浏览器（persistent context 模式）
2. 创建浏览器页面
3. 反自动化检测（伪装成真实用户）
4. 模拟人类行为（随机鼠标移动、滚动）
5. 登录态持久化管理（自动维持 VIP 登录状态）

关键设计：
- 使用 launch_persistent_context 替代 new_context
- 浏览器数据持久化到本地目录，自动恢复登录态
- 禁止在请求后覆盖 cookie.txt（cookie 由浏览器自行管理）
"""

import asyncio
import os
from playwright.async_api import async_playwright, BrowserContext, Page
from typing import Dict, List, Optional


# 默认浏览器数据目录（相对项目根目录）
DEFAULT_USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "qixin_user_data")


class BrowserManager:
    """浏览器管理器——管理 Playwright 浏览器（persistent context）的生命周期"""

    def __init__(self, config: Dict, user_data_dir: str = DEFAULT_USER_DATA_DIR):
        """
        初始化浏览器管理器

        Args:
            config: 配置字典（来自 config.json）
            user_data_dir: 浏览器数据持久化目录（包含 cookie、localStorage 等）
        """
        self.config = config
        self.browser_config = config.get("browser", {})
        self.anti_detection = config.get("anti_detection", {})
        self.user_data_dir = user_data_dir
        self.playwright = None
        self.context: Optional[BrowserContext] = None

    async def start(self):
        """
        启动浏览器（persistent context 模式）

        首次启动（user_data_dir 不存在）：弹出有界面浏览器，等待人工扫码登录，
        登录后自动关闭，状态持久化到磁盘。

        后续启动：直接以 headless 模式运行，自动恢复已保存的登录态。
        """
        import os as _os

        # 判断是否为首次启动
        is_first_launch = not _os.path.exists(self.user_data_dir)

        if is_first_launch:
            await self._first_launch_login()
            return

        # 后续启动：以 headless 模式直接运行
        await self._launch_headless()

    async def _first_launch_login(self):
        """首次启动：弹出有界面浏览器供人工扫码登录"""
        print("[浏览器] 首次启动，正在打开登录窗口...")
        self.playwright = await async_playwright().start()

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-size=1920,1080",
        ]

        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=False,
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            args=launch_args,
        )

        # 打开启信宝登录页
        page = await self.context.new_page()
        await page.goto("https://www.qixin.com/login", timeout=15000)
        print("[浏览器] 请在打开的窗口中扫码登录（60秒超时）...")
        await page.wait_for_timeout(60000)

        # 直接认为登录成功（让用户自己确认是否完成）
        # 关闭 context 时 Playwright 会自动将 cookie/localStorage 持久化到 user_data_dir
        print("[浏览器] 窗口关闭，状态已持久化到磁盘。手动重启服务进行验证。")
        await self.stop()

    async def _launch_headless(self):
        """后续启动：以 headless 模式运行"""
        self.playwright = await async_playwright().start()

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-size=1920,1080",
            "--headless=new",
        ]

        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=True,
            viewport={"width": 1920, "height": 1080},
            user_agent=self.browser_config.get(
                "user_agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            args=launch_args,
        )

        if self.anti_detection.get("stealth_mode", True):
            await self._init_stealth_mode()

        print(f"[浏览器] 启动成功（数据目录: {self.user_data_dir}，headless=True）")

    async def _init_stealth_mode(self):
        """
        注入反检测 JavaScript，绕过网站自动化识别
        """
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en-US', 'en'] });
        """)

    async def create_page(self) -> Page:
        """
        创建新的浏览器标签页

        登录态由浏览器自动管理，不需要手动注入 cookie。

        Returns:
            Playwright 页面对象
        """
        page = await self.context.new_page()
        page.set_default_timeout(self.browser_config.get("timeout", 30000))
        return page

    async def close_page(self, page: Page):
        """关闭页面"""
        try:
            await page.close()
        except Exception:
            pass

    async def human_like_actions(self, page: Page):
        """
        执行类人操作——随机鼠标移动、滚动，模拟真实用户行为
        """
        from utils import random_delay, random_mouse_move, random_scroll

        if self.anti_detection.get("random_mouse_move", True):
            await random_mouse_move(page)
        if self.anti_detection.get("random_scroll", True):
            await random_scroll(page)
        await random_delay(0.5, 1.5)

    async def is_logged_in(self) -> bool:
        """
        检测当前 session 是否仍保持 VIP 登录态

        通过调用启信宝 VIP 配置接口判断，返回 True 表示登录有效。
        """
        if self.context is None:
            return False

        try:
            # 使用 context.request 走浏览器的 session，确保共享登录态
            from utils import compute_qixin_signature, qixin_json

            body = "{}"
            header_name, header_value = compute_qixin_signature(
                "/v4/internal/user/getEquityConfig", body, "/api-proxy/app"
            )

            resp = await self.context.request.post(
                "https://www.qixin.com/api-proxy/app/v4/internal/user/getEquityConfig",
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": "https://www.qixin.com",
                    "Referer": "https://www.qixin.com/",
                    header_name: header_value,
                },
                data=body,
                timeout=15000,
            )

            if resp.status == 200:
                data = await resp.json()
                return data.get("vipCount", 0) > 0
            return False
        except Exception as e:
            print(f"[登录检测] 失败: {e}")
            return False

    async def stop(self):
        """停止浏览器——完整释放资源"""
        if self.context:
            await self.context.close()
            self.context = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        print("[浏览器] 已关闭")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
