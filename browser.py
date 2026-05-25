"""
浏览器管理模块

负责：
1. 启动/关闭 Chromium 浏览器
2. 创建浏览器页面
3. 反自动化检测（伪装成真实用户）
4. 模拟人类行为（随机鼠标移动、滚动）

Playwright 是本爬虫的核心技术，它像一个"机器人手指"，
可以自动操控浏览器完成各种操作。
"""

import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from typing import Dict, List, Optional
from utils import random_delay, random_mouse_move, random_scroll


class BrowserManager:
    """浏览器管理器——管理 Playwright 浏览器的生命周期"""

    def __init__(self, config: Dict):
        """
        初始化浏览器管理器

        Args:
            config: 配置字典（来自 config.json）
        """
        self.config = config
        self.browser_config = config.get('browser', {})        # 浏览器配置
        self.anti_detection = config.get('anti_detection', {})  # 反检测配置
        self.playwright = None          # Playwright 控制器实例
        self.browser: Optional[Browser] = None          # 浏览器实例
        self.context: Optional[BrowserContext] = None    # 浏览器上下文（类似隐身窗口）

    async def start(self):
        """启动浏览器——打开一个 Chromium 窗口"""
        self.playwright = await async_playwright().start()

        # 浏览器启动参数
        launch_options = {
            'headless': self.browser_config.get('headless', False),  # True=无头模式（看不到窗口）
            'timeout': self.browser_config.get('timeout', 30000),
            'args': [
                '--disable-blink-features=AutomationControlled',  # 隐藏自动化标记
                '--disable-web-security',                          # 关闭网页安全限制
                '--disable-features=IsolateOrigins,site-per-process',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-infobars',                              # 隐藏"正受自动控制"提示
                '--window-size=1920,1080'                          # 设置窗口大小
            ]
        }

        # 启动 Chromium 浏览器
        self.browser = await self.playwright.chromium.launch(**launch_options)

        # 创建浏览器上下文（类似一个干净的浏览器会话）
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},          # 视口大小
            user_agent=self.browser_config.get('user_agent'),  # 浏览器标识
            locale='zh-CN',                                      # 语言：中文
            timezone_id='Asia/Shanghai'                          # 时区：中国
        )

        # 如果启用了隐身模式，注入反检测脚本
        if self.anti_detection.get('stealth_mode', True):
            await self._init_stealth_mode()

        print("浏览器启动成功")

    async def _init_stealth_mode(self):
        """
        初始化隐身模式——绕过网站的反爬虫检测

        启信宝会检测浏览器是不是被自动化工具控制的。
        这里通过 JavaScript 覆盖掉自动化特征标记，
        让网站以为我们是真实用户。
        """
        await self.context.add_init_script("""
            // 覆盖 navigator.webdriver 属性（最重要的检测点）
            // 正常浏览器这个值是 undefined，自动化工具会设为 true
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // 覆盖 chrome 对象（自动化工具没有这个）
            window.chrome = {
                runtime: {}
            };

            // 覆盖权限查询，避免被检测
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // 伪造插件列表（自动化工具通常没有插件）
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // 设置浏览器语言（启信宝会检测）
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en-US', 'en']
            });
        """)

    async def create_page(self, cookies: List[Dict] = None) -> Page:
        """
        创建新的浏览器标签页

        Args:
            cookies: 要注入的 Cookie 列表（登录信息）

        Returns:
            Playwright 页面对象
        """
        page = await self.context.new_page()

        # 设置默认超时时间
        page.set_default_timeout(self.browser_config.get('timeout', 30000))

        # 如果有 Cookie，注入到浏览器（实现 VIP 登录）
        if cookies:
            await self.context.add_cookies(cookies)

        return page

    async def close_page(self, page: Page):
        """关闭页面"""
        try:
            await page.close()
        except:
            pass

    async def human_like_actions(self, page):
        """
        执行类人操作——让爬虫行为更像真实用户

        包括随机移动鼠标和滚动页面，避免被网站识别为机器。
        """
        if self.anti_detection.get('random_mouse_move', True):
            await random_mouse_move(page)   # 随机移动鼠标

        if self.anti_detection.get('random_scroll', True):
            await random_scroll(page)       # 随机滚动页面

        await random_delay(0.5, 1.5)        # 随机等待

    async def get_cookies(self) -> List[Dict]:
        """
        从浏览器 context 导出当前有效的 cookies

        用于高级搜索 API 成功后热更新 cookie.txt，保持 cookie 始终新鲜。

        Returns:
            Playwright 格式的 cookie 字典列表 [{name, value, domain, path}, ...]
        """
        if self.context is None:
            return []
        try:
            return await self.context.cookies()
        except Exception:
            return []

    async def refresh_cookie_file(self, filepath: str = "cookie.txt"):
        """
        从浏览器 context 提取 cookies 并写入文件

        每次 API 查询成功后调用，确保 cookie.txt 始终是浏览器中最新的 cookie。
        写入格式兼容 cookie.txt 的 "key=value; key2=value2" 格式。
        """
        cookies = await self.get_cookies()
        if not cookies:
            return

        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(cookie_str)
            print(f"[Cookie] 已热更新 cookie.txt（{len(cookies)} 条）")
        except Exception as e:
            print(f"[Cookie] 热更新失败: {e}")

    async def stop(self):
        """停止浏览器——释放所有资源"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("浏览器已关闭")

    async def __aenter__(self):
        """异步上下文管理器入口——支持 async with 语法"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出——自动关闭浏览器"""
        await self.stop()
