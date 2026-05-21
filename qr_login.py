"""
启信宝扫码登录工具

这个脚本的作用：用浏览器打开启信宝，显示二维码，等你用手机扫码登录，
登录成功后自动把 Cookie 保存到 cookie.txt 文件。

为什么要用这个？
- 手动从浏览器复制 Cookie 很麻烦，而且容易漏掉关键字段
- 这个工具会自动获取所有 Cookie，还能验证 VIP 是否有效
- 自动保存到 cookie.txt，爬虫直接用

使用方法：python qr_login.py
"""

import asyncio, sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests
from playwright.async_api import async_playwright


def check_cookies_valid(cookie_str: str) -> bool:
    """
    调启信宝 API 验证 Cookie 是否真实有效

    具体做法：调 getEquityConfig 接口看返回的 vipCount 是否大于 0。
    如果 > 0 说明是 VIP 账号且登录有效。
    """
    try:
        from utils import compute_qixin_signature
        # 把 Cookie 字符串解析为字典
        cookies = {}
        for part in cookie_str.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                cookies[k.strip()] = v.strip()

        body = "{}"
        # 计算启信宝签名头（每次请求都必须带）
        header_name, header_value = compute_qixin_signature(
            "/v4/internal/user/getEquityConfig", body, "/api-proxy/app"
        )
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.qixin.com",
            "Referer": "https://www.qixin.com/",
            header_name: header_value,
        }
        # 发请求验证
        resp = requests.post(
            "https://www.qixin.com/api-proxy/app/v4/internal/user/getEquityConfig",
            headers=headers, cookies=cookies, data=body, timeout=10,
        )
        data = resp.json()
        vip = data.get("vipCount", 0)
        print(f"    API验证: vipCount={vip}", flush=True)
        return vip > 0
    except Exception as e:
        print(f"    API验证失败: {e}", flush=True)
        return False


async def save_cookies(context, label=""):
    """
    从浏览器上下文获取所有 Cookie，保存到文件

    会保存两份：
    1. cookie.txt — 纯文本格式，爬虫直接用
    2. storage_state.json — Playwright 格式，可用于恢复登录状态

    Args:
        context: Playwright 浏览器上下文
        label: 来源标签（哪个页面保存的）
    """
    cookies = await context.cookies()
    domains = set(c["domain"] for c in cookies)
    print(f"  [{label}] 共 {len(cookies)} 个Cookie, 域名: {domains}", flush=True)

    # 保存为 cookie.txt（纯文本格式）
    cookie_str = "; ".join(f'{c["name"]}={c["value"]}' for c in cookies)
    with open("cookie.txt", "w", encoding="utf-8") as f:
        f.write(cookie_str)

    # 同时保存 Playwright 的 storage_state（可用于恢复完整登录状态）
    with open("storage_state.json", "w", encoding="utf-8") as f:
        json.dump(await context.storage_state(), f, ensure_ascii=False)

    # 验证 Cookie 是否真的有效
    valid = check_cookies_valid(cookie_str)
    if valid:
        print(f"    ✅ Cookie有效！VIP登录正常", flush=True)
    else:
        print(f"    ❌ Cookie无效（或未登录VIP）", flush=True)
    return valid


async def main():
    """主流程：打开浏览器 → 显示二维码 → 等待扫码 → 保存 Cookie"""
    print("=" * 60)
    print("    Qixinbao QR Code Login")
    print("=" * 60)
    print()

    async with async_playwright() as p:
        print("[1/4] 正在打开浏览器...")

        # 优先使用用户自己安装的 Chrome（Cookie 更完整）
        chrome_paths = [
            "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
            os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe"),
        ]

        chrome_exe = None
        for path in chrome_paths:
            if os.path.exists(path):
                chrome_exe = path
                break

        if chrome_exe:
            print(f"  使用本机 Chrome: {chrome_exe}", flush=True)
            browser = await p.chromium.launch(
                executable_path=chrome_exe,
                headless=False,  # 非无头模式，用户能看到浏览器窗口
                args=["--disable-blink-features=AutomationControlled"],
            )
        else:
            print("  使用 Playwright 内置 Chromium", flush=True)
            browser = await p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )

        # 创建浏览器上下文（设置中文语言和时区）
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        page = await context.new_page()

        print("\n[2/4] 正在打开启信宝首页...", flush=True)
        await page.goto("https://www.qixin.com/", wait_until="domcontentloaded")
        await asyncio.sleep(3)

        print("\n[3/4] 等待扫码登录...（请用手机微信/启信宝扫码）", flush=True)
        print("    （如果没出现二维码，可能需要手动点击登录按钮）", flush=True)

        # 每2秒检查一次是否登录成功（最长等4分钟）
        logged_in = False
        for i in range(120):
            await asyncio.sleep(2)
            try:
                text = await page.evaluate("() => document.body.innerText")
                # 如果页面不再显示"登录"文字，说明登录成功了
                if "登录" not in text[:500]:
                    print(f"\n  检测到登录成功！({i*2}秒)", flush=True)
                    logged_in = True
                    break
            except:
                pass
            if i % 10 == 0:
                print(f"  等待中... ({i*2}秒)", flush=True)

        if not logged_in:
            print("\n  4分钟未检测到登录。", flush=True)
            print("  请重试，或手动从 Chrome 开发者工具中复制 Cookie。", flush=True)
        else:
            print(f"  当前 URL: {page.url}", flush=True)

        print("\n[4/4] 访问多个页面来捕获完整 Cookie...", flush=True)
        # 访问启信宝的不同页面，确保捕获所有域名的 Cookie
        urls = [
            ("UserCenter", "https://www.qixin.com/usercenter"),
            ("Member", "https://www.qixin.com/member"),
            ("Search", "https://www.qixin.com/search?key=%E8%85%BE%E8%AE%AF"),
            ("Settings", "https://www.qixin.com/setting"),
            ("Messages", "https://www.qixin.com/msg"),
        ]
        got_valid = False
        for name, url in urls:
            try:
                print(f"  正在访问 {name}...", flush=True)
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(2)
                got_valid = await save_cookies(context, name)
                if got_valid:
                    break  # 一旦验证有效，就不再继续了
            except Exception as e:
                print(f"  跳过 {name}: {str(e)[:50]}", flush=True)

        print(f"\n{'='*60}")
        if got_valid:
            print("  ✅ 登录成功！Cookie 已保存到 cookie.txt")
            print("  现在可以运行 start.bat 启动 API 服务器了。")
        else:
            print("  ❌ 登录后 Cookie 仍然无效。")
            print("  手动方法：Chrome → F12 → Network → 复制 Cookie → 粘贴到 cookie.txt")
        print(f"{'='*60}")

        await asyncio.sleep(3)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
